import type { MarkdownMessage } from "../types";
import { ChatMarkdown } from "./ChatMarkdown";

interface MarkdownRowProps {
  msg: MarkdownMessage;
}

export function MarkdownRow({ msg }: MarkdownRowProps) {
  return <ChatMarkdown text={msg.text} />;
}
