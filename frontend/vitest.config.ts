import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["**/*.d.ts", "**/*.test.ts", "**/*.test.tsx"],
      reporter: ["text", "lcov", "cobertura", "json-summary"],
      reportsDirectory: "coverage",
      thresholds: {
        lines: 80,
        branches: 80,
        functions: 70,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
