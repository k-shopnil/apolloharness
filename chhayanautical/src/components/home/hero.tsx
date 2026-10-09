import Image from "next/image";

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
    <section aria-label="Moon — LRO orbit" className="bg-black">
      <div className="relative mx-auto aspect-[1440/850] w-full max-w-[90rem] overflow-hidden">
        <Image
          src="/images/home/hero-moon-clean.webp"
          alt="The Moon, orbited by the Lunar Reconnaissance Orbiter (LRO)"
          fill
          priority
          sizes="(min-width: 1440px) 1440px, 100vw"
          className="object-cover"
        />

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
