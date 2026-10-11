"use client";

import { useState } from "react";
import { renderShareCard } from "@/lib/share-card";

type Props = {
  title: string;
  text: string;
  path: string;
  /** Crew slug; selects the card design in src/data/share-cards.ts. */
  slug: string;
  className?: string;
};

type Status = "idle" | "working" | "shared" | "saved" | "error";

const MESSAGES: Record<Status, string> = {
  idle: "",
  working: "Creating share card…",
  shared: "Share card ready",
  saved: "Share card downloaded",
  error: "Couldn’t create the share card",
};

export default function ShareButton({
  title,
  text,
  path,
  slug,
  className,
}: Props) {
  const [status, setStatus] = useState<Status>("idle");

  function flash(next: Status) {
    setStatus(next);
    window.setTimeout(() => setStatus("idle"), 2500);
  }

  async function share() {
    if (status === "working") return;
    setStatus("working");
    try {
      const url = new URL(path, window.location.origin).toString();
      const blob = await renderShareCard({
        slug,
        name: title,
        role: text,
      });
      const fileName = `chhayanautical-${title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")}.png`;
      const file = new File([blob], fileName, { type: "image/png" });

      // Mobile: hand the image to the native share sheet (Instagram, etc.).
      if (navigator.canShare?.({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title, text, url });
          flash("shared");
          return;
        } catch (err) {
          if ((err as DOMException).name === "AbortError") {
            setStatus("idle");
            return;
          }
          // anything else: fall through to the download path
        }
      }

      // Desktop / unsupported: download the PNG so it can be posted manually.
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(href), 1000);
      flash("saved");
    } catch {
      flash("error");
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={share}
        disabled={status === "working"}
        aria-label={`Share ${title} as an image`}
        aria-busy={status === "working"}
        className={`${className ?? ""} ${status === "working" ? "animate-pulse" : ""}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/crew/icon-share.svg"
          alt=""
          className="block size-full max-w-none"
        />
      </button>
      <span role="status" className="sr-only">
        {MESSAGES[status]}
      </span>
    </>
  );
}
