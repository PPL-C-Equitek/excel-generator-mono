import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx", "tests/**/*.spec.ts", "tests/**/*.spec.tsx"],
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "**/*.d.ts",
        "tests/**",
        // Pure TypeScript interface — compile-time only, tidak ada JS runtime yang bisa diukur
        "src/lib/ILLMService.ts",
      ],
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
