import type { NextConfig } from "next";

/**
 * The browser API client calls `/v1/...` on the same origin, so the web server
 * proxies those paths to the API. In local development and end-to-end runs the API
 * listens on `NEXT_API_URL` (default http://localhost:8000, matching the root dev
 * script's uvicorn process).
 */
const apiTarget = process.env.NEXT_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${apiTarget}/v1/:path*` },
      { source: "/healthz", destination: `${apiTarget}/healthz` },
    ];
  },
};

export default nextConfig;
