import type { NextConfig } from "next";

const isDevelopment = process.env.NODE_ENV !== "production";
const connectSrc = isDevelopment ? "'self' ws: http://localhost:* ws://localhost:*" : "'self'";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_APP_VERSION:
      process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_TAG ||
      process.env.VERCEL_GIT_COMMIT_REF ||
      process.env.NEXT_PUBLIC_APP_VERSION ||
      "dev",
  },
  output: "standalone",
  productionBrowserSourceMaps: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.icenter.ai" },
      { protocol: "https", hostname: "**.nvidia.com" },
      { protocol: "https", hostname: "placehold.co" },
    ],
  },
  skipTrailingSlashRedirect: true,
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
