import { Catalog, CommonSchemas as S } from "@a2ui/web_core/v0_9";
import { basicCatalog } from "@a2ui/lit/v0_9";
import { z } from "zod";

export const catalogId =
  "https://github.com/robotdad/possibly/catalogs/review-v1.json";
const component = (name, fields) => ({
  name,
  tagName: "possibly-" + name.toLowerCase(),
  schema: z.object(fields).strict(),
});
export const Layout = component("ReviewLayout", {
  children: S.ChildList,
  kind: z.enum([
    "stack",
    "actions",
    "tabs",
    "details",
    "panel",
    "overall",
    "card",
    "content",
    "grid",
    "workspace",
    "focused",
    "compare",
    "dialog",
  ]),
  label: z.string().optional(),
  expanded: z.boolean().optional(),
});
export const Input = component("ReviewInput", {
  label: S.DynamicString,
  value: S.DynamicString,
  disabled: z.boolean(),
  onChange: S.Action.optional(),
});
export const Tab = component("ReviewTab", {
  label: S.DynamicString,
  selected: z.boolean(),
  action: S.Action,
});
export const Picker = component("RevisionPicker", {
  label: z.string(),
  value: z.string(),
  options: z.array(z.object({ value: z.string(), label: z.string() })),
});
export const Preview = component("PrototypePreview", {
  revisionId: z.string(),
  title: z.string(),
  width: z.number().positive(),
  height: z.number().positive(),
  colorScheme: z.enum(["light", "dark"]),
  onExpand: S.Action,
});
export const Thumbnail = component("RevisionThumbnail", {
  revisionId: z.string(),
  title: z.string(),
  action: S.Action,
});
export const Text = {
  ...basicCatalog.components.get("Text"),
  tagName: "possibly-text",
};
// Deliberately small catalog: no remote media, arbitrary URLs, or executable extensions.
export const catalog = new Catalog(
  catalogId,
  [
    ...["Button", "Column", "Row", "Card"].map((name) =>
      basicCatalog.components.get(name),
    ),
    Text,
    Layout,
    Input,
    Tab,
    Picker,
    Preview,
    Thumbnail,
  ],
  [],
);
