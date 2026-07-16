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
assert.match(source, /if\s*\(!hasRemainingWork\)\s*closeBulkUpload\(\)/, "the modal may close only after all queue states are gone");
assert.match(source, /成功 ['"]?\s*\+\s*succeeded\s*\+\s*['"]?，失败 ['"]?\s*\+\s*failed/, "completion text must use exact success and failure counters");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function fakeElement() {
  const values = new Set();
  return {
    textContent: "",
    className: "",
    value: "",
    disabled: false,
    innerHTML: "",
    style: {},
    dataset: {},
    children: [],
    classList: {
      add(...names) { names.forEach((name) => values.add(name)); },
      remove(...names) { names.forEach((name) => values.delete(name)); },
      contains(name) { return values.has(name); },
    },
    appendChild(child) { this.children.push(child); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
  };
}

function createHarness() {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, fakeElement());
    return elements.get(id);
  };
  const panelInner = element("panel-inner");
  element("edit-panel").querySelector = (selector) => selector === ".panel-inner" ? panelInner : null;
  const objectUrls = [];
  const revokedUrls = [];
  let nextObjectUrl = 1;
  let nextOperationKey = 1;
  const document = {
    getElementById: element,
    querySelectorAll() { return []; },
    createElement(tag) {
      if (tag === "canvas" && this.canvasFactory) return this.canvasFactory();
      return fakeElement();
    },
    replaceElement(id, replacement = fakeElement()) {
      elements.set(id, replacement);
      return replacement;
    },
    canvasFactory: null,
  };
  class FakeFormData {
    constructor() { this.entries = []; }
    append(name, value, filename) { this.entries.push({ name, value, filename }); }
  }
  class IdleImage {}
  class IdleFileReader { readAsArrayBuffer() {} }
  const context = vm.createContext({
    Blob,
    DataView,
    Date,
    Error,
    FileReader: IdleFileReader,
    FormData: FakeFormData,
    Image: IdleImage,
    Math,
    Number,
    Promise,
    Set,
    String,
    URL: {
      createObjectURL(value) {
        const url = `blob:test-${nextObjectUrl++}`;
        objectUrls.push({ url, value });
        return url;
      },
      revokeObjectURL(url) { revokedUrls.push(url); },
    },
    clearTimeout() {},
    confirm: () => true,
    console,
    crypto: {
      randomUUID() {
        return `00000000-0000-4000-8000-${String(nextOperationKey++).padStart(12, "0")}`;
      },
    },
    document,
    fetch: async () => { throw new Error("unexpected fetch"); },
    queueMicrotask,
    setTimeout() { return 0; },
  });
  context.window = context;
  const withoutBootstrap = source.replace(/\r?\nloadData\(\);\s*$/, "");
  const exposure = `
globalThis.__cms = {
  createEditorState, editEditorState, openPanel, closePanel, savePanel,
  uploadPhotoBlob, handleBulkFiles, doBulkUpload, retryFailedUploads,
  compressImage, getExifDate, updateHealthStatus, renderBulkPreviews,
  getEditorState: () => editorState,
  getSaving: () => saving,
  getBulkFiles: () => bulkFiles,
  getBulkUploading: () => bulkUploading,
  setBulkFiles: (value) => { bulkFiles = value; },
  setBulkUploading: (value) => { bulkUploading = value; },
  setBulkGroups: (value) => { bulkGroups = value; },
  setBulkSelectedCat: (value) => { bulkSelectedCat = value; },
  setHealthState: (value) => { healthState = value; },
  setApi: (value) => { api = value; },
  setCompressImage: (value) => { compressImage = value; },
  setGetExifDate: (value) => { getExifDate = value; },
  setUploadPhotoBlob: (value) => { uploadPhotoBlob = value; },
  setLoadData: (value) => { loadData = value; },
  setToast: (value) => { toast = value; },
};`;
  new vm.Script(`${withoutBootstrap}\n${exposure}`, { filename: "cms-behavior.js" }).runInContext(context);
  return { cms: context.__cms, context, document, element, elements, objectUrls, revokedUrls, FakeFormData };
}

async function nextTurn() {
  await Promise.resolve();
  await Promise.resolve();
}

async function rejectsWithin(promise, pattern) {
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("timed out")), 50));
  await assert.rejects(Promise.race([promise, timeout]), pattern);
}

async function testSaveRequestOwnership() {
  const h = createHarness();
  for (const id of ["ef-title", "ef-desc", "ef-url", "ef-platform", "ef-source"]) h.element(id).value = "value";
  const oldButton = h.document.replaceElement("panel-save-btn");
  const request = deferred();
  let calls = 0;
  h.cms.setApi(async () => { calls++; return request.promise; });
  h.cms.setLoadData(async () => {});
  const oldState = h.cms.editEditorState("video", { id: 1 });
  h.cms.openPanel(oldState);
  const firstSave = h.cms.savePanel();
  h.cms.savePanel();
  await nextTurn();
  assert.equal(calls, 1, "savePanel must reject duplicate submissions");
  assert.equal(h.cms.getSaving(), true, "saving must remain true while the request is pending");
  assert.equal(oldButton.disabled, true, "the owning editor save button must be disabled");
  h.cms.closePanel();
  assert.equal(h.cms.getEditorState(), oldState, "user close must be rejected while saving");
  assert.equal(h.cms.getSaving(), true, "closePanel must not clear another request's saving guard");

  const newState = h.cms.editEditorState("video", { id: 2 });
  h.cms.openPanel(newState);
  const newButton = h.document.replaceElement("panel-save-btn");
  request.resolve({ ok: true });
  await firstSave;
  assert.equal(h.cms.getEditorState(), newState, "an old save response must not close a newer editor");
  assert.equal(newButton.disabled, false, "an old save response must not toggle a newer editor's button");
  assert.equal(h.cms.getSaving(), false, "only the owning request may settle saving");

  const failed = createHarness();
  for (const id of ["ef-title", "ef-desc", "ef-url", "ef-platform", "ef-source"]) failed.element(id).value = "value";
  const failedRequest = deferred();
  const failureMessages = [];
  failed.cms.setApi(async () => failedRequest.promise);
  failed.cms.setLoadData(async () => {});
  failed.cms.setToast((message, isError) => failureMessages.push({ message, isError }));
  failed.cms.openPanel(failed.cms.editEditorState("video", { id: 3 }));
  const failedSave = failed.cms.savePanel();
  const laterState = failed.cms.editEditorState("video", { id: 4 });
  failed.cms.openPanel(laterState);
  const laterButton = failed.document.replaceElement("panel-save-btn");
  failedRequest.reject(new Error("old request failed"));
  await failedSave;
  assert.equal(failed.cms.getEditorState(), laterState, "an old failure must not close a newer editor");
  assert.equal(laterButton.disabled, false, "an old failure must not toggle a newer editor's button");
  assert.deepEqual(failureMessages, [], "an old failure must not display an error in a newer editor");
}

async function testMultipartContract() {
  const h = createHarness();
  let request;
  h.cms.setApi(async (url, options) => { request = { url, options }; return { ok: true }; });
  const blob = new Blob(["image"], { type: "image/jpeg" });
  const operationKey = "multipart-operation-key-000000001";
  await h.cms.uploadPhotoBlob(
    blob,
    "camera.png",
    { id: 7, category: "portrait" },
    "2026-07-16",
    operationKey,
  );
  assert.equal(request.url, "/api/photo-items/upload");
  assert.equal(request.options.method, "POST");
  assert.equal(request.options.headers["Idempotency-Key"], operationKey);
  assert.deepEqual(request.options.body.entries.map((entry) => entry.name), ["image", "group_id", "category", "date"]);
  assert.equal(request.options.body.entries.length, 4, "multipart requests must contain exactly four fields");
  assert.match(request.options.body.entries[0].filename, /\.jpg$/);
  assert.equal(request.options.body.entries[0].filename, "camera.jpg");
}

async function testBulkRetriesReuseOperationKeys() {
  const h = createHarness();
  h.element("bulk-modal").classList.add("active");
  h.cms.setBulkFiles([
    { file: {}, name: "retry.jpg", date: "2026-07-16", status: "pending", error: "", previewUrl: "blob:retry" },
  ]);
  h.cms.setCompressImage(async () => new Blob(["ok"], { type: "image/jpeg" }));
  h.cms.setLoadData(async () => {});
  h.cms.setToast(() => {});
  const groupKeys = [];
  let groupAttempts = 0;
  h.cms.setApi(async (url, options) => {
    if (url !== "/api/photo-groups") throw new Error(`unexpected ${url}`);
    groupKeys.push(options.headers["Idempotency-Key"]);
    groupAttempts++;
    if (groupAttempts === 1) throw new Error("lost group response");
    return { ok: true, id: 41 };
  });
  const uploadKeys = [];
  let uploadAttempts = 0;
  h.cms.setUploadPhotoBlob(async (_blob, _name, _group, _date, operationKey) => {
    uploadKeys.push(operationKey);
    uploadAttempts++;
    if (uploadAttempts === 1) throw new Error("lost upload response");
    return { ok: true, id: 51 };
  });

  await h.cms.doBulkUpload();
  await h.cms.retryFailedUploads();
  await h.cms.retryFailedUploads();

  assert.equal(groupKeys.length, 2);
  assert.equal(groupKeys[0], groupKeys[1], "group response-loss retry must reuse its operation key");
  assert.match(groupKeys[0], /^[A-Za-z0-9_-]{32,128}$/);
  assert.equal(uploadKeys.length, 2);
  assert.equal(uploadKeys[0], uploadKeys[1], "image response-loss retry must reuse its operation key");
  assert.notEqual(uploadKeys[0], groupKeys[0], "group and image operations need distinct keys");
}

async function testBulkInputGuardAndSnapshotRetention() {
  const h = createHarness();
  h.element("bulk-modal").classList.add("active");
  const original = { file: {}, name: "old.jpg", date: "2026-07-16", status: "pending", error: "", previewUrl: "blob:old" };
  h.cms.setBulkFiles([original]);
  h.cms.setBulkGroups({ "2026-07": { id: 9, category: "portrait", date: "2026-07" } });
  h.cms.setGetExifDate(async () => null);
  const upload = deferred();
  h.cms.setCompressImage(async () => new Blob(["ok"], { type: "image/jpeg" }));
  h.cms.setUploadPhotoBlob(async () => upload.promise);
  h.cms.setLoadData(async () => {});
  const running = h.cms.doBulkUpload();
  await nextTurn();
  assert.equal(h.cms.getBulkUploading(), true);
  assert.equal(h.element("bulk-file-input").disabled, true, "file input must be disabled while uploading");
  assert.equal(h.element("bulk-drop").classList.contains("disabled"), true, "drop zone must be disabled while uploading");
  const before = h.cms.getBulkFiles().length;
  await h.cms.handleBulkFiles([{ name: "late.jpg", type: "image/jpeg", lastModified: Date.now() }]);
  assert.equal(h.cms.getBulkFiles().length, before, "handleBulkFiles must reject files while uploading");

  const late = { file: {}, name: "race.jpg", date: "2026-07-17", status: "pending", error: "", previewUrl: "blob:race" };
  h.cms.setBulkFiles([...h.cms.getBulkFiles(), late]);
  upload.resolve({ ok: true });
  await running;
  assert.equal(h.element("bulk-modal").classList.contains("active"), true, "pending work added after the snapshot must keep the modal open");
  assert.equal(h.cms.getBulkFiles().length, 1, "pending work added after the snapshot must not be discarded");
  assert.equal(h.cms.getBulkFiles()[0].name, "race.jpg");
  assert.equal(h.element("bulk-file-input").disabled, false, "file input must be restored after upload settles");
}

async function testBulkFailureRetryAndCounts() {
  const h = createHarness();
  h.element("bulk-modal").classList.add("active");
  h.cms.setBulkFiles([
    { file: {}, name: "one.jpg", date: "2026-07-16", status: "pending", error: "", previewUrl: "blob:one" },
    { file: {}, name: "two.jpg", date: "2026-07-17", status: "pending", error: "", previewUrl: "blob:two" },
  ]);
  h.cms.setApi(async (url) => url === "/api/photo-groups" ? { id: 21 } : { ok: true });
  h.cms.setCompressImage(async () => new Blob(["ok"], { type: "image/jpeg" }));
  h.cms.setLoadData(async () => {});
  const messages = [];
  h.cms.setToast((message, isError) => messages.push({ message, isError }));
  let uploads = 0;
  h.cms.setUploadPhotoBlob(async () => {
    uploads++;
    if (uploads === 2) throw new Error("server rejected two.jpg");
    return { ok: true };
  });
  await h.cms.doBulkUpload();
  assert.equal(h.cms.getBulkFiles().length, 1, "successful batch items must be removed");
  assert.equal(h.cms.getBulkFiles()[0].status, "failed");
  assert.equal(h.cms.getBulkFiles()[0].error, "server rejected two.jpg");
  assert.equal(h.element("bulk-modal").classList.contains("active"), true, "a failure must keep the modal open");
  assert.equal(h.element("bulk-label").textContent, "上传完成：成功 1，失败 1");
  assert.deepEqual(messages.at(-1), { message: "上传完成：成功 1，失败 1", isError: true });
  assert.equal(h.element("bulk-retry-btn").style.display, "", "failed items must expose retry");

  h.cms.setUploadPhotoBlob(async () => ({ ok: true }));
  await h.cms.retryFailedUploads();
  assert.equal(h.cms.getBulkFiles().length, 0);
  assert.equal(h.element("bulk-modal").classList.contains("active"), false, "the modal may close after all queue states are gone");
  assert.deepEqual(messages.at(-1), { message: "上传完成：成功 1，失败 0", isError: false });
}

async function testMalformedImageCleanup() {
  const broken = createHarness();
  broken.context.Image = class {
    set src(value) { queueMicrotask(() => this.onerror?.(new Error(`cannot decode ${value}`))); }
  };
  await rejectsWithin(broken.cms.compressImage({}), /decode|image/i);
  assert.equal(broken.objectUrls.length, 1);
  assert.deepEqual(broken.revokedUrls, [broken.objectUrls[0].url], "failed image decode must revoke its object URL");

  const success = createHarness();
  success.document.canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({ drawImage() {} }),
    toBlob(callback) { callback(new Blob(["x"], { type: "image/jpeg" })); },
  });
  success.context.Image = class {
    constructor() { this.width = 10; this.height = 10; }
    set src(_) { queueMicrotask(() => this.onload()); }
  };
  await success.cms.compressImage({});
  assert.deepEqual(success.revokedUrls, [success.objectUrls[0].url], "successful compression must revoke its object URL");

  const malformedExif = createHarness();
  malformedExif.context.FileReader = class {
    readAsArrayBuffer() { this.onload({ target: { result: new ArrayBuffer(1) } }); }
  };
  const file = { slice: () => ({}) };
  assert.equal(await malformedExif.cms.getExifDate(file), null, "truncated EXIF data must settle safely");

  const failedReader = createHarness();
  failedReader.context.FileReader = class {
    readAsArrayBuffer() { this.onerror(new Error("read failed")); }
  };
  assert.equal(await failedReader.cms.getExifDate(file), null, "FileReader errors must settle safely");

  const malformedQueue = createHarness();
  malformedQueue.element("bulk-modal").classList.add("active");
  malformedQueue.cms.setBulkFiles([
    { file: {}, name: "broken.jpg", date: "2026-07-16", status: "pending", error: "", previewUrl: "blob:broken" },
  ]);
  malformedQueue.cms.setBulkGroups({ "2026-07": { id: 31, category: "portrait", date: "2026-07" } });
  malformedQueue.cms.setCompressImage(async () => { throw new Error("image decode failed"); });
  malformedQueue.cms.setLoadData(async () => {});
  await malformedQueue.cms.doBulkUpload();
  assert.equal(malformedQueue.cms.getBulkUploading(), false, "malformed images must not leave bulk upload pending");
  assert.equal(malformedQueue.cms.getBulkFiles()[0].status, "failed");
  assert.equal(malformedQueue.element("bulk-modal").classList.contains("active"), true);
  assert.equal(malformedQueue.element("bulk-file-input").disabled, false);
}

async function testHealthDomContract() {
  const h = createHarness();
  h.cms.setHealthState({
    database: true,
    r2: { configured: true, reachable: false },
    orphan_photo_items: 2,
    orphan_commercial_items: 3,
  });
  h.cms.updateHealthStatus();
  assert.equal(h.element("health-status").textContent, "数据库：正常 · R2：不可访问 · 孤儿：5");
  assert.equal(h.element("health-status").className, "health-status error");
  h.cms.setHealthState({
    database: true,
    r2: { configured: false, reachable: false },
    orphan_photo_items: 0,
    orphan_commercial_items: 0,
  });
  h.cms.updateHealthStatus();
  assert.equal(h.element("health-status").textContent, "数据库：正常 · R2：未配置 · 孤儿：0");
  assert.equal(h.element("health-status").className, "health-status");
}

await testSaveRequestOwnership();
await testMultipartContract();
await testBulkRetriesReuseOperationKeys();
await testBulkInputGuardAndSnapshotRetention();
await testBulkFailureRetryAndCounts();
await testMalformedImageCleanup();
await testHealthDomContract();

console.log("CMS scripts: OK");
