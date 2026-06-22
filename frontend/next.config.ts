import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone is needed for Docker self-hosting; Vercel handles its own output
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
