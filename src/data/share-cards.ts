/*
 * Per-member styling for the crew share card, transcribed from the Figma
 * "Widget card from share button" section (card = 1080×1383).
 * Keys are crew slugs from src/data/crew.ts.
 */
export type GradientStop = [offset: number, r: number, g: number, b: number];

export type ShareCardStyle = {
  /** Instagram-style handle printed next to the social icons. */
  handle: string;
  /** Figma omits the GitHub glyph on cards of members without a GitHub link. */
  showGithub: boolean;
  /** Portrait placement inside the 587.859px circle, in Figma px. */
  portrait: { x: number; y: number; w: number; h: number };
  /** Radial glow from the top-right corner. */
  gradient: GradientStop[];
};

export const shareCards: Record<string, ShareCardStyle> = {
  "fahim-uddin": {
    handle: "/asmfahim",
    showGithub: true,
    portrait: { x: -67.34, y: -91.72, w: 723.47, h: 1085.2 },
    gradient: [
      [0, 47, 61, 102],
      [0.25, 35, 46, 76],
      [0.5, 23, 31, 51],
      [0.75, 12, 15, 25],
      [0.875, 6, 8, 13],
      [1, 0, 0, 0],
    ],
  },
  "mehedi-hasan": {
    handle: "/mehedihasan",
    showGithub: true,
    portrait: { x: -39.13, y: -56.27, w: 665, h: 774 },
    gradient: [
      [0, 130, 83, 53],
      [0.25, 98, 62, 40],
      [0.5, 65, 42, 27],
      [0.75, 33, 21, 13],
      [0.875, 16, 10, 7],
      [0.9375, 8, 5, 3],
      [1, 0, 0, 0],
    ],
  },
  "shopnil-karmakar": {
    handle: "/shopnilk",
    showGithub: true,
    portrait: { x: -58.13, y: -73.27, w: 735, h: 735 },
    gradient: [
      [0, 117, 130, 6],
      [0.25, 88, 98, 5],
      [0.5, 59, 65, 3],
      [0.75, 29, 33, 2],
      [0.875, 15, 16, 1],
      [0.9375, 7, 8, 0],
      [1, 0, 0, 0],
    ],
  },
  "thirtha-karmakar": {
    handle: "/thirthakarmakar",
    showGithub: true,
    portrait: { x: -87.13, y: -17.27, w: 728, h: 728 },
    gradient: [
      [0, 165, 202, 237],
      [0.25, 124, 152, 178],
      [0.375, 103, 126, 148],
      [0.5, 83, 101, 119],
      [0.625, 62, 76, 89],
      [0.75, 41, 51, 59],
      [0.875, 21, 25, 30],
      [0.9375, 10, 13, 15],
      [0.96875, 5, 6, 7],
      [1, 0, 0, 0],
    ],
  },
  "humayra-akter": {
    handle: "/humayraakter",
    showGithub: false,
    portrait: { x: -85.13, y: -144.27, w: 760, h: 1007 },
    gradient: [
      [0, 187, 61, 50],
      [0.25, 140, 46, 38],
      [0.5, 94, 31, 25],
      [0.625, 70, 23, 19],
      [0.75, 47, 15, 13],
      [0.875, 23, 8, 6],
      [0.9375, 12, 4, 3],
      [1, 0, 0, 0],
    ],
  },
  "sadril-ether": {
    handle: "/sadrilether",
    showGithub: true,
    portrait: { x: -48.13, y: -26.27, w: 665, h: 665 },
    gradient: [
      [0, 183, 150, 193],
      [0.25, 137, 113, 145],
      [0.375, 114, 94, 121],
      [0.5, 92, 75, 97],
      [0.625, 69, 56, 72],
      [0.75, 46, 38, 48],
      [0.875, 23, 19, 24],
      [0.9375, 11, 9, 12],
      [1, 0, 0, 0],
    ],
  },
  "ariful-islam": {
    handle: "/arifulislam",
    showGithub: true,
    portrait: { x: -47.13, y: -27.27, w: 681, h: 817 },
    gradient: [
      [0, 156, 154, 160],
      [0.25, 117, 116, 120],
      [0.5, 78, 77, 80],
      [0.625, 59, 58, 60],
      [0.75, 39, 39, 40],
      [0.875, 20, 19, 20],
      [0.9375, 10, 10, 10],
      [1, 0, 0, 0],
    ],
  },
};
