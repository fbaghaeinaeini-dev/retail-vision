import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    open: true,
    proxy: {
      "/api": {
        target: "http://localhost:8100",
        changeOrigin: true,
        // SSE: prevent proxy from buffering streamed responses
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
              // Disable compression so events flush immediately
              proxyRes.headers["cache-control"] = "no-cache, no-transform";
              delete proxyRes.headers["content-encoding"];
              delete proxyRes.headers["content-length"];
            }
          });
        },
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three", "@react-three/fiber", "@react-three/drei"],
          charts: ["recharts", "d3-sankey", "d3-shape", "d3-scale", "d3-array"],
        },
      },
    },
  },
});
