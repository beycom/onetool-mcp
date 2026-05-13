import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

export const HEADER_PROTOCOL = "X-OneTool-Protocol";
export const HEADER_TIMESTAMP = "X-OneTool-Timestamp";
export const HEADER_NONCE = "X-OneTool-Nonce";
export const HEADER_SIGNATURE = "X-OneTool-Signature";
const PROTOCOL = "hmac-sha256-v1";

export class HmacAuthError extends Error {}

export class NonceCache {
  private readonly seen = new Map<string, number>();

  constructor(private readonly ttlSeconds = 60) {}

  check(nonce: string, nowSeconds = Date.now() / 1000): void {
    for (const [value, seenAt] of this.seen.entries()) {
      if (nowSeconds - seenAt > this.ttlSeconds) {
        this.seen.delete(value);
      }
    }
    if (this.seen.has(nonce)) {
      throw new HmacAuthError("Replayed OneTool auth nonce");
    }
    this.seen.set(nonce, nowSeconds);
  }
}

export function ensureHmacKey(namespace: string): Buffer {
  if (!namespace || namespace.includes("/") || namespace.includes("\\")) {
    throw new Error("HMAC key namespace must be a simple name");
  }
  const dir = path.join(os.homedir(), ".onetool", namespace);
  const file = path.join(dir, "auth.key");
  if (fs.existsSync(file)) {
    return decodeKey(fs.readFileSync(file, "utf8").trim());
  }

  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  try {
    fs.chmodSync(dir, 0o700);
  } catch {
    // Best effort on platforms that do not support POSIX modes.
  }
  const key = crypto.randomBytes(32);
  try {
    const fd = fs.openSync(file, "wx", 0o600);
    try {
      fs.writeFileSync(fd, `${key.toString("base64")}\n`, "utf8");
    } finally {
      fs.closeSync(fd);
    }
    return key;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "EEXIST") {
      return decodeKey(fs.readFileSync(file, "utf8").trim());
    }
    throw error;
  }
}

export function signHttpMessage(args: {
  key: Buffer;
  method?: string;
  statusCode?: number;
  path: string;
  body: Buffer;
  timestamp?: number;
  nonce?: string;
}): Record<string, string> {
  const timestamp = String(Math.trunc(args.timestamp ?? Date.now() / 1000));
  const nonce = args.nonce ?? crypto.randomBytes(16).toString("hex");
  const signature = signatureFor({ ...args, timestamp, nonce });
  return {
    [HEADER_PROTOCOL]: PROTOCOL,
    [HEADER_TIMESTAMP]: timestamp,
    [HEADER_NONCE]: nonce,
    [HEADER_SIGNATURE]: signature,
  };
}

export function verifyHttpMessage(args: {
  key: Buffer;
  method?: string;
  statusCode?: number;
  path: string;
  body: Buffer;
  headers: Record<string, string | string[] | undefined>;
  maxSkewSeconds?: number;
  nonceCache?: NonceCache;
  now?: number;
}): void {
  const protocol = header(args.headers, HEADER_PROTOCOL);
  if (protocol !== PROTOCOL) {
    throw new HmacAuthError(`Unsupported OneTool auth protocol: ${protocol}`);
  }
  const timestamp = header(args.headers, HEADER_TIMESTAMP);
  const nonce = header(args.headers, HEADER_NONCE);
  const signature = header(args.headers, HEADER_SIGNATURE);
  const parsedTimestamp = Number.parseInt(timestamp, 10);
  if (!Number.isFinite(parsedTimestamp)) {
    throw new HmacAuthError("Invalid OneTool auth timestamp");
  }
  const now = args.now ?? Date.now() / 1000;
  if (Math.abs(now - parsedTimestamp) > (args.maxSkewSeconds ?? 30)) {
    throw new HmacAuthError("Stale OneTool auth timestamp");
  }
  const expected = signatureFor({ ...args, timestamp, nonce });
  const provided = Buffer.from(signature);
  const expectedBuffer = Buffer.from(expected);
  if (provided.length !== expectedBuffer.length || !crypto.timingSafeEqual(provided, expectedBuffer)) {
    throw new HmacAuthError("Invalid OneTool auth signature");
  }
  args.nonceCache?.check(nonce, now);
}

function decodeKey(value: string): Buffer {
  const key = Buffer.from(value, "base64");
  if (key.length !== 32) {
    throw new HmacAuthError("Invalid OneTool HMAC key length");
  }
  return key;
}

function header(headers: Record<string, string | string[] | undefined>, name: string): string {
  const found = Object.entries(headers).find(([key]) => key.toLowerCase() === name.toLowerCase())?.[1];
  const value = Array.isArray(found) ? found[0] : found;
  if (!value) {
    throw new HmacAuthError(`Missing OneTool auth header: ${name}`);
  }
  return value;
}

function signatureFor(args: {
  key: Buffer;
  method?: string;
  statusCode?: number;
  path: string;
  body: Buffer;
  timestamp: string;
  nonce: string;
}): string {
  if ((args.method === undefined) === (args.statusCode === undefined)) {
    throw new Error("Provide exactly one of method or statusCode");
  }
  const subject = args.method ? args.method.toUpperCase() : `STATUS:${args.statusCode}`;
  const bodyHash = crypto.createHash("sha256").update(args.body).digest("hex");
  const payload = [subject, args.path, args.timestamp, args.nonce, bodyHash].join("\n");
  return crypto.createHmac("sha256", args.key).update(payload).digest("base64");
}
