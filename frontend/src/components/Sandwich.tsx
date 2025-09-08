// components/Sandwich.tsx
"use client";

import Image from "next/image";
import * as React from "react";

/**
 * Public assets expected:
 * /public/ingredients/bread.png
 * /public/ingredients/ham.png
 * /public/ingredients/cheese.png
 * /public/ingredients/lettuce.png
 * /public/ingredients/tomato.png
 * /public/ingredients/onion.png
 */

const FILLINGS = ["ham", "cheese", "lettuce", "tomato", "onion"] as const;
type FillingName = (typeof FILLINGS)[number];

export type WeekProgress = {
  week: number; // 1-based week index
  unlocked: boolean; // true if “earned” (e.g., quiz passed)
};

export type SandwichProps = {
  /** total number of weeks (determines layer count) */
  totalWeeks: number;

  /** which weeks are unlocked; if omitted, all fillings are shown as unlocked */
  progress?: WeekProgress[];

  /** rotate starting filling for different courses (0..FILLINGS.length-1) */
  themeOffset?: number;

  /** visual width of a slice in px */
  width?: number;

  /** pixels each slice shifts vertically; smaller = tighter stack */
  overlap?: number;

  /** when true, show every filling even if not unlocked (dim locked ones).
   *  when false, hide locked fillings (stack grows as you progress). */
  showLockedDimmed?: boolean;

  /** alt prefix for a11y (e.g., course title) */
  altPrefix?: string;
};

function pickFilling(i: number): FillingName {
  return FILLINGS[((i % FILLINGS.length) + FILLINGS.length) % FILLINGS.length];
}

export default function Sandwich({
  totalWeeks,
  progress,
  themeOffset = 0,
  width = 200,
  overlap = 16,
  showLockedDimmed = true,
  altPrefix = "Course sandwich",
}: SandwichProps) {
  // heuristic slice height so container stays compact (tweak if your PNGs change)
  const sliceH = Math.round(width * 0.42);

  // Build visual layers: bottom bread → fillings → top bread
  type Layer = { key: string; src: string; alt: string; dim?: boolean };
  const layers: Layer[] = [];

  // bottom bread
  layers.push({
    key: "bread-bottom",
    src: "/ingredients/bread.png",
    alt: `${altPrefix} – bread (bottom)`,
  });

  // fillings
  const weeks = Math.max(0, totalWeeks | 0);
  for (let i = 0; i < weeks; i++) {
    const name = pickFilling(i + themeOffset);
    const unlocked = progress?.find((p) => p.week === i + 1)?.unlocked ?? true;

    if (unlocked || showLockedDimmed) {
      layers.push({
        key: `week-${i + 1}-${name}`,
        src: `/ingredients/${name}.png`,
        alt: `${altPrefix} – ${name} (week ${i + 1})`,
        dim: !unlocked,
      });
    }
  }

  // top bread
  layers.push({
    key: "bread-top",
    src: "/ingredients/bread.png",
    alt: `${altPrefix} – bread (top)`,
  });

  // compute compact container height
  const visibleCount = layers.length;
  const totalHeight = sliceH + Math.max(0, visibleCount - 1) * overlap;

  return (
    <div
      className="relative mx-auto select-none"
      style={{ width, height: totalHeight }}
      aria-label="Sandwich progress"
    >
      {layers.map((L, idx) => {
        // stack downward so we don’t need a tall container
        const y = idx * overlap;
        // draw later = visually on top
        const z = 100 + idx;

        return (
          <div
            key={L.key}
            className={`absolute left-1/2 transition-opacity duration-200 ${
              L.dim ? "opacity-35 grayscale" : "opacity-100"
            }`}
            style={{
              transform: `translateX(-50%) translateY(${y}px)`,
              zIndex: z,
            }}
          >
            <Image
              src={L.src}
              alt={L.alt}
              width={width}
              height={sliceH}
              draggable={false}
              priority={idx === visibleCount - 1}
              // prevent layout shifts if images load slowly
              style={{ width, height: sliceH, objectFit: "contain" }}
            />
          </div>
        );
      })}
    </div>
  );
}
