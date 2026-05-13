const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "ot-ide-auth-"));
process.env.HOME = tempHome;

const {
  HmacAuthError,
  NonceCache,
  ensureHmacKey,
  signHttpMessage,
  verifyHttpMessage,
} = require("../dist/auth");

const key = ensureHmacKey("ide");
assert.equal(key.length, 32);
assert.deepEqual(ensureHmacKey("ide"), key);
assert.ok(fs.existsSync(path.join(tempHome, ".onetool", "ide", "auth.key")));

const tempAuthDir = fs.mkdtempSync(path.join(os.tmpdir(), "ot-ide-auth-dir-"));
const scopedKey = ensureHmacKey("ide", tempAuthDir);
assert.equal(scopedKey.length, 32);
assert.ok(fs.existsSync(path.join(tempAuthDir, "ide", "auth.key")));

const body = Buffer.from('{"ok":true}');
const headers = signHttpMessage({
  key,
  method: "POST",
  path: "/state",
  body,
  timestamp: 1000,
  nonce: "abc",
});
verifyHttpMessage({
  key,
  method: "POST",
  path: "/state",
  body,
  headers,
  now: 1000,
});

assert.throws(
  () =>
    verifyHttpMessage({
      key,
      method: "POST",
      path: "/state",
      body: Buffer.from("tampered"),
      headers,
      now: 1000,
    }),
  HmacAuthError,
);

assert.throws(
  () =>
    verifyHttpMessage({
      key,
      method: "POST",
      path: "/state",
      body,
      headers,
      now: 1100,
    }),
  /Stale OneTool auth timestamp/,
);

const cache = new NonceCache();
cache.check("one", 1000);
assert.throws(() => cache.check("one", 1001), /Replayed OneTool auth nonce/);
