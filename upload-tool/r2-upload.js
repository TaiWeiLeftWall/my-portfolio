const ALLOWED_UPLOADS = new Map([
  ["image/jpeg", "jpg"],
  ["image/png", "png"],
  ["image/webp", "webp"],
]);
const ALLOWED_CATEGORIES = new Set([
  "portrait",
  "landscape",
  "street",
  "performance",
  "official",
]);
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;
const encoder = new TextEncoder();

function operationFor(pathname) {
  if (pathname === "/health") return "health";
  if (pathname === "/upload") return "upload";
  if (pathname === "/delete") return "delete";
  return "unknown";
}

function respond(context, status, payload, key = null, errorCode = null) {
  const entry = {
    requestId: context.requestId,
    operation: context.operation,
    status,
    key,
    errorCode,
  };
  if (status >= 500) {
    console.error(JSON.stringify(entry));
  } else {
    console.log(JSON.stringify(entry));
  }
  return Response.json(payload, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

function reject(context, status, error, message, key = null) {
  return respond(context, status, { ok: false, error, message }, key, error);
}

async function tokenMatches(request, expectedToken) {
  const authorization = request.headers.get("Authorization") || "";
  const match = /^Bearer (.+)$/.exec(authorization);
  const providedToken = match ? match[1] : "";
  const [providedDigest, expectedDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(providedToken)),
    crypto.subtle.digest("SHA-256", encoder.encode(expectedToken)),
  ]);
  return crypto.subtle.timingSafeEqual(providedDigest, expectedDigest);
}

function isRealDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function publicBaseUrl(value) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value) {
    return null;
  }
  try {
    const parsed = new URL(value);
    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash
    ) {
      return null;
    }
    return parsed.href.replace(/\/+$/, "");
  } catch {
    return null;
  }
}

async function upload(request, env, url, context) {
  if (!env.MY_BUCKET) {
    return reject(context, 503, "service_not_configured", "R2 bucket is not configured");
  }
  const baseUrl = publicBaseUrl(env.PUBLIC_BASE_URL);
  if (!baseUrl) {
    return reject(context, 503, "service_not_configured", "Public base URL is not configured");
  }

  const contentType = request.headers.get("Content-Type") || "";
  const extension = ALLOWED_UPLOADS.get(contentType);
  if (!extension) {
    return reject(context, 415, "unsupported_media_type", "Unsupported image type");
  }
  if (!request.body) {
    return reject(context, 400, "missing_body", "Image body is required");
  }

  const contentLength = request.headers.get("Content-Length");
  if (contentLength !== null) {
    if (!/^\d+$/.test(contentLength)) {
      return reject(context, 400, "invalid_content_length", "Content-Length is invalid");
    }
    const declaredBytes = Number(contentLength);
    if (declaredBytes === 0) {
      return reject(context, 400, "missing_body", "Image body is required");
    }
    if (declaredBytes > MAX_UPLOAD_BYTES) {
      return reject(context, 413, "payload_too_large", "Image exceeds the 15 MiB limit");
    }
  }

  const category = url.searchParams.get("category") || "";
  if (!ALLOWED_CATEGORIES.has(category)) {
    return reject(context, 400, "invalid_category", "Upload category is invalid");
  }
  const date = url.searchParams.get("date") || "";
  if (!isRealDate(date)) {
    return reject(context, 400, "invalid_date", "Upload date must be YYYY-MM-DD");
  }

  const key = `images/${category}/${date}/${crypto.randomUUID()}.${extension}`;
  try {
    await env.MY_BUCKET.put(key, request.body, {
      httpMetadata: { contentType },
    });
  } catch {
    return reject(context, 500, "internal_error", "Internal server error", key);
  }
  const encodedKey = key.split("/").map(encodeURIComponent).join("/");
  return respond(
    context,
    200,
    { ok: true, key, url: `${baseUrl}/${encodedKey}` },
    key,
  );
}

async function remove(request, env, context) {
  if (!env.MY_BUCKET) {
    return reject(context, 503, "service_not_configured", "R2 bucket is not configured");
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return reject(context, 400, "invalid_json", "Delete body must be valid JSON");
  }
  const key = payload && typeof payload === "object" ? payload.key : null;
  if (typeof key !== "string" || !key.startsWith("images/") || key.length <= 7) {
    return reject(context, 400, "invalid_key", "Delete key must use the images/ prefix");
  }

  try {
    await env.MY_BUCKET.delete(key);
  } catch {
    return reject(context, 500, "internal_error", "Internal server error", key);
  }
  return respond(context, 200, { ok: true, key }, key);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const context = {
      requestId: request.headers.get("cf-ray") || crypto.randomUUID(),
      operation: operationFor(url.pathname),
    };

    try {
      if (context.operation === "unknown") {
        return reject(context, 404, "not_found", "Not found");
      }
      if (typeof env.UPLOAD_TOKEN !== "string" || env.UPLOAD_TOKEN.length === 0) {
        return reject(
          context,
          503,
          "service_not_configured",
          "Worker upload token is not configured",
        );
      }
      if (!(await tokenMatches(request, env.UPLOAD_TOKEN))) {
        return reject(context, 401, "unauthorized", "Authentication failed");
      }

      if (url.pathname === "/health" && request.method === "GET") {
        return respond(context, 200, { ok: true, service: "r2" });
      }
      if (url.pathname === "/upload" && request.method === "POST") {
        return await upload(request, env, url, context);
      }
      if (url.pathname === "/delete" && request.method === "POST") {
        return await remove(request, env, context);
      }
      return reject(context, 405, "method_not_allowed", "Method not allowed");
    } catch {
      return reject(context, 500, "internal_error", "Internal server error");
    }
  },
};
