import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "frontend",
  plugins: [react()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-dom/client"],
          three: ["three"],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
