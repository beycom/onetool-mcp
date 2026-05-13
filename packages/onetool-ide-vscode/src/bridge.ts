import * as http from "node:http";
import { ensureHmacKey, HmacAuthError, NonceCache, signHttpMessage, verifyHttpMessage } from "./auth";
import { PROTOCOL_VERSION, buildSnapshot } from "./snapshot";

interface BridgeRequest {
  protocol_version: number;
  operation: string;
  connection_id: string;
}

export class IdeBridgeServer {
  private server: http.Server | undefined;
  private port: number | undefined;
  private readonly requestNonces = new NonceCache();
  private readonly key = ensureHmacKey("ide");

  constructor(
    private readonly getConnectionId: () => string,
    private readonly portStart: number,
    private readonly portCount: number,
  ) {}

  async start(): Promise<number> {
    if (this.server) {
      return this.port ?? this.portStart;
    }

    for (let port = this.portStart; port < this.portStart + this.portCount; port += 1) {
      const bound = await this.tryStart(port);
      if (bound) {
        this.port = port;
        return port;
      }
    }
    throw new Error(`No available OneTool IDE bridge port in range ${this.portStart}..${this.portStart + this.portCount - 1}`);
  }

  getPort(): number | undefined {
    return this.port;
  }

  private tryStart(port: number): Promise<boolean> {
    const server = http.createServer((request, response) => {
      void this.handleRequest(request, response);
    });
    return new Promise((resolve, reject) => {
      server.once("error", (error: NodeJS.ErrnoException) => {
        if (error.code === "EADDRINUSE") {
          resolve(false);
          return;
        }
        reject(error);
      });
      server.listen(port, "127.0.0.1", () => {
        this.server = server;
        resolve(true);
      });
    });
  }

  stop(): Promise<void> {
    if (!this.server) {
      return Promise.resolve();
    }
    const server = this.server;
    this.server = undefined;
    return new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }

  private async handleRequest(request: http.IncomingMessage, response: http.ServerResponse): Promise<void> {
    const requestPath = request.url ?? "/";
    if (request.method === "GET" && requestPath === "/health") {
      this.handleHealth(request, response);
      return;
    }
    if (request.method !== "POST" || requestPath !== "/state") {
      this.send(response, 404, requestPath, { error: "Not found" });
      return;
    }

    let body = "";
    request.on("data", (chunk: Buffer) => {
      body += chunk.toString("utf8");
    });
    request.on("end", () => {
      try {
        this.verifyRequest(request, "POST", "/state", Buffer.from(body, "utf8"));
        const parsed = JSON.parse(body) as BridgeRequest;
        if (parsed.protocol_version !== PROTOCOL_VERSION) {
          this.send(response, 409, "/state", {
            error: "protocol_mismatch",
            expected: PROTOCOL_VERSION,
            received: parsed.protocol_version,
          });
          return;
        }
        if (parsed.operation !== "get_state") {
          this.send(response, 400, "/state", { error: "unsupported_operation" });
          return;
        }
        const connectionId = this.getConnectionId();
        if (parsed.connection_id !== connectionId) {
          this.send(response, 404, "/state", { error: "unknown_connection" });
          return;
        }

        this.send(response, 200, "/state", {
          protocol_version: PROTOCOL_VERSION,
          snapshot: buildSnapshot(connectionId),
        });
      } catch (error) {
        if (error instanceof HmacAuthError) {
          this.send(response, 401, "/state", { error: "unauthorized" });
          return;
        }
        this.send(response, 400, "/state", { error: "malformed_request" });
      }
    });
  }

  private handleHealth(request: http.IncomingMessage, response: http.ServerResponse): void {
    try {
      this.verifyRequest(request, "GET", "/health", Buffer.alloc(0));
    } catch (error) {
      if (error instanceof HmacAuthError) {
        this.send(response, 401, "/health", { error: "unauthorized" });
        return;
      }
      throw error;
    }
    const snapshot = buildSnapshot(this.getConnectionId());
    this.send(response, 200, "/health", {
      ok: true,
      protocol_version: PROTOCOL_VERSION,
      connection: snapshot.connection,
      workspace: snapshot.workspace,
    });
  }

  private verifyRequest(request: http.IncomingMessage, method: string, path: string, body: Buffer): void {
    verifyHttpMessage({
      key: this.key,
      method,
      path,
      body,
      headers: request.headers,
      nonceCache: this.requestNonces,
    });
  }

  private send(response: http.ServerResponse, status: number, path: string, payload: unknown): void {
    const body = Buffer.from(JSON.stringify(payload), "utf8");
    response.writeHead(status, {
      "content-type": "application/json",
      ...signHttpMessage({
        key: this.key,
        statusCode: status,
        path,
        body,
      }),
    });
    response.end(body);
  }
}
