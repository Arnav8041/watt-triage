"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// a real escalation from this build's own history — not invented copy, the same
// reading, reasoning, and gate rule a visitor can find again on the live dashboard
const EXAMPLE = {
  watts: 3180,
  rated: 1500,
  appliance: "Space heater",
  location: "Bedroom",
  reasoning:
    "The space heater in the bedroom is drawing 3,180 watts, exceeding its 1,500-watt rated capacity by more than 112%. This is a critical rated breach indicating either a serious equipment malfunction or internal fault. The doubling of rated power draws poses a significant fire and electrical hazard. This reading demands immediate escalation to the homeowner with a recommendation to unplug the device and cease use until it can be professionally inspected or replaced.",
  gateRule: "Reading is above the appliance's rated wattage (Rated Breach)",
};

function CtaButton({ children }: { children: React.ReactNode }) {
  return (
    <motion.span
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className="inline-block cursor-pointer rounded-md px-5 py-3 text-sm font-medium text-bg"
      style={{ background: "var(--safe)" }}
    >
      {children}
    </motion.span>
  );
}

export default function LandingPage() {
  const storyRef = useRef<HTMLDivElement>(null);
  const fillRef = useRef<HTMLDivElement>(null);
  // MotionConfig's reducedMotion="user" only neutralizes transform/layout animations —
  // a flicker built from opacity/textShadow keyframes plays at full length regardless,
  // so this one needs its own explicit check to actually honor the OS setting
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const story = storyRef.current;
    const fill = fillRef.current;
    if (!story || !fill) return;

    const ctx = gsap.context(() => {
      // the spine fills exactly as far as the reader has scrolled through the three
      // stages — the one scrubbed moment; each stage's own reveal below is a discrete cut
      gsap.to(fill, {
        scaleY: 1,
        ease: "none",
        scrollTrigger: { trigger: story, start: "top center", end: "bottom center", scrub: 0.3 },
      });

      gsap.utils.toArray<HTMLElement>("[data-stage]").forEach((stage) => {
        gsap.from(stage, {
          opacity: 0,
          y: 24,
          duration: 0.5,
          ease: "power2.out",
          scrollTrigger: { trigger: stage, start: "top 75%", once: true },
        });
      });
    }, story);

    return () => ctx.revert();
  }, []);

  return (
    <main className="bg-bg text-ink">
      <section className="flex min-h-dvh flex-col justify-center gap-8 px-4">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={{
            hidden: {},
            visible: { transition: { delayChildren: reduceMotion ? 0 : 1.05, staggerChildren: reduceMotion ? 0 : 0.12 } },
          }}
          className="mx-auto flex w-full max-w-3xl flex-col gap-6"
        >
          <div>
            {/* the one signature moment: the name flickers to life once, like a sign
                switching on, before anything else on the page moves */}
            <motion.h1
              className="text-6xl font-bold leading-none tracking-tight sm:text-8xl"
              initial={{ opacity: 0, textShadow: "0 0 0px transparent" }}
              animate={
                reduceMotion
                  ? { opacity: 1, textShadow: "0 0 0px transparent" }
                  : {
                      opacity: [0, 1, 0.15, 1, 0.25, 1, 0.6, 1],
                      textShadow: [
                        "0 0 0px transparent",
                        "0 0 40px var(--safe-glow)",
                        "0 0 0px transparent",
                        "0 0 30px var(--safe-glow)",
                        "0 0 0px transparent",
                        "0 0 16px var(--safe-glow)",
                        "0 0 0px transparent",
                        "0 0 0px transparent",
                      ],
                    }
              }
              transition={
                reduceMotion
                  ? { duration: 0.3 }
                  : { duration: 1, times: [0, 0.08, 0.15, 0.22, 0.3, 0.42, 0.6, 1], ease: "easeInOut" }
              }
            >
              WattTriage
            </motion.h1>
            <span className="mt-3 flex items-center gap-1.5 text-xs text-ink-dim">
              <motion.span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: "var(--safe)" }}
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: reduceMotion ? 0 : 1.05 }}
              />
              live — five real appliances, reporting right now
            </span>
          </div>
          <motion.p
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }}
            className="text-2xl leading-snug tracking-tight text-ink-dim sm:text-3xl"
          >
            Five appliances. One agent deciding what&apos;s actually wrong.
          </motion.p>
          <motion.p
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }}
            className="max-w-xl text-lg text-ink-dim"
          >
            WattTriage watches real power draw from a small home fleet. When a reading looks off, an AI agent
            investigates it — then a fixed set of rules, not the model&apos;s opinion, decides whether a person
            needs to know.
          </motion.p>
          <motion.div
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }}
            className="flex flex-wrap gap-3 pt-2"
          >
            <Link href="/dashboard">
              <CtaButton>Open the live dashboard</CtaButton>
            </Link>
          </motion.div>
        </motion.div>
      </section>

      <section className="mx-auto max-w-2xl px-4 py-20 text-center">
        <p className="text-xl leading-relaxed text-ink sm:text-2xl">
          Imagine a space heater quietly overheating in an empty bedroom at 2am. Most &ldquo;smart home&rdquo;
          gadgets either miss it, or text you every time the AC kicks on. WattTriage tells the two apart — and only
          interrupts a person when something is actually wrong.
        </p>
      </section>

      <section ref={storyRef} className="mx-auto max-w-3xl px-4 py-32">
        <div className="relative flex flex-col gap-28 pl-8">
          <div className="absolute inset-y-0 left-0 w-px bg-line" aria-hidden />
          <div
            ref={fillRef}
            className="absolute left-0 top-0 w-px origin-top bg-safe"
            style={{ height: "100%", transform: "scaleY(0)" }}
            aria-hidden
          />

          <div data-stage className="flex flex-col gap-3">
            <span className="text-xs text-ink-dim">A real reading, from this build&apos;s own history</span>
            <div className="tnum glow-breach text-5xl font-medium" style={{ color: "var(--breach)" }}>
              {EXAMPLE.watts}W
            </div>
            <p className="text-sm text-ink-dim">
              {EXAMPLE.appliance} · {EXAMPLE.location} · rated for {EXAMPLE.rated}W
            </p>
            <p className="max-w-md text-ink-dim">
              Every appliance reports its wattage every few seconds. Almost always, nothing happens. This time the
              reading came in at more than double what the device is rated for.
            </p>
          </div>

          <div data-stage className="flex flex-col gap-3">
            <span className="text-xs text-ink-dim">The agent investigates</span>
            <p className="prose-log text-ink">{EXAMPLE.reasoning}</p>
            <p className="max-w-md text-sm text-ink-dim">
              An AI agent pulls the appliance&apos;s profile and recent history, then writes out its own reasoning
              in full — not a black box.
            </p>
          </div>

          <div data-stage className="flex flex-col gap-3">
            <span className="text-xs text-ink-dim">The gate has the final word</span>
            <div
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: "var(--breach)", color: "var(--breach)" }}
            >
              <span className="tnum shrink-0">1</span>
              {EXAMPLE.gateRule}
            </div>
            <p className="max-w-md text-sm text-ink-dim">
              The agent doesn&apos;t get the final say. A short, fixed list of rules checks its work — here, the
              reading alone was enough to escalate, regardless of what the model thought.
            </p>
            <span
              className="mt-1 inline-block w-fit rounded-full px-3 py-1 text-xs font-medium"
              style={{ background: "color-mix(in srgb, var(--breach) 18%, transparent)", color: "var(--breach)" }}
            >
              Escalation
            </span>
          </div>
        </div>
      </section>

      <section className="flex flex-col items-center gap-4 px-4 py-24 text-center">
        <h2 className="text-2xl font-bold tracking-tight">See it running on real data</h2>
        <p className="max-w-md text-ink-dim">
          The dashboard is live — the same appliances, the same agent, updating in real time.
        </p>
        <Link href="/dashboard">
          <CtaButton>Open the live dashboard</CtaButton>
        </Link>
        <p className="pt-8 text-xs text-ink-dim">Built by Arnav Nayak</p>
      </section>
    </main>
  );
}
