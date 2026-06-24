import type { NextConfig } from "next";
import { execSync } from "child_process";

const isDevelopment = process.env.NODE_ENV !== "production";
const connectSrc = isDevelopment ? "'self' ws: http://localhost:* ws://localhost:*" : "'self'";

const getGitVersion = () => {
  try {
    return execSync("git describe --tags --always").toString().trim();
  } catch (e) {
    return "dev";
  }
};

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_APP_VERSION: getGitVersion(),
  },
  output: "standalone",
  productionBrowserSourceMaps: false,
  turbopack: {
    root: __dirname,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "geolocation=(), microphone=(), camera=(), payment=()",
          },
          { key: "X-DNS-Prefetch-Control", value: "on" },
          {
            key: "Content-Security-Policy",
            value:
              `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src ${connectSrc};`,
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
