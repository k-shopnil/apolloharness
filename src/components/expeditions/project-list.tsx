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
    <div className="flex items-center gap-2 sm:gap-3">
      {links.github !== undefined && (
        <IconLink
          href={links.github}
          label={`${name} on GitHub`}
          className="size-8 sm:size-9 overflow-clip lg:size-[2.75rem]"
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
          className="size-8 sm:size-9 overflow-clip lg:size-[2.75rem]"
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
          className="h-8 w-24 sm:h-9 sm:w-[7.85rem] lg:h-[2.75rem] lg:w-[12.138rem]"
        >
          <img
            src={`${ICONS}/logo-youtube.svg`}
            alt=""
            className="block size-full max-w-none object-contain"
          />
        </IconLink>
      )}
    </div>
  );
}

/** Space Apps / BASIS / NASA / mission badge / project branding */
function PartnerLogos({ project }: { project?: Project }) {
  return (
    <div className="flex max-w-full flex-wrap items-center gap-x-5 gap-y-3 sm:gap-x-6 sm:gap-y-4 lg:gap-x-8">
      {/* NASA Space Apps Challenge */}
      <div className="relative h-8 w-24 sm:h-10 sm:w-32 lg:h-[3.75rem] lg:w-[9.6rem] shrink-0">
        <Image
          src={`${ICONS}/logo-space-apps.webp`}
          alt="NASA Space Apps Challenge"
          fill
          className="object-contain object-left"
        />
      </div>
      {/* BASIS */}
      <div className="relative h-7 w-12 sm:h-8 sm:w-14 lg:h-[2.85rem] lg:w-[4.7rem] shrink-0">
        <Image
          src={`${ICONS}/logo-basis.webp`}
          alt="BASIS"
          fill
          className="object-contain"
        />
      </div>
      {/* NASA */}
      <div className="relative h-8 w-20 sm:h-10 sm:w-24 lg:h-[3.75rem] lg:w-[8.65rem] shrink-0">
        <Image
          src={`${ICONS}/logo-nasa.webp`}
          alt="NASA"
          fill
          className="object-contain"
        />
      </div>
      {/* Mission badge / self logo with ring */}
      <div className="relative flex size-9 shrink-0 items-center justify-center sm:size-10 lg:size-[3rem]">
        <img
          src={`${ICONS}/ring.svg`}
          alt=""
          className="size-full max-w-none"
        />
        <Image
          src={`${ICONS}/logo-badge.webp`}
          alt="Mission badge"
          width={160}
          height={160}
          className="absolute size-[68%] object-cover"
        />
      </div>
      {/* Project branding logo */}
      {project?.branding && (
        <div className="flex shrink-0 items-center pl-1 sm:pl-2">
          <img
            src={project.branding}
            alt={`${project.name} branding`}
            className="h-8 max-h-[2.25rem] w-auto max-w-[7.5rem] sm:h-9 sm:max-h-[2.75rem] sm:max-w-[9.5rem] lg:h-10 lg:max-h-[3rem] lg:max-w-[12rem] object-contain"
          />
        </div>
      )}
    </div>
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
      className="group relative block h-32 w-full overflow-hidden text-left sm:h-36 lg:h-[17.125rem]"
    >
      {/* blurred artwork background, properly contained within the button */}
      <div className="pointer-events-none absolute inset-0 size-full overflow-hidden">
        <Image
          src={project.banner}
          alt=""
          fill
          sizes="(min-width: 768px) 84rem, 100vw"
          className="object-cover"
        />
      </div>

      <div className="relative flex h-full flex-col justify-center pl-4 sm:pl-6 lg:pl-[3.8125rem]">
        <h2 className="text-2xl font-semibold leading-tight sm:text-3xl lg:text-[4rem] lg:leading-[5.125rem]">
          {project.name}
        </h2>
        <p className="text-base font-semibold sm:text-lg lg:text-[2.25rem] lg:leading-[2.875rem]">
          {project.year}
        </p>
      </div>

      <img
        src={`${ICONS}/chevron-down.svg`}
        alt=""
        aria-hidden
        className="absolute right-4 top-1/2 size-8 sm:size-10 lg:right-[3.25rem] lg:size-[6rem] max-w-none -translate-y-1/2 transition-transform group-hover:scale-105"
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
      className="relative w-full max-w-full overflow-hidden border-y-2 border-white bg-black px-4 py-6 sm:px-6 sm:py-8 lg:px-[3.8125rem] lg:pb-[3.6875rem] lg:pt-[4.4375rem]"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 sm:gap-x-6 lg:gap-x-[1.375rem]">
          <h2
            id={`project-${project.id}-title`}
            className="text-2xl font-semibold leading-tight sm:text-3xl lg:text-[4rem] lg:leading-[5.125rem]"
          >
            {project.name}
          </h2>
          {project.links && <ProjectLinks links={project.links} name={project.name} />}
        </div>
        <p className="shrink-0 text-lg font-semibold sm:text-xl lg:text-[2.25rem] lg:leading-[2.875rem]">
          {project.year}
        </p>
      </div>

      <p className="mt-5 w-full max-w-full font-body text-base leading-relaxed text-justify sm:text-lg lg:mt-[1.5rem] lg:max-w-[70rem] lg:text-[1.35rem] lg:leading-normal xl:text-[1.5rem]">
        {project.description ?? "More details coming soon."}
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-6 lg:mt-[2rem]">
        {project.partners ? <PartnerLogos project={project} /> : <span />}
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
            className="block size-8 sm:size-10 lg:size-[4.5rem] max-w-none"
          />
        </button>
      </div>
    </section>
  );
}

/* ── list ─────────────────────────────────────────────────────────────── */

export default function ProjectList({ projects }: { projects: Project[] }) {
  // Default to all projects collapsed.
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="flex w-full max-w-full flex-col gap-6 lg:gap-[5rem]">
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
