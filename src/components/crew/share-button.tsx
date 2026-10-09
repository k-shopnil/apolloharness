"use client";

import { useState } from "react";

type Props = {
  title: string;
  text: string;
  path: string;
  className?: string;
};

export default function ShareButton({ title, text, path, className }: Props) {
  const [copied, setCopied] = useState(false);

  async function share() {
    const url = new URL(path, window.location.origin).toString();
    try {
      if (navigator.share) {
        await navigator.share({ title, text, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* share sheet dismissed or clipboard unavailable */
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={share}
        aria-label={`Share ${title}`}
        className={className}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/crew/icon-share.svg"
          alt=""
          className="block size-full max-w-none"
        />
      </button>
      <span role="status" className="sr-only">
        {copied ? "Link copied" : ""}
      </span>
    </>
  );
}
