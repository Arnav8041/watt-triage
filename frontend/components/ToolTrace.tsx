"use client";

import { useEffect, useRef, type RefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { EXPAND_TRANSITION_SECONDS } from "@/lib/motion-constants";
import type { ToolCall } from "@/lib/types";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

/**
 * The trace is the hero element (see the ticket): the ordered record of what the agent
 * actually checked. It reveals step by step as it scrolls into view within the decision
 * feed panel — scroll-driven, not a page-load flourish, and it plays once per expansion.
 */
export function ToolTrace({ trace, scrollerRef }: { trace: ToolCall[]; scrollerRef: RefObject<HTMLDivElement | null> }) {
  const containerRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const steps = container.querySelectorAll<HTMLElement>("[data-trace-step]");
    let ctx: gsap.Context | undefined;
    // The parent row's expand animation (DecisionRow, 250ms) is still resizing this
    // container's ancestor when this effect runs, so ScrollTrigger would measure the
    // wrong position if created immediately. Wait for that transition to settle first.
    const timer = setTimeout(() => {
      ctx = gsap.context(() => {
        gsap.set(steps, { opacity: 0, y: 8 });
        ScrollTrigger.create({
          trigger: container,
          scroller: scrollerRef.current ?? window,
          start: "top 95%",
          once: true,
          onEnter: () => gsap.to(steps, { opacity: 1, y: 0, duration: 0.4, stagger: 0.08, ease: "power2.out" }),
        });
        ScrollTrigger.refresh();
      }, container);
    }, EXPAND_TRANSITION_SECONDS * 1000 + 100); // + margin past the parent's own transition
    return () => {
      clearTimeout(timer);
      ctx?.revert();
    };
  }, [scrollerRef]);

  return (
    <ol ref={containerRef} className="flex flex-col gap-2">
      {trace.map((step, i) => (
        <li key={i} data-trace-step className="rounded border border-line bg-surface-raised px-3 py-2">
          <div className="tnum text-sm text-ink">
            {i + 1}. {step.tool}
          </div>
          {step.input != null && (
            <pre className="mt-1 overflow-x-auto text-xs text-ink-dim">{JSON.stringify(step.input)}</pre>
          )}
        </li>
      ))}
    </ol>
  );
}
