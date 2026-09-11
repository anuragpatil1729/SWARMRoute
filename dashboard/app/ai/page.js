"use client";

import { useState } from "react";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import { useDashboardState } from "../../lib/useDashboardState";

export default function AIDecisionsPage() {
  const { state, connectionStatus } = useDashboardState();
  const [selectedObsFeature, setSelectedObsFeature] = useState(null);

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">AI ENGINE OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            Please make sure the SWARMRoute backend is running at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8 max-w-md mx-auto">
          <div className="font-mono text-xs text-slate-400">Loading AI Telemetry</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO PPO POLICY</h2>
          <p className="text-xs text-slate-500 mt-2">Streaming neural network policy telemetry & spatial forecasts...</p>
        </div>
      </div>
    );
  }

  const { ppo = {}, predictions = {}, positioning = [], vehicles = [] } = state;
  const zones = predictions.zones || [];

  return (
    <div className="space-y-6 w-full">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">
                AI Decisions, PPO Policy & Spatial Predictions
              </h2>
              <span className="text-[11px] font-mono px-2.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 font-semibold">
                {ppo.policy_status || "OPERATIONAL (MlpPolicy)"}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Reinforcement Learning decision trajectory, multi-objective reward decomposition, observation vector diagnostics, and predictive spatial demand forecasting.
            </p>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 font-semibold">
              Steps: {ppo.step_count || 0}
            </span>
            <span className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-semibold">
              Reward: {ppo.current_reward || 0.0}
            </span>
          </div>
        </div>
      </div>

      {/* AI KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <Stat
          label="Active PPO Action"
          value={ppo.current_action || "HOLD"}
          help="Autonomous fleet decision"
        />
        <Stat
          label="Step Reward"
          value={ppo.current_reward !== undefined ? `${ppo.current_reward > 0 ? "+" : ""}${ppo.current_reward}` : "0.0"}
          help="Multi-objective delta"
        />
        <Stat
          label="Episode Cumulative"
          value={ppo.episode_reward !== undefined ? Math.round(ppo.episode_reward) : "0"}
          help="Discounted return"
        />
        <Stat
          label="Policy Algorithm"
          value="PPO (Clip 0.2)"
          help="Stable-Baselines3 PyTorch"
        />
        <Stat
          label="Observation Space"
          value="25-dim State"
          help="Normalized local perception"
        />
        <Stat
          label="Action Space"
          value="5 Discrete Actions"
          help="Assign, Reassign, Reroute, Repos, Hold"
        />
      </div>

      {/* 2-Column: Decision History & Spatial Demand Forecasting */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decision History Feed */}
        <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="border-b border-slate-100 pb-3 mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                Recent PPO Policy Actions
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Sequential autonomous discrete actions selected by agent
              </p>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Last 10 Decisions</span>
          </div>

          <div className="space-y-2.5 max-h-80 overflow-y-auto font-mono text-xs">
            {ppo.history && ppo.history.length > 0 ? (
              ppo.history.map((h, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{h.action}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 font-semibold">
                        Step {h.step}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1">
                      Time: {h.time_str || `${h.time}m`} · Vehicle Target: {h.target || "Fleet"}
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-xs font-bold ${
                        (h.reward || 0) >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}
                    >
                      {(h.reward || 0) > 0 ? "+" : ""}{h.reward || 0.0}
                    </span>
                    <div className="text-[10px] text-slate-400">Reward</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-10 text-xs text-slate-400 font-mono">
                Running initial policy evaluations. Decisions will stream here automatically.
              </div>
            )}
          </div>
        </div>

        {/* Spatial Demand Predictions per Quadrant */}
        <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="border-b border-slate-100 pb-3 mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                Predictive Spatial Demand (Layer A)
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Proactive order arrival rate forecasting by geographic quadrant
              </p>
            </div>
            <span className="text-[11px] font-mono text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
              DemandPredictor ML
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {zones.map((z, idx) => (
              <div key={idx} className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 font-mono">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1">
                  <span>{z.zone}</span>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                      z.trend === "UP"
                        ? "bg-red-100 text-red-700"
                        : z.trend === "DOWN"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {z.trend}
                  </span>
                </div>
                <div className="text-lg font-bold text-slate-900">
                  {z.predicted_demand} <span className="text-xs font-normal text-slate-400">orders/h</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-1 flex justify-between">
                  <span>Actual: {z.actual_demand}</span>
                  <span className={z.diff?.startsWith("+") ? "text-red-600" : "text-emerald-600"}>
                    {z.diff}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Predictive Fleet Positioning Status */}
          <div className="mt-4 pt-4 border-t border-slate-100">
            <h4 className="text-xs font-bold text-slate-800 uppercase font-mono mb-2">
              Proactive Vehicle Repositioning
            </h4>
            {positioning && positioning.length > 0 ? (
              <div className="space-y-1.5 text-xs font-mono">
                {positioning.map((p, i) => (
                  <div key={i} className="p-2 rounded bg-blue-50 border border-blue-200 text-blue-900 flex justify-between">
                    <span>{p.vehicle_id} repositioning to {p.target_zone}</span>
                    <span className="font-semibold">Demand surge +{p.expected_demand}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 font-mono">
                Fleet balanced across current customer demand zones. No repositioning required.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Observation Space Diagnostic Matrix */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="border-b border-slate-100 pb-3 mb-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
            Gymnasium Observation Space Architecture (25 Dimensions)
          </h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Decentralized local state vector fed to policy network at every decision step with zero unrevealed future disruption leakage
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 font-mono text-[11px]">
          {[
            { idx: 0, name: "t_norm", desc: "Normalized simulation time [0, 2]" },
            { idx: 1, name: "x_norm", desc: "Normalized X coordinate [0, 1]" },
            { idx: 2, name: "y_norm", desc: "Normalized Y coordinate [0, 1]" },
            { idx: 3, name: "cap_rem_norm", desc: "Remaining payload fraction [0, 1]" },
            { idx: 4, name: "load_norm", desc: "Current cargo load fraction [0, 1]" },
            { idx: 5, name: "fuel_norm", desc: "Current battery / fuel level [0, 1]" },
            { idx: 6, name: "traffic_norm", desc: "Next road edge traffic index [0.2, 1.0]" },
            { idx: 7, name: "stranded_norm", desc: "Stranded order ratio across fleet" },
            { idx: 8, name: "avail_norm", desc: "Operational vehicle ratio" },
            { idx: 9, name: "broken_norm", desc: "Broken down vehicle ratio" },
            { idx: 10, name: "mesh_neighbors", desc: "Connected RF peer ratio [0, 1]" },
            { idx: 11, name: "conn_code", desc: "1.0=Cloud, 0.5=Mesh, 0.0=Isolated" },
            { idx: 12, name: "pred_demand", desc: "Quadrant forecasted demand [0, 1]" },
            { idx: 13, name: "route_prog", desc: "Stops completed fraction [0, 1]" },
            { idx: 14, name: "rem_stops", desc: "Normalized remaining stop count" },
            { idx: 15, name: "urgency_norm", desc: "Earliest deadline urgency delta" },
            { idx: "16-18", name: "cand1_features", desc: "Distance, Demand, Urgency for Candidate 1" },
            { idx: "19-21", name: "cand2_features", desc: "Distance, Demand, Urgency for Candidate 2" },
            { idx: "22-24", name: "cand3_features", desc: "Distance, Demand, Urgency for Candidate 3" },
          ].map((item, i) => (
            <div
              key={i}
              className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 transition cursor-pointer"
            >
              <div className="flex items-center justify-between text-slate-800 font-bold">
                <span>[{item.idx}]</span>
                <span className="text-blue-600">{item.name}</span>
              </div>
              <p className="text-[10px] text-slate-500 mt-1 leading-tight">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
