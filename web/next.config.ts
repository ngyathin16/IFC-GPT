import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack config (Next.js 16 default bundler)
  turbopack: {},
  // Webpack fallback — used when running with --webpack flag
  webpack: (config) => {
    // ThatOpen uses WASM — allow loading .wasm files
    config.experiments = { ...config.experiments, asyncWebAssembly: true };
    return config;
  },
};

export default nextConfig;
