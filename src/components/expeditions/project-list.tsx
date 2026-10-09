"use client";

import Image from "next/image";
import { useState } from "react";
import type { ReactNode } from "react";
import type { Project } from "@/data/projects";

const ICONS = "/images/expeditions";

/* ── small pieces ─────────────────────────────────────────────────────── */

function IconLink({
  href,
  label,
  className,
  children,
}: {
  href?: string | null;
  label: string;
  className: string;
  children: ReactNode;
}) {
  const base = `relative block shrink-0 ${className}`;
  return href ? (
    <a
      href={href}
      target="_blank"
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
function ProjectLinks({ links, name }: { links: NonNullable<Project["links"]>; name: string }) {
  return (
    <>
      {links.github !== undefined && (
        <IconLink
          href={links.github}
          label={`${name} on GitHub`}
          className="size-9 overflow-clip lg:size-[2.75rem]"
        >
          <span
            className="absolute inset-[0_0_2.47%_0]"
            style={{
              WebkitMaskImage: `url(${ICONS}/icon-github-mask.svg)`,
              maskImage: `url(${ICONS}/icon-github-mask.svg)`,
              WebkitMaskSize: "100% 100%",
              maskSize: "100% 100%",
              WebkitMaskRepeat: "no-repeat",
              maskRepeat: "no-repeat",
            }}
          >
            <img
              src={`${ICONS}/icon-github.svg`}
              alt=""
              className="block size-full max-w-none"
            />
          </span>
        </IconLink>
      )}
      {links.site !== undefined && (
        <IconLink
          href={links.site}
          label={`${name} website`}
          className="size-9 overflow-clip lg:size-[2.75rem]"
        >
          <span className="absolute inset-[10.94%_10.94%_17.19%_17.19%]">
            <span className="absolute inset-[-5.53%]">
              <img
                src={`${ICONS}/icon-external-link.svg`}
                alt=""
                className="block size-full max-w-none"
              />
            </span>
          </span>
        </IconLink>
      )}
      {links.youtube !== undefined && (
        <IconLink
          href={links.youtube}
          label={`${name} on YouTube`}
          className="h-9 w-[7.85rem] lg:h-[2.75rem] lg:w-[12.138rem]"
        >
          <img
            src={`${ICONS}/logo-youtube.svg`}
            alt=""
            className="block size-full max-w-none"
          />
        </IconLink>
      )}
    </>
  );
}

/** Space Apps / BASIS / NASA / mission badge — positions are the Figma offsets. */
function PartnerLogos() {
  return (
    <>
      {/* md+: exact Figma placement */}
      <div className="relative hidden h-[4.875rem] w-[33rem] shrink-0 lg:block">
        <Image
          src={`${ICONS}/logo-space-apps.webp`}
          alt="NASA Space Apps Challenge"
          width={440}
          height={172}
          className="absolute left-[0.1875rem] top-[0.5rem] h-[4.125rem] w-[10.5rem]"
        />
        <Image
          src={`${ICONS}/logo-basis.webp`}
          alt="BASIS"
          width={750}
          height={451}
          className="absolute left-[12.375rem] top-[1.125rem] h-[3.1875rem] w-[5.25rem] object-cover"
        />
        <Image
          src={`${ICONS}/logo-nasa.webp`}
          alt="NASA"
          width={720}
          height={312}
          className="absolute left-[17.9375rem] top-0 h-[4.875rem] w-[11.25rem] object-cover"
        />
        <img
          src={`${ICONS}/ring.svg`}
          alt=""
          className="absolute left-[29.5rem] top-[1.5rem] size-[2.9375rem] max-w-none"
        />
        <Image
          src={`${ICONS}/logo-badge.webp`}
          alt="Mission badge"
          width={160}
          height={160}
          className="absolute left-[30rem] top-[1.99rem] size-[1.96rem] object-cover"
        />
      </div>

      {/* mobile: simple wrapping row */}
      <div className="flex flex-wrap items-center gap-4 lg:hidden">
        <Image
          src={`${ICONS}/logo-space-apps.webp`}
          alt="NASA Space Apps Challenge"
          width={440}
          height={172}
          className="h-10 w-auto"
        />
        <Image
          src={`${ICONS}/logo-basis.webp`}
          alt="BASIS"
          width={750}
          height={451}
          className="h-9 w-auto"
        />
        <Image
          src={`${ICONS}/logo-nasa.webp`}
          alt="NASA"
          width={720}
          height={312}
          className="h-10 w-auto"
        />
        <Image
          src={`${ICONS}/logo-badge.webp`}
          alt="Mission badge"
          width={160}
          height={160}
          className="size-9"
        />
      </div>
    </>
  );
}

/* ── collapsed banner ─────────────────────────────────────────────────── */

function Banner({
  project,
  onOpen,
}: {
  project: Project;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-expanded={false}
      aria-controls={`project-${project.id}`}
      className="group relative block h-36 w-full text-left lg:h-[17.125rem]"
    >
      {/* blurred artwork, exported from Figma with 37.5px of blur bleed */}
      <div className="pointer-events-none absolute -inset-3 lg:inset-auto lg:left-[-2.344rem] lg:top-[-2.344rem] lg:h-[21.81rem] lg:w-[82.94rem]">
        <Image
          src={project.banner}
          alt=""
          fill
          sizes="(min-width: 768px) 84rem, 100vw"
          className="object-cover"
        />
      </div>

      <div className="relative flex h-full flex-col justify-center pl-5 lg:pl-[3.8125rem]">
        <h2 className="text-3xl font-semibold leading-tight lg:text-[4rem] lg:leading-[5.125rem]">
          {project.name}
        </h2>
        <p className="text-base font-semibold lg:text-[2.25rem] lg:leading-[2.875rem]">
          {project.year}
        </p>
      </div>

      <img
        src={`${ICONS}/chevron-down.svg`}
        alt=""
        aria-hidden
        className="absolute right-4 top-1/2 size-12 max-w-none -translate-y-1/2 transition-transform group-hover:scale-105 lg:right-[3.25rem] lg:size-[7.25rem]"
      />
      <span className="sr-only">Expand {project.name} details</span>
    </button>
  );
}

/* ── expanded panel ───────────────────────────────────────────────────── */

function Panel({
  project,
  onClose,
}: {
  project: Project;
  onClose: () => void;
}) {
  return (
    <section
      id={`project-${project.id}`}
      aria-labelledby={`project-${project.id}-title`}
      className="relative border-y-2 border-white bg-black px-5 py-8 lg:px-0 lg:py-0 lg:pb-[3.6875rem] lg:pl-[3.8125rem] lg:pr-[4.375rem] lg:pt-[4.4375rem]"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 flex-wrap items-center gap-x-[1.375rem] gap-y-2">
          <h2
            id={`project-${project.id}-title`}
            className="text-3xl font-semibold leading-tight lg:text-[4rem] lg:leading-[5.125rem]"
          >
            {project.name}
          </h2>
          {project.links && <ProjectLinks links={project.links} name={project.name} />}
        </div>
        <p className="shrink-0 text-lg font-semibold lg:text-[2.25rem] lg:leading-[2.875rem]">
          {project.year}
        </p>
      </div>

      <p className="mt-5 font-body text-base leading-snug text-justify lg:ml-[0.3125rem] lg:mt-[1.0625rem] lg:w-[69.6875rem] lg:text-[1.5rem] lg:leading-none">
        {/* TODO: copy for this project is not in the design yet */}
        {project.description ?? "More details coming soon."}
      </p>

      <div className="mt-6 flex items-center justify-between gap-4 lg:mt-[1.3125rem]">
        {project.partners ? <PartnerLogos /> : <span />}
        <button
          type="button"
          onClick={onClose}
          aria-label={`Collapse ${project.name}`}
          aria-expanded
          aria-controls={`project-${project.id}`}
          className="shrink-0 transition-opacity hover:opacity-80"
        >
          <img
            src={`${ICONS}/chevron-up.svg`}
            alt=""
            className="block size-12 max-w-none lg:size-[4.875rem]"
          />
        </button>
      </div>
    </section>
  );
}

/* ── list ─────────────────────────────────────────────────────────────── */

export default function ProjectList({ projects }: { projects: Project[] }) {
  // The Figma frame shows EdgeVenture expanded.
  const [openId, setOpenId] = useState<string | null>("edgeventure");

  return (
    <div className="flex flex-col gap-6 lg:gap-[5rem]">
      {projects.map((project) =>
        openId === project.id ? (
          <Panel key={project.id} project={project} onClose={() => setOpenId(null)} />
        ) : (
          <Banner key={project.id} project={project} onOpen={() => setOpenId(project.id)} />
        ),
      )}
    </div>
  );
}
