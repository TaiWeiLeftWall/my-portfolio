import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const tool = path.resolve(here, "..");
const html = fs.readFileSync(path.join(tool, "cms.html"), "utf8");
const cmsPath = path.join(tool, "cms.js");

const scriptTags = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
const openingTag = (match) => match[0].slice(0, match[0].indexOf(">") + 1);
const externalScripts = scriptTags.filter((match) => /\bsrc\s*=/.test(openingTag(match)));
const inlineScripts = scriptTags.filter((match) => !/\bsrc\s*=/.test(openingTag(match)));

assert.equal(externalScripts.length, 1, "cms.html must load exactly one external script");
assert.equal(inlineScripts.length, 0, "cms.html must not contain inline JavaScript");
assert.match(
  openingTag(externalScripts[0]),
  /\bsrc=["']\/upload-tool\/cms\.js["']/,
  "cms.html must load /upload-tool/cms.js",
);
assert.match(openingTag(externalScripts[0]), /\bdefer\b/, "the CMS script must be deferred");
assert.ok(fs.existsSync(cmsPath), "upload-tool/cms.js must exist");

const source = fs.readFileSync(cmsPath, "utf8");
new vm.Script(source, { filename: "cms.js" });

assert.doesNotMatch(
  source,
  /R2_UPLOAD_URL|R2_BASE_URL|bulk-import-form|deleteFromR2|r2KeyFromUrl/,
  "browser code must not call R2 or the mutating GET import route directly",
);
assert.doesNotMatch(source, /(?:workers|r2)\.dev/i, "browser code must not contain an R2 host");
assert.doesNotMatch(source, /['"]\/api\/upload['"]/, "legacy split upload must not be used");
assert.match(source, /\/api\/photo-items\/upload/, "uploads must use the local multipart endpoint");
for (const field of ["image", "group_id", "category", "date"]) {
  assert.match(source, new RegExp(`\\.append\\(['"]${field}['"]`), `multipart upload must append ${field}`);
}
assert.match(source, /jpgName\s*=\s*[^;]+\+\s*['"]\.jpg['"]/, "compressed upload names must end in .jpg");
assert.match(source, /\.append\(['"]image['"],\s*blob,\s*jpgName\)/, "multipart image must use the .jpg name");
assert.match(source, /let\s+editorState\s*=\s*null/, "editor state must be explicit");
assert.match(source, /mode:\s*['"]create['"]/, "editor state must support create mode");
assert.match(source, /mode:\s*['"]edit['"]/, "editor state must support edit mode");
assert.match(source, /\bsaving\b/, "savePanel must guard duplicate submissions");
assert.match(source, /if\s*\(!editorState\s*\|\|\s*saving\)\s*return/, "savePanel must reject duplicate submissions");
assert.match(source, /state\.mode\s*===\s*['"]create['"]\s*\?\s*['"]POST['"]\s*:\s*['"]PUT['"]/, "savePanel must choose POST or PUT from editor state");
assert.match(source, /Promise\.all\s*\(/, "state and health must load concurrently");
assert.match(source, /\/api\/health/, "CMS must load health information");
assert.match(source, /status\s*=\s*['"]pending['"]/, "batch items must start pending");
assert.match(source, /status\s*=\s*['"]uploading['"]/, "batch items must expose uploading state");
assert.match(source, /status\s*=\s*['"]succeeded['"]/, "batch items must expose succeeded state");
assert.match(source, /status\s*=\s*['"]failed['"]/, "batch items must expose failed state");
assert.match(source, /retryFailedUploads/, "failed batch uploads must have a retry action");
assert.match(source, /status\s*!==\s*['"]succeeded['"]/, "succeeded batch items must be removed");
assert.match(source, /if\s*\(failed\s*===\s*0\)\s*closeBulkUpload\(\)/, "a failed batch must keep the modal open");
assert.match(source, /成功 ['"]?\s*\+\s*succeeded\s*\+\s*['"]?，失败 ['"]?\s*\+\s*failed/, "completion text must use exact success and failure counters");

console.log("CMS scripts: OK");
