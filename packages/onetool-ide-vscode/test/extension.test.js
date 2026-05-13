const assert = require("node:assert/strict");
const Module = require("node:module");

const originalLoad = Module._load;
const registeredCommands = {};
let writtenText = undefined;
let statusMessage = undefined;

Module._load = function load(request, parent, isMain) {
  if (request === "vscode") {
    return {
      Uri: {
        file: (value) => ({ scheme: "file", fsPath: value }),
      },
      commands: {
        registerCommand: (name, callback) => {
          registeredCommands[name] = callback;
          return { dispose: () => {} };
        },
      },
      env: {
        clipboard: {
          writeText: async (value) => {
            writtenText = value;
          },
        },
      },
      workspace: {
        name: "onetool-mcp",
        getConfiguration: () => ({ get: (_key, value) => value }),
        workspaceFolders: [{ uri: { scheme: "file", fsPath: "/repo" } }],
      },
      window: {
        createStatusBarItem: () => ({
          show: () => {},
          dispose: () => {},
        }),
        setStatusBarMessage: (message) => {
          statusMessage = message;
        },
        showQuickPick: async () => undefined,
        showInformationMessage: async () => undefined,
      },
      StatusBarAlignment: { Right: 1 },
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};

const { activate, deactivate } = require("../dist/extension");

(async () => {
  assert.equal(writtenText, undefined);
  assert.equal(statusMessage, undefined);

  const context = { subscriptions: [] };
  await activate(context);
  assert.equal(typeof registeredCommands["onetoolIde.showConnection"], "function");
  assert.deepEqual(Object.keys(registeredCommands), ["onetoolIde.showConnection"]);
  assert.equal(context.subscriptions.length, 3);
  await deactivate();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
