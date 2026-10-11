import type { MetadataRoute } from "next";

/** Install / "Add to Home Screen" metadata. Icons come from scripts/generate_icons.py. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Fantasy Football AI",
    short_name: "FF.AI",
    description: "Gameweek intelligence for Fantasy Premier League: transfers, captaincy, chips, live points and mini-leagues.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#04060d",
    theme_color: "#04060d",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
