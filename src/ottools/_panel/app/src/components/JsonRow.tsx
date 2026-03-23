import { JSONTree } from "react-json-tree";
import type { JsonMessage } from "../types";

const THEME = {
  scheme: "github",
  base00: "#ffffff",
  base01: "#f5f5f5",
  base02: "#e8e8e8",
  base03: "#8e8e8e",
  base04: "#626262",
  base05: "#24292f",
  base06: "#1f2328",
  base07: "#000000",
  base08: "#cf222e",
  base09: "#953800",
  base0A: "#633c01",
  base0B: "#116329",
  base0C: "#1b7c83",
  base0D: "#0550ae",
  base0E: "#8250df",
  base0F: "#6e7781",
};

interface JsonRowProps {
  msg: JsonMessage;
}

export function JsonRow({ msg }: JsonRowProps) {
  return (
    <div>
      {msg.label && (
        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
          {msg.label}
        </div>
      )}
      <div className="text-sm font-mono">
        <JSONTree
          data={msg.data}
          theme={THEME}
          invertTheme={false}
          shouldExpandNodeInitially={(_keyPath: unknown, _data: unknown, level: number) =>
            level < (msg.expanded ?? 1)
          }
        />
      </div>
    </div>
  );
}
