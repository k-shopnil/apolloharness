"use client";

import { motion, useReducedMotion } from "motion/react";
import type { CSSProperties } from "react";
import { planets, type Layer, type Planet } from "./planets-data";

/* Figma node 69:18614 — x: 1242.748 → -278.252, 22s, linear, infinite */
const MARQUEE_FROM = 1242.748;
const MARQUEE_TO = -278.252;
const MARQUEE_DURATION = 22;
const REST_X = 0; // the static (non-animated) frame in Figma

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

  return (
    <section aria-hidden className="@container w-full max-w-full overflow-hidden bg-black">
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
                src="/images/home/space-stars.png"
                alt=""
                draggable={false}
                style={{ ...fillImg, transform: "scaleX(-1)" }}
              />
            </div>
          </div>

          <motion.div
            data-node-id="69:18614"
            className="absolute flex items-center"
            style={{ left: -201, top: 41 }}
            initial={{ x: reduceMotion ? REST_X : MARQUEE_FROM }}
            animate={
              reduceMotion
                ? { x: REST_X }
                : {
                    x: [MARQUEE_FROM, MARQUEE_TO],
                    transition: {
                      x: {
                        duration: MARQUEE_DURATION,
                        times: [0, 1],
                        ease: "linear",
                        repeat: Infinity,
                      },
                    },
                  }
            }
          >
            {planets.map((planet, i) => (
              <PlanetView
                key={planet.id}
                planet={planet}
                last={i === planets.length - 1}
              />
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
