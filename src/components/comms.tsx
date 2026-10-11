"use client";

import Image from "next/image";
import { useState, type FormEvent } from "react";

const CREW_EMAIL = "chhayanautical@gmail.com";

/* Static export has no server, so messages go through FormSubmit, which
   relays the POST to CREW_EMAIL (first submission needs a one-time activation
   click in that inbox). */
const RELAY_URL = `https://formsubmit.co/ajax/${CREW_EMAIL}`;

type SendState = "idle" | "sending" | "sent" | "error";

export default function Comms() {
  const [copied, setCopied] = useState(false);
  const [sendState, setSendState] = useState<SendState>("idle");

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(CREW_EMAIL);
    } catch {
      // Clipboard API unavailable (insecure context / denied): legacy fallback.
      const ta = document.createElement("textarea");
      ta.value = CREW_EMAIL;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      if (!ok) return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const contact = String(new FormData(form).get("contact") ?? "").trim();
    if (!contact || sendState === "sending") return;

    setSendState("sending");
    try {
      const res = await fetch(RELAY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          _subject: "Chhayanautical website: contact request",
          _captcha: "false",
          contact,
          message: `Please contact me at: ${contact}`,
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      form.reset();
      setSendState("sent");
    } catch {
      setSendState("error");
    }
  }

  return (
    <section
      id="comms"
      aria-label="Contact the crew"
      className="flex flex-col items-center gap-6 overflow-hidden px-4 py-10 lg:h-[15.1875rem] lg:flex-row lg:justify-center lg:gap-4 lg:px-[3.3125rem] lg:py-[2.25rem]"
    >
      <Image
        src="/images/shared/crew-avatars.png"
        alt="The Chhayanautical crew"
        width={699}
        height={130}
        className="h-auto w-full max-w-[22rem] shrink-0 lg:h-[8.125rem] lg:w-[43.6875rem] lg:max-w-none"
      />

      <div className="relative flex size-24 shrink-0 items-center justify-center lg:size-[9.614rem]">
        <button
          type="button"
          onClick={copyEmail}
          aria-label={`Copy ${CREW_EMAIL} to clipboard`}
          className="flex size-full cursor-pointer items-center justify-center transition-transform hover:scale-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          <span className="relative block size-[77.19%] -rotate-[21.36deg] overflow-clip">
            <span className="absolute inset-[6.25%]">
              <span className="absolute inset-[-3.91%]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/shared/comms-icon.svg"
                  alt=""
                  className={`block size-full max-w-none transition-opacity ${
                    copied ? "opacity-30" : ""
                  }`}
                />
              </span>
            </span>
            {copied && (
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--orange-1)"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="absolute inset-[25%] size-1/2"
              >
                <path d="M4 12.5l5 5L20 6.5" />
              </svg>
            )}
          </span>
        </button>
        <span
          aria-hidden
          className={`pointer-events-none absolute -bottom-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-white px-2 py-0.5 text-sm font-semibold text-black transition-opacity ${
            copied ? "opacity-100" : "opacity-0"
          }`}
        >
          Email copied!
        </span>
        <span role="status" className="sr-only">
          {copied ? "Email address copied to clipboard" : ""}
        </span>
      </div>

      <form
        className="relative flex w-full max-w-[28rem] flex-col gap-4 sm:flex-row sm:items-center lg:w-auto lg:max-w-none lg:gap-4"
        onSubmit={onSubmit}
      >
        <label className="sr-only" htmlFor="comms-contact">
          Your email or phone number
        </label>
        <input
          id="comms-contact"
          name="contact"
          type="text"
          required
          autoComplete="email"
          placeholder="Or let us contact you instead"
          className="h-[5.9375rem] min-h-16 w-full rounded-md bg-surface px-[1.88rem] text-lg leading-[0.8] text-white placeholder:text-muted lg:w-[15.625rem] lg:text-[1.5rem]"
        />
        <button
          type="submit"
          disabled={sendState === "sending"}
          className="h-[4.5rem] min-h-14 shrink-0 rounded-md bg-white px-10 text-xl font-semibold text-black transition-opacity hover:opacity-80 disabled:opacity-60 lg:w-[8.875rem] lg:px-0 lg:text-[1.3125rem]"
        >
          {sendState === "sending" ? "Sending…" : "Send"}
        </button>
        {(sendState === "sent" || sendState === "error") && (
          <p
            role="status"
            className={`text-sm sm:absolute sm:left-0 sm:top-full sm:mt-2 ${
              sendState === "error" ? "text-red-1" : "text-green"
            }`}
          >
            {sendState === "sent"
              ? "Thanks — we’ll be in touch soon."
              : `Couldn’t send. Please email ${CREW_EMAIL} directly.`}
          </p>
        )}
      </form>
    </section>
  );
}
