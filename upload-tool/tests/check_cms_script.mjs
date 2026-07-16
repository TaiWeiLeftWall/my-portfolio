import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import assert from "node:assert/strict";
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

function functionSource(start, end) {
  const startIndex = html.indexOf(start);
  const endIndex = html.indexOf(end, startIndex);
  assert.notEqual(startIndex, -1, `missing ${start}`);
  assert.notEqual(endIndex, -1, `missing ${end}`);
  return html.slice(startIndex, endIndex);
}

const singleUploadSource = functionSource(
  "async function handleFileUpload(event)",
  "// ==================== Bulk Upload (R2) ====================",
);
const bulkUploadSource = functionSource(
  "async function doBulkUpload()",
  "function setupDragSort()",
);

async function runUnconfiguredUpload(source, name, config) {
  const apiMutations = [];
  const elements = new Map();
  const context = {
    ...config,
    currentGroupId: 1,
    S: { photoGroups: [{ id: 1, category: "portrait", date: "2026-07-16" }] },
    bulkFiles: [{ name: "test.jpg", date: "2026-07-16", file: {} }],
    bulkSelectedCat: "portrait",
    toast() {},
    loadData() {},
    compressImage: async () => ({}),
    FormData: class { append() {} },
    document: { getElementById: () => ({ textContent: "" }) },
    $(id) {
      if (!elements.has(id)) elements.set(id, { disabled: false, style: {} });
      return elements.get(id);
    },
    fetch: async (url) => {
      if (String(url).startsWith("/api/")) apiMutations.push(String(url));
      return { ok: false };
    },
  };
  context.window = {};
  Object.defineProperty(context.window, "location", {
    set(value) { apiMutations.push(String(value)); },
  });
  new vm.Script(`${source}\nthis.uploadUnderTest = ${name};`).runInNewContext(context);
  if (name === "handleFileUpload") {
    await context.uploadUnderTest({ target: { files: [{ name: "test.jpg", type: "image/jpeg" }] } });
  } else {
    await context.uploadUnderTest();
  }
  assert.deepEqual(apiMutations, [], `${name} mutated CMS state while R2 was unconfigured`);
}

for (const sourceAndName of [
  [singleUploadSource, "handleFileUpload"],
  [bulkUploadSource, "doBulkUpload"],
]) {
  await runUnconfiguredUpload(sourceAndName[0], sourceAndName[1], {
    R2_UPLOAD_URL: "",
    R2_BASE_URL: "https://configured.invalid",
  });
  await runUnconfiguredUpload(sourceAndName[0], sourceAndName[1], {
    R2_UPLOAD_URL: "https://configured.invalid/upload",
    R2_BASE_URL: "",
  });
}

assert.doesNotMatch(html, /r2-upload\.linweigh58\.workers\.dev/i);
assert.doesNotMatch(html, /(?:workers|r2)\.dev/i);

console.log("CMS scripts: OK");
