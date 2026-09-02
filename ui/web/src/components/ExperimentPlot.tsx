import { EstimatedState } from "../types/state";

type Props = {
  trajectory: EstimatedState[];
};

export function ExperimentPlot({ trajectory }: Props) {
  const latest = trajectory.at(-1);
  return (
    <section className="side-panel">
      <h2>Plot</h2>
      <div className="plot-placeholder">
        <span>position uncertainty</span>
        <strong>{latest ? latest.uncertainty.sigma_x_m.toFixed(2) : "--"} m</strong>
      </div>
    </section>
  );
}

