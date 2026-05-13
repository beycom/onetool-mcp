const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const Module = require("node:module");
const os = require("node:os");
const path = require("node:path");

const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "ot-ide-bridge-"));
process.env.HOME = tempHome;

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === "vscode") {
    return {
      workspace: {
        name: "onetool-mcp",
        workspaceFile: null,
        workspaceFolders: [{ uri: { scheme: "file", fsPath: "/repo" } }],
      },
      window: {
        activeTextEditor: null,
      },
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};

const { ensureHmacKey, signHttpMessage, verifyHttpMessage } = require("../dist/auth");
const { IdeBridgeServer } = require("../dist/bridge");

async function request(port, method, requestPath, body, nonce) {
  const key = ensureHmacKey("ide", tempHome);
  const bodyBuffer = Buffer.from(body || "");
  const headers = signHttpMessage({
    key,
    method,
    path: requestPath,
    body: bodyBuffer,
    nonce,
  });
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: "127.0.0.1",
        port,
        method,
        path: requestPath,
        headers: {
          ...headers,
          "content-type": "application/json",
          "content-length": bodyBuffer.length,
        },
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const responseBody = Buffer.concat(chunks);
          resolve({ statusCode: res.statusCode, headers: res.headers, body: responseBody });
        });
      },
    );
    req.on("error", reject);
    req.end(bodyBuffer);
  });
}

async function unsignedRequest(port) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, method: "GET", path: "/health" }, (res) => {
      res.resume();
      res.on("end", () => resolve(res.statusCode));
    });
    req.on("error", reject);
    req.end();
  });
}

(async () => {
  const blocker = http.createServer((_req, res) => res.end("busy"));
  await new Promise((resolve) => blocker.listen(0, "127.0.0.1", resolve));
  const busyPort = blocker.address().port;

  const bridge = new IdeBridgeServer(() => "onetool-mcp", busyPort, 2, tempHome);
  const port = await bridge.start();
  assert.equal(port, busyPort + 1);

  const health = await request(port, "GET", "/health", "", "health-one");
  assert.equal(health.statusCode, 200);
  verifyHttpMessage({
    key: ensureHmacKey("ide", tempHome),
    statusCode: 200,
    path: "/health",
    body: health.body,
    headers: health.headers,
  });
  assert.equal(JSON.parse(health.body.toString("utf8")).connection.id, "onetool-mcp");

  const stateBody = JSON.stringify({
    protocol_version: 1,
    operation: "get_state",
    connection_id: "onetool-mcp",
  });
  const state = await request(port, "POST", "/state", stateBody, "state-one");
  assert.equal(state.statusCode, 200);
  assert.equal(JSON.parse(state.body.toString("utf8")).snapshot.connection.id, "onetool-mcp");

  const unsupportedBody = JSON.stringify({
    protocol_version: 1,
    operation: "unknown_operation",
    connection_id: "onetool-mcp",
  });
  const unsupported = await request(port, "POST", "/state", unsupportedBody, "unsupported-one");
  assert.equal(unsupported.statusCode, 400);
  assert.equal(JSON.parse(unsupported.body.toString("utf8")).error, "unsupported_operation");

  const unauthorized = await unsignedRequest(port);
  assert.equal(unauthorized, 401);

  const replayOne = await request(port, "GET", "/health", "", "replay");
  const replayTwo = await request(port, "GET", "/health", "", "replay");
  assert.equal(replayOne.statusCode, 200);
  assert.equal(replayTwo.statusCode, 401);

  await bridge.stop();
  await new Promise((resolve) => blocker.close(resolve));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
