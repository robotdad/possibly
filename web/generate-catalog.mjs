import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { zodToJsonSchema } from "zod-to-json-schema";
import { catalog } from "./catalog.js";
// The pinned processor's inline exporter leaves dangling local refs when it wraps
// Zod schemas. Generate self-contained schemas and preserve A2UI's semantic refs.
function commonRefs(value) {
  if (!value || typeof value !== "object") return value;
  if (
    typeof value.description === "string" &&
    value.description.startsWith("REF:")
  ) {
    return {
      $ref: value.description
        .slice(4)
        .split("|")[0]
        .replace(
          "common_types.json",
          "https://a2ui.org/specification/v0_9/common_types.json",
        ),
    };
  }
  if (Array.isArray(value)) return value.map(commonRefs);
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, commonRefs(item)]),
  );
}
const components = {};
for (const [name, component] of catalog.components) {
  const raw = zodToJsonSchema(component.schema, {
    $refStrategy: "none",
    target: "jsonSchema7",
  });
  delete raw.$schema;
  delete raw.additionalProperties;
  raw.properties = { component: { const: name }, ...raw.properties };
  raw.required = ["component", ...(raw.required || [])];
  components[name] = {
    allOf: [
      {
        $ref: "https://a2ui.org/specification/v0_9/common_types.json#/$defs/ComponentCommon",
      },
      commonRefs(raw),
    ],
    unevaluatedProperties: false,
  };
}
const capabilities = {
  "v0.9.1": {
    supportedCatalogIds: [catalog.id],
    inlineCatalogs: [{ catalogId: catalog.id, components, functions: [] }],
  },
};
const schema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: catalog.id,
  catalogId: catalog.id,
  components,
  functions: [],
  $defs: {
    anyComponent: { oneOf: Object.values(components) },
    theme: { type: "object", additionalProperties: false },
  },
};
for (const [name, data] of [
  ["review-catalog.json", capabilities],
  ["review-schema.json", schema],
])
  await writeFile(
    fileURLToPath(new URL("../src/possibly/static/" + name, import.meta.url)),
    JSON.stringify(data, null, 2) + "\n",
  );
