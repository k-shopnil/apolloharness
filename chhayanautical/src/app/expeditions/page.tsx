import type { Metadata } from "next";
import ProjectList from "@/components/expeditions/project-list";
import { projects } from "@/data/projects";

export const metadata: Metadata = {
  title: "Expeditions — Chhayanautical",
  description: "Past projects and expeditions by Team Chhayanautical.",
};

export default function ExpeditionsPage() {
  return (
    <div className="mx-auto max-w-[90rem] px-4 py-10 lg:px-[5.875rem] lg:pb-[11rem] lg:pt-[4.0625rem]">
      <h1 className="sr-only">Expeditions</h1>
      <ProjectList projects={projects} />
    </div>
  );
}
