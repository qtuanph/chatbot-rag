import type { NextConfig } from "next";
import path from "node:path";

const isDevelopment = process.env.NODE_ENV !== "production";
const workspaceRoot = path.resolve(process.cwd(), "..");

const nextConfig: NextConfig = {
  experimental: {
    useTypeScriptCli: true,
    optimizePackageImports: ["lucide-react", "recharts", "date-fns"],
  },
  env: {
    NEXT_PUBLIC_APP_VERSION:
      process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_TAG ||
      process.env.VERCEL_GIT_COMMIT_REF ||
      process.env.NEXT_PUBLIC_APP_VERSION ||
      "dev",
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ];
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
    root: workspaceRoot,
  },
};

export default nextConfig;
