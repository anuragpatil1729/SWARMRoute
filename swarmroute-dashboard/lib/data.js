import finalComparisonRaw from "./data/finalComparison.json";
import disruptionScenariosRaw from "./data/disruptionScenarios.json";
import ppoAblationRaw from "./data/ppoAblation.json";
import ppoTrainingRaw from "./data/ppoTraining.json";
import routesC101Raw from "./data/routesC101.json";
import solomonC101Raw from "./data/solomonC101.json";

// ---- Method comparison (final_comparison.json) ----
export const methodOrder = [
  "Nearest Neighbor",
  "OR-Tools (Static)",
  "OR-Tools + Prediction",
  "Rule-Based Decentralized",
  "PPO Adaptive Agent",
  "Random Policy",
];

export function getMethodComparison() {
  return methodOrder
    .filter((name) => finalComparisonRaw[name])
    .map((name) => {
      const m = finalComparisonRaw[name];
      return {
        method: name,
        success: m.success_pct_mean,
        onTime: m.on_time_pct_mean,
        distance: m.distance_km_mean,
        fuel: m.fuel_liters_mean,
        co2: m.co2_kg_mean,
        emptyKm: m.empty_km_mean,
        utilization: m.utilization_pct_mean,
        failed: m.failed_mean,
        delay: m.delay_mins_mean,
        runtime: m.runtime_sec_mean,
      };
    });
}

// ---- Disruption scenarios (A-H) ----
const scenarioDescriptions = {
  A: "Single truck breakdown",
  B: "Two truck breakdowns",
  C: "Traffic congestion spikes",
  D: "Cloud outage (mesh mode)",
  E: "Cloud outage + breakdown",
  F: "Cloud outage + breakdown + traffic",
  G: "Sudden demand burst",
  H: "Compound cascading failure",
};

export function getDisruptionScenarios() {
  return Object.entries(disruptionScenariosRaw).map(([key, val]) => {
    const methods = val.methods || {};
    return {
      key,
      name: scenarioDescriptions[key] || val.scenario_name,
      disruptions: val.disruptions_count,
      urgentOrders: val.urgent_orders_count,
      methods: Object.entries(methods).map(([mName, m]) => ({
        method: mName,
        success: m.delivery_success_pct,
        onTime: m.on_time_delivery_pct,
        distance: m.total_distance_km,
        fuel: m.total_fuel_liters,
        recovery: m.recovery_time_sec,
        failed: m.failed_deliveries,
        delay: m.average_delay_mins,
        commOverhead: m.communication_overhead,
        cloudDependency: m.cloud_dependency,
      })),
    };
  });
}

// ---- PPO ablation ----
export function getPpoAblation() {
  return Object.entries(ppoAblationRaw).map(([name, val]) => ({
    config: name,
    description: val.description,
    success: val.metrics.delivery_success_pct.mean,
    successStd: val.metrics.delivery_success_pct.std,
    onTime: val.metrics.on_time_delivery_pct.mean,
    distance: val.metrics.total_distance_km.mean,
    fuel: val.metrics.total_fuel_liters.mean,
    failed: val.metrics.failed_deliveries.mean,
    delay: val.metrics.average_delay_mins.mean,
  }));
}

// ---- PPO training curve ----
export function getPpoTraining() {
  const d = ppoTrainingRaw;
  const episodes = d.episode_rewards.map((reward, i) => ({
    episode: i + 1,
    reward,
    successRate: d.delivery_success_rates[i],
    onTimeRate: d.on_time_rates[i],
    fuel: d.fuel_consumed ? d.fuel_consumed[i] : undefined,
    co2: d.co2_emissions ? d.co2_emissions[i] : undefined,
  }));
  return {
    seed: d.seed,
    timesteps: d.timesteps,
    evalMetrics: d.eval_metrics,
    episodes,
  };
}

// ---- Routes + coordinates (C101 baseline) ----
export function getRouteMap() {
  const coordsById = {};
  solomonC101Raw.forEach((c) => {
    coordsById[c.id] = c;
  });

  const routes = Object.entries(routesC101Raw.routes || {})
    .map(([truck, stops]) => {
      const path = stops
        .map((id) => coordsById[id])
        .filter(Boolean);
      return { truck, stops, path };
    })
    .filter((r) => r.stops.length > 2); // drop unused trucks (just depot-depot)

  return {
    dataset: routesC101Raw.dataset,
    status: routesC101Raw.status,
    totalDistance: routesC101Raw.total_distance,
    depot: coordsById[0],
    customers: solomonC101Raw,
    routes,
  };
}
