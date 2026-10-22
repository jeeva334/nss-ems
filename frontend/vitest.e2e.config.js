import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Full-stack E2E: the real React app (jsdom) -> real HTTP -> real FastAPI -> real PostgreSQL. No mocks.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost:5173" } },  // an origin the API's CORS list allows
    globals: true,
    setupFiles: "./src/setupTests.js",
    include: ["e2e/**/*.e2e.jsx"],
    testTimeout: 30000,
    hookTimeout: 30000,
    fileParallelism: false,
  },
});
