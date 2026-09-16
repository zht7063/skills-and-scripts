# Installing skills from this repository

Run all commands from the repository root with Node.js **22.16+**. Replace
example paths with your own. The skill installer requires no npm dependencies;
MWF installation also requires npm and may download build dependencies.

## Choose an installation

| Need | Recommended route | Result |
| --- | --- | --- |
| Emoji commit messages, manuscript audit, LaTeX layout, Mihomo guidance or travel guides | `install-skill.ts NAME --mode copy` | Independent skill instructions and helpers |
| Develop a skill in this checkout | `install-skill.ts NAME --mode link` | A live link to the source directory |
| Project memory with local MCP | `install-mwf.ts --root PROJECT --harness codex --git-mode track` | Runtime, project rules, adapters and verified MCP connection |

There is no Codex plugin manifest or marketplace in this repository.

## MWF: install the runtime and connect the project

```sh
node --experimental-strip-types scripts/install-mwf.ts --root "/absolute/project" --harness codex --git-mode track
```

The project directory must already exist. Choose `--git-mode ignore` for
local-only memory; preserve an existing project's mode. Add `--dry-run` for a
plan without writes. Use `--harness pi` or `--harness codex,pi` if Pi is installed.

The runtime defaults to `~/.local/share/mwf`. The installer prints an absolute
CLI command; use it for subsequent operations because this route does not add
`mwf` to your shell PATH. Setup registers the MCP server and probes bootstrap.
Restart/reload the selected client and trust the project through its normal
mechanism. Copying `memory-with-files` alone does not install the runtime or
connect the project. Avoid installing another memory adapter into the same
skill discovery scope.

For offline bundles, verification, upgrade, migration and detach instructions,
use [the MWF runtime guide](../packages/mwf/README.md).

## Install an independent skill

Copy mode is recommended for use: it remains usable if the checkout moves.
Choose one command:

```sh
node --experimental-strip-types scripts/install-skill.ts auditing-manuscript-loopholes --mode copy
node --experimental-strip-types scripts/install-skill.ts emoji-commits --mode copy
node --experimental-strip-types scripts/install-skill.ts latex-layout-fixer --mode copy
node --experimental-strip-types scripts/install-skill.ts mihomo-remote-linux --mode copy
node --experimental-strip-types scripts/install-skill.ts travel-guide-html --mode copy
```

Install for Pi or a custom destination:

```sh
node --experimental-strip-types scripts/install-skill.ts latex-layout-fixer --agent pi --mode copy
node --experimental-strip-types scripts/install-skill.ts latex-layout-fixer --target-dir "/path/to/skills" --mode copy
```

| Target | Destination |
| --- | --- |
| Codex (default) | `$CODEX_HOME/skills`, otherwise `~/.codex/skills` |
| Pi | `$PI_CODING_AGENT_DIR/skills`, otherwise `~/.pi/agent/skills` |
| Custom | The exact directory supplied by `--target-dir` |

Use `--agent` or `--target-dir`, not both. These are destinations used by this
repository's installer. MWF setup uses project-scoped client configuration.

Copy mode excludes root-level `evals/`, caches, bytecode and platform metadata;
versioned tests and runtime helpers are retained. It does not install Python,
TeX, SSH tools or other dependencies declared by a skill.

For development, use `--mode link` (also the CLI default). Keep the source
checkout at the same path; edits become visible through the link.

## Verify installation

Add `--dry-run` to an install command to inspect resolved paths before writing.
After installation, check the printed destination contains `SKILL.md`, start a
new client session and ask it to use the skill by name on a suitable task.
Filesystem installation alone does not prove that the client discovered it.
If unavailable, check the destination against the client's configured skill
location and any project or client discovery settings.

## Update and handle collisions

Copy installations remain unchanged when the checkout changes. After updating
the checkout, repeat the original command with `--replace`, keeping the target
and mode the same:

```sh
node --experimental-strip-types scripts/install-skill.ts latex-layout-fixer --mode copy --replace
```

An occupied destination is otherwise refused. Replacement backs it up beneath
`.skill-install-backups/` outside the active skills directory. An existing link
to the same source is already installed; its contents follow checkout updates.
Start a new client session after updating.

## Uninstall an independent skill

Use the same target options as installation. Removal previews by default:

```sh
node --experimental-strip-types scripts/uninstall-skill.ts latex-layout-fixer
node --experimental-strip-types scripts/uninstall-skill.ts latex-layout-fixer --apply
node --experimental-strip-types scripts/uninstall-skill.ts latex-layout-fixer --agent pi --apply
```

Only the exact installed skill is removed. Removing a linked installation
preserves its source. For setup-managed MWF adapters, use `mwf detach` as
explained in the runtime guide; this generic command does not detach MCP.

## Validate source packages (development)

Install repository development dependencies before full YAML and structural
validation. This covers all standalone skills and three bundled MWF adapters,
JSON, local Markdown links and shared MWF instruction synchronization:

```sh
npm ci
npm run validate
```

To also run TypeScript tests found inside skills:

```sh
node --experimental-strip-types scripts/validate-all.ts --tests
```

Full runtime and repository checks are documented in the
[root development guide](../README.md#development).
