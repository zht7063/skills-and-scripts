# LaTeX Layout Fixer

Diagnose and repair floats, blank areas, page breaks and other academic-paper layout defects while preserving the venue template.

## Recommended installation

From the repository root with Node.js **22.16+**:

```sh
node --experimental-strip-types scripts/install-skill.ts latex-layout-fixer --mode copy
```

Add `--agent pi` for Pi, or use `--mode link` for development in this checkout.
Restart the client or open a new session and ask it to use `latex-layout-fixer`.
To update a copy, repeat the command with `--replace`.

The repository's `docs/installing-skills.md` is the shared guide for custom
destinations, verification and removal. This path refers to the source checkout;
it is not included in the installed skill.

## Dependencies and use

Requires Python 3.10+ for the bundled helpers, a TeX distribution with `latexmk`, and `pdftoppm` or `mutool` for rendering. Rendering all pages also requires `pdfinfo`. The agent needs an image-viewing tool for visual QA. Installation copies this skill; it does not install external tools.

Read [SKILL.md](SKILL.md) for the workflow and operating boundaries.
