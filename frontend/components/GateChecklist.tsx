import { GATE_RULES } from "@/lib/gate-rules";
import type { Decision } from "@/lib/types";

export function GateChecklist({ decision }: { decision: Decision }) {
  return (
    <ol className="flex flex-col gap-1">
      {GATE_RULES.map((rule, i) => {
        const active = rule.matches(decision);
        return (
          <li
            key={rule.label}
            className="flex gap-2 rounded px-2 py-1 text-xs"
            style={{
              background: active ? "color-mix(in srgb, var(--pending) 16%, transparent)" : "transparent",
              color: active ? "var(--pending)" : "var(--ink-dim)",
            }}
          >
            <span className="tnum shrink-0">{i + 1}</span>
            <span>{rule.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
