export type CrewLinks = {
  github?: string;
  email?: string;
  linkedin?: string;
  instagram?: string;
};

export type CrewMember = {
  slug: string;
  name: string;
  role: string;
  bio: string;
  photo: string;
  /** Unset fields render as plain (non-link) glyphs. LinkedIn / Instagram / email are pending bulk injection. */
  links: CrewLinks;
};

export const crew: CrewMember[] = [
  {
    slug: "shopnil-karmakar",
    name: "Shopnil Karmakar",
    role: "Team, Product & AL/ML Lead",
    bio: "I am a Computer Science undergraduate working across artificial intelligence, product design, and embedded systems. My work focuses on building autonomous agent workflows and user experiences that translate complex data into intuitive tools. Having co-founded tech initiatives and conducted applied computational research, I enjoy leading multidisciplinary teams to ship reliable software. My goal is to build intelligent systems that connect hardware, software, and human interaction to solve real-world problems.",
    photo: "/images/crew/shopnil-karmakar.webp",
    links: {
      github: "https://github.com/k-shopnil",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
  {
    slug: "mehedi-hasan",
    name: "Md. Mehedi Hasan",
    role: "Sr. Data & AL/ML Engineer",
    bio: "I am an AI and machine learning researcher focused on computer vision, deep learning, and robust data engineering. My work involves designing data pipelines and human-in-the-loop systems that translate raw, complex datasets into dependable models. Having built applied solutions across computer vision and predictive analytics, I place a high focus on data integrity and algorithmic reliability. My goal is to develop practical machine learning systems that address demanding, mission-critical real-world challenges.",
    photo: "/images/crew/mehedi-hasan.webp",
    links: {
      github: "https://github.com/0mehedihasan",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
  {
    slug: "fahim-uddin",
    name: "A S M Fahim Uddin",
    role: "Frontend/Software Developer",
    bio: "I am a Computer Science undergraduate, software developer, and builder focused on creating responsive, high-performance web products. My technical work centers on frontend architecture, interactive 3D visualizations, and translating complex spatial data into intuitive interfaces. Driven by an entrepreneurial mindset, I have built and deployed practical applications from initial architecture to production. My ambition is to craft seamless digital experiences that make advanced data systems accessible and engaging.",
    photo: "/images/crew/fahim-uddin.webp",
    links: {
      github: "https://github.com/ASMFahim71",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
  {
    slug: "thirtha-karmakar",
    name: "Thirtha Karmakar",
    role: "Subject Matter Researcher",
    bio: "I am a physics and astronomy researcher specializing in gravitational-wave astrophysics and computational simulations. My work focuses on modeling compact binary mergers, generating scientific waveforms, and analyzing orbital dynamics for space missions. Alongside theoretical research, I build physics-based computing tools, ray-tracing simulations, and automated hardware setups. My ambition is to advance observational astrophysics and gravitational research through rigorous computational modeling and data analysis.",
    photo: "/images/crew/thirtha-karmakar.webp",
    links: {
      github: "https://github.com/Thirtha17",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
  {
    slug: "ariful-islam",
    name: "Md Ariful Islam",
    role: "Backend & DevOps Engineer",
    bio: "I am a software engineer and web developer with over three years of experience building scalable web applications. Currently completing my Computer Science degree with a focus on Artificial Intelligence, my work centers on the intersection of modern web architectures and intelligent systems. Having delivered dozens of full-stack client solutions and production services, I specialize in building resilient backends and clean APIs. My ambition is to develop fast, reliable platforms that power data-intensive applications.",
    photo: "/images/crew/ariful-islam.webp",
    links: {
      github: "https://github.com/ariful305",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
  {
    slug: "humayra-akter",
    name: "Humayra Akter",
    role: "Researcher & Presenter",
    bio: "I am an Electrical and Electronic Engineering student with a background in technical research, copywriting, and digital communication. Years of competitive debate helped me develop strong communication, presentation, and critical-thinking skills for explaining complex ideas. Alongside my engineering studies, I conduct research in machine learning and explore emerging technical applications. I enjoy combining technical analysis, clear storytelling, and collaborative teamwork to make complex projects accessible.",
    photo: "/images/crew/humayra-akter.webp",
    links: {},
  },
  {
    slug: "sadril-ether",
    name: "Sadril Hossain Ether",
    role: "Backend & MLOps Engineer",
    bio: "I am a Computer Science student passionate about software systems, practical problem-solving, and building dependable tools. My work centers on exploring backend logic, workflow automation, and structured software development through hands-on project builds. I enjoy breaking down complex engineering challenges and turning conceptual requirements into clean, functional code. My goal is to deepen my expertise across full-stack engineering and build scalable, user-focused software that solves meaningful problems.",
    photo: "/images/crew/sadril-ether.webp",
    links: {
      github: "https://github.com/Eetherr77",
      // linkedin: "", instagram: "", email: "" — inject when available
    },
  },
];
