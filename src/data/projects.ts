export type ProjectLinks = {
  /** `null` = icon is shown (as in the design) but has no URL yet. */
  github?: string | null;
  site?: string | null;
  youtube?: string | null;
};

export type Project = {
  id: string;
  name: string;
  year: string;
  banner: string;
  links?: ProjectLinks;
  description?: string;
  /** Show the Space Apps / BASIS / NASA badges row. */
  partners?: boolean;
};

export const projects: Project[] = [
  {
    id: "stellerquest",
    name: "StellerQuest",
    year: "2024",
    banner: "/images/expeditions/banner-stellerquest.webp",
  },
  {
    id: "trashformer",
    name: "Trashformer",
    year: "2025",
    banner: "/images/expeditions/banner-trashformer.webp",
    links: { github: null, site: null, youtube: null },
    partners: true,
    // TODO: placeholder copy taken from the Figma frame — replace with the real write-up.
    description:
      "Contrary to popular belief, Lorem Ipsum is not simply random text. It has roots in a piece of classical Latin literature from 45 BC, making it over 2000 years old. Richard McClintock, a Latin professor at Hampden-Sydney College in Virginia, looked up one of the more obscure Latin words, consectetur, from a Lorem Ipsum passage, and going through the cites of the word in classical literature, discovered the undoubtable source. Lorem Ipsum comes from sections 1.10.32 and 1.10.33 of \"de Finibus Bonorum et Malorum\" (The Extremes of Good and Evil) by Cicero, written in 45 BC. This book is a treatise on the theory of ethics, very popular during the Renaissance. The first line of Lorem Ipsum, \"Lorem ipsum dolor sit amet..\", comes from a line in section 1.10.32. The first line of Lorem Ipsum, \"Lorem ipsum dolor sit amet..\", comes from a line in section 1.10.32.",
  },
  {
    id: "harnessapollo",
    name: "HarnessApollo",
    year: "2026",
    banner: "/images/expeditions/banner-harnessapollo.webp",
  },
];
