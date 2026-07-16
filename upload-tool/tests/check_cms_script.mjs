import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const tool = path.resolve(here, "..");
const html = fs.readFileSync(path.join(tool, "cms.html"), "utf8");
for (const [index, match] of [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].entries()) {
  new vm.Script(match[1], { filename: `cms-inline-${index}.js` });
}
const external = path.join(tool, "cms.js");
if (fs.existsSync(external)) {
  new vm.Script(fs.readFileSync(external, "utf8"), { filename: "cms.js" });
}
console.log("CMS scripts: OK");
