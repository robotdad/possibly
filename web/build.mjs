import { build } from "esbuild";
import {
  writeFile,
  readFile,
  readdir,
  mkdir,
  copyFile,
} from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
process.chdir(fileURLToPath(new URL("..", import.meta.url)));
await import("./generate-catalog.mjs");
await build({
  absWorkingDir: process.cwd(),
  entryPoints: ["web/review.js"],
  outfile: "src/possibly/static/review.js",
  bundle: true,
  format: "esm",
  minify: true,
  loader: { ".css": "text" },
  legalComments: "linked",
  metafile: true,
}).then(async (result) => {
  const packages = new Map();
  for (const input of Object.keys(result.metafile.inputs)) {
    if (!input.includes("node_modules/")) continue;
    let dir = dirname(input);
    while (dir.includes("node_modules")) {
      try {
        const info = JSON.parse(
          await readFile(join(dir, "package.json"), "utf8"),
        );
        if (info.name && info.version) {
          packages.set(info.name, { dir, info });
          break;
        }
      } catch {}
      dir = dirname(dir);
    }
  }
  const notices = [];
  for (const [name, { dir, info }] of [...packages].sort()) {
    const licenses = (await readdir(dir)).filter((file) =>
      /^(licen[sc]e|notice|copying)([.-]|$)/i.test(file),
    );
    notices.push(
      name +
        " " +
        info.version +
        " — " +
        info.license +
        "\n" +
        (
          await Promise.all(
            licenses.map((file) => readFile(join(dir, file), "utf8")),
          )
        ).join("\n"),
    );
    if (!licenses.length) throw Error("Missing license text for " + name);
  }
  await writeFile(
    "src/possibly/static/THIRD_PARTY_NOTICES.txt",
    notices.join("\n\n--------------------\n\n"),
  );
  await writeFile(
    "src/possibly/static/build.json",
    JSON.stringify(
      {
        entry: "web/review.js",
        dependencies: {
          "@a2ui/lit": "0.10.3",
          "@a2ui/web_core": "0.10.7",
          lit: "3.3.3",
        },
        bytes: result.metafile.outputs["src/possibly/static/review.js"].bytes,
      },
      null,
      2,
    ) + "\n",
  );
});

// The same built renderer serves Python hosts and portable frontend consumers.
await mkdir("web/dist", { recursive: true });
for (const name of [
  "review.js",
  "review.js.LEGAL.txt",
  "THIRD_PARTY_NOTICES.txt",
  "build.json",
  "review-catalog.json",
]) {
  await copyFile("src/possibly/static/" + name, "web/dist/" + name);
}

await copyFile("web/review.d.ts", "web/dist/review.d.ts");
