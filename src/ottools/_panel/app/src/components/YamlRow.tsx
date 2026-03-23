import { useMemo } from "react";
import yaml from "js-yaml";
import type { YamlMessage } from "../types";
import { JsonRow } from "./JsonRow";
import type { JsonMessage } from "../types";

interface YamlRowProps {
  msg: YamlMessage;
}

export function YamlRow({ msg }: YamlRowProps) {
  const parsed = useMemo(() => {
    try {
      return { data: yaml.load(msg.text), error: null };
    } catch (e) {
      return { data: null, error: e instanceof Error ? e.message : String(e) };
    }
  }, [msg.text]);

  if (parsed.error) {
    return (
      <div>
        {msg.label && (
          <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
            {msg.label}
          </div>
        )}
        <pre className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded overflow-x-auto">
          {`YAML parse error: ${parsed.error}`}
        </pre>
      </div>
    );
  }

  const jsonMsg: JsonMessage = {
    kind: "json",
    id: msg.id,
    data: parsed.data,
    label: msg.label,
  };

  return <JsonRow msg={jsonMsg} />;
}
