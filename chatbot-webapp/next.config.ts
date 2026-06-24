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
};

export default nextConfig;
