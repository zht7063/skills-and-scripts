/** Development-only checks; installers remain dependency-free. */
import fs from "node:fs";
import path from "node:path";
import { parseDocument } from "yaml";
import { repositoryRoot } from "./skill-tools.ts";

export function validateFrontmatter(skill: string): string[] {
  const text = fs.readFileSync(path.join(skill, "SKILL.md"), "utf8");
  const head = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)?.[1];
  if (head === undefined) return ["missing or unterminated YAML frontmatter"];
  const document = parseDocument(head);
  if (document.errors.length)
    return document.errors.map((error) => `invalid YAML: ${error.message}`);
  const data = document.toJS();
  if (!data || typeof data !== "object" || Array.isArray(data))
    return ["frontmatter must be a mapping"];
  return ["name", "description"].flatMap((key) =>
    typeof data[key] !== "string" || !data[key].trim()
      ? [`frontmatter ${key} must be a non-empty string`]
      : [],
  );
}

export function discoverAdapters(repo = repositoryRoot): string[] {
  const root = path.join(repo, "packages/mwf/adapters");
  return fs
    .readdirSync(root)
    .sort()
    .map((name) => path.join(root, name))
    .filter((dir) => fs.existsSync(path.join(dir, "SKILL.md")));
}

export const referenceParagraph =
  "For schema details read [the protocol](references/protocol.md); for maintenance read [operations](references/operations.md).";

export function validateMwfSync(repo = repositoryRoot): string[] {
  const read = (file: string) =>
    fs
      .readFileSync(path.join(repo, file), "utf8")
      .replace(/\r\n/g, "\n")
      .trim();
  const source = read("skills/memory-with-files/SKILL.md");
  const adapter = read("packages/mwf/adapters/memory-with-files/SKILL.md");
  return source === `${adapter}\n\n${referenceParagraph}`
    ? []
    : [
        "MWF adapter drift: copy the canonical skills/memory-with-files/SKILL.md to packages/mwf/adapters/memory-with-files/SKILL.md, omitting only the final references paragraph",
      ];
}
