/* Derived design-system guard.
 *
 * The token set is read from the @theme block in src/styles.css rather than from a
 * hand-maintained list, so a token that is renamed or removed fails here instead of
 * silently producing a class Tailwind never generates.
 *
 * It refuses:
 *   1. literal colors in components (hex, rgb(), hsl());
 *   2. raw Tailwind palette utilities, which bypass the semantic tokens of A.2;
 *   3. outline-none / outline-hidden, since the global :focus-visible rule owns focus;
 *   4. a cv- color, radius, or shadow utility whose token does not exist.
 *
 * EXCEPTIONS is deliberately empty. Add an entry only with a reason, so forgetting to
 * register something fails instead of passing.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const sourceRoot = join(root, "src");
const stylesPath = join(sourceRoot, "styles.css");

/** @type {{ file: string, rule: string, reason: string }[]} */
const EXCEPTIONS = [];

const PALETTE = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
].join("|");

const BUILTIN_RADIUS = new Set(["none", "sm", "md", "lg", "xl", "2xl", "3xl", "full"]);
const BUILTIN_SHADOW = new Set(["none", "2xs", "xs", "sm", "md", "lg", "xl", "2xl", "inner"]);

const collectFiles = (dir) =>
  readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    return statSync(full).isDirectory() ? collectFiles(full) : /\.(ts|tsx)$/.test(full) ? [full] : [];
  });

const readTokens = (prefix) => {
  const theme = readFileSync(stylesPath, "utf8");
  const block = theme.slice(theme.indexOf("@theme"), theme.indexOf("\n}", theme.indexOf("@theme")));
  return new Set([...block.matchAll(new RegExp(`--${prefix}-([a-z0-9-]+):`, "g"))].map((match) => match[1]));
};

const colorTokens = readTokens("color");
const radiusTokens = readTokens("radius");
const shadowTokens = readTokens("shadow");

const rules = [
  {
    name: "literal-color",
    pattern: /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g,
    message: "literal color in a component; use a --color-cv-* token",
  },
  {
    name: "raw-palette",
    pattern: new RegExp(`\\b(?:bg|text|border|ring|fill|stroke|accent|from|via|to)-(?:${PALETTE})-\\d{2,3}\\b`, "g"),
    message: "raw Tailwind palette utility; use a semantic cv token",
  },
  {
    name: "focus-opt-out",
    pattern: /\boutline-(?:none|hidden)\b/g,
    message: "the global :focus-visible rule owns focus; do not clear the outline",
  },
];

const errors = [];

for (const file of collectFiles(sourceRoot)) {
  const relativePath = relative(root, file);
  const source = readFileSync(file, "utf8");

  for (const rule of rules) {
    const exempt = EXCEPTIONS.some((entry) => entry.file === relativePath && entry.rule === rule.name);

    if (exempt) {
      continue;
    }

    for (const match of source.matchAll(rule.pattern)) {
      const line = source.slice(0, match.index).split("\n").length;
      errors.push(`${relativePath}:${line} ${rule.message} (${match[0]})`);
    }
  }

  for (const match of source.matchAll(
    /\b(?:bg|text|border|ring|fill|stroke|accent|divide|outline|caret|shadow)-(cv-[a-z0-9-]+)(?:\/\d{1,3})?\b/g,
  )) {
    if (!colorTokens.has(match[1])) {
      const line = source.slice(0, match.index).split("\n").length;
      errors.push(`${relativePath}:${line} unknown color token --color-${match[1]}`);
    }
  }

  for (const [tokens, prefix, builtin] of [
    [radiusTokens, "rounded", BUILTIN_RADIUS],
    [shadowTokens, "shadow", BUILTIN_SHADOW],
  ]) {
    for (const match of source.matchAll(new RegExp(`\\b${prefix}-([a-z0-9-]+)\\b`, "g"))) {
      const name = match[1];

      if (builtin.has(name) || tokens.has(name) || name.startsWith("cv-")) {
        continue;
      }

      const line = source.slice(0, match.index).split("\n").length;
      errors.push(`${relativePath}:${line} unknown ${prefix} token (${match[0]})`);
    }
  }
}

if (errors.length > 0) {
  console.error(`design-token guard failed (${errors.length}):`);
  for (const error of errors) {
    console.error(`  ${error}`);
  }
  process.exit(1);
}

console.log(
  `design-token guard passed: ${colorTokens.size} color, ${radiusTokens.size} radius, ${shadowTokens.size} shadow tokens.`,
);
