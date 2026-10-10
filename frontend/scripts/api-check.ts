/**
 * Compare the committed contract artifacts with a fresh export.
 * This command never writes those committed files. A missing file or a mismatch exits nonzero.
 */
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { openapiPath, schemaPath } from "./contract-paths.ts";
import { exportOpenApi, generateTypes } from "./contract-tools.ts";

// Stop before any comparison writes a committed file. process.exit keeps the working tree as it was.
function fail(message: string): never {
  console.error(message);
  process.exit(1);
}

if (!existsSync(openapiPath) || !existsSync(schemaPath)) {
  fail("Committed API artifacts are missing. Run bun run api:generate. This check does not write them.");
}

const scratch = mkdtempSync(path.join(tmpdir(), "rounds-api-"));
const freshOpenapi = path.join(scratch, "openapi.json");
const freshSchema = path.join(scratch, "schema.ts");
let exitCode = 0;

try {
  exportOpenApi(freshOpenapi);
  if (!readFileSync(openapiPath).equals(readFileSync(freshOpenapi))) {
    console.error("openapi.json does not match the backend. Run bun run api:generate. The committed file was left unchanged.");
    exitCode = 1;
  } else {
    generateTypes(freshOpenapi, freshSchema);
    if (!readFileSync(schemaPath).equals(readFileSync(freshSchema))) {
      console.error("schema.ts does not match openapi.json. Run bun run api:generate. The committed file was left unchanged.");
      exitCode = 1;
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

process.exit(exitCode);
