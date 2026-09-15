#!/usr/bin/env python3
"""Read-only static and log audit for LaTeX layout investigations."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "build",
    "dist",
    "node_modules",
    "output",
    "tmp",
}

FLOAT_RE = re.compile(
    r"\\begin\{(?P<env>figure\*?|table\*?)\}"
    r"\s*(?:\[(?P<placement>[^\]]*)\])?"
    r"(?P<body>.*?)"
    r"\\end\{(?P=env)\}",
    re.DOTALL,
)
DOC_RE = re.compile(r"\\documentclass(?:\[(?P<options>[^\]]*)\])?\{(?P<class>[^}]+)\}")
INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[(?P<opts>[^\]]*)\])?\{(?P<path>[^}]+)\}")
REF_RE = re.compile(r"\\(?:ref|autoref|cref|Cref|eqref)\{([^}]+)\}")


def strip_comments(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines(keepends=True):
        cut = None
        for index, char in enumerate(line):
            if char != "%":
                continue
            slashes = 0
            probe = index - 1
            while probe >= 0 and line[probe] == "\\":
                slashes += 1
                probe -= 1
            if slashes % 2 == 0:
                cut = index
                break
        cleaned.append(line if cut is None else line[:cut] + ("\n" if line.endswith("\n") else ""))
    return "".join(cleaned)


def tex_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.tex"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def discover_main(root: Path) -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in tex_files(root):
        try:
            text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if not DOC_RE.search(text) or "\\begin{document}" not in text:
            continue
        score = 0
        if path.stem.lower() in {"main", "root", "paper", "manuscript"}:
            score += 10
        score += min(len(INCLUDE_RE.findall(text)), 5)
        score -= len(path.relative_to(root).parts)
        candidates.append((score, path))
    if not candidates:
        raise SystemExit("No .tex file containing both \\documentclass and \\begin{document} was found.")
    candidates.sort(key=lambda item: (-item[0], str(item[1])))
    return candidates[0][1]


def resolve_main(root: Path, value: str | None) -> Path:
    if value is None:
        return discover_main(root)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise SystemExit(f"Main TeX file not found: {candidate}")
    return candidate


def included_sources(main: Path) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen or not path.is_file():
            return
        seen.add(path)
        ordered.append(path)
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for match in INCLUDE_RE.finditer(text):
            child = Path(match.group(1))
            if child.suffix == "":
                child = child.with_suffix(".tex")
            if not child.is_absolute():
                child = path.parent / child
            visit(child)

    visit(main)
    return ordered


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def compact_tex(value: str, limit: int = 100) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def balanced_group(text: str, start: int, opening: str, closing: str) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != opening:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opening and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == closing and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    return None


def caption_text(body: str) -> str | None:
    command = re.search(r"\\caption\b", body)
    if not command:
        return None
    index = command.end()
    while index < len(body) and body[index].isspace():
        index += 1
    if index < len(body) and body[index] == "[":
        optional = balanced_group(body, index, "[", "]")
        if optional is None:
            return None
        index = optional[1]
        while index < len(body) and body[index].isspace():
            index += 1
    required = balanced_group(body, index, "{", "}")
    return required[0] if required else None


def prose_word_count(text: str) -> int:
    """Estimate prose between floats after removing LaTeX control sequences."""
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\s*\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}$&_^~#%]", " ", text)
    return len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", text))


def inventory(sources: list[Path], root: Path) -> tuple[list[dict], list[dict], list[dict], dict[str, dict]]:
    floats: list[dict] = []
    risky: list[dict] = []
    consecutive_groups: list[dict] = []
    first_refs: dict[str, dict] = {}
    risk_patterns = {
        "forced_H": re.compile(r"\\begin\{(?:figure|table)\*?\}\s*\[[^\]]*H[^\]]*\]"),
        "negative_vspace": re.compile(r"\\vspace\*?\s*\{\s*-"),
        "page_break": re.compile(r"\\(?:newpage|clearpage)\b"),
        "float_barrier": re.compile(r"\\FloatBarrier\b"),
        "geometry_change": re.compile(r"\\(?:geometry|newgeometry)\b"),
        "global_float_tuning": re.compile(r"\\(?:topfraction|bottomfraction|textfraction|floatpagefraction|dbltopfraction|setcounter\{(?:topnumber|bottomnumber|totalnumber|dbltopnumber))"),
    }

    for source in sources:
        raw = source.read_text(encoding="utf-8", errors="replace")
        text = strip_comments(raw)
        relative = str(source.relative_to(root)) if source.is_relative_to(root) else str(source)

        source_matches = list(FLOAT_RE.finditer(text))
        source_floats: list[dict] = []
        for match in source_matches:
            body = match.group("body")
            caption = caption_text(body)
            label_match = LABEL_RE.search(body)
            graphics = []
            for graphic in GRAPHICS_RE.finditer(body):
                options = graphic.group("opts") or ""
                width_match = re.search(r"(?:^|,)\s*width\s*=\s*([^,]+)", options)
                graphics.append(
                    {
                        "path": graphic.group("path"),
                        "width": width_match.group(1).strip() if width_match else None,
                    }
                )
            record = {
                "file": relative,
                "line": line_number(text, match.start()),
                "environment": match.group("env"),
                "placement": match.group("placement"),
                "label": label_match.group(1) if label_match else None,
                "caption": compact_tex(caption) if caption else None,
                "graphics": graphics,
            }
            floats.append(record)
            source_floats.append(record)

        current_group: list[dict] = []
        for index in range(len(source_matches) - 1):
            first_match = source_matches[index]
            next_match = source_matches[index + 1]
            words = prose_word_count(text[first_match.end() : next_match.start()])
            if words < 20:
                if not current_group:
                    current_group.append(source_floats[index])
                current_group.append(source_floats[index + 1])
            elif current_group:
                consecutive_groups.append(
                    {
                        "file": relative,
                        "prose_threshold_words": 20,
                        "members": current_group,
                    }
                )
                current_group = []
        if current_group:
            consecutive_groups.append(
                {
                    "file": relative,
                    "prose_threshold_words": 20,
                    "members": current_group,
                }
            )

        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in risk_patterns.items():
                if pattern.search(line):
                    risky.append({"file": relative, "line": line_no, "kind": name, "source": compact_tex(line)})
            for reference in REF_RE.finditer(line):
                for label in (item.strip() for item in reference.group(1).split(",")):
                    first_refs.setdefault(label, {"file": relative, "line": line_no})

    return floats, risky, consecutive_groups, first_refs


def log_findings(log_path: Path | None) -> list[dict]:
    if log_path is None or not log_path.is_file():
        return []
    patterns = {
        "latex_error": re.compile(r"^! (?:LaTeX|Package).*Error:|^! Emergency stop", re.MULTILINE),
        "float_too_large": re.compile(r"^LaTeX Warning: Float too large.*$", re.MULTILINE),
        "unprocessed_floats": re.compile(r"Too many unprocessed floats|Float\(s\) lost", re.IGNORECASE),
        "float_spec_changed": re.compile(r"`h' float specifier changed to `ht'", re.IGNORECASE),
        "overfull_box": re.compile(r"^Overfull \\[hv]box.*$", re.MULTILINE),
        "underfull_box": re.compile(r"^Underfull \\[hv]box.*$", re.MULTILINE),
        "undefined_reference": re.compile(r"undefined references?|Citation .* undefined", re.IGNORECASE),
        "rerun_needed": re.compile(r"Rerun to get cross-references right|Label\(s\) may have changed", re.IGNORECASE),
    }
    text = log_path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict] = []
    for kind, pattern in patterns.items():
        matches = [compact_tex(match.group(0), 180) for match in pattern.finditer(text)]
        if matches:
            findings.append({"kind": kind, "count": len(matches), "examples": matches[:5]})
    return findings


def engine_hint(main_text: str, root: Path) -> str:
    magic = re.search(r"^\s*%\s*!TEX\s+program\s*=\s*([^\s]+)", main_text, re.IGNORECASE | re.MULTILINE)
    if magic:
        return f"magic-comment:{magic.group(1)}"
    rc = root / ".latexmkrc"
    if rc.is_file():
        rc_text = rc.read_text(encoding="utf-8", errors="replace")
        if "xelatex" in rc_text.lower():
            return ".latexmkrc:xelatex"
        if "lualatex" in rc_text.lower():
            return ".latexmkrc:lualatex"
        return ".latexmkrc:present"
    return "not-detected"


def build_report(root: Path, main: Path, log_path: Path | None) -> dict:
    raw_main = main.read_text(encoding="utf-8", errors="replace")
    main_text = strip_comments(raw_main)
    doc_match = DOC_RE.search(main_text)
    sources = included_sources(main)
    floats, risky, consecutive_groups, first_refs = inventory(sources, root)
    for item in floats:
        label = item.get("label")
        item["first_reference"] = first_refs.get(label) if label else None
        reference = item["first_reference"]
        item["reference_relation"] = None
        if reference and reference["file"] == item["file"]:
            item["reference_relation"] = "before-float" if reference["line"] < item["line"] else "after-float"
        width_findings = []
        for graphic in item["graphics"]:
            width = graphic["width"] or ""
            if not item["environment"].endswith("*") and "\\textwidth" in width:
                width_findings.append("page-wide width used in a single-column float")
            if item["environment"].endswith("*") and "\\columnwidth" in width:
                width_findings.append("column width used in a full-width float")
        item["width_findings"] = sorted(set(width_findings))

    detected_log = log_path
    if detected_log is None:
        adjacent = main.with_suffix(".log")
        detected_log = adjacent if adjacent.is_file() else None

    return {
        "root": str(root),
        "main": str(main),
        "document_class": doc_match.group("class") if doc_match else None,
        "class_options": [part.strip() for part in (doc_match.group("options") or "").split(",") if part.strip()] if doc_match else [],
        "engine_hint": engine_hint(raw_main, root),
        "sources": [str(path.relative_to(root)) if path.is_relative_to(root) else str(path) for path in sources],
        "floats": floats,
        "consecutive_float_groups": consecutive_groups,
        "risky_constructs": risky,
        "log": str(detected_log) if detected_log else None,
        "log_findings": log_findings(detected_log),
    }


def print_text(report: dict) -> None:
    print(f"Main: {report['main']}")
    options = ",".join(report["class_options"]) or "(none)"
    print(f"Class: {report['document_class']} [{options}]")
    print(f"Engine hint: {report['engine_hint']}")
    print(f"Included sources: {len(report['sources'])}")
    print(f"Floats: {len(report['floats'])}")
    for item in report["floats"]:
        identity = item["label"] or item["caption"] or "(unlabelled)"
        place = item["placement"] if item["placement"] is not None else "default"
        widths = ", ".join(graphic["width"] or "unspecified" for graphic in item["graphics"]) or "n/a"
        ref = item["first_reference"]
        ref_text = f"{ref['file']}:{ref['line']}" if ref else "not found"
        print(f"  {item['file']}:{item['line']} {item['environment']} [{place}] {identity}")
        relation = item["reference_relation"] or "unknown"
        print(f"    graphic widths: {widths}; first reference: {ref_text} ({relation})")
        for finding in item["width_findings"]:
            print(f"    width finding: {finding}")
    print(f"Consecutive float groups: {len(report['consecutive_float_groups'])}")
    for group in report["consecutive_float_groups"]:
        members = ", ".join(
            f"{item['environment']}@{item['line']}:{item['label'] or '(unlabelled)'}"
            for item in group["members"]
        )
        print(f"  {group['file']}: {members}")
    print(f"Risky constructs: {len(report['risky_constructs'])}")
    for item in report["risky_constructs"]:
        print(f"  {item['file']}:{item['line']} {item['kind']}: {item['source']}")
    print(f"Log: {report['log'] or '(not found)'}")
    for finding in report["log_findings"]:
        print(f"  {finding['kind']}: {finding['count']}")
        for example in finding["examples"]:
            print(f"    {example}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="LaTeX project root")
    parser.add_argument("--main", help="Root TeX file, relative to project root or absolute")
    parser.add_argument("--log", help="LaTeX log file, relative to project root or absolute")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Project root not found: {root}")
    main_path = resolve_main(root, args.main)
    log_path = None
    if args.log:
        log_path = Path(args.log).expanduser()
        if not log_path.is_absolute():
            log_path = root / log_path
        log_path = log_path.resolve()
    report = build_report(root, main_path, log_path)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_text(report)


if __name__ == "__main__":
    main()
