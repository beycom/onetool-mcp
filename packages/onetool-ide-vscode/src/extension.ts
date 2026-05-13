import * as vscode from "vscode";
import { IdeBridgeServer } from "./bridge";
import { getDefaultConnectionId } from "./snapshot";

let bridge: IdeBridgeServer | undefined;
let statusBar: vscode.StatusBarItem | undefined;
let connectionId: string;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const config = vscode.workspace.getConfiguration("onetoolIde");
  const portStart = config.get<number>("portStart", 58764);
  const portCount = config.get<number>("portCount", 10);
  connectionId = getDefaultConnectionId();

  bridge = new IdeBridgeServer(() => connectionId, portStart, portCount);
  const port = await bridge.start();

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = "onetoolIde.showConnection";
  updateStatusBar();
  statusBar.show();

  context.subscriptions.push(
    statusBar,
    vscode.commands.registerCommand("onetoolIde.showConnection", () => showConnection(context)),
    {
      dispose: () => {
        void bridge?.stop();
      },
    },
  );

  vscode.window.setStatusBarMessage(`OneTool IDE bridge listening on 127.0.0.1:${port}`, 3000);
}

export async function deactivate(): Promise<void> {
  await bridge?.stop();
  statusBar?.dispose();
}

async function showConnection(context: vscode.ExtensionContext): Promise<void> {
  const choice = await vscode.window.showQuickPick(["Copy connection id", "Show connection id"], {
    placeHolder: `OneTool IDE connection: ${connectionId}`,
    ignoreFocusOut: true,
  });
  if (choice === "Copy connection id") {
    await vscode.env.clipboard.writeText(connectionId);
    vscode.window.setStatusBarMessage("OneTool IDE connection id copied.", 3000);
  } else if (choice === "Show connection id") {
    await vscode.window.showInformationMessage(`OneTool IDE connection id: ${connectionId}`);
  }
}

function updateStatusBar(): void {
  if (!statusBar) {
    return;
  }
  const port = bridge?.getPort();
  statusBar.text = `$(plug) OneTool IDE: ${connectionId}${port ? ` :${port}` : ""}`;
  statusBar.tooltip = `OneTool IDE connection ${connectionId}${port ? ` on 127.0.0.1:${port}` : ""}`;
}
