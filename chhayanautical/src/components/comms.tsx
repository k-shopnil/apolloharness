"use client";

import Image from "next/image";

export default function Comms() {
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

      <div className="flex size-24 shrink-0 items-center justify-center lg:size-[9.614rem]">
        <div className="relative size-[77.19%] -rotate-[21.36deg] overflow-clip">
          <div className="absolute inset-[6.25%]">
            <div className="absolute inset-[-3.91%]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/shared/comms-icon.svg"
                alt=""
                className="block size-full max-w-none"
              />
            </div>
          </div>
        </div>
      </div>

      {/* TODO: wire the submit to the team inbox / form backend. */}
      <form
        className="flex w-full max-w-[28rem] flex-col gap-4 sm:flex-row sm:items-center lg:w-auto lg:max-w-none lg:gap-4"
        onSubmit={(e) => e.preventDefault()}
      >
        <label className="sr-only" htmlFor="comms-contact">
          Your email or phone number
        </label>
        <input
          id="comms-contact"
          name="contact"
          type="text"
          autoComplete="email"
          placeholder="Or let us contact you instead"
          className="h-[5.9375rem] min-h-16 w-full rounded-md bg-surface px-[1.88rem] text-lg leading-[0.8] text-white placeholder:text-muted lg:w-[15.625rem] lg:text-[1.5rem]"
        />
        <button
          type="submit"
          className="h-[4.5rem] min-h-14 shrink-0 rounded-md bg-white px-10 text-xl font-semibold text-black transition-opacity hover:opacity-80 lg:w-[8.875rem] lg:px-0 lg:text-[1.3125rem]"
        >
          Send
        </button>
      </form>
    </section>
  );
}
