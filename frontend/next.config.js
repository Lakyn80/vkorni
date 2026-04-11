/** @type {import('next').NextConfig} */
const apiProxyTarget = (process.env.API_PROXY_TARGET || "http://localhost:8020").replace(/\/+$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
      {
        source: "/static/:path*",
        destination: `${apiProxyTarget}/static/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
