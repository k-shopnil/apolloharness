/**
 * Planet artwork for the Home "Collab" strip, transcribed from Figma node
 * 69:18614 (Frame 40). All numbers are Figma px, relative to their parent.
 * Rendering lives in planet-strip.tsx.
 */

type Box = { l: number; t: number; w: number; h: number };

export type Layer =
  | ({
      kind: "flat";
      src: string;
      inset?: string;
      opacity?: number;
      cover?: boolean;
    } & Box)
  | ({
      kind: "rot";
      src: string;
      iw: number;
      ih: number;
      tf: string;
      inset?: string;
      cover?: boolean;
    } & Box);

export type Planet = {
  id: string;
  width: number;
  disc: {
    l: number;
    t: number;
    /** Rotated wrapper (size + rotate) — omitted when the disc is placed directly. */
    wrap?: { size: number; rotate: number };
    shadow: string;
    gradient: string;
  };
  layers: Layer[];
  overlay?: Layer[];
};

const p = (name: string) => `/images/planets/${name}`;

const flat = (
  name: string,
  l: number,
  t: number,
  w: number,
  h: number,
  inset?: string,
  extra?: { opacity?: number; cover?: boolean },
): Layer => ({ kind: "flat", src: p(name), l, t, w, h, inset, ...extra });

const rot = (
  name: string,
  box: Box,
  iw: number,
  ih: number,
  tf: string,
  inset?: string,
  cover?: boolean,
): Layer => ({ kind: "rot", src: p(name), ...box, iw, ih, tf, inset, cover });

/* Shared light/shadow overlays that sit on top of every disc */
const SHADOW_IN = { iw: 351.272, ih: 302.105 };
const shadow = (name: string, box: Box, deg: number, inset: string) =>
  rot(name, box, SHADOW_IN.iw, SHADOW_IN.ih, `rotate(${deg}deg)`, inset);

const SHADOW_A: Box = { l: -122.12, t: -70.48, w: 420.994, h: 387.302 };
const HIGHLIGHT_A: Box = { l: -108.47, t: -119.64, w: 457.597, h: 441.584 };
const SHADOW_B: Box = { l: -134.33, t: -85.73, w: 438.909, h: 411.759 };
const HIGHLIGHT_B: Box = { l: -81.69, t: -119.09, w: 447.24, h: 424.098 };

const A_DEG = { shadow: 16.02, highlight: -148.31 };
const B_DEG = { shadow: 22.02, highlight: -154.44 };
const SH_INSET = "-4.7% -4.04%";
const HL_INSET = "-5.88% -5.05%";

/* Horizontal bands wrapped around the ringed / banded planets */
const band = (
  name: string,
  t: number,
  inset: string,
  l = -107.92,
  w = 881.82,
  h = 9.94,
) => flat(name, l, t, w, h, inset);

const STRIPE_INSET = "-7.86% 0 -28.39% 0";
const STRIPE_TOP_INSET = "0 0 -14.19% 0";

/* Neptune stripes: [left, top, width, inset, asset] */
const neptuneStripes: [number, number, number, string, string][] = [
  [-89.69, 100.82, 834.494, "-0.96% -0.21% -16.04% -0.21%", "vector1.svg"],
  [-130.6, 135.53, 834.494, "3.25% -0.16% -12.03% -0.16%", "vector12.svg"],
  [-103.72, 113.6, 834.494, "7.46% -0.1% -8.02% -0.1%", "vector2.svg"],
  [-116.82, 120.7, 834.494, "11.67% 0 -4.01% 0", "vector6.svg"],
  [-112.83, 124.06, 834.494, "13.77% 0 -2.01% 0", "vector10.svg"],
  [-122.08, 128.09, 834.494, "13.77% 0 -2.01% 0", "vector10.svg"],
  [-103.48, 162.82, 861.157, "13.88% 0 -1.01% 0", "vector9.svg"],
  [-118.61, 168.02, 861.157, "13.88% 0 -1.01% 0", "vector9.svg"],
  [-102.52, 172.96, 861.157, "10.72% 0 -4.02% 0", "vector18.svg"],
  [-109.62, 176.51, 861.157, "6.51% 0 -8.04% 0", "vector23.svg"],
  [-110.35, 187.18, 861.157, "12.83% 0 -2.01% 0", "vector21.svg"],
  [-101.85, 92.66, 834.494, "11.67% 0 -4.01% 0", "vector6.svg"],
  [-110.46, 88.15, 834.494, "13.77% 0 -2.01% 0", "vector10.svg"],
  [-140.21, 15.98, 861.157, "10.72% 0 -4.02% 0", "vector5.svg"],
  [-126.4, 10.28, 861.157, "12.83% 0 -2.01% 0", "vector16.svg"],
  [-121.84, -14.33, 861.157, "12.83% 0 -2.01% 0", "vector20.svg"],
  [-142.16, 26.52, 861.157, "6.51% 0 -8.04% 0", "vector14.svg"],
  [-140.72, 44.24, 861.157, "10.72% 0 -4.02% 0", "vector15.svg"],
  [-159.43, 37.14, 861.157, "10.72% 0 -4.02% 0", "vector15.svg"],
  [-154.17, 21.46, 861.157, "12.83% 0 -2.01% 0", "vector16.svg"],
];

/* Venus-style spot clusters share one inner size */
const SPOT_IN = { iw: 154.425, ih: 152.071 };
const spot = (name: string, box: Box, tf: string) =>
  rot(name, box, SPOT_IN.iw, SPOT_IN.ih, tf);

export const planets: Planet[] = [
  {
    id: "69:18615",
    width: 426,
    disc: {
      l: 99.33,
      t: 99.33,
      wrap: { size: 227.339, rotate: -4 },
      shadow: "0px 1.42px 35.5px 7.1px rgba(166,143,231,0.3)",
      gradient:
        "linear-gradient(226.576deg, rgb(226,216,254) 15.137%, rgb(131,110,190) 125.76%)",
    },
    layers: [
      flat("spots.svg", -31.24, -30.53, 259.732, 274.052),
      flat("spots1.svg", 228.49, -30.53, 259.732, 274.052),
      shadow("shadow.svg", SHADOW_A, A_DEG.shadow, SH_INSET),
      shadow("highlight.svg", HIGHLIGHT_A, A_DEG.highlight, HL_INSET),
      rot(
        "image8.png",
        { l: 59.47, t: 60.54, w: 93.924, h: 93.924 },
        88,
        88,
        "rotate(-176deg) scaleY(-1)",
        undefined,
        true,
      ),
    ],
  },
  {
    id: "69:18746",
    width: 426,
    disc: {
      l: 97.62,
      t: 97.62,
      wrap: { size: 230.754, rotate: -5 },
      shadow: "0px 0px 28.4px 0px #ea6b02",
      gradient:
        "linear-gradient(85.144deg, rgb(245,97,15) 27.409%, rgb(255,145,4) 106.4%)",
    },
    layers: [
      spot("group2.svg", { l: 25.39, t: 20.91, w: 154.425, h: 152.071 }, "scaleY(-1)"),
      spot("group3.svg", { l: 2.31, t: 0.51, w: 216.544, h: 216.38 }, "rotate(137.82deg)"),
      spot("group4.svg", { l: 234.84, t: 20.91, w: 154.425, h: 152.071 }, "scaleY(-1)"),
      spot("group5.svg", { l: 211.76, t: 0.51, w: 216.544, h: 216.38 }, "rotate(137.82deg)"),
      flat("group1.svg", -91.54, -14.33, 701.427, 235.238, "0 -0.5% -1.18% -0.34%"),
      shadow("shadow1.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight1.svg", HIGHLIGHT_B, B_DEG.highlight, HL_INSET),
    ],
    overlay: [flat("image5Vectorized.svg", 120.78, 159, 184, 92)],
  },
  {
    id: "69:18827",
    width: 426,
    disc: {
      l: 106.5,
      t: 106.5,
      shadow: "0px 0px 28.4px 0px rgba(13,75,84,0.5)",
      gradient:
        "linear-gradient(260.672deg, rgb(0,221,254) 6.8213%, rgb(95,54,215) 93.193%)",
    },
    layers: [
      ...neptuneStripes.map(([l, t, w, inset, name]) =>
        flat(name, l, t, w, 33.725, inset),
      ),
      flat("group17.svg", 41.89, 24.85, 326.067, 147.488),
      flat("group18.svg", 461.14, 24.85, 326.067, 147.488),
      shadow("shadow2.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight2.svg", HIGHLIGHT_B, B_DEG.highlight, HL_INSET),
    ],
    overlay: [flat("image9.png", 132.55, 166, 180, 81, undefined, { cover: true })],
  },
  {
    id: "69:18878",
    width: 490.965,
    disc: {
      l: 95.21,
      t: 67.52,
      wrap: { size: 290.963, rotate: -60 },
      shadow: "0px 0px 28.4px 0px #20103f",
      gradient:
        "linear-gradient(250.117deg, rgb(182,138,255) 12.636%, rgb(62,22,182) 89.177%)",
    },
    layers: [
      band("group19.svg", 17.22, STRIPE_TOP_INSET),
      band("group20.svg", 31.42, STRIPE_INSET),
      band("group21.svg", 113.07, "-36.43% 0 -56.77% -0.1%"),
      band("group22.svg", 83.6, "-54.29% 0 -74.51% -0.14%"),
      band("group23.svg", 173.42, STRIPE_TOP_INSET),
      band("group24.svg", 191.17, STRIPE_INSET),
      band("group25.svg", 159.22, STRIPE_INSET),
      shadow("shadow3.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight3.svg", HIGHLIGHT_B, B_DEG.highlight, HL_INSET),
    ],
    overlay: [
      rot(
        "ellipse221.svg",
        { l: 130.64, t: 25.76, w: 226.991, h: 369.099 },
        412.308,
        24.06,
        "rotate(-60deg)",
        "-26.55% -1.55% -26.56% -1.55%",
      ),
      rot(
        "ellipse222.svg",
        { l: 143.05, t: 47.03, w: 198.804, h: 330.792 },
        374.144,
        13.546,
        "rotate(-60deg)",
        "-41.93% -1.52%",
      ),
      flat("image6.png", 154.33, 121, 179, 179, undefined, { cover: true }),
    ],
  },
  {
    id: "69:18901",
    width: 490.965,
    disc: {
      l: 108.96,
      t: 81.27,
      wrap: { size: 263.459, rotate: -16 },
      shadow: "0px 0px 28.4px 0px rgba(51,78,14,0.6)",
      gradient:
        "linear-gradient(250.117deg, rgb(167,207,117) 12.636%, rgb(98,123,52) 89.177%)",
    },
    layers: [
      band("group26.svg", 17.22, STRIPE_TOP_INSET),
      band("group27.svg", 31.42, STRIPE_INSET),
      band("group28.svg", 84.67, STRIPE_INSET),
      band("group29.svg", 70.47, "-22.15% 0 -42.58% 0"),
      band("group30.svg", 173.42, STRIPE_TOP_INSET),
      band("group31.svg", 191.17, STRIPE_INSET),
      band("group32.svg", 159.22, STRIPE_INSET),
      shadow("shadow4.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight4.svg", HIGHLIGHT_B, B_DEG.highlight, HL_INSET),
    ],
    overlay: [
      rot(
        "rings.svg",
        { l: 19.62, t: 140.78, w: 448.539, h: 166.199 },
        454.4,
        42.6,
        "rotate(-16deg)",
        "-14.98% -1.41% -15% -1.41%",
      ),
      flat("image7.png", 160.14, 160, 162, 107, undefined, { cover: true }),
    ],
  },
  {
    id: "69:18925",
    width: 426,
    disc: {
      l: 92.71,
      t: 92.71,
      wrap: { size: 240.571, rotate: -8 },
      shadow: "0px 0px 28.4px 0px rgba(103,40,18,0.8)",
      gradient:
        "linear-gradient(260.672deg, rgb(244,232,213) 6.8213%, rgb(252,113,0) 93.193%)",
    },
    layers: [
      flat("group6.svg", -159.43, -14.33, 948.059, 235.238, "0 -0.15% -1.04% -0.23%"),
      shadow("shadow5.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight5.svg", HIGHLIGHT_B, B_DEG.highlight, HL_INSET),
      rot(
        "image10.png",
        { l: 23.01, t: 23.9, w: 164.898, h: 164.898 },
        146,
        146,
        "rotate(8deg)",
        undefined,
        true,
      ),
    ],
  },
  {
    id: "69:18983",
    width: 426,
    disc: {
      l: 97.62,
      t: 97.62,
      wrap: { size: 230.754, rotate: -5 },
      shadow: "0px 2.84px 71px 8.875px rgba(233,3,56,0.4)",
      gradient:
        "linear-gradient(226.576deg, rgb(243,22,78) 15.137%, rgb(139,1,25) 125.76%)",
    },
    layers: [
      flat("spots2.svg", -34.34, -14.07, 262.837, 257.589),
      flat("spots3.svg", 228.49, -14.07, 262.837, 257.589),
      flat("group16.svg", -535.34, 116.79, 888.21, 65.675, "0 0 -6.19% -0.14%"),
      rot(
        "shadow6.svg",
        SHADOW_A,
        SHADOW_IN.iw,
        SHADOW_IN.ih,
        `rotate(${A_DEG.shadow}deg)`,
        "-7.05% -6.06%",
      ),
      rot(
        "highlight6.svg",
        { l: -108.47, t: -119.63, w: 457.597, h: 441.584 },
        SHADOW_IN.iw,
        SHADOW_IN.ih,
        `rotate(${A_DEG.highlight}deg)`,
        "-10.58% -9.1%",
      ),
    ],
    overlay: [flat("image4Vectorized.svg", 133.72, 174, 157, 68)],
  },
  {
    id: "69:19086",
    width: 426,
    disc: {
      l: 106.5,
      t: 106.15,
      shadow: "0px 0px 28.4px 0px rgba(0,117,144,0.6)",
      gradient:
        "linear-gradient(85.144deg, rgb(34,142,169) 27.409%, rgb(2,222,254) 106.4%)",
    },
    layers: [
      flat("group14.svg", -116.44, 16.51, 637.073, 196.791, "-2.89% -1.11% -4.33% -1.11%"),
      flat("group46.svg", -102.95, 1.12, 434.165, 224.982, undefined, { opacity: 0.6 }),
      flat("group47.svg", -537.11, 1.12, 434.165, 224.982, undefined, { opacity: 0.6 }),
      shadow("shadow7.svg", SHADOW_B, B_DEG.shadow, SH_INSET),
      shadow("highlight7.svg", HIGHLIGHT_B, B_DEG.highlight, "-9.4% -8.08%"),
    ],
  },
];
