"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [
  { href: "/", label: "Habitat" },
  { href: "/expeditions", label: "Expeditions" },
  { href: "/crew", label: "Crew" },
] as const;

function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" aria-label="Chhayanautical — home" className={className}>
      <Image
        src="/images/shared/logo-mark.svg"
        alt=""
        width={100}
        height={107}
        priority
        className="absolute left-0 top-1/2 h-auto w-9 -translate-y-1/2 lg:-left-[1.488rem] lg:top-[-0.0225rem] lg:w-[6.231rem] lg:translate-y-0"
      />
      <span className="absolute left-11 top-1/2 -translate-y-1/2 font-display text-[1.375rem] uppercase leading-[0.8] lg:left-[5.305rem] lg:top-[0.393rem] lg:translate-y-0 lg:text-[3.811rem]">
        Chhaya
        <br />
        Nautical
      </span>
    </Link>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-50 bg-black/20 backdrop-blur-xl backdrop-saturate-150">
      {/* Desktop / tablet — Figma 1440 layout */}
      <div className="mx-auto hidden h-[10rem] max-w-[90rem] items-center justify-between px-6 lg:flex lg:h-[13.75rem] lg:px-[5.875rem]">
        <Logo className="relative block h-[6.732rem] w-[23.07rem] shrink-0" />
        <nav
          aria-label="Primary"
          className="flex w-[38.181rem] shrink-0 items-center justify-between text-[1.941rem] font-semibold leading-[0.8]"
        >
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? "page" : undefined}
              className={`transition-colors hover:text-white ${
                isActive(href) ? "text-white" : "text-white/50"
              }`}
            >
              {label}
            </Link>
          ))}
          <Link
            href="#comms"
            className="group relative flex h-[3.0625rem] w-[9.0625rem] items-center justify-center border border-white transition-colors hover:border-white hover:bg-white hover:text-black"
          >
            <span className="relative z-10 leading-[0.8]">Comms</span>
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 z-20 hidden items-center justify-center group-hover:flex"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/shared/comms-scribble.svg"
                alt=""
                className="h-[50.7px] w-[132.3px] max-w-none rotate-[-6.74deg] object-contain"
              />
            </span>
          </Link>
        </nav>
      </div>

      {/* Mobile */}
      <div className="lg:hidden">
        <div className="flex h-16 items-center justify-between px-4">
          <Logo className="relative block h-10 w-[11.5rem]" />
          <button
            type="button"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
            className="flex size-10 flex-col items-center justify-center gap-1.5"
          >
            <span
              className={`h-0.5 w-6 bg-white transition-transform ${
                open ? "translate-y-2 rotate-45" : ""
              }`}
            />
            <span
              className={`h-0.5 w-6 bg-white transition-opacity ${
                open ? "opacity-0" : ""
              }`}
            />
            <span
              className={`h-0.5 w-6 bg-white transition-transform ${
                open ? "-translate-y-2 -rotate-45" : ""
              }`}
            />
          </button>
        </div>
        {open && (
          <nav
            id="mobile-nav"
            aria-label="Primary"
            className="flex flex-col gap-5 border-t border-white/15 bg-black px-4 py-6 text-2xl font-semibold"
          >
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={isActive(href) ? "page" : undefined}
                className={isActive(href) ? "text-white" : "text-white/50"}
              >
                {label}
              </Link>
            ))}
            <Link
              href="#comms"
              onClick={() => setOpen(false)}
              className="group relative flex h-[3.0625rem] w-[9.0625rem] items-center justify-center border border-white transition-colors hover:border-white hover:bg-white hover:text-black"
            >
              <span className="relative z-10 leading-[0.8]">Comms</span>
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 z-20 hidden items-center justify-center group-hover:flex"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/shared/comms-scribble.svg"
                  alt=""
                  className="h-[50.7px] w-[132.3px] max-w-none rotate-[-6.74deg] object-contain"
                />
              </span>
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
