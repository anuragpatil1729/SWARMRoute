import Section from "../../components/Section";
import Stat from "../../components/Stat";
import EpisodeLineChart from "../../components/EpisodeLineChart";
import { getPpoTraining, getPpoAblation } from "../../lib/data";

export default function PpoTrainingPage() {
  const training = getPpoTraining();
  const ablation = getPpoAblation();

  return (
    <div>
      <Section index="1" title="PPO training">
        <p className="text-sm text-muted max-w-2xl">
          Stable-Baselines3 PPO trained on the 25-dimensional Gymnasium
          environment. This is a {training.timesteps.toLocaleString()}
          -timestep smoke test (seed {training.seed}), not a converged
          production run — treat the curve as a sanity check, not a final
          result.
        </p>
      </Section>

      <Section index="2">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          <Stat label="timesteps" value={training.timesteps.toLocaleString()} sub="baseline smoke test" />
          <Stat label="mean eval reward" value={training.evalMetrics.mean_reward} sub={`± ${training.evalMetrics.std_reward}`} />
          <Stat label="mean deliveries / episode" value={training.evalMetrics.mean_deliveries} />
        </div>
      </Section>

      <Section
        index="3"
        title="Reward per episode"
        description="Six short evaluation episodes from the checkpoint. Reward combines delivery success, on-time bonus, recovery bonus, and penalties for fuel/CO₂/failure — see reward.py for the full weighting."
      >
        <EpisodeLineChart data={training.episodes} lines={[{ dataKey: "reward", color: "#181a16", name: "reward" }]} />
      </Section>

      <Section
        index="4"
        title="Success vs on-time rate"
        description="Delivery success stayed pinned at 100% across all eval episodes; on-time rate is the more sensitive signal at this training scale."
      >
        <EpisodeLineChart
          data={training.episodes}
          lines={[
            { dataKey: "successRate", color: "#2e6b34", name: "success %" },
            { dataKey: "onTimeRate", color: "#8a6d1f", name: "on-time %" },
          ]}
        />
      </Section>

      <Section
        index="5"
        title="Predictor ablation, configs A–E"
        description="Progressively adding ML predictors (travel time, fuel, demand) to the PPO agent's inputs. At this smoke-test scale the configs are statistically indistinguishable — the predictors haven't yet moved the policy."
      >
        <div className="overflow-x-auto border border-ink">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="text-left border-b border-ink">
                {["config", "success", "on-time", "distance", "fuel", "failed"].map((h) => (
                  <th key={h} className="font-normal px-4 py-2.5 mono text-xs text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="mono">
              {ablation.map((a, i) => (
                <tr key={a.config} className={`align-top ${i % 2 ? "bg-panel2" : ""}`}>
                  <td className="px-4 py-2.5 text-ink">
                    {a.config}
                    <div className="text-[11px] text-muted mt-0.5 normal-case serif">{a.description}</div>
                  </td>
                  <td className="px-4 py-2.5">{a.success}% <span className="text-muted">± {a.successStd}</span></td>
                  <td className="px-4 py-2.5">{a.onTime}%</td>
                  <td className="px-4 py-2.5">{a.distance} km</td>
                  <td className="px-4 py-2.5">{a.fuel} L</td>
                  <td className="px-4 py-2.5">{a.failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
