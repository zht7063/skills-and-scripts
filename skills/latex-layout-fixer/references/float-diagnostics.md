# Float diagnostics reference

Read this reference when ordinary source inspection does not immediately explain a float or page-layout symptom.

## Diagnose from the symptom

| Symptom | Likely causes | Evidence to collect | Preferred first fixes |
|---|---|---|---|
| Large blank area around a single float | `[p]` float-only placement; float too tall for text placement; restrictive placement list | Float specifier, float height, neighboring page renders, `Float too large` warning | Allow `[t]`/`[tbp]`; modestly resize; keep the float near its reference |
| Float appears many pages late | Early blocked float; many same-class floats; consecutive starred floats; source far from reference | Caption page map, source order of all preceding floats, log float warnings | Move floats near references; correct float type; reorder independent nearby floats |
| One empty column in a two-column page | Pending wide float; forced break/barrier; fixed non-float block; section-end imbalance | Page before/after, source boundary commands, starred-float queue | Remove unnecessary break; schedule wide float earlier; let following text fill the page |
| Figure is wider than its column | `\textwidth` used inside normal `figure`; nested container width ignored | `\includegraphics` width, environment type, rendered clipping/overflow | Use `width=\linewidth` or an appropriate fraction |
| Wide figure is unreadably small | Content incorrectly forced into one column | Figure density and label size at final render | Use `figure*` if the template permits; redesign artwork only with user authorization |
| Figures/tables appear after References | Late float queue not flushed at a safe boundary; source environments occur too late | Caption page map, bibliography start page, source locations | Move floats to discussion; repair queue; use one justified terminal boundary if necessary |
| Float order is surprising | Different float classes; starred versus unstarred queues; source order | Inventory every intervening float by type and source line | Align source order with narrative; avoid mixing forms without need |
| `Too many unprocessed floats` | Queue cannot drain; oversized/restrictive floats; large burst of floats | First blocked float, placement specs, sizes | Fix the first blocked float; relax placement; redistribute floats |
| Fixed full-width block is clipped | Non-floating output-routine construct inserted without enough remaining height | Bottom of rendered page, block height, package behavior | Return to a page-safe float; place at a safer source boundary |
| Blank area followed by clustered floats | An earlier float is blocking or constraining the queue | Earliest abnormal page, 1–3 neighboring pages, every preceding float through the cluster | Fix the first float that missed a legal placement; do not patch the blank page |

## Cascading float-queue diagnosis

When normal text is followed by an unexpectedly large blank region and then several accumulated figures or tables, assume the visible blank region may be downstream of an earlier blocker.

1. Find the earliest abnormal page rather than the most severe later page.
2. Inspect 1–3 pages before and after it.
3. Trace backward through all nearby `figure`, `figure*`, `table`, and `table*` environments.
4. Identify the first float that did not appear near its expected location.
5. Record its source position, type, placement, dimensions, caption size, first reference, and actual PDF page.
6. Test the most likely root cause with one change, rebuild the full manuscript, and check every downstream float that moved.

Use this blocker priority so symptom-level spacing changes do not distract from the queue's first failure:

1. `[H]`;
2. oversized float plus caption and spacing;
3. constrained starred float;
4. consecutive floats with little or no prose;
5. `\FloatBarrier`;
6. `\clearpage` or `\newpage`;
7. manual `\vspace`;
8. global float tuning.

If page N improves but pages N+1 through N+k become worse, revert the edit. A healthy queue improves or preserves surrounding pagination; it does not merely move the defect.

## Placement specifiers

- `t`: top of a text page.
- `b`: bottom of a text page where supported for that float form.
- `p`: a float-only page. Using only `[p]` prevents text from sharing the page; combining it with text-page eligibility, for example `[tp]`, expands the legal set rather than forcing a float-only page.
- `h`: approximately here, subject to LaTeX's constraints; it is not exact positioning.
- `!`: relaxes some internal float constraints for this float but does not create impossible space.
- `H`: supplied by the `float` package; makes the object non-floating. Treat it as an exception because it transfers page-breaking problems into the text stream.

Do not add every letter reflexively. Choose a small set that matches the desired legal positions. `[tbp]` is often more resilient than a single forced location.

## Page and queue mechanics

LaTeX schedules floats through queues rather than placing each object independently. Therefore:

1. Find the earliest float that has not placed as expected; it may be the real blocker.
2. Compare the float's height with available column/page height.
3. Check whether the placement list permits the visually desired location.
4. Inspect all floats of the same class between the source location and rendered page.
5. Change source order only when it remains consistent with the narrative.

For two or more consecutive wide floats, compare the sum of each complete float's artwork, caption, and vertical separation with the usable float-page height. If they plausibly fit together but `[t]` serializes them across text pages, test `[tp]`; combine it with a modest container-relative reduction only when the capacity calculation and render support that hypothesis. A source-anchor move that leaves the caption page map unchanged improves maintainability but has not drained the queue.

A `\clearpage` drains pending floats and starts a new page. This can be appropriate before a bibliography or appendix only when the venue and final layout require all research floats to finish first. It is too blunt for routine local spacing. `\newpage` starts a page but does not necessarily drain floats, so it can let them cross a semantic boundary.

`\FloatBarrier` is less global but still alters scheduling. Use it at a real section boundary after proving that source proximity and normal placement cannot prevent floats from crossing that boundary. Treat it as a semantic guard, not as a queue repair: a barrier-only result is unacceptable if it stops leakage by creating sparse pages, float-only pages, or empty columns immediately before the boundary. Repair the upstream queue separately, then retain the barrier only if the final render still proves it necessary.

## Two-column cautions

- Standard starred floats commonly have more restricted placement than single-column floats. Do not promise a bottom position without verifying the actual class, LaTeX version, and loaded packages.
- Packages that modify the output routine (`dblfloatfix`, `stfloats`, `cuted`, `balance`, and similar tools) can interact with publisher classes. Read template documentation and inspect the whole affected range before introducing one.
- Converting everything to starred floats usually worsens the queue. Use full width only where the content needs it.
- A float-only page is acceptable when it is substantially filled by logically related, readable floats and drains a queue without creating sparse neighbors. Reject low-occupancy or unrelated float-only pages even if they improve one boundary.
- A pair of related medium-width panels may sometimes share one `figure*`, but changing grouping can affect captions and semantics. Preserve caption numbering and obtain authorization if the scientific presentation changes.
- Manual column breaks and balancing commands can relocate downstream floats. Evaluate them as global layout changes, not local cosmetics.

## Width semantics

Use the width of the current container whenever possible:

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{plot}
  \caption{...}
\end{figure}
```

Inside a normal one-column float, `\linewidth` is usually the column width. Inside a full-width float or a full-width minipage, it follows that container. This makes the source more robust than hard-coding a page-wide dimension in every context.

A wide float can dominate a queue through height even when it fits within the page and produces no `Float too large` warning. If two or more related wide floats cannot obtain useful legal positions, test a modest container-relative reduction such as a fraction of `\linewidth`; keep the full-width float environment when the content still needs both columns. Resize a related group only when the group interaction is the hypothesis, then increase width toward the failed boundary and retain the largest conservative value that passes final-scale readability and pagination checks.

Keep aspect ratio unless deliberate cropping is part of the figure design. After resizing, inspect small labels, legends, line weights, and raster sharpness at the final PDF scale.

## Evidence checklist

Before declaring a fix complete, capture:

- original and final float page numbers;
- first textual-reference location;
- original and final placement specifiers and width expressions;
- original and final page images for the affected page plus neighbors;
- relevant warnings before and after;
- confirmation that later float ordering and the bibliography boundary remain correct.
- an iteration ledger identifying the hypothesis, source diff, artifact path, page/caption changes, warnings, visual outcome, and keep/refine/revert decision for every edited build; do not count the untouched baseline or final artifact-only QA as edit passes.

Search the full source for `[H]`, `\FloatBarrier`, `\clearpage`, `\newpage`, `\vspace`, `\vspace*`, `figure*`, and `table*`. Rejustify every occurrence introduced or modified during the task against the final render.
