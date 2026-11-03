import { HeartRatePoint } from "../api/heartRate";

// A missing period must never look like a continuous measured trace.
export function graphSegments(points: HeartRatePoint[]): HeartRatePoint[][] {
  const segments: HeartRatePoint[][] = [];
  for (const point of points) {
    const previous = segments.at(-1)?.at(-1);
    if (!previous || point.timestamp_us <= previous.timestamp_us ||
        point.timestamp_us - previous.timestamp_us > 5_000_000) segments.push([]);
    segments.at(-1)!.push(point);
  }
  return segments;
}

export function HeartRateGraph({ points, nowUs }: { points: HeartRatePoint[]; nowUs: number }) {
  const recent = points.filter(p => p.timestamp_us >= nowUs - 300_000_000 && p.timestamp_us <= nowUs);
  const values = recent.map(p => p.bpm);
  const minimum = Math.max(0, Math.floor((Math.min(50, ...values) - 10) / 10) * 10);
  const maximum = Math.ceil((Math.max(160, ...values) + 10) / 10) * 10;
  const x = (t: number) => 34 + (t - (nowUs - 300_000_000)) / 300_000_000 * 220;
  const y = (bpm: number) => 116 - (bpm - minimum) / (maximum - minimum) * 100;
  return <div className="hr-graph">
    <svg viewBox="0 0 270 145" role="img" aria-label="Real heart rate over the last five minutes; gaps indicate missing data">
      {[minimum, Math.round((minimum + maximum) / 2), maximum].map(value => <g key={value}>
        <line x1="34" x2="254" y1={y(value)} y2={y(value)} stroke="#dfe5ec" />
        <text x="29" y={y(value) + 4} textAnchor="end">{value}</text>
      </g>)}
      {graphSegments(recent).map((segment, i) => segment.length === 1 ?
        <circle key={i} cx={x(segment[0].timestamp_us)} cy={y(segment[0].bpm)} r="2" fill="#b82c39" /> :
        <polyline key={i} points={segment.map(p => `${x(p.timestamp_us)},${y(p.bpm)}`).join(" ")}
          fill="none" stroke="#b82c39" strokeWidth="2" />)}
      <text x="34" y="136">−5 min</text><text x="254" y="136" textAnchor="end">Now</text>
      {!recent.length ? <text x="144" y="65" textAnchor="middle">Waiting for valid readings</text> : null}
    </svg>
  </div>;
}
