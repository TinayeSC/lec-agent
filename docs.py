"""Read README.md back to the user at the prompt.

The README is the project's documentation of record, so /usage renders it
directly rather than keeping a second copy of the same prose in the source —
one file to update, and the help text can never drift from the docs.
"""

import re
import textwrap
from pathlib import Path

README = Path("README.md")
WRAP = 78

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
RESET = "\033[0m"


def load_sections():
    """Split README.md on its '## ' headings into {title: body}."""
    if not README.exists():
        return {}

    sections, title, buf = {}, None, []
    for line in README.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title is not None:
                sections[title] = "\n".join(buf).strip()
            title, buf = line[3:].strip(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        sections[title] = "\n".join(buf).strip()
    return sections


def find_section(sections, query):
    """Match by 1-based number, exact title, or unique substring."""
    titles = list(sections)
    query = query.strip()
    if not query:
        return None, "no section given"

    if query.isdigit():
        i = int(query) - 1
        if 0 <= i < len(titles):
            return titles[i], None
        return None, f"no section {query} — pick 1-{len(titles)}"

    lowered = query.lower()
    for title in titles:
        if title.lower() == lowered:
            return title, None

    hits = [t for t in titles if lowered in t.lower()]
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, f"'{query}' matches {len(hits)}: {', '.join(hits)}"
    return None, f"no section matching '{query}'"


ITALIC = "\033[3m"

# close codes that end ONE attribute rather than resetting everything, so
# nested emphasis (**bold with *italic* inside**) doesn't clip the outer style
UNBOLD = "\033[22m"
UNITALIC = "\033[23m"
UNCOLOUR = "\033[39m"

# a line that starts a new block, so paragraph/list continuation must stop
BLOCK_START = re.compile(r"^(\||```|#|>|-{3,}\s*$|\s*([-*]|\d+\.)\s)")


def _inline(text):
    """**bold**, *italic* and `code` -> ANSI. Never applied inside fences."""
    text = re.sub(r"\*\*(.+?)\*\*", BOLD + r"\1" + UNBOLD, text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", ITALIC + r"\1" + UNITALIC, text)
    text = re.sub(r"`([^`]+?)`", CYAN + r"\1" + UNCOLOUR, text)
    return text


def _visible_len(text):
    return len(re.sub(r"\033\[[0-9;]*m", "", text))


def _render_table(rows):
    """Markdown pipe table -> aligned columns (markdown source is ragged)."""
    cells = []
    for row in rows:
        parts = [c.strip() for c in row.strip().strip("|").split("|")]
        if all(set(p) <= set("-: ") for p in parts):
            continue  # the |---|---| separator
        cells.append([_inline(p) for p in parts])
    if not cells:
        return []

    ncols = max(len(r) for r in cells)
    widths = [
        max(_visible_len(r[i]) for r in cells if len(r) > i)
        for i in range(ncols)
    ]

    out = []
    for n, row in enumerate(cells):
        padded = []
        for i, cell in enumerate(row):
            pad = " " * (widths[i] - _visible_len(cell))
            padded.append(cell + pad)
        out.append("  " + "  ".join(padded).rstrip())
        if n == 0:
            out.append("  " + DIM + "─" * min(sum(widths) + 2 * (ncols - 1), WRAP) + RESET)
    return out


def render(title, body):
    """Markdown -> terminal. Handles headings, fences, tables, lists, prose."""
    out = ["", f"  {BOLD}{CYAN}{title.upper()}{RESET}", f"  {DIM}{'─' * WRAP}{RESET}", ""]

    lines = body.splitlines()
    i = 0
    in_fence = False
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue

        if in_fence:
            out.append(f"    {DIM}{line}{RESET}")
            i += 1
            continue

        if line.startswith("|"):
            table = []
            while i < len(lines) and lines[i].startswith("|"):
                table.append(lines[i])
                i += 1
            out.extend(_render_table(table))
            out.append("")
            continue

        if line.startswith("### "):
            out.append(f"  {BOLD}{line[4:].strip()}{RESET}")
            i += 1
            continue

        if not line.strip():
            out.append("")
            i += 1
            continue

        if re.match(r"^-{3,}\s*$", line):
            out.append(f"  {DIM}{'─' * WRAP}{RESET}")
            i += 1
            continue

        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
        if bullet:
            indent, marker, text = bullet.groups()
            marker = "•" if marker in ("-", "*") else marker
            prefix = "  " + " " * len(indent) + f"{marker} "
            # a list item may run over several source lines — pull them in so
            # the whole item wraps as one block under a hanging indent
            item = [text.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
                item.append(lines[i].strip())
                i += 1
            wrapped = textwrap.wrap(_inline(" ".join(item)), WRAP - len(prefix)) or [""]
            out.append(prefix + wrapped[0])
            out.extend(" " * len(prefix) + w for w in wrapped[1:])
            continue

        if line.startswith("> "):
            quote = [line[2:].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(lines[i][2:].strip())
                i += 1
            for w in textwrap.wrap(_inline(" ".join(quote)), WRAP - 4):
                out.append(f"  {DIM}│{RESET} " + w)
            continue

        # ordinary prose — rejoin the paragraph, then wrap to WRAP
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        for w in textwrap.wrap(_inline(" ".join(para)), WRAP):
            out.append("  " + w)

    out.append("")
    return "\n".join(out)


def list_sections(sections):
    out = ["", f"  {BOLD}{CYAN}README SECTIONS{RESET}", f"  {DIM}{'─' * WRAP}{RESET}"]
    for n, title in enumerate(sections, 1):
        out.append(f"  {DIM}{str(n).rjust(2)}{RESET}  {title}")
    out.append("")
    out.append(f"  {DIM}Enter a number or part of a title. Blank to cancel.{RESET}")
    out.append("")
    return "\n".join(out)
