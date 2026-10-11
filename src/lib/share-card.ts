import { shareCards } from "@/data/share-cards";

/*
 * Renders a crew member's share card to a PNG on a <canvas>, following the
 * Figma "Profile card" frame (1080×1383, ≈ Instagram 4:5 portrait). All
 * coordinates below are Figma px.
 */
const W = 1080;
const H = 1383;
const ASSETS = "/images/share-card";

export type ShareCardInput = {
  slug: string;
  name: string;
  role: string;
};

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load ${src}`));
    img.src = src;
  });
}

function cssFont(variable: string, fallback: string) {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(variable)
    .trim();
  return v || fallback;
}

export async function renderShareCard({
  slug,
  name,
  role,
}: ShareCardInput): Promise<Blob> {
  const style = shareCards[slug];
  if (!style) throw new Error(`No share card design for "${slug}"`);

  const sans = cssFont("--font-onest", "system-ui, sans-serif");
  const display = cssFont("--font-baumans", "system-ui, sans-serif");

  const [
    backdrop,
    portrait,
    ring,
    object,
    logo,
    harness,
    union,
    line,
    github,
    linkedin,
    instagram,
  ] = await Promise.all([
    loadImage(`${ASSETS}/backdrop.png`),
    loadImage(`${ASSETS}/portrait-${slug}.webp`),
    loadImage(`${ASSETS}/ring.svg`),
    loadImage(`${ASSETS}/object.png`),
    loadImage(`${ASSETS}/logo-space-apps.png`),
    loadImage(`${ASSETS}/harness-mark.png`),
    loadImage(`${ASSETS}/union.svg`),
    loadImage(`${ASSETS}/line.svg`),
    loadImage(`${ASSETS}/github.svg`),
    loadImage(`${ASSETS}/linkedin.svg`),
    loadImage(`${ASSETS}/instagram.svg`),
    document.fonts
      .load(`600 82px ${sans}`)
      .then(() => document.fonts.load(`500 41px ${sans}`))
      .then(() => document.fonts.load(`400 91px ${display}`))
      .catch(() => undefined),
  ]);

  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context unavailable");

  // Background: radial glow centred just above the top-right corner.
  const glow = ctx.createRadialGradient(1025.5, -17, 0, 1025.5, -17, 922.6);
  for (const [offset, r, g, b] of style.gradient) {
    glow.addColorStop(offset, `rgb(${r},${g},${b})`);
  }
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  // Dot-matrix texture, multiplied over the glow.
  ctx.save();
  ctx.globalCompositeOperation = "multiply";
  ctx.globalAlpha = 0.32;
  ctx.drawImage(backdrop, 8, -3, 1064, 1064);
  ctx.restore();

  // Portrait in a circle.
  const CIRCLE = 587.859;
  const cx = W / 2 + 1.06;
  const cy = 189.27 + CIRCLE / 2;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, CIRCLE / 2, 0, Math.PI * 2);
  ctx.clip();
  ctx.fillStyle = "#fff";
  ctx.fillRect(cx - CIRCLE / 2, cy - CIRCLE / 2, CIRCLE, CIRCLE);
  const p = style.portrait;
  ctx.drawImage(portrait, cx - CIRCLE / 2 + p.x, 189.27 + p.y, p.w, p.h);
  ctx.restore();

  // Hand-drawn ring around the portrait (svg overflows its 626px frame).
  ctx.drawImage(
    ring,
    227 - 626 * 0.014,
    176 - 626 * 0.0131,
    626 * 1.014,
    626 * (1 + 0.0131 + 0.0155),
  );

  // Starfield strip behind the footer (rotated asset).
  ctx.save();
  ctx.translate(-106 + 1942.59 / 2, 1025 + 548 / 2);
  ctx.scale(1, -1);
  ctx.rotate(Math.PI / 2);
  ctx.drawImage(object, -548 / 2, -1942.59 / 2, 548, 1942.59);
  ctx.restore();

  ctx.drawImage(line, 0, 1121, 1080, 0.5);
  ctx.drawImage(union, 922, 55, 99.695, 106.511);

  // Social glyphs + handle (GitHub glyph is dropped for members without one).
  let x = 96;
  const iconY = 71.55;
  if (style.showGithub) {
    ctx.drawImage(github, x, iconY, 29.87, 29.13);
    x += 43;
  }
  ctx.drawImage(linkedin, x, iconY, 29.87, 29.87);
  x += style.showGithub ? 40.5 : 39;
  ctx.drawImage(instagram, x, 70, 32.43, 32.43);
  x += 41.5;

  ctx.fillStyle = "#fff";
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  ctx.font = `500 22.1px ${sans}`;
  ctx.fillText(style.handle, x, 73);

  // Name + role, centred.
  ctx.textAlign = "center";
  ctx.font = `600 81.72px ${sans}`;
  ctx.fillText(name, W / 2, 848);
  ctx.font = `500 40.86px ${sans}`;
  ctx.fillText(role, W / 2, 956);

  ctx.drawImage(harness, 413, 1023, 254, 57);

  // Footer: wordmark + Space Apps badge.
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.font = `400 90.85px ${display}`;
  ctx.fillText("CHHAYA", 96, 1174 + 36.3);
  ctx.fillText("NAUTICAL.", 96, 1174 + 36.3 + 72.7);
  ctx.drawImage(logo, 706, 1185, 316, 123);

  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Could not encode PNG"))),
      "image/png",
    ),
  );
}
