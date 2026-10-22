"use client";

import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { planets, type Layer, type Planet } from "./planets-data";

/* Figma node 69:18614 marquee (x: 1242.748 → -278.252, 22s) lives in
   .planet-marquee in globals.css so it runs on the compositor thread. */

const PLANET_OVERLAP = -72.775;
const PLANET_HEIGHT = 426;
const DISC_SIZE = 213;

const absolute: CSSProperties = { position: "absolute" };
const fillImg: CSSProperties = {
  display: "block",
  maxWidth: "none",
  width: "100%",
  height: "100%",
};

function Art({ layer }: { layer: Layer }) {
  const img = (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={layer.src}
      alt=""
      draggable={false}
      decoding="async"
      style={{ ...fillImg, objectFit: layer.cover ? "cover" : undefined }}
    />
  );
  return layer.inset ? (
    <div style={{ ...absolute, inset: layer.inset }}>{img}</div>
  ) : (
    <div style={{ ...absolute, inset: 0 }}>{img}</div>
  );
}

function LayerView({ layer }: { layer: Layer }) {
  const box: CSSProperties = {
    ...absolute,
    left: layer.l,
    top: layer.t,
    width: layer.w,
    height: layer.h,
  };

  if (layer.kind === "flat") {
    return (
      <div style={{ ...box, opacity: layer.opacity }}>
        <Art layer={layer} />
      </div>
    );
  }

  return (
    <div
      style={{
        ...box,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          flex: "none",
          position: "relative",
          width: layer.iw,
          height: layer.ih,
          transform: layer.tf,
        }}
      >
        <Art layer={layer} />
      </div>
    </div>
  );
}

function PlanetView({ planet, last }: { planet: Planet; last: boolean }) {
  const { disc } = planet;
  const ball = (
    <div
      style={{
        ...(disc.wrap ? { position: "relative" } : { ...absolute, left: disc.l, top: disc.t }),
        width: DISC_SIZE,
        height: DISC_SIZE,
        borderRadius: 355,
        overflow: "clip",
        boxShadow: disc.shadow,
        backgroundImage: disc.gradient,
      }}
    >
      {planet.layers.map((layer, i) => (
        <LayerView key={i} layer={layer} />
      ))}
    </div>
  );

  return (
    <div
      data-node-id={planet.id}
      style={{
        position: "relative",
        flexShrink: 0,
        width: planet.width,
        height: PLANET_HEIGHT,
        marginRight: last ? 0 : PLANET_OVERLAP,
      }}
    >
      {disc.wrap ? (
        <div
          style={{
            ...absolute,
            left: disc.l,
            top: disc.t,
            width: disc.wrap.size,
            height: disc.wrap.size,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ flex: "none", transform: `rotate(${disc.wrap.rotate}deg)` }}>
            {ball}
          </div>
        </div>
      ) : (
        ball
      )}
      {planet.overlay?.map((layer, i) => (
        <LayerView key={i} layer={layer} />
      ))}
    </div>
  );
}

export default function PlanetStrip() {
  const reduceMotion = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);

  // Only animate while the strip is on screen.
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), {
      rootMargin: "100px",
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <section
      ref={sectionRef}
      aria-hidden
      className="@container w-full max-w-full overflow-hidden bg-black"
    >
      {/* --k comes from .planet-stage in globals.css (matches the rem scaling) */}
      <div
        className="planet-stage relative overflow-hidden"
        style={{ height: "calc(525px * var(--k))" }}
      >
        <div
          className="absolute left-1/2 top-0 h-[525px] w-[3270px] origin-top"
          style={{ transform: "translateX(-50%) scale(var(--k))" }}
        >
          {/* star field */}
          <div
            style={{
              ...absolute,
              left: 746,
              top: 0,
              width: 1942.59,
              height: 548,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                flex: "none",
                position: "relative",
                width: 548,
                height: 1942.59,
                transform: "rotate(90deg) scaleY(-1)",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/home/space-stars.webp"
                alt=""
                draggable={false}
                loading="lazy"
                decoding="async"
                style={{ ...fillImg, transform: "scaleX(-1)" }}
              />
            </div>
          </div>

          <div
            data-node-id="69:18614"
            className="planet-marquee absolute flex items-center"
            style={{
              left: -201,
              top: 41,
              animationPlayState: reduceMotion || !inView ? "paused" : "running",
            }}
          >
            {planets.map((planet, i) => (
              <PlanetView
                key={planet.id}
                planet={planet}
                last={i === planets.length - 1}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
