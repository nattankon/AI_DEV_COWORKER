import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  base: "./",
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  server: {
    host: "127.0.0.1",
    port: 5273,
    strictPort: true,
    fs: {
      allow: [appRoot],
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4273,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        main: path.resolve(appRoot, "index.html"),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: [path.resolve(appRoot, "test/setup.js")],
    include: ["frontend/tests/**/*.test.{js,jsx}"],
    // jsdom cold-start on a loaded machine can push a menu-open interaction past
    // the 5s default and flake a different cell each run; the assertions
    // themselves are fast, so a generous ceiling only affects genuine hangs.
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});
