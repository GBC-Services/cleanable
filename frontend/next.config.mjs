/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // ── API Proxy (dev only — production uses reverse proxy) ──────────
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },

  // ── PWA Headers ──────────────────────────────────────────────────
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
      {
        source: "/manifest.json",
        headers: [
          { key: "Cache-Control", value: "public, max-age=3600" },
        ],
      },
      {
        // Security headers for all routes
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(self), microphone=(), geolocation=(self), payment=(self)",
          },
        ],
      },
    ];
  },

  // ── Image Optimization ───────────────────────────────────────────
  images: {
    // Serve modern formats (WebP/AVIF) automatically
    formats: ["image/avif", "image/webp"],
    // Responsive breakpoints matching Tailwind defaults
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    // External image domains (Cloudflare R2, Mapbox tiles)
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.r2.cloudflarestorage.com",
      },
      {
        protocol: "https",
        hostname: "api.mapbox.com",
      },
      {
        protocol: "https",
        hostname: "*.tiles.mapbox.com",
      },
    ],
    // Minimize layout shift
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },

  // ── Bundle Optimization ──────────────────────────────────────────
  experimental: {
    // Optimize package imports — tree-shake large libraries
    optimizePackageImports: [
      "lucide-react",
      "recharts",
      "zod",
      "zustand",
      "react-hook-form",
      "@hookform/resolvers",
      "mapbox-gl",
    ],
  },

  // ── Compiler Optimizations ───────────────────────────────────────
  compiler: {
    // Remove console.log in production (keep warn/error)
    removeConsole: process.env.NODE_ENV === "production"
      ? { exclude: ["error", "warn"] }
      : false,
  },

  // ── Output ───────────────────────────────────────────────────────
  // Standalone output for Docker deployment — bundles node_modules
  output: "standalone",

  // ── Webpack Customization ────────────────────────────────────────
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Split Mapbox GL into its own chunk (it's ~800KB)
      config.optimization.splitChunks = {
        ...config.optimization.splitChunks,
        cacheGroups: {
          ...config.optimization.splitChunks?.cacheGroups,
          mapbox: {
            test: /[\\/]node_modules[\\/](mapbox-gl|@mapbox)[\\/]/,
            name: "mapbox",
            chunks: "all",
            priority: 30,
          },
          charts: {
            test: /[\\/]node_modules[\\/](recharts|d3-[a-z]+)[\\/]/,
            name: "charts",
            chunks: "all",
            priority: 20,
          },
          stripe: {
            test: /[\\/]node_modules[\\/](@stripe)[\\/]/,
            name: "stripe",
            chunks: "all",
            priority: 20,
          },
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: "vendor",
            chunks: "all",
            priority: 10,
            reuseExistingChunk: true,
          },
        },
      };
    }

    return config;
  },

  // ── Power Header — preload critical resources ────────────────────
  poweredByHeader: false,
};

export default nextConfig;
