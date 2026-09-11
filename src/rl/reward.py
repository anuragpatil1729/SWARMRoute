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

    def calculate_step_reward_decomposed(
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
    ) -> Tuple[float, Dict[str, float]]:
        cfg = self.config

        delivery_reward = cfg.delivery_reward * max(0, new_deliveries)
        ontime_reward = cfg.on_time_bonus * max(0, new_on_time)
        recovery_reward = cfg.recovery_bonus * max(0, new_recoveries)
        utilization_reward = cfg.load_utilization_weight * min(1.0, max(0.0, fleet_utilization_ratio))
        repositioning_reward = cfg.useful_repositioning_bonus if useful_repositioning else 0.0

        failure_penalty = cfg.failure_penalty * max(0, new_failed)
        late_penalty = cfg.late_delivery_penalty * max(0, new_late)
        delay_penalty = cfg.delay_penalty_weight * max(0.0, delay_minutes)
        distance_penalty = cfg.distance_penalty_weight * max(0.0, incremental_distance_km)
        fuel_penalty = cfg.fuel_penalty_weight * max(0.0, incremental_fuel_liters)
        co2_penalty = cfg.co2_penalty_weight * max(0.0, incremental_co2_kg)
        empty_km_penalty = cfg.empty_km_penalty_weight * max(0.0, incremental_empty_km)
        infeasible_penalty = cfg.infeasible_action_penalty if infeasible_action else 0.0
        reassignment_penalty = cfg.excessive_reassignment_penalty if excessive_reassignment else 0.0

        total_positive = delivery_reward + ontime_reward + recovery_reward + utilization_reward + repositioning_reward
        total_negative = (
            failure_penalty + late_penalty + delay_penalty + distance_penalty
            + fuel_penalty + co2_penalty + empty_km_penalty + infeasible_penalty + reassignment_penalty
        )
        total_reward = float(round(total_positive - total_negative, 3))

        decomp = {
            "delivery_reward": round(delivery_reward, 3),
            "ontime_reward": round(ontime_reward, 3),
            "recovery_reward": round(recovery_reward, 3),
            "fuel_penalty": round(fuel_penalty, 3),
            "distance_penalty": round(distance_penalty, 3),
            "delay_penalty": round(delay_penalty, 3),
            "failure_penalty": round(failure_penalty, 3),
            "total_reward": total_reward,
        }

        return total_reward, decomp


def calculate_step_reward_decomposed(
    new_deliveries: int = 0,
    new_on_time: int = 0,
    new_recoveries: int = 0,
    new_failed: int = 0,
    new_late: int = 0,
    delay_minutes: float = 0.0,
    incremental_distance_km: float = 0.0,
    incremental_fuel_liters: float = 0.0,
    incremental_co2_kg: float = 0.0,
    incremental_empty_km: float = 0.0,
    fleet_utilization_ratio: float = 0.0,
    useful_repositioning: bool = False,
    infeasible_action: bool = False,
    excessive_reassignment: bool = False,
    config: Optional[MultiObjectiveRewardConfig] = None,
) -> Tuple[float, Dict[str, float]]:
    """Module-level convenience wrapper for decomposed reward calculation."""
    calc = FleetRewardCalculator(config)
    return calc.calculate_step_reward_decomposed(
        new_deliveries=new_deliveries,
        new_on_time=new_on_time,
        new_recoveries=new_recoveries,
        new_failed=new_failed,
        new_late=new_late,
        delay_minutes=delay_minutes,
        incremental_distance_km=incremental_distance_km,
        incremental_fuel_liters=incremental_fuel_liters,
        incremental_co2_kg=incremental_co2_kg,
        incremental_empty_km=incremental_empty_km,
        fleet_utilization_ratio=fleet_utilization_ratio,
        useful_repositioning=useful_repositioning,
        infeasible_action=infeasible_action,
        excessive_reassignment=excessive_reassignment,
    )

