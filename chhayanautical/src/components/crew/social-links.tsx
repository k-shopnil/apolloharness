import type { ReactNode } from "react";
import type { CrewLinks } from "@/data/crew";

const ICON = "/images/crew";

function Glyph({
  href,
  label,
  className,
  children,
}: {
  href?: string;
  label: string;
  className: string;
  children: ReactNode;
}) {
  const base = `relative block shrink-0 ${className}`;
  return href ? (
    <a
      href={href}
      target={href.startsWith("mailto:") ? undefined : "_blank"}
      rel="noreferrer"
      aria-label={label}
      className={`${base} transition-opacity hover:opacity-70`}
    >
      {children}
    </a>
  ) : (
    <span role="img" aria-label={label} className={base}>
      {children}
    </span>
  );
}

/* eslint-disable @next/next/no-img-element */
export default function SocialLinks({
  links,
  name,
}: {
  links: CrewLinks;
  name: string;
}) {
  const maskSize = "1.867rem 1.867rem";
  return (
    <div className="flex items-center gap-[0.667rem]">
      <Glyph
        href={links.github}
        label={`${name} on GitHub`}
        className="size-[1.867rem] overflow-clip"
      >
        <span
          className="absolute inset-[0_0_2.47%_0]"
          style={{
            WebkitMaskImage: `url(${ICON}/icon-github-mask.svg)`,
            maskImage: `url(${ICON}/icon-github-mask.svg)`,
            WebkitMaskSize: maskSize,
            maskSize,
            WebkitMaskRepeat: "no-repeat",
            maskRepeat: "no-repeat",
          }}
        >
          <img
            src={`${ICON}/icon-github.svg`}
            alt=""
            className="block size-full max-w-none"
          />
        </span>
      </Glyph>

      <Glyph
        href={links.email ? `mailto:${links.email}` : undefined}
        label={`Email ${name}`}
        className="size-[2.56rem]"
      >
        <img
          src={`${ICON}/icon-email.svg`}
          alt=""
          className="block size-full max-w-none"
        />
      </Glyph>

      <Glyph
        href={links.linkedin}
        label={`${name} on LinkedIn`}
        className="size-[1.867rem]"
      >
        <img
          src={`${ICON}/icon-linkedin.svg`}
          alt=""
          className="block size-full max-w-none"
        />
      </Glyph>

      <Glyph
        href={links.instagram}
        label={`${name} on Instagram`}
        className="size-[2.027rem] overflow-clip"
      >
        <span className="absolute inset-[12.5%]">
          <span className="absolute inset-[-5.12%]">
            <img
              src={`${ICON}/icon-instagram.svg`}
              alt=""
              className="block size-full max-w-none"
            />
          </span>
        </span>
      </Glyph>
    </div>
  );
}
