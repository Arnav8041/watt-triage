import type { Metadata } from "next";
import { Space_Grotesk, Martian_Mono, Source_Serif_4 } from "next/font/google";
import { MotionConfig } from "motion/react";
import "./globals.css";

const sans = Space_Grotesk({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const mono = Martian_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const serif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "WattTriage",
  description: "Live triage dashboard for home appliance power draw.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${serif.variable} h-full`}>
      {/* suppressHydrationWarning: some browser extensions (e.g. ColorZilla's
          cz-shortcut-listen) write an attribute onto <body> before React hydrates.
          React can't tell that apart from a real mismatch, so it's silenced here. */}
      <body className="min-h-full" suppressHydrationWarning>
        {/* every whileHover/animate value in the app respects the OS's reduced-motion
            setting from here, once, instead of each component checking it separately */}
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </body>
    </html>
  );
}
