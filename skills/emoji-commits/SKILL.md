---
name: emoji-commits
description: Write and review Git commit messages using a Gitmoji prefix followed by Conventional Commits. Use when drafting a commit message, preparing an authorized commit, or checking a proposed commit message against this convention.
---

# Emoji Commits

Use a **Gitmoji prefix followed by the Conventional Commits structure**. This skill governs commit messages only; invoking it does not authorize staging, committing, pushing, splitting commits, or rewriting history.

## Format

```text
<emoji> <type>[(scope)][!]: <summary>

[optional body]

[optional trailers]
```

- Start the subject with exactly one actual Unicode emoji followed by one space. Do not use `:shortcode:` notation or stack classification emojis.
- Use concise lowercase English identifiers for `type` and `scope`. The optional scope identifies a module or subsystem; prefer existing repository names.
- Follow the colon with one space. Describe the change with a concrete action, omit the final period, and avoid vague summaries such as "update code". Keep the subject readable on one line and follow repository length limits.
- Follow explicit user or repository language preferences. Otherwise, use the predominant language of recent ordinary commits; if no convention is available, use the user's language.
- Use only a subject for simple changes. Add a body when needed to explain motivation, key behavior changes, compatibility impact, or migration steps, separated from the subject by a blank line. Do not require a testing or explanation template or claim unverified results.
- Preserve repository syntax for issue references and trailers such as `Co-authored-by`. Do not invent associations, authors, or test results.

## Choose the type

Classify by the primary purpose, not the file extension. Use exactly one type per subject.

| Type | Primary purpose | Default emoji |
| --- | --- | --- |
| feat | Add or intentionally change functionality | ✨ |
| fix | Correct faulty behavior | 🐛 |
| refactor | Restructure implementation without changing intended behavior | ♻️ |
| perf | Improve performance or reduce resource consumption | ⚡️ |
| docs | Update documentation or explanatory comments | 📝 |
| test | Add or update tests or test infrastructure | ✅ |
| style | Adjust code formatting without changing semantics | 🎨 |
| build | Change builds, packaging, or dependency management | 📦️ |
| ci | Change CI workflows or automated check configuration | 👷 |
| chore | Perform maintenance that does not fit the other categories | 🔧 |
| revert | Explicitly undo a previous commit | ⏪️ |

`style` does not mean product visual styling. Use feat for new UI, fix for display defects, and style only for code formatting changes.

Default emojis are starting points and must still match the meanings below. For example, use 🔨 for development script maintenance; do not describe every maintenance task as a configuration change.

## Choose the emoji

Use this curated set of Gitmoji meanings. The type expresses the broad category, while the emoji expresses a more specific intent; they do not need a one-to-one mapping. Do not invent mappings based on intuition. Follow explicit repository conventions when they require other Gitmoji entries.

| Emoji | Meaning and scope |
| --- | --- |
| ✨ | Introduce new features |
| 🐛 | Fix a bug |
| ♻️ | Refactor code |
| ⚡️ | Improve performance |
| 📝 | Add or update documentation |
| ✅ | Add or update tests |
| 🎨 | Improve code structure or formatting; prefer ♻️ for refactoring under this convention |
| 📦️ | Add or update compiled artifacts or packages |
| 👷 | Add or update the CI build system |
| 🔧 | Add or update configuration files |
| ⏪️ | Revert changes |
| 💥 | Introduce breaking changes |
| 🔒️ | Fix security or privacy issues |
| 🚑️ | Apply a critical hotfix; use only when the task is explicitly an urgent fix |
| 💚 | Fix a failing CI build |
| 💄 | Add or update UI and style files |
| ♿️ | Improve accessibility |
| 🌐 | Implement internationalization or localization |
| ⬆️ | Upgrade dependencies |
| ⬇️ | Downgrade dependencies |
| ➕ | Add a dependency |
| ➖ | Remove a dependency |
| 📌 | Pin dependency versions |
| 🔨 | Add or update development scripts |
| 🔥 | Remove code or files |
| 🚚 | Move or rename resources |
| 💡 | Add or update source code comments |
| 🔖 | Make release or version tag changes |
| 🎉 | Initialize a project |

### Resolve overlapping categories

Apply these rules in order. Once an emoji is selected, do not add another:

1. Use ⏪️ for an explicit revert. Keep ⏪️ even if the revert breaks compatibility; express that impact through `!` and the footer.
2. Use 💥 for other breaking changes.
3. Use 🔒️ for security or privacy fixes, ahead of hotfixes, dependency operations, or domains such as UI.
4. Use 🚑️ for an explicitly urgent, critical hotfix.
5. Use 🐛 for ordinary bug fixes, except when the target is specifically a failing CI build, which uses 💚. Do not switch to a domain emoji merely because a bug fix touches UI or dependencies.
6. Otherwise, choose a specific emoji for the primary purpose: accessibility ♿️, localization 🌐, UI 💄, dependency operations, and so on. When accessibility or localization is the primary purpose, prefer it over the broader UI category.
7. If no specific case applies, use the type's default emoji and verify that its meaning actually fits.

If the default emoji does not fit either, do not use chore as an unlimited fallback. Reconsider a more specific type or a listed maintenance category. If the change still cannot be classified accurately, explain the gap and request a specific convention instead of inventing an emoji.

## Breaking changes

Use the ordinary ASCII `!` after the type or scope and before the colon. Do not substitute `❗`. This skill also requires a `BREAKING CHANGE:` footer for breaking commits, explaining the incompatibility and available migration steps. If the migration path is unknown, say so rather than inventing one.

```text
💥 feat(api)!: move pagination metadata into the pagination object

BREAKING CHANGE: Remove the top-level total response field. Callers must read pagination.total instead.
```

This is a stricter local convention than Conventional Commits, which permits either `!` or a breaking-change footer. Deletions, major dependency upgrades, and internal refactoring do not always break compatibility for this project's consumers; assess the actual impact.

## Generate messages from changes

- When the user provides a diff or change description, ground the message in that material. Ask for necessary information if the intent cannot be determined; do not invent behavior.
- When preparing an actual commit in a repository, inspect project conventions, recent messages, and the intended commit diff. Default to staged changes; use another scope when the user specifies it.
- If the staging area is empty, do not assume every working-tree change belongs in the commit. When requested, review unstaged changes and provide a draft with its scope clearly stated; do not stage files on your own.
- Classify a feature and its supporting tests or documentation as a feature, and a fix with its regression tests as a fix. Recommend splitting unrelated changes without performing the split on your own. If the user requests one commit, base the subject on the primary purpose and describe other substantive changes in the body.
- Explicit user instructions and mandatory repository conventions take precedence. If they prohibit emojis or require unextended Conventional Commits, comply and briefly explain the conflict. Do not modify hooks or release configuration on your own.
- When only a message is requested, provide a directly copyable message without lengthy classification analysis. Briefly explain any scope or compatibility uncertainty outside the code block.

## Examples

```text
✨ feat(auth): support sign-in with email verification codes
🐛 fix(cache): stop returning stale data after cache expiration
🔒️ fix(auth): prevent regular users from accessing admin endpoints
🔒️ fix(deps): upgrade the parser to fix a confirmed path traversal vulnerability
⬆️ build(deps): upgrade development dependencies
💄 feat(settings): add a dark theme to the settings page
🐛 fix(dialog): prevent dialog buttons from being obscured
♿️ feat(dialog): support closing dialogs with the keyboard
💚 ci: fix the build workflow cache path
🔨 chore(scripts): add a local cleanup script
💡 docs(parser): explain the empty-input handling contract
🔥 refactor(legacy): remove the unused legacy parser
⏪️ revert(auth): revert email verification code sign-in
```

For ordinary revert commits, include the verified hash of the reverted commit in the body. Do not automatically rewrite existing tool-generated merge, revert, fixup, or squash messages whose tooling relies on fixed subjects. When explicitly asked to convert them, first explain any potential change in tool recognition.

## Sources and compatibility

- [Gitmoji catalog](https://gitmoji.dev/): the source of emoji meanings.
- [Gitmoji specification](https://gitmoji.dev/specification): native Gitmoji does not require a textual type; this skill uses a combined format.
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): the source of the type, scope, body, and trailer structure.

This skill combines and extends the two conventions. It does not claim full compliance with the separate specification named Conventional Emoji Commits. The emoji prefix may require additional parsing rules for commitlint, changelog generators, or release tools; compatibility with standard parsers is not guaranteed. Use these local rules for routine work without querying the web each time or deploying validation hooks on your own.
