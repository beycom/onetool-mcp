import * as path from "node:path";
import * as vscode from "vscode";

export const PROTOCOL_VERSION = 1;

export interface Snapshot {
  connection: {
    id: string;
  };
  workspace: {
    name: string | null;
    workspace_folders: string[];
    workspace_file: string | null;
  };
  active_editor: {
    visible_ranges: Array<{
      start_line: number;
      end_line: number;
    }>;
    document: {
      path: string;
      dirty: boolean;
      untitled: boolean;
    };
  } | null;
  selection: {
    path: string;
    ranges: Array<{
      start_line: number;
      start_character: number;
      end_line: number;
      end_character: number;
    }>;
    text: string;
  } | null;
}

export function uriToPath(uri: vscode.Uri): string {
  if (uri.scheme === "untitled") {
    return uri.toString();
  }
  return path.resolve(uri.fsPath);
}

export function normalizeConnectionId(value: string): string {
  return value.replace(/\s+\((Workspace|Folder)\)$/u, "");
}

export function getDefaultConnectionId(): string {
  return normalizeConnectionId(vscode.workspace.name ?? path.basename(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "vscode"));
}

export function getWorkspaceFile(): string | null {
  const workspaceFile = vscode.workspace.workspaceFile;
  return workspaceFile ? uriToPath(workspaceFile) : null;
}

export function buildSnapshot(connectionId: string): Snapshot {
  const editor = vscode.window.activeTextEditor;
  const workspace_folders = (vscode.workspace.workspaceFolders ?? []).map((folder) => uriToPath(folder.uri));
  const active_editor = editor
    ? {
        visible_ranges: editor.visibleRanges.map((range) => ({
          start_line: range.start.line,
          end_line: range.end.line,
        })),
        document: {
          path: uriToPath(editor.document.uri),
          dirty: editor.document.isDirty,
          untitled: editor.document.isUntitled,
        },
      }
    : null;

  const nonEmptySelections = editor?.selections.filter((selection) => !selection.isEmpty) ?? [];
  const selection =
    editor && nonEmptySelections.length > 0
      ? {
          path: uriToPath(editor.document.uri),
          ranges: nonEmptySelections.map((selectionRange) => ({
            start_line: selectionRange.start.line,
            start_character: selectionRange.start.character,
            end_line: selectionRange.end.line,
            end_character: selectionRange.end.character,
          })),
          text: nonEmptySelections.map((selectionRange) => editor.document.getText(selectionRange)).join("\n"),
        }
      : null;

  return {
    connection: {
      id: connectionId,
    },
    workspace: {
      name: vscode.workspace.name ?? null,
      workspace_folders,
      workspace_file: getWorkspaceFile(),
    },
    active_editor,
    selection,
  };
}
