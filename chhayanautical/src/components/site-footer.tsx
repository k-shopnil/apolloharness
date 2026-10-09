import Image from "next/image";
import ScrollToTop from "./scroll-to-top";

export default function SiteFooter() {
  return (
    <footer className="flex items-end justify-center gap-2.5 overflow-hidden px-4 pt-16 lg:h-[34rem] lg:px-[3.75rem] lg:pt-0">
      <div className="relative min-w-0 flex-1 lg:h-[29.375rem] lg:w-[77.125rem] lg:flex-none">
        <p className="mb-6 text-xs tracking-[0.2em] lg:absolute lg:left-[1.94rem] lg:top-[-4.58rem] lg:mb-0 lg:text-[1.375rem] lg:leading-[0.8] lg:tracking-[0.21rem]">
          Copyright ©2026 TEAM Chhayanautical <b className="font-extrabold">·</b>{" "}
          Dhaka, Bangladesh
        </p>
        <p
          aria-hidden
          className="font-display text-[18vw] uppercase leading-[0.8] whitespace-nowrap lg:text-[18.353rem]"
        >
          Chhaya
          <br />
          Nautical.
        </p>
      </div>

      <div className="flex shrink-0 flex-col items-center gap-[5px] lg:h-[29.375rem]">
        <Image
          src="/images/shared/flag-bangladesh.svg"
          alt="Flag of Bangladesh"
          width={96}
          height={96}
          className="size-9 lg:size-[6rem]"
        />
        <ScrollToTop>
          <Image
            src="/images/shared/rocket.svg"
            alt=""
            width={96}
            height={96}
            className="size-9 lg:size-[6rem]"
          />
        </ScrollToTop>
      </div>
    </footer>
  );
}
