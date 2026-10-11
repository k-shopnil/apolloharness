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
  branding?: string;
  links?: ProjectLinks;
  description?: string;
  /** Show the Space Apps / BASIS / NASA badges row. */
  partners?: boolean;
};

export const projects: Project[] = [
  {
    id: "stellarquest",
    name: "StellarQuest",
    year: "2024",
    banner: "/images/expeditions/banner-stellerquest.webp",
    branding: "/images/expeditions/stellarquest-branding.svg",
    links: { github: null, site: null },
    partners: true,
    description:
      "StellarQuest is an interactive celestial navigation and star-mapping application designed for the NASA Space Apps Challenge (\"Exosky\" track). Produced by Chhayanautical, the app leverages NASA exoplanet datasets and astronomical APIs to reconstruct what the night sky looks like from distant worlds outside our solar system. Featuring a gamified, intuitive UI, StellarQuest allows users to search any known exoplanet to generate and explore real-time star charts and undiscovered constellations.",
  },
  {
    id: "edgeventure",
    name: "EdgeVenture",
    year: "2025",
    banner: "/images/expeditions/banner-trashformer.webp",
    branding: "/images/expeditions/edgeventure-branding.svg",
    links: { github: null, site: null },
    partners: true,
    description:
      "Addressing the Data Pathways to Healthy Cities and Human Settlements challenge, EdgeVenture is an AI-powered waste-sorting solution paired with a Flutter app that decodes edge-generated QR data to track local waste streams in real time. By correlating ground-level disposal metrics with NASA's open Earth observation datasets on air quality, water quality, surface temperature, and landfill accumulation, the platform demonstrates how intelligent waste segregation directly bolsters urban environmental health, turning everyday civic habits into vital data pathways for cleaner, more sustainable communities.",
  },
  {
    id: "harnessapollo",
    name: "HarnessApollo",
    year: "2026",
    banner: "/images/expeditions/banner-harnessapollo.webp",
    branding: "/images/expeditions/apollo-branding.svg",
    links: {
      github: "https://github.com/k-shopnil/apolloharness",
      site: "https://apolloharness.web.app",
      youtube: "https://nsac26.shopnilmax-16c.workers.dev/",
    },
    partners: true,
    description:
      "HarnessApollo is a next-generation lunar mission intelligence and surface analysis platform engineered for the NASA Space Apps Challenge (Commercial Lunar Payload Services track). Produced by Chhayanautical, the platform synthesizes NASA Planetary Data System (PDS) archives, lunar surface topography, and extreme polar environmental conditions into high-fidelity mission intelligence. Featuring an aerospace telemetry-inspired interface with interactive 3D lunar cartography, HarnessApollo enables mission planners and researchers to evaluate landing site viability, volatile deposits, and operational surface hazards.",
  },
];
