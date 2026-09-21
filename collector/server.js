"use strict";

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const port = Number(process.env.PORT || 8099);
const dataDir = process.env.DATA_DIR || path.join(process.cwd(), "data");
const eventFile = path.join(dataDir, "events.ndjson");
const artifactFile = path.join(dataDir, "artifacts.ndjson");
const artifactDir = path.join(dataDir, "artifacts");
const maxBodyBytes = 8 * 1024 * 1024;
const maxArtifactBytes = 16 * 1024 * 1024;
const ring = [];
const ringLimit = 2000;
const artifacts = [];
const artifactLimit = 500;
let received = 0;
let rejected = 0;
let artifactsReceived = 0;

fs.mkdirSync(dataDir, { recursive: true });
fs.mkdirSync(artifactDir, { recursive: true });

function redact(value, key = "") {
  if (/(?:token|secret|password|signature|authorization|cookie|otp)/i.test(key)) {
    return "<redacted>";
  }
  if (Array.isArray(value)) return value.map((item) => redact(item, key));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [childKey, redact(childValue, childKey)]));
  }
  if (typeof value === "string") {
    return value
      .replace(/([?&](?:otp|token|signature|password|secret|authorization|cookie)=)[^&\s]*/gi, "$1<redacted>")
      .replace(/(Bearer\s+)[^\s]+/gi, "$1<redacted>");
  }
  return value;
}

function parseEvents(body, contentType) {
  const text = body.toString("utf8").trim();
  if (!text) return [];
  if (contentType.includes("application/json")) {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : [parsed];
  }
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

function appendEvents(events, request) {
  const ingestedAt = new Date().toISOString();
  const remote = request.socket.remoteAddress || "unknown";
  const normalized = events.map((event) => {
    const safe = redact(event);
    const result = {
      schema: "blustone.instrumented.event.v1",
      ingest_id: crypto.randomUUID(),
      ingested_at: ingestedAt,
      remote,
      ...safe,
    };
    ring.push(result);
    if (ring.length > ringLimit) ring.splice(0, ring.length - ringLimit);
    return result;
  });
  if (normalized.length) {
    fs.appendFileSync(eventFile, normalized.map((event) => JSON.stringify(event)).join("\n") + "\n", "utf8");
    received += normalized.length;
  }
  return normalized;
}

function sendJson(response, status, value) {
  const body = JSON.stringify(value);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
  });
  response.end(body);
}

function safeArtifactName(value) {
  const decoded = decodeURIComponent(String(value || "artifact.bin"));
  const normalized = decoded.replace(/[\\/]+/g, "__").replace(/[^A-Za-z0-9._-]/g, "_");
  return normalized || "artifact.bin";
}

function appendArtifact(body, request, url) {
  const session = String(request.headers["x-blustone-session"] || "unknown-session").replace(/[^A-Za-z0-9._-]/g, "_");
  const name = safeArtifactName(request.headers["x-blustone-artifact-name"] || url.searchParams.get("name"));
  const sessionDir = path.join(artifactDir, session);
  fs.mkdirSync(sessionDir, { recursive: true });
  const filePath = path.join(sessionDir, name);
  fs.writeFileSync(filePath, body);
  const metadata = {
    schema: "blustone.instrumented.artifact.v1",
    ingested_at: new Date().toISOString(),
    remote: request.socket.remoteAddress || "unknown",
    session_id: session,
    package: String(request.headers["x-blustone-package"] || "unknown"),
    name,
    bytes: body.length,
    sha256: String(request.headers["x-blustone-sha256"] || crypto.createHash("sha256").update(body).digest("hex")),
    path: filePath,
  };
  artifacts.push(metadata);
  if (artifacts.length > artifactLimit) artifacts.splice(0, artifacts.length - artifactLimit);
  fs.appendFileSync(artifactFile, JSON.stringify(metadata) + "\n", "utf8");
  artifactsReceived += 1;
  return metadata;
}

const viewer = `<!doctype html>
<meta charset="utf-8"><title>BLUSTONE - Instrumented events</title>
<style>body{font:14px system-ui;background:#111;color:#eee;margin:20px}button{padding:6px 10px}#status{color:#9f9}pre{white-space:pre-wrap;border-bottom:1px solid #333;padding:8px 0}small{color:#aaa}</style>
<h1>BLUSTONE - Instrumented</h1><p id="status">loading</p><button onclick="load()">Refresh</button><div id="events"></div>
<script>
async function load(){const s=await fetch('/v1/stats').then(r=>r.json());document.querySelector('#status').textContent='received '+s.received+' events; rejected '+s.rejected+'; '+s.event_file;const e=await fetch('/v1/events?limit=200').then(r=>r.json());document.querySelector('#events').innerHTML=e.events.slice().reverse().map(x=>'<pre>'+JSON.stringify(x,null,2).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</pre>').join('');}
load();setInterval(load,3000);
</script>`;

const server = http.createServer((request, response) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  if (request.method === "OPTIONS") {
    response.writeHead(204, { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" });
    return response.end();
  }
  if (request.method === "GET" && url.pathname === "/") {
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
    return response.end(viewer);
  }
  if (request.method === "GET" && url.pathname === "/healthz") {
    return sendJson(response, 200, { ok: true, service: "blustone-instrumentation-collector", received, rejected, event_file: eventFile });
  }
  if (request.method === "GET" && url.pathname === "/v1/stats") {
    return sendJson(response, 200, { received, rejected, artifacts_received: artifactsReceived, event_file: eventFile, artifact_file: artifactFile, ring_size: ring.length });
  }
  if (request.method === "GET" && url.pathname === "/v1/events") {
    const requested = Number(url.searchParams.get("limit") || 200);
    const limit = Math.max(1, Math.min(2000, Number.isFinite(requested) ? requested : 200));
    return sendJson(response, 200, { events: ring.slice(-limit) });
  }
  if (request.method === "GET" && url.pathname === "/v1/artifacts") {
    return sendJson(response, 200, { artifacts: artifacts.slice(-artifactLimit) });
  }
  if (request.method === "POST" && url.pathname === "/v1/events") {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size <= maxBodyBytes) chunks.push(chunk);
      else request.destroy();
    });
    request.on("end", () => {
      if (size > maxBodyBytes) {
        rejected += 1;
        return sendJson(response, 413, { ok: false, error: "body too large" });
      }
      try {
        const events = parseEvents(Buffer.concat(chunks), String(request.headers["content-type"] || ""));
        const accepted = appendEvents(events, request);
        return sendJson(response, 202, { ok: true, accepted: accepted.length });
      } catch (error) {
        rejected += 1;
        return sendJson(response, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
      }
    });
    return;
  }
  if (request.method === "POST" && url.pathname === "/v1/artifacts") {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size <= maxArtifactBytes) chunks.push(chunk);
      else request.destroy();
    });
    request.on("end", () => {
      if (size > maxArtifactBytes) {
        rejected += 1;
        return sendJson(response, 413, { ok: false, error: "artifact too large" });
      }
      try {
        const metadata = appendArtifact(Buffer.concat(chunks), request, url);
        return sendJson(response, 202, { ok: true, artifact: metadata });
      } catch (error) {
        rejected += 1;
        return sendJson(response, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
      }
    });
    return;
  }
  sendJson(response, 404, { ok: false, error: "not found" });
});

server.listen(port, "0.0.0.0", () => {
  console.log(`BLUSTONE instrumentation collector listening on 0.0.0.0:${port}`);
  console.log(`Writing events to ${eventFile}`);
});
