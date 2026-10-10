/** Run the backend export and openapi-typescript. Callers choose the output paths. */
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

import { backendDir, frontendDir } from "./contract-paths.ts";

// Surface a tool failure in the terminal. stdio is inherited so secrets in the environment are not printed.
function run(command: string[], cwd: string): void {
  const result = spawnSync(command[0], command.slice(1), { cwd, stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

// Ask the backend for its schema. The destination is the only file this writes.
export function exportOpenApi(destination: string): void {
  mkdirSync(path.dirname(destination), { recursive: true });
  // uv reads the backend lockfile. Export does not start a server or need a vendor key.
  run(
    ["uv", "run", "--directory", backendDir, "python", "-m", "scripts.export_openapi", destination],
    backendDir,
  );
}

// Turn one OpenAPI file into TypeScript. The destination is the only file this writes.
export function generateTypes(source: string, destination: string): void {
  mkdirSync(path.dirname(destination), { recursive: true });
  run(["bunx", "openapi-typescript", source, "-o", destination], frontendDir);
}
