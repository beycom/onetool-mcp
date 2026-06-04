// Adapted from pingdotgg/t3code apps/web/src/lib/diffRendering.ts (MIT).
import { parsePatchFiles } from "@pierre/diffs";
import type { FileDiffMetadata } from "@pierre/diffs/react";

export const DIFF_THEME_NAMES = {
  light: "pierre-light",
  dark: "pierre-dark",
} as const;

export type DiffThemeName = (typeof DIFF_THEME_NAMES)[keyof typeof DIFF_THEME_NAMES];

const FNV_OFFSET_BASIS_32 = 0x811c9dc5;
const FNV_PRIME_32 = 0x01000193;
const SECONDARY_HASH_SEED = 0x9e3779b9;
const SECONDARY_HASH_MULTIPLIER = 0x85ebca6b;

export function resolveDiffThemeName(theme: "light" | "dark"): DiffThemeName {
  return theme === "dark" ? DIFF_THEME_NAMES.dark : DIFF_THEME_NAMES.light;
}

export function fnv1a32(
  input: string,
  seed = FNV_OFFSET_BASIS_32,
  multiplier = FNV_PRIME_32,
): number {
  let hash = seed >>> 0;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, multiplier) >>> 0;
  }
  return hash >>> 0;
}

function buildPatchCacheKey(patch: string, scope = "onetool-display"): string {
  const normalizedPatch = patch.trim();
  const primary = fnv1a32(normalizedPatch).toString(36);
  const secondary = fnv1a32(normalizedPatch, SECONDARY_HASH_SEED, SECONDARY_HASH_MULTIPLIER).toString(36);
  return `${scope}:${normalizedPatch.length}:${primary}:${secondary}`;
}

export type RenderablePatch =
  | { kind: "files"; files: FileDiffMetadata[] }
  | { kind: "raw"; text: string; reason: string };

export function getRenderablePatch(patch: string | undefined, scope?: string): RenderablePatch | null {
  if (!patch) return null;
  const normalizedPatch = patch.trim();
  if (!normalizedPatch) return null;
  try {
    const parsed = parsePatchFiles(normalizedPatch, buildPatchCacheKey(normalizedPatch, scope));
    const files = parsed.flatMap((entry) => entry.files);
    return files.length > 0 ? { kind: "files", files } : { kind: "raw", text: normalizedPatch, reason: "Unsupported diff format." };
  } catch {
    return { kind: "raw", text: normalizedPatch, reason: "Failed to parse patch." };
  }
}

export function resolveFileDiffPath(fileDiff: FileDiffMetadata): string {
  const raw = fileDiff.name ?? fileDiff.prevName ?? "";
  return raw.startsWith("a/") || raw.startsWith("b/") ? raw.slice(2) : raw;
}
