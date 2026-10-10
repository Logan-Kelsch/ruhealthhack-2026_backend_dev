/** Paths for the two committed contract artifacts. Both commands use this so check and generate cannot drift apart. */
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));

// frontend/scripts -> frontend -> repo root.
export const frontendDir = path.resolve(scriptsDir, "..");
export const repoRoot = path.resolve(frontendDir, "..");
export const backendDir = path.join(repoRoot, "backend");

export const openapiPath = path.join(frontendDir, "src", "api", "openapi.json");
export const schemaPath = path.join(frontendDir, "src", "api", "schema.ts");
