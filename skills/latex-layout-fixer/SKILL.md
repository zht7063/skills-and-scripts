---
name: latex-layout-fixer
description: Diagnose and fix academic-paper LaTeX layout defects while preserving the publisher or conference template. Use this skill whenever a user asks to repair or improve figure/table placement, floats far from their first citation, large blank areas, float-only pages, awkward page or column breaks, overfull/underfull boxes, unprocessed floats, or one-column versus two-column layout—even if they mention only a bad PDF page or an image appearing in the wrong place. Also use it when converting an existing manuscript between one- and two-column modes requires layout QA. Do not use it to rewrite scholarly content, redesign figure artwork, or evade a venue's formatting rules.
compatibility: Requires Python 3.10+ for bundled scripts, a TeX distribution with latexmk and a PDF rasterizer such as pdftoppm or mutool; visual inspection requires an image-viewing tool.
---

# LaTeX Layout Fixer

Repair layout by treating the rendered PDF as the ground truth and the LaTeX source as the cause. A successful fix is a small, template-compliant source change that improves the affected page without degrading adjacent pages or the rest of the manuscript.

## Operating contract

- Preserve the document class, publisher files, page geometry, margins, fonts, and required column mode. Layout quality never justifies silently changing submission rules.
- Preserve scientific prose, equations, numerical results, captions, labels, citations, and artwork unless the user explicitly authorizes content changes.
- Distinguish diagnosis from implementation. For a review-only request, inspect and report without editing. For a fix request, edit, rebuild, and verify.
- Check repository status before editing. Preserve unrelated and pre-existing changes, and avoid broad cleanup of generated files.
- Use the PDF, not source intuition alone, to judge placement. Float scheduling is global, so a local source edit may change later pages.
- Prefer the smallest reversible change that addresses the identified root cause.

## Workflow

Follow this loop in order. Do not skip rendering and visual inspection merely because compilation succeeds.

### 1. Establish the manuscript and constraints

1. Find the root file containing `\documentclass` and `\begin{document}`. Follow `\input` and `\include` chains rather than assuming that `main.tex` is the root.
2. Record the document class, class options, template files, bibliography tool, compiler, and any `.latexmkrc` or TeX magic comment.
3. Determine whether the document is one-column, two-column, or mixed, and whether the venue template constrains float forms.
4. Read project instructions and, when supplied, the venue's author guide before making layout choices.
5. Record a baseline: Git status, PDF page count, relevant page images, log warnings, and the current page positions of affected captions.

Use the bundled audit as a fast first pass:

```bash
python scripts/latex_layout_audit.py /path/to/project --main path/to/root.tex
```

The audit is evidence collection, not a substitute for reading the relevant source or viewing the PDF.

### 2. Compile with the project's own toolchain

Run `latexmk` from the directory expected by the project. Respect `.latexmkrc`, magic comments, shell-escape requirements, and the existing engine.

Typical commands are:

```bash
latexmk -interaction=nonstopmode -file-line-error root.tex
latexmk -pdf -interaction=nonstopmode -file-line-error root.tex
latexmk -xelatex -interaction=nonstopmode -file-line-error root.tex
latexmk -lualatex -interaction=nonstopmode -file-line-error root.tex
```

Choose one command based on project evidence; do not switch engines speculatively. Keep build outputs in the project's established location. If compilation fails, fix or report the build failure before diagnosing pagination.

### 3. Inspect warnings and build state

Read the complete log and distinguish causal warnings from background noise. Prioritize:

- `Float too large for page`
- `Too many unprocessed floats`
- `Float(s) lost`
- a changed float specifier such as `h` to `ht`
- overfull boxes and their source line ranges
- underfull boxes that visibly correlate with bad spacing
- undefined references/citations or rerun warnings
- package errors and output-routine conflicts

Run the audit again with an explicit log when the build directory is separate:

```bash
python scripts/latex_layout_audit.py . --main root.tex --log build/root.log
```

Do not treat every underfull box as a defect. Connect diagnostics to a visible symptom before editing.

### 4. Render and inspect the evidence pages

Find the earliest page where normal text flow first becomes abnormal; do not begin with the later page that merely looks worst. Render the affected page plus 1–3 pages before and after it. For a float queue or section-boundary problem, include the page of the first textual reference and every page through the misplaced float.

```bash
python scripts/render_pdf_pages.py build/root.pdf --pages 6-8,15 --output-dir layout-renders
```

Visually inspect each PNG at readable resolution. Check:

- float position relative to its first textual reference;
- blank space above, below, or between columns;
- clipping, overlap, illegible scaling, and caption separation;
- column balance and reading order;
- whether a float-only page is wasteful or instead substantially filled by related, readable material that improves the downstream queue;
- whether a float crosses into declarations, appendices, or references;
- whether a supposedly fixed page merely moved the defect elsewhere.

Record what is visible before touching the source.

### 5. Map each symptom to source

Locate the float by caption text or `\label`, then find its first `\ref`, `\autoref`, `\cref`, or equivalent textual reference. Read the surrounding paragraphs and all floats between the reference and the rendered placement.

Treat this rendered pattern as a likely cascading queue problem:

```text
normal text → unexpectedly large blank area → clustered later figures/tables
```

The blank area may be only a downstream symptom. Trace backward from the earliest abnormal page and identify the first float that failed to obtain a legal placement. Do not immediately edit spacing on the blank page.

For every suspicious float, record its source position, environment type, placement specifier, dimensions including caption/spacing where relevant, first textual reference, and actual PDF page. For consecutive same-class floats, also estimate whether their complete vertical footprints could share a legal float page; image height alone omits captions and float spacing. Then investigate blockers in this order:

1. forced `[H]` placement;
2. a float whose image, caption, and spacing are too tall or wide for a legal position;
3. constrained `figure*` or `table*` floats in two-column output;
4. consecutive floats with little or no intervening text;
5. `\FloatBarrier`;
6. `\clearpage` or `\newpage`;
7. manual `\vspace`, especially negative spacing;
8. unusual global float parameters.

For each problem, write a one-sentence causal hypothesis, for example:

- “Table 2 is on a vertically centered float-only page because `[p]` excludes text placement.”
- “Figures 6–8 form a late queue because three `figure*` environments occur after the discussion and are restricted to wide-float positions.”
- “The plot exceeds one column because a normal `figure` uses `width=\textwidth`.”

If the evidence does not support a cause, gather more evidence instead of applying a generic float hack.

### 6. Choose the smallest fix

Use this preference order, stopping as soon as a smaller change solves the cause:

1. Move the float environment close to, normally just after, its first textual reference while preserving prose order.
2. Replace an unnecessarily restrictive placement with a normal specifier such as `[t]`, `[tbp]`, or `[!t]` when the page evidence supports it. For consecutive starred floats, test float-page eligibility such as `[tp]` when a shared, well-filled float page could drain the queue; `p` expands the legal set and should not be added reflexively.
3. Correct width semantics: use `\linewidth` inside the current container, `\columnwidth` for an intentional single-column width, and `\textwidth` only for an intentional full-text-width object.
4. Resize an oversized or queue-dominating figure modestly when reducing its height creates a useful legal placement, while keeping labels legible at final PDF scale.
5. Use `figure`/`table` for one-column material and `figure*`/`table*` only when the content genuinely needs both columns.
6. Reorder nearby independent floats when queue ordering—not narrative order—is blocking placement.
7. Add a narrowly scoped float boundary only at a genuine semantic boundary and only after rendering proves it is needed.

Read [references/float-diagnostics.md](references/float-diagnostics.md) when the cause involves a two-column float queue, float-only pages, barriers, output-routine packages, or unexplained whitespace.

### 7. Edit conservatively

- Test one falsifiable causal hypothesis per iteration. Related symmetric floats may be changed as a diagnostic group when their queue interaction is the hypothesis; if the group works, minimize or bisect it before accepting the final source.
- Keep captions, labels, and textual references intact.
- Do not add packages until source ordering, float type, placement, and sizing have been tested.
- Explain any unavoidable template-sensitive change before making it.
- Never edit generated `.bbl`, `.aux`, or publisher class files as the fix.

Avoid unless the evidence shows that ordinary float behavior cannot meet the requirement:

- `[H]`, which stops floating and can create worse breaks;
- negative `\vspace` or manual `\hspace` compensation;
- `\newpage` or `\clearpage` used only to make one screenshot look better;
- arbitrary `\FloatBarrier` placement;
- global float-fraction or counter tuning;
- `geometry` changes, margin changes, page-size changes, font-size reductions, or document-class changes;
- fixed-position `strip`-like blocks that can clip when insufficient vertical space remains.

If an exception is truly necessary, state why all smaller options failed and verify the complete manuscript afterward.

### 8. Rebuild and compare

After every edit:

1. Recompile with the same command and confirm references/citations settle.
2. Re-read the warnings relevant to the changed source.
3. Render the affected page and its neighbors again.
4. Compare caption order, page count, blank areas, readability, and column balance with the baseline.
5. Inspect downstream float pages whenever the float queue changed.
6. Revert and investigate the queue again if one page improves but later pages gain blank pages, nearly empty columns, unnecessary float-only pages, remote float clusters, or illogical float order.

Do not classify every float-only page as a regression. Keep one when it is substantially occupied by logically related, readable floats, preserves caption order, and measurably improves citation proximity or a semantic boundary without creating new sparse pages downstream. Conversely, moving a float beside its first source reference is narratively cleaner but is not a placement success if the rendered page map is unchanged; record that outcome and continue diagnosing the queue.

Keep a compact iteration ledger with one row per edited build: hypothesis, exact source change, PDF/log artifact, page count and affected caption pages, relevant warnings, visible result, and `keep`, `refine`, or `revert`. Keep the untouched baseline and final QA separate from the edit-pass count. Use distinct build directories when practical so a rejected experiment remains auditable after its source change is reverted.

Repeat until the layout is acceptable or no template-compliant local fix exists. If blocked, report the constraint and the least harmful alternatives instead of silently weakening the template.

### 9. Perform final manuscript QA

Compile the complete manuscript from a clean-enough build state using the established toolchain. Then:

- inspect every changed page and adjacent page;
- inspect all pages between moved floats and their new positions;
- confirm every figure/table remains present, numbered, referenced, and readable;
- confirm no research float leaked into the bibliography or other prohibited region;
- when a boundary command is retained, confirm it did not merely move the queue into sparse pages, float-only pages, or empty columns immediately before the boundary;
- check for unresolved references/citations, fatal errors, overfull content, and unprocessed floats;
- when pagination changed substantially, review an all-page contact sheet or equivalent overview.

Finally search the full manuscript for `[H]`, `\FloatBarrier`, `\clearpage`, `\newpage`, `\vspace`, `\vspace*`, `figure*`, and `table*`. For every occurrence introduced or modified during the task, confirm that the final PDF proves it is necessary. Inspect every changed page, the page before, the page after, and any later page whose float position moved.

## Width and float rules for two-column papers

- A normal `figure` or `table` belongs to one column. Size its contents against `\linewidth` or `\columnwidth`.
- A starred `figure*` or `table*` spans both columns. Use it only when a one-column rendering would be unreadable.
- Wide floats have fewer legal positions than single-column floats and can create a queue. Several consecutive starred floats are a common cause of late artwork and blank columns.
- Two related starred floats restricted to `[t]` may remain serialized across text pages even when a float page could accommodate both. Compare their combined artwork, captions, and spacing, then test `[tp]` plus the smallest readable size reduction if the capacity hypothesis is plausible.
- Float order is constrained by source order and float class. A blocked early float can delay otherwise placeable later floats.
- Top-of-page placement before the paragraph containing the first reference may be technically legal but rhetorically awkward. Judge proximity and reading order visually.
- Do not shrink dense multi-panel figures until their labels are technically present but practically unreadable. Readability is part of correctness.
- After a grouped resize succeeds, increase the width toward the failed boundary to preserve readability, but stop at a conservative verified value rather than chasing an exact unstable threshold.

## Completion report

Return a concise report with one row per problem:

| Item | Visible symptom | Root cause | Source change | Verified result |
|---|---|---|---|---|
| Figure/Table label or page | What was wrong | Why LaTeX placed it that way | File and minimal edit | New page/position and QA result |

Also report:

- root TeX file, document class/options, compiler command, and output PDF;
- number of edited iterations, excluding the untouched baseline and final artifact-only QA, plus which passes were kept, refined, or reverted;
- pages inspected before and after;
- remaining relevant warnings or unresolved risks;
- confirmation that the template geometry and scholarly content were preserved.
