# Emoji Commits

Draft and review Git commit messages using a Gitmoji prefix followed by
Conventional Commits structure:

```text
✨ feat(auth): support sign-in with email verification codes
🔒️ fix(auth): prevent regular users from accessing admin endpoints
⬆️ build(deps): upgrade development dependencies
```

The [full convention](SKILL.md) defines types, emoji meanings, selection
priorities, breaking changes, and examples. The instructions are in English;
generated messages follow explicit user or repository language preferences,
then recent commit language, and finally the user's language.

## Install

Run from this repository's root with Node.js **22.16+**:

```sh
node --experimental-strip-types scripts/install-skill.ts emoji-commits --mode copy
```

Add `--agent pi` to install for Pi. Use `--mode link` for a live link to this
checkout during development. General installation, update, and removal
instructions are in the source repository's `docs/installing-skills.md`.

The skill itself requires no script runtime. Git is needed when inspecting an
actual repository diff. Installation is separate from saving the source files
in this repository.

## Use

The skill supports automatic selection for commit-message tasks. To invoke it
explicitly after installation, ask:

```text
Use $emoji-commits to draft a commit message for my staged changes.
```

You can also supply a diff or ask it to review a proposed message. It checks
the intended commit scope and repository conventions before choosing the type
and emoji. Invoking the skill does not authorize staging, committing, pushing,
splitting commits, or rewriting history.

## Format and compatibility

```text
<emoji> <type>[(scope)][!]: <summary>
```

Each subject starts with one Unicode emoji. The type describes the broad
category; the emoji can express a more specific intent, such as a security
fix. Breaking changes require both ASCII `!` and a `BREAKING CHANGE:` footer
under this convention.

This is a combined extension of Gitmoji and Conventional Commits. Existing
commit checks, changelog generators, or release tools may need additional
parsing rules for the emoji prefix. Mandatory repository conventions take
precedence; the skill does not install hooks or modify release configuration.
