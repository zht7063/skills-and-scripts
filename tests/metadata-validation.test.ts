import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  validateFrontmatter,
  validateMwfSync,
  referenceParagraph,
  discoverAdapters,
} from "../scripts/validate-metadata.ts";
import { validateSkill } from "../scripts/skill-tools.ts";

test("full frontmatter validation rejects malformed YAML, duplicate keys and non-string fields", (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "metadata-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  for (const head of [
    "name: demo\ndescription: [broken",
    "name: demo\nname: duplicate\ndescription: valid",
    "name: demo\ndescription: [list]",
  ]) {
    fs.writeFileSync(path.join(dir, "SKILL.md"), `---\n${head}\n---\n`);
    assert.ok(validateFrontmatter(dir).length);
  }
  fs.writeFileSync(
    path.join(dir, "SKILL.md"),
    "---\nname: demo\ndescription: >-\n  Valid multiline\n  description.\nmetadata:\n  label: test\n---\n",
  );
  assert.deepEqual(validateFrontmatter(dir), []);
  fs.writeFileSync(
    path.join(dir, "SKILL.md"),
    `---\nname: ${"a".repeat(65)}\ndescription: valid\n---\n`,
  );
  assert.ok(
    validateSkill(dir).some((issue) => issue.includes("64 characters")),
  );
});

test("MWF sync permits only the standalone references paragraph and discovers bundled entries", (t) => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "mwf-sync-"));
  t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  const source = path.join(repo, "skills/memory-with-files");
  const adapter = path.join(repo, "packages/mwf/adapters/memory-with-files");
  for (const dir of [source, adapter]) fs.mkdirSync(dir, { recursive: true });
  const shared =
    "---\nname: memory-with-files\ndescription: Memory\n---\n\nShared instructions.";
  fs.writeFileSync(
    path.join(source, "SKILL.md"),
    `${shared}\n\n${referenceParagraph}\n`,
  );
  fs.writeFileSync(path.join(adapter, "SKILL.md"), shared);
  assert.deepEqual(validateMwfSync(repo), []);
  assert.deepEqual(discoverAdapters(repo), [adapter]);
  fs.appendFileSync(path.join(adapter, "SKILL.md"), "\nUnintentional drift.");
  assert.equal(validateMwfSync(repo).length, 1);
});
