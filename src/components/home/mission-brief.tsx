"use client";

import Image from "next/image";
import { useState } from "react";

interface MissionSlide {
  id: string;
  title: string;
  provider: string;
  story: string;
  image: string;
  alt: string;
  creditLabel: string;
  creditUrl: string;
}

const SLIDES: MissionSlide[] = [
  {
    id: "challenge",
    title: "The Challenge",
    provider: "Intuitive Machines — Nova-C \"Odysseus\"",
    story:
      "Missions to the Moon’s south pole face extreme lighting and communication constraints, and planning them takes careful coordination between science and engineering teams. Tools for determining Sun and Earth positions at candidate landing sites exist, but their complicated interfaces make it difficult to evaluate critical information with efficiency. Our challenge is to create an intuitive tool or application that lets mission planners, educators, and the public compare landing sites and dates quickly, visualizing Sun and Earth positions relative to the horizon to assess power generation potential and direct-to-Earth communication windows. The experience would make complex data easy to explore through clear timelines, accessible controls, and side-by-side comparisons, helping users identify favorable conditions and understand the trade-offs of each site.",
    image: "/images/home/mission-bg.png",
    alt: "Intuitive Machines Nova-C Odysseus lunar lander on the lunar surface",
    creditLabel: "Intuitive Machines",
    creditUrl: "https://twitter.com/Int_Machines/status/1762919217089720716/photo/1",
  },
  {
    id: "topographic-gauntlet",
    title: "The Topographic Gauntlet",
    provider: "Astrobotic Technology — Griffin Lander",
    story:
      "As robotic explorers advance toward high-relief landing zones like Mons Mouton and Nobile Crater, the terrain itself becomes the decisive factor in survival. At these polar extremes, elevation defines the boundary between life and mission failure: a ridge elevated just fifty meters can harvest weeks of low-grazing sunlight, while a crater basin plunges into permanent, sub-zero shadow. Heavy-class landers like Astrobotic’s Griffin cannot rely on static assumptions; they require real-time horizon modeling that charts how jagged crater peaks eclipse the Sun and sever direct lines of sight to Earth. By transforming raw ephemeris into clear visual horizons, mission teams can pinpoint the precise micro-windows where solar arrays stay energized and communication signals remain uninterrupted.",
    image: "/images/home/astrobotic-peregrine-pyld-ps-10.webp",
    alt: "Astrobotic Griffin lunar lander payload",
    creditLabel: "Astrobotic / NASA",
    creditUrl: "https://www.astrobotic.com/",
  },
  {
    id: "path-to-permanence",
    title: "The Path to Permanence",
    provider: "Firefly Aerospace — Blue Ghost Lander",
    story:
      "Mastering this astronomical geometry does more than safeguard individual touchdowns—it lays the groundwork for sustained lunar infrastructure. As scouts like Firefly Aerospace’s Blue Ghost touch down on the regolith, every hour of harvestable solar energy and every direct-to-Earth data link helps map the operational blueprint for future Artemis base camps and rover traverses. When the Sun dips beneath the horizon, surface temperatures crash by hundreds of degrees, testing batteries, materials, and electronics to their breaking point. By putting intuitive, comparative tools into the hands of planners and the public alike, we transform chaotic polar shadows into predictable, actionable routes—turning fleeting commercial landings into a continuous, enduring human presence on the Moon.",
    image: "/images/home/blue-ghost-first-image-1.webp",
    alt: "Firefly Aerospace Blue Ghost lunar lander on the regolith",
    creditLabel: "Firefly Aerospace / NASA",
    creditUrl: "https://fireflyspace.com/",
  },
];

/** Carousel geometry is expressed as % of the 399×317 Figma box so it scales. */
function Carousel({
  currentSlide,
  onPrev,
  onNext,
  onSelect,
}: {
  currentSlide: number;
  onPrev: () => void;
  onNext: () => void;
  onSelect: (index: number) => void;
}) {
  const slide = SLIDES[currentSlide];

  return (
    <div
      className="relative mx-auto aspect-[399/317] w-full max-w-[24.9375rem] shrink-0 lg:mx-0 lg:w-[24.9375rem]"
      role="region"
      aria-roledescription="carousel"
      aria-label="Mission imagery gallery"
    >
      <div className="absolute inset-y-0 left-[4.01%] w-[92.98%] overflow-clip bg-[#2f2f2f]">
        {currentSlide === 0 ? (
          <div className="absolute left-[-35.58%] top-[-70.84%] h-[170.97%] w-[153.1%] rotate-180">
            <Image
              src={slide.image}
              alt={slide.alt}
              fill
              sizes="(min-width: 768px) 30rem, 90vw"
              className="object-cover"
              priority
            />
          </div>
        ) : (
          <div className="relative size-full">
            <Image
              src={slide.image}
              alt={slide.alt}
              fill
              sizes="(min-width: 768px) 30rem, 90vw"
              className="object-cover"
              priority
            />
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onPrev}
        aria-label="Previous slide"
        className="absolute left-0 top-[44.8%] z-10 aspect-square w-[8.42%] cursor-pointer transition-opacity hover:opacity-80"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/home/chevron-left.svg"
          alt=""
          className="block size-full max-w-none -rotate-90 -scale-y-100"
        />
      </button>

      <button
        type="button"
        onClick={onNext}
        aria-label="Next slide"
        className="absolute left-[91.48%] top-[44.8%] z-10 aspect-square w-[8.54%] cursor-pointer transition-opacity hover:opacity-80"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/home/chevron-right.svg"
          alt=""
          className="block size-full max-w-none -rotate-90"
        />
      </button>

      {/* 3 Figma indicator dots positioned exactly at 17.4%, 43%, and 68.6% */}
      <div
        className="absolute left-[39.35%] top-[87.4%] z-10 h-[9.46%] w-[21.55%]"
        role="tablist"
        aria-label="Slide selectors"
      >
        {SLIDES.map((s, i) => {
          const leftPercent = i === 0 ? "17.4%" : i === 1 ? "43%" : "68.6%";
          const isActive = currentSlide === i;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-label={"Slide " + (i + 1) + ": " + s.title}
              onClick={() => onSelect(i)}
              className={
                "absolute top-[30%] size-[13.95%] cursor-pointer transition-all " +
                (isActive
                  ? "bg-white opacity-100 scale-110"
                  : "bg-white/50 opacity-60 hover:opacity-90")
              }
              style={{ left: leftPercent, aspectRatio: 1 }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function MissionBrief() {
  const [currentSlide, setCurrentSlide] = useState(0);

  const slide = SLIDES[currentSlide];

  const handlePrev = () => {
    setCurrentSlide((prev) => (prev - 1 + SLIDES.length) % SLIDES.length);
  };

  const handleNext = () => {
    setCurrentSlide((prev) => (prev + 1) % SLIDES.length);
  };

  return (
    <section
      aria-labelledby="mission-brief"
      className="relative w-full overflow-hidden bg-black py-16 sm:py-20 lg:py-24 xl:py-28"
    >
      {/* background photograph — vertically flipped at 28% opacity, stretches full viewport width flexibly */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/images/home/mission-bg.png"
        alt=""
        aria-hidden
        className="pointer-events-none absolute inset-0 size-full -scale-y-100 object-cover object-center opacity-[0.28]"
      />

      {/* Inner container with generous padding inward from backdrop edges */}
      <div className="relative mx-auto w-full max-w-[90rem] px-6 sm:px-12 md:px-16 lg:px-[8rem] xl:px-[10rem]">
        {/* Header row */}
        <div className="relative flex flex-wrap items-center justify-between gap-x-6 gap-y-4 pb-8 lg:flex-nowrap lg:pb-10">
          <h2
            id="mission-brief"
            className="text-3xl font-normal leading-[0.8] lg:text-[4rem]"
          >
            Mission Brief
          </h2>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/home/mission-line.svg"
            alt=""
            aria-hidden
            className="hidden h-[0.698rem] w-[35.54rem] shrink lg:block"
          />
          <div className="flex items-center gap-4 lg:w-[14.3125rem] lg:gap-6">
            <p className="whitespace-nowrap text-sm lg:text-[1.2366rem] lg:leading-[0.8]">
              5 min. read
            </p>
            {/* TODO: hook up narration audio */}
            <button
              type="button"
              className="flex h-10 w-[6.5625rem] items-center justify-center gap-[1.274px] bg-white text-sm font-semibold leading-[0.8] text-black lg:h-[2.625rem] lg:text-[1.2366rem]"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/home/play-fill.svg"
                alt=""
                aria-hidden
                className="size-6 lg:size-[1.672rem]"
              />
              Listen
            </button>
          </div>
        </div>

        {/* Content row */}
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between lg:gap-12 xl:gap-16">
          <div className="flex flex-col gap-3 lg:max-w-[46rem] lg:shrink xl:max-w-[50rem]">
            <p className="font-display text-sm uppercase tracking-wider text-white/60 sm:text-base">
              Part {currentSlide + 1} of 3 — {slide.title} ({slide.provider})
            </p>
            <p className="font-body text-base leading-relaxed text-justify transition-opacity duration-300 lg:text-[1.3rem] lg:leading-relaxed xl:text-[1.45rem]">
              {slide.story}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-center lg:items-end">
            <Carousel
              currentSlide={currentSlide}
              onPrev={handlePrev}
              onNext={handleNext}
              onSelect={setCurrentSlide}
            />
            <p className="mt-3.5 w-full text-right text-xs text-white/70 lg:text-[0.875rem] lg:leading-[1.2]">
              <b className="font-bold">Photo credit:</b>{" "}
              <a
                href={slide.creditUrl}
                target="_blank"
                rel="noreferrer"
                className="underline transition-colors hover:text-white"
              >
                {slide.creditLabel}
              </a>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
