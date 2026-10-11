import Image from "next/image";
import type { CrewMember } from "@/data/crew";
import ShareButton from "./share-button";
import SocialLinks from "./social-links";

/*
 * Figma card (415×553): avatar at x=131, text inset 20px, share icon floating
 * to the right of the avatar. md+ values are figma px / 16 (see globals.css).
 */
export default function CrewCard({ member }: { member: CrewMember }) {
  return (
    <article
      id={member.slug}
      className="mx-auto w-full max-w-[34rem] scroll-mt-32 lg:h-[34.555rem] lg:w-[25.9375rem] lg:max-w-none"
    >
      <div className="lg:ml-[8.1875rem] lg:w-[32rem]">
        <div className="relative mx-auto size-56 sm:size-64 lg:mx-0 lg:size-[19.095rem]">
          <Image
            src={member.photo}
            alt={member.name}
            width={306}
            height={306}
            sizes="(min-width: 768px) 20rem, 16rem"
            className="size-full rounded-full"
          />
          <ShareButton
            title={member.name}
            text={member.role}
            path={`/crew#${member.slug}`}
            slug={member.slug}
            className="absolute right-[-3.5rem] top-4 size-12 transition-opacity hover:opacity-70 max-sm:right-0 lg:left-[21.85rem] lg:right-auto lg:top-[5.375rem] lg:size-[6.4rem]"
          />
        </div>

        <div className="mt-6 lg:mt-[1.3125rem] lg:pl-[1.25rem]">
          <h2 className="text-3xl font-semibold leading-tight lg:text-[3.414rem] lg:leading-normal">
            {member.name}
          </h2>
          <p className="mt-1 text-lg font-semibold lg:mt-[0.28rem] lg:text-[1.707rem] lg:leading-normal">
            {member.role}
          </p>
          <p className="mt-3 font-body text-[0.9375rem] leading-snug text-justify lg:mt-[0.56rem] lg:w-[30.75rem] lg:text-[0.96rem] lg:leading-none">
            {member.bio}
          </p>
        </div>

        <div className="mt-5 lg:mt-[1rem] lg:pl-[1.2rem]">
          <SocialLinks links={member.links} name={member.name} />
        </div>
      </div>
    </article>
  );
}
