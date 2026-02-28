import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // for Docker / ECS (creates .next/standalone with server.js)
  // When behind ALB, use full URL for static assets to avoid chunk load errors
  assetPrefix: process.env.NEXT_PUBLIC_APP_URL || undefined,
};

export default nextConfig;
