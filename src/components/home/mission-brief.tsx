import Image from "next/image";

const BRIEF =
  "Missions to the Moon’s south pole face extreme lighting and communication constraints, and planning them takes careful coordination between science and engineering teams. Tools for determining Sun and Earth positions at candidate landing sites exist, but their complicated interfaces make it difficult to evaluate critical information with efficiency. Your challenge is to create an intuitive tool or application that lets mission planners, educators, and the public compare landing sites and dates quickly, visualizing Sun and Earth positions relative to the horizon to assess power generation potential and direct-to-Earth communication windows. The experience should make complex data easy to explore through clear timelines, accessible controls, and side-by-side comparisons, helping users identify favorable conditions and understand the trade-offs of each site.";

/** Carousel geometry is expressed as % of the 399×317 Figma box so it scales. */
function Carousel() {
  return (
    <div
      className="relative mx-auto aspect-[399/317] w-full max-w-[24.9375rem] shrink-0 lg:mx-0 lg:w-[24.9375rem]"
      role="group"
      aria-roledescription="carousel"
      aria-label="Mission imagery"
    >
      <div className="absolute inset-y-0 left-[4.01%] w-[92.98%] overflow-clip bg-[#2f2f2f]">
        <div className="absolute left-[-35.58%] top-[-70.84%] h-[170.97%] w-[153.1%] rotate-180">
          <Image
            src="/images/home/mission-bg.png"
            alt="Intuitive Machines lander on the lunar surface"
            fill
            sizes="(min-width: 768px) 30rem, 90vw"
            className="object-cover"
          />
        </div>
      </div>

      {/* TODO: only one slide is exported from Figma — wire real slides here. */}
      <button
        type="button"
        aria-label="Previous slide"
        className="absolute left-0 top-[44.8%] aspect-square w-[8.42%]"
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
        aria-label="Next slide"
        className="absolute left-[91.48%] top-[44.8%] aspect-square w-[8.54%]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/home/chevron-right.svg"
          alt=""
          className="block size-full max-w-none -rotate-90"
        />
      </button>

      <div
        aria-hidden
        className="absolute left-[39.35%] top-[87.4%] h-[9.46%] w-[21.55%]"
      >
        <span className="absolute left-[17.4%] top-[30%] size-[13.95%] bg-white/50" style={{ aspectRatio: 1 }} />
        <span className="absolute left-[43%] top-[30%] size-[13.95%] bg-white" style={{ aspectRatio: 1 }} />
        <span className="absolute left-[68.6%] top-[30%] size-[13.95%] bg-white/50" style={{ aspectRatio: 1 }} />
      </div>
    </div>
  );
}

export default function MissionBrief() {
  return (
    <section
      aria-labelledby="mission-brief"
      className="relative w-full overflow-hidden bg-black px-4 pb-14 pt-12 lg:min-h-[36.0625rem] lg:px-0 lg:py-0"
    >
      {/* background photograph — vertically flipped at 28% opacity, stretches full viewport width flexibly */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/images/home/mission-bg.png"
        alt=""
        aria-hidden
        className="pointer-events-none absolute inset-0 size-full -scale-y-100 object-cover object-center opacity-[0.28]"
      />

      <div className="relative mx-auto w-full max-w-[90rem] px-4 sm:px-6 lg:px-[5.875rem]">
        {/* Header row */}
        <div className="relative flex flex-wrap items-center justify-between gap-x-6 gap-y-3 lg:h-[10.6875rem] lg:flex-nowrap lg:pb-[2.1875rem] lg:pt-[5.3125rem]">
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
        <div className="relative mt-8 flex flex-col gap-8 lg:mt-[1.518rem] lg:flex-row lg:items-start lg:justify-between lg:gap-12">
          <p className="font-body text-base leading-relaxed text-justify lg:max-w-[49.3125rem] lg:shrink lg:text-[1.35rem] lg:leading-relaxed xl:text-[1.5rem]">
            {BRIEF}
          </p>
          <div className="flex shrink-0 flex-col items-center lg:items-end">
            <Carousel />
            <p className="mt-3 w-full text-right text-xs text-white/70 lg:text-[0.875rem] lg:leading-[1.2]">
              <b className="font-bold">Photo credit:</b>{" "}
              <a
                href="https://twitter.com/Int_Machines/status/1762919217089720716/photo/1"
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                Intuitive Machines
              </a>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
