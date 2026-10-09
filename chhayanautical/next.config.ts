import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for Firebase Hosting (output goes to ./out)
  output: "export",
  // The image optimizer needs a server; the assets are already compressed WebP.
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
