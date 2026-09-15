# Auditing Manuscript Loopholes

Audit manuscript evidence, internal consistency and claims; report actionable issues without editing by default.

## Recommended installation

From the repository root with Node.js **22.16+**:

```sh
node --experimental-strip-types scripts/install-skill.ts auditing-manuscript-loopholes --mode copy
```

Add `--agent pi` for Pi, or use `--mode link` for development in this checkout.
Restart the client or open a new session and ask it to use `auditing-manuscript-loopholes`.
To update a copy, repeat the command with `--replace`.

The repository's `docs/installing-skills.md` is the shared guide for custom
destinations, verification and removal. This path refers to the source checkout;
it is not included in the installed skill.

## Dependencies and use

The instruction skill has no executable runtime dependency. Provide the current manuscript and relevant artifacts; PDF or LaTeX inspection requires suitable tools in the agent environment. Installation copies this skill; it does not install external tools.

Read [SKILL.md](SKILL.md) for the workflow and operating boundaries.
