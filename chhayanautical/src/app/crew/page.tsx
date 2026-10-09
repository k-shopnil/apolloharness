import type { Metadata } from "next";
import CrewCard from "@/components/crew/crew-card";
import { crew } from "@/data/crew";

export const metadata: Metadata = {
  title: "Crew — Chhayanautical",
  description: "Meet the Chhayanautical crew.",
};

export default function CrewPage() {
  return (
    <div className="mx-auto max-w-[90rem] px-4 py-10 lg:p-0">
      <h1 className="sr-only">Crew</h1>
      <div className="flex flex-col gap-14 lg:grid lg:grid-cols-2 lg:gap-0 lg:pr-[17.9375rem] lg:[grid-auto-rows:43.41rem]">
        {crew.map((member) => (
          <CrewCard key={member.slug} member={member} />
        ))}
      </div>
    </div>
  );
}
