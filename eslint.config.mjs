import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  globalIgnores([
    ".next/**",
    ".venv/**",
    ".ruff_cache/**",
    "node_modules/**",
    ".web/**",
    "reflex.lock/**",
    "Chatly/**",
    "migrations/**",
    "tests/**",
    ".states/**",
  ]),
]);
