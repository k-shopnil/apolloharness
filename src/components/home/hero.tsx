import Image from "next/image";
import type { CSSProperties } from "react";

/*
 * Figma only ships a still of the NASA LRO orbit clip, so the moon plate
 * (arc/dot/label removed) is animated here: LRO circles the Moon continuously
 * with a fading trail. Coordinates are in the 1440×850 hero frame.
 */
const FRAME = { w: 1440, h: 850 };
const MOON = { cx: 721, cy: 425 };
const ORBIT_R = 356;
const SIZE = ORBIT_R * 2;
const TRAIL_DEG = 100;
const SEGMENTS = 28;
const LABEL_OFFSET = 31;

const pct = (n: number, of: number) => `${(n / of) * 100}%`;
const cqw = (n: number) => `${(n / FRAME.w) * 100}cqw`;

/*
 * Drifting starfield behind the moon. Each layer is a seamless SVG tile of
 * deterministic pseudo-random stars (same output on server and client) that
 * scrolls left → right; nearer layers are larger and faster for parallax.
 */
const STAR_LAYERS = [
  { tile: 960, count: 60, rMin: 0.5, rMax: 1.0, opacity: 0.55, seconds: 160 },
  { tile: 720, count: 40, rMin: 0.8, rMax: 1.4, opacity: 0.75, seconds: 100 },
  { tile: 540, count: 18, rMin: 1.2, rMax: 2.0, opacity: 0.95, seconds: 60 },
].map((layer, li) => {
  let seed = 1013 + li * 7919;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
  const stars = Array.from({ length: layer.count }, () => {
    const r = layer.rMin + rand() * (layer.rMax - layer.rMin);
    const tint = rand() < 0.15 ? "#ffe7c7" : rand() < 0.15 ? "#cfe0ff" : "#fff";
    return `<circle cx="${(rand() * layer.tile).toFixed(1)}" cy="${(rand() * FRAME.h).toFixed(1)}" r="${r.toFixed(2)}" fill="${tint}"/>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${layer.tile}" height="${FRAME.h}" viewBox="0 0 ${layer.tile} ${FRAME.h}">${stars}</svg>`;
  return { ...layer, url: `url("data:image/svg+xml,${encodeURIComponent(svg)}")` };
});

/* Moon disc (plate is a full-bleed black photo): keep only the circle. */
const MOON_MASK = `radial-gradient(circle at ${pct(MOON.cx, FRAME.w)} ${pct(MOON.cy, FRAME.h)}, #000 ${cqw(ORBIT_R - 1)}, transparent ${cqw(ORBIT_R + 3)})`;

/*
 * Lunar eclipse (after NASA's LRO eclipse clip): Earth's umbra is a disc
 * ~2.5× the Moon's radius passing slightly south of centre, ringed by a faint
 * penumbra. It travels ±UMBRA_TRAVEL from the Moon's centre; timing lives in
 * globals.css (.umbra*).
 */
const MOON_R = 350;
const UMBRA_R = 880;
const UMBRA_D = UMBRA_R * 2;
const UMBRA_DY = 40;
const PENUMBRA = 120;
const UMBRA_TRAVEL = UMBRA_R + PENUMBRA + MOON_R + 10;
const UMBRA_BOX = { x: MOON.cx - UMBRA_R, y: MOON.cy + UMBRA_DY - UMBRA_R };

/* soft shadow edge; also clips the copper moon to the umbra */
const UMBRA_MASK =
  "radial-gradient(closest-side, #000 96.8%, rgba(0, 0, 0, 0.62) 98.4%, transparent 100%)";
const PENUMBRA_SHADE = `radial-gradient(closest-side, rgba(16, 4, 0, 0.5) ${((UMBRA_R / (UMBRA_R + PENUMBRA)) * 100).toFixed(1)}%, transparent 100%)`;
/* totality is darker and redder toward the umbra's centre */
const UMBRA_DEPTH =
  "radial-gradient(closest-side, #b8604c 0%, #d99a84 40%, #fff 85%)";
const UMBRA_FRINGE =
  "radial-gradient(closest-side, transparent 94.5%, rgba(64, 18, 8, 0.7) 98%)";

const point = (deg: number) => {
  const rad = (deg * Math.PI) / 180;
  return [ORBIT_R + ORBIT_R * Math.cos(rad), ORBIT_R + ORBIT_R * Math.sin(rad)];
};

/* dot sits at 0° (right); the trail fades out behind it, counter-clockwise */
const trail = Array.from({ length: SEGMENTS }, (_, i) => {
  const a0 = -TRAIL_DEG + (i * TRAIL_DEG) / SEGMENTS;
  const a1 = -TRAIL_DEG + ((i + 1) * TRAIL_DEG) / SEGMENTS;
  const [x0, y0] = point(a0);
  const [x1, y1] = point(a1);
  return {
    d: `M${x0.toFixed(2)} ${y0.toFixed(2)}A${ORBIT_R} ${ORBIT_R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`,
    opacity: Math.pow((i + 1) / SEGMENTS, 1.6),
  };
});

export default function Hero() {
  const [dotX, dotY] = point(0);

  return (
    <section
      aria-label="Moon — LRO orbit"
      className="relative overflow-hidden bg-black [container-type:inline-size]"
    >
      {STAR_LAYERS.map((layer) => (
        <div
          key={layer.tile}
          aria-hidden
          className="star-drift pointer-events-none absolute inset-0"
          style={
            {
              backgroundImage: layer.url,
              backgroundSize: `${cqw(layer.tile)} ${cqw(FRAME.h)}`,
              opacity: layer.opacity,
              animationDuration: `${layer.seconds}s`,
              "--tile": cqw(layer.tile),
            } as CSSProperties
          }
        />
      ))}

      {/*
        On lg+ the frame also shrinks so its height fits the space under the
        sticky 13.75rem header, keeping the whole moon visible above the fold
        (1.6941 = 1440/850).
      */}
      <div className="relative mx-auto aspect-[1440/850] w-full max-w-[90rem] overflow-hidden [container-type:inline-size] lg:w-[min(100%,calc((100svh-13.75rem)*1.6941))] lg:min-w-[36rem]">
        <div
          className="absolute inset-0"
          style={{ maskImage: MOON_MASK, WebkitMaskImage: MOON_MASK }}
        >
          <Image
            src="/images/home/hero-moon-clean.webp"
            alt="The Moon, orbited by the Lunar Reconnaissance Orbiter (LRO), passing through Earth's shadow"
            fill
            preload
            sizes="(min-width: 1440px) 1440px, 100vw"
            className="object-cover"
          />

          <div
            aria-hidden
            className="umbra pointer-events-none absolute"
            style={
              {
                left: pct(UMBRA_BOX.x, FRAME.w),
                top: pct(UMBRA_BOX.y, FRAME.h),
                width: pct(UMBRA_D, FRAME.w),
                aspectRatio: "1",
                "--umbra-travel": pct(UMBRA_TRAVEL, UMBRA_D),
              } as CSSProperties
            }
          >
            <div
              className="absolute rounded-full"
              style={{
                inset: `-${pct(PENUMBRA, UMBRA_D)}`,
                backgroundImage: PENUMBRA_SHADE,
              }}
            />
            <div
              className="absolute inset-0 bg-black"
              style={{ maskImage: UMBRA_MASK, WebkitMaskImage: UMBRA_MASK }}
            >
              <div className="umbra-counter absolute inset-0">
                {/* the hero frame, re-registered inside the umbra's box */}
                <div
                  className="umbra-blood absolute isolate"
                  style={{
                    left: pct(-UMBRA_BOX.x, UMBRA_D),
                    top: pct(-UMBRA_BOX.y, UMBRA_D),
                    width: pct(FRAME.w, UMBRA_D),
                    height: pct(FRAME.h, UMBRA_D),
                  }}
                >
                  <Image
                    src="/images/home/hero-moon-clean.webp"
                    alt=""
                    fill
                    loading="eager"
                    sizes="(min-width: 1440px) 1440px, 100vw"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-[#e0641f] mix-blend-multiply" />
                  <div className="umbra-crimson absolute inset-0 bg-[#b0261c] mix-blend-multiply" />
                </div>
              </div>
              <div
                className="absolute inset-0 mix-blend-multiply"
                style={{ backgroundImage: UMBRA_DEPTH }}
              />
              <div
                className="absolute inset-0"
                style={{ backgroundImage: UMBRA_FRINGE }}
              />
            </div>
          </div>
        </div>

        <div
          aria-hidden
          className="lro-orbit pointer-events-none absolute"
          style={{
            left: pct(MOON.cx - ORBIT_R, FRAME.w),
            top: pct(MOON.cy - ORBIT_R, FRAME.h),
            width: pct(SIZE, FRAME.w),
            aspectRatio: "1",
          }}
        >
          <svg
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            className="size-full overflow-visible"
            fill="none"
          >
            <g stroke="#7dabeb" strokeWidth="4">
              {trail.map((seg) => (
                <path key={seg.d} d={seg.d} opacity={seg.opacity} />
              ))}
            </g>
            <circle cx={dotX} cy={dotY} r="7" fill="#7dabeb" />
            <g transform={`translate(${dotX + LABEL_OFFSET} ${dotY})`}>
              <text
                className="lro-label font-sans"
                textAnchor="middle"
                dominantBaseline="central"
                fill="#fff"
                fontSize="22"
                fontWeight="600"
              >
                LRO
              </text>
            </g>
          </svg>
        </div>
      </div>
    </section>
  );
}
