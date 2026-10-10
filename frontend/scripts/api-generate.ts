/** Write the committed OpenAPI document and the TypeScript generated from it. */
import { exportOpenApi, generateTypes } from "./contract-tools.ts";
import { openapiPath, schemaPath } from "./contract-paths.ts";

exportOpenApi(openapiPath);
generateTypes(openapiPath, schemaPath);
