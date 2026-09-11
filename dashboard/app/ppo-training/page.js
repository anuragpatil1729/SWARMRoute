import Section from "../../components/Section";
import Stat from "../../components/Stat";
import EpisodeLineChart from "../../components/EpisodeLineChart";
import { getPpoTraining, getPpoAblation } from "../../lib/data";

export default function PpoTrainingPage() {
  const training = getPpoTraining();
  const ablation = getPpoAblation();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white mb-1">PPO training</h1>
      <p className="text-sm text-muted mb-8 max-w-2xl">
        Stable-Baselines3 PPO trained on the 25-dimensional Gymnasium
        environment. This is a {training.timesteps.toLocaleString()}-timestep
        smoke test (seed {training.seed}), not a converged production run —
        treat the curve as a sanity check, not a final result.
      </p>

      <Section>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          <Stat
            label="Timesteps"
            value={training.timesteps.toLocaleString()}
            tickColor="#818cf8"
            sub="baseline smoke test"
          />
          <Stat
            label="Mean eval reward"
            value={training.evalMetrics.mean_reward}
            tickColor="#4dd9c4"
            sub={`± ${training.evalMetrics.std_reward}`}
          />
          <Stat
            label="Mean deliveries / episode"
            value={training.evalMetrics.mean_deliveries}
            tickColor="#f5a623"
          />
        </div>
      </Section>

      <Section
        title="Reward per episode"
        description="Six short evaluation episodes from the checkpoint. Reward combines delivery success, on-time bonus, recovery bonus, and penalties for fuel/CO₂/failure — see reward.py for the full weighting."
      >
        <EpisodeLineChart
          data={training.episodes}
          lines={[{ dataKey: "reward", color: "#4dd9c4", name: "reward" }]}
        />
      </Section>

      <Section
        title="Success vs on-time rate"
        description="Delivery success stayed pinned at 100% across all eval episodes; on-time rate is the more sensitive signal at this training scale."
      >
        <EpisodeLineChart
          data={training.episodes}
          lines={[
            { dataKey: "successRate", color: "#4dd9c4", name: "success %" },
            { dataKey: "onTimeRate", color: "#f5a623", name: "on-time %" },
          ]}
        />
      </Section>

      <Section
        title="Predictor ablation (Configs A–E)"
        description="Progressively adding ML predictors (travel time, fuel, demand) to the PPO agent's inputs. At this smoke-test scale the configs are statistically indistinguishable — the predictors haven't yet moved the policy."
      >
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="text-left text-muted border-b border-border">
                <th className="font-normal px-4 py-3">Config</th>
                <th className="font-normal px-4 py-3">Success</th>
                <th className="font-normal px-4 py-3">On-time</th>
                <th className="font-normal px-4 py-3">Distance</th>
                <th className="font-normal px-4 py-3">Fuel</th>
                <th className="font-normal px-4 py-3">Failed</th>
              </tr>
            </thead>
            <tbody className="mono">
              {ablation.map((a) => (
                <tr key={a.config} className="border-b border-border last:border-0 align-top">
                  <td className="px-4 py-3 text-white">
                    {a.config}
                    <div className="text-[11px] text-muted mt-0.5 normal-case">
                      {a.description}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {a.success}% <span className="text-muted">± {a.successStd}</span>
                  </td>
                  <td className="px-4 py-3">{a.onTime}%</td>
                  <td className="px-4 py-3">{a.distance} km</td>
                  <td className="px-4 py-3">{a.fuel} L</td>
                  <td className="px-4 py-3">{a.failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
