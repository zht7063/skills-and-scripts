# Skills Repository

This repository is the source workspace for independently installable agent skills and the repository-level tooling used to build, validate, evaluate, and install them.

## Layout

```text
skills/
  <skill-name>/          One self-contained skill package
packages/mwf/            TypeScript CLI, local MCP and Harness setup
scripts/                 Repository-wide install and validation tools
docs/                    Repository conventions and design notes
```

Skill packages live under `skills/<skill-name>/`. Generated evaluation workspaces, packaged artifacts, and local agent planning state are intentionally excluded from Git.

See [docs/repository-layout.md](docs/repository-layout.md) for the detailed structure and conventions.

## Skills

- [`emoji-commits`](skills/emoji-commits/README.md) — Draft and review Gitmoji-prefixed Conventional Commit messages, with emoji selection priorities and breaking-change guidance.
- [`memory-with-files`](skills/memory-with-files/README.md) — Durable,
  project-scoped agent memory in `.mwf`, including scoped recall, structured
  decisions and incidents, handoffs, safe maintenance, and a local TypeScript CLI/MCP runtime.
- [`mihomo-remote-linux`](skills/mihomo-remote-linux/README.md) — A
  privacy-preserving, recovery-first guide for operating Mihomo on remote Linux
  hosts, from loopback proxy services to guarded system-wide TUN routing.
- [`auditing-manuscript-loopholes`](skills/auditing-manuscript-loopholes/README.md) — Read-only manuscript evidence and consistency audits.
- [`latex-layout-fixer`](skills/latex-layout-fixer/README.md) — Diagnose and repair LaTeX layout while preserving venue templates. Requires Python 3.10+, a TeX distribution with `latexmk`, and `pdftoppm` or `mutool`; rendering all pages also requires `pdfinfo`.
- [`travel-guide-html`](skills/travel-guide-html/README.md) — Chinese travel research, daily itineraries and linked maps delivered as offline HTML; includes a Python static checker.

### Runtime adapters and plugins

`packages/mwf/adapters/` ships three skills with the runtime: `memory-with-files`, `mwf-init`, and `mwf-status`. They are installed by MWF setup, not the standalone skill installer. The standalone memory skill requires the MWF runtime for executable operations.

This repository currently has no Codex plugin manifest or marketplace. MWF is an npm CLI/MCP package with a Pi extension adapter.

Repository-level commands under `scripts/` install skills for Codex, Pi Agent,
or a custom target, safely uninstall one exact skill, and validate all source
packages. See [docs/installing-skills.md](docs/installing-skills.md) for command
examples and safety behavior.

Generated review workspaces remain local and ignored.

## Recommended installation

Run commands from this repository's root with Node.js **22.16+**. Replace
`/absolute/project` with an existing project directory.

### Independent skills

For a standalone installation, copy the chosen skill into Codex:

```sh
node --experimental-strip-types scripts/install-skill.ts auditing-manuscript-loopholes --mode copy
```

Use `emoji-commits`, `latex-layout-fixer`, `mihomo-remote-linux` or
`travel-guide-html` in place of the name above.
Add `--agent pi` for Pi. Contributors who want edits in this checkout to remain
live can use `--mode link` and keep the checkout at its current path.
The installer copies instructions and helpers; install the skill's external
runtime tools separately.

See [the installation guide](docs/installing-skills.md) for destinations,
verification, updates and removal.

### Emoji commit messages

After installing `emoji-commits`, ask the agent to use `$emoji-commits` to draft
or review a commit message. It uses a Gitmoji prefix followed by Conventional
Commits structure:

```text
✨ feat(auth): support sign-in with email verification codes
🔒️ fix(auth): prevent regular users from accessing admin endpoints
```

The skill follows user or repository language preferences and defines how to
choose an emoji when categories overlap. It does not authorize Git mutations.
Existing commit checks and release tools may need parsing rules for the emoji
prefix. See the [skill guide](skills/emoji-commits/README.md) for installation
and usage, and the [full convention](skills/emoji-commits/SKILL.md) for rules.

### MWF memory and MCP

Install the runtime and connect a project together (npm also required):

```sh
node --experimental-strip-types scripts/install-mwf.ts --root "/absolute/project" --harness codex --git-mode track
```

Choose `--git-mode ignore` for local-only memory, preserving the existing mode
when upgrading. Add `--dry-run` to preview. Setup deploys the memory adapters,
registers the local MCP server and probes the connection; copying the memory
skill alone does not do this. Restart/reload the client afterward.

See [the MWF runtime guide](packages/mwf/README.md) for offline bundles,
verification, migration, upgrades and detaching projects. The npm package is
not published to the registry. No Codex plugin installation is required.

## Development

Repository tooling, MWF runtime code, their tests and the Pi adapter
are TypeScript. Individual skills may use other languages when needed;
`latex-layout-fixer` and `travel-guide-html` include Python helpers using only the standard library. Requires Node **22.16+** and npm. Restore both independent
lockfiles before running the full checks:

```sh
npm ci
npm ci --prefix packages/mwf
npm test
npm run format:check
npm run test:package --prefix packages/mwf
```

`npm test` checks types for runtime, tooling and tests, runs repository and skill
tests, validates all standalone skills and three bundled adapters, checks MWF instruction synchronization, and runs MWF integration tests. Repository commands use
`node --experimental-strip-types scripts/<command>.ts` and need no build step or
third-party loader. The published-package layout continues to use compiled JS;
TS scripts and development dependencies are not shipped. See
[installation commands](docs/installing-skills.md).

The two Python modules under evaluation fixtures represent example user projects;
they are test data and are never executed by the repository toolchain. Historical
review documents preserve their original Python-era descriptions.
