import path from "node:path";
import {
  discoverAdapters,
  validateFrontmatter,
  validateMwfSync,
} from "./validate-metadata.ts";
import { argumentsFor, fail } from "./arguments.ts";
import {
  discoverSkills,
  runSkillTests,
  SkillToolError,
  validateSkill,
} from "./skill-tools.ts";
try {
  const { values } = argumentsFor({
    options: {
      tests: { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help)
    console.log(
      "Usage: node --experimental-strip-types scripts/validate-all.ts [--tests]\nValidate every source skill, optionally running its TypeScript tests.",
    );
  else {
    const skills = [...discoverSkills(), ...discoverAdapters()];
    if (!skills.length) throw new SkillToolError("no skills found");
    const syncIssues = validateMwfSync();
    let failures = syncIssues.length;
    for (const issue of syncIssues) console.log(`FAIL ${issue}`);
    for (const skill of skills) {
      const issues = [...validateSkill(skill), ...validateFrontmatter(skill)];
      if (issues.length) {
        failures++;
        console.log(
          `FAIL ${path.relative(process.cwd(), skill)}\n${issues.map((i) => `  - ${i}`).join("\n")}`,
        );
        continue;
      }
      console.log(`PASS ${path.relative(process.cwd(), skill)}`);
      if (values.tests) {
        const result = runSkillTests(skill);
        if (!result) console.log("  tests: none");
        else if (result.status === 0) console.log("  tests: passed");
        else {
          failures++;
          console.log(
            `  tests: failed\n${result.error?.message ?? ""}${result.stdout ?? ""}${result.stderr ?? ""}`,
          );
        }
      }
    }
    if (failures)
      throw new SkillToolError(
        `validation failed: ${failures} skill operation(s) failed`,
      );
    console.log(`validated ${skills.length} skill(s)`);
  }
} catch (error) {
  fail(error);
}
