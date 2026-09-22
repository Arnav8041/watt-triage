import type { Reading } from "@/lib/types";

export function Sparkline({ readings, color }: { readings: Reading[]; color: string }) {
  if (readings.length < 2) {
    return <div className="h-8 w-full" aria-hidden />;
  }
  const watts = readings.map((r) => r.watts);
  const min = Math.min(...watts);
  const max = Math.max(...watts);
  const span = max - min || 1;
  const points = watts
    .map((w, i) => {
      const x = (i / (watts.length - 1)) * 100;
      const y = 28 - ((w - min) / span) * 26;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="h-8 w-full" aria-hidden>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
