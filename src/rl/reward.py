from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MultiObjectiveRewardConfig(BaseModel):
    """
    Transparent, configurable weights for the multi-objective fleet reward function.
    Encourages delivery fulfillment, on-time arrivals, and resilient stranded recovery.
    Penalizes failed orders, lateness, excessive fuel/CO2, empty miles, and infeasible decisions.
    """
    # Positive incentives
    delivery_reward: float = Field(default=25.0, description="Reward per completed order")
    on_time_bonus: float = Field(default=10.0, description="Bonus for delivery within time window")
    recovery_bonus: float = Field(default=20.0, description="Bonus per recovered stranded breakdown order")
    load_utilization_weight: float = Field(default=5.0, description="Incentive for efficient payload capacity usage")
    useful_repositioning_bonus: float = Field(default=8.0, description="Bonus for moving idle vehicle to high-demand zone")

    # Penalties
    failure_penalty: float = Field(default=40.0, description="Penalty per failed or abandoned order")
    delay_penalty_weight: float = Field(default=2.5, description="Penalty per minute of delivery delay past deadline")
    late_delivery_penalty: float = Field(default=15.0, description="Fixed penalty per late delivery")
    distance_penalty_weight: float = Field(default=0.2, description="Penalty per km traveled")
    fuel_penalty_weight: float = Field(default=1.0, description="Penalty per Liter of diesel consumed")
    co2_penalty_weight: float = Field(default=0.5, description="Penalty per kg of CO2 emitted")
    empty_km_penalty_weight: float = Field(default=0.8, description="Penalty per empty (deadhead) km")
    infeasible_action_penalty: float = Field(default=5.0, description="Penalty for choosing an infeasible action")
    unnecessary_reposition_penalty: float = Field(default=4.0, description="Penalty for repositioning an active vehicle")
    excessive_reassignment_penalty: float = Field(default=3.0, description="Penalty for unnecessary repeated order transfers")


RewardConfig = MultiObjectiveRewardConfig


class FleetRewardCalculator:
    """
    Computes mathematically rigorous, un-fabricated multi-objective rewards
    directly from empirical discrete physical simulation deltas.
    
    Reward Equation:
    R = w_deliv * ΔDelivered
      + w_ontime * ΔOnTime
      + w_rec * ΔRecovered
      + w_util * FleetUtilization
      + w_repos * UsefulRepos
      - w_fail * ΔFailed
      - w_late * ΔLate
      - w_delay * TotalDelayMins
      - w_dist * ΔDistance
      - w_fuel * ΔFuel
      - w_co2 * ΔCO2
      - w_empty * ΔEmptyKm
      - P_infeasible
      - P_excessive_reassign
    """

    def __init__(self, config: Optional[MultiObjectiveRewardConfig] = None) -> None:
        self.config = config or MultiObjectiveRewardConfig()

    def calculate_step_reward(
        self,
        new_deliveries: int,
        new_on_time: int,
        new_recoveries: int,
        new_failed: int,
        new_late: int,
        delay_minutes: float,
        incremental_distance_km: float,
        incremental_fuel_liters: float,
        incremental_co2_kg: float,
        incremental_empty_km: float,
        fleet_utilization_ratio: float = 0.0,
        useful_repositioning: bool = False,
        infeasible_action: bool = False,
        excessive_reassignment: bool = False,
    ) -> float:
        cfg = self.config
        reward = 0.0

        # Positive incentives
        reward += cfg.delivery_reward * max(0, new_deliveries)
        reward += cfg.on_time_bonus * max(0, new_on_time)
        reward += cfg.recovery_bonus * max(0, new_recoveries)
        reward += cfg.load_utilization_weight * min(1.0, max(0.0, fleet_utilization_ratio))
        if useful_repositioning:
            reward += cfg.useful_repositioning_bonus

        # Penalties
        reward -= cfg.failure_penalty * max(0, new_failed)
        reward -= cfg.late_delivery_penalty * max(0, new_late)
        reward -= cfg.delay_penalty_weight * max(0.0, delay_minutes)
        reward -= cfg.distance_penalty_weight * max(0.0, incremental_distance_km)
        reward -= cfg.fuel_penalty_weight * max(0.0, incremental_fuel_liters)
        reward -= cfg.co2_penalty_weight * max(0.0, incremental_co2_kg)
        reward -= cfg.empty_km_penalty_weight * max(0.0, incremental_empty_km)

        if infeasible_action:
            reward -= cfg.infeasible_action_penalty
        if excessive_reassignment:
            reward -= cfg.excessive_reassignment_penalty

        return float(round(reward, 3))
