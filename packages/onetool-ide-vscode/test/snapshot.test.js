const assert = require("node:assert/strict");
const Module = require("node:module");

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === "vscode") {
    return {
      workspace: {
        name: "onetool-mcp",
        workspaceFile: { scheme: "file", fsPath: "/repo/onetool.code-workspace" },
        workspaceFolders: [{ uri: { scheme: "file", fsPath: "/repo" } }],
      },
      window: {
        activeTextEditor: {
          visibleRanges: [{ start: { line: 0 }, end: { line: 40 } }],
          document: {
            uri: { scheme: "file", fsPath: "/repo/src/app.ts" },
            isDirty: false,
            isUntitled: false,
            getText: () => "selected code",
          },
          selections: [
            {
              isEmpty: false,
              start: { line: 1, character: 2 },
              end: { line: 2, character: 3 },
            },
          ],
        },
      },
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};

const {
  buildSnapshot,
  getDefaultConnectionId,
  normalizeConnectionId,
} = require("../dist/snapshot");

assert.equal(getDefaultConnectionId(), "onetool-mcp");
assert.equal(normalizeConnectionId("onetool-mcp (Workspace)"), "onetool-mcp");
assert.equal(normalizeConnectionId("src (Folder)"), "src");
assert.equal(normalizeConnectionId("docs"), "docs");

const snapshot = buildSnapshot("ot1");
assert.deepEqual(snapshot.connection, { id: "ot1" });
assert.deepEqual(snapshot.workspace, {
  name: "onetool-mcp",
  workspace_folders: ["/repo"],
  workspace_file: "/repo/onetool.code-workspace",
});
assert.deepEqual(snapshot.active_editor.visible_ranges, [{ start_line: 0, end_line: 40 }]);
assert.deepEqual(snapshot.active_editor.document, {
  path: "/repo/src/app.ts",
  dirty: false,
  untitled: false,
});
assert.deepEqual(snapshot.selection.ranges, [
  {
    start_line: 1,
    start_character: 2,
    end_line: 2,
    end_character: 3,
  },
]);
assert.equal(snapshot.selection.text, "selected code");
