"""Generic MediaWiki wikitext syntax helpers: balanced `{{template}}` matching and splitting.

Plain regexes with a `(?=\\n}}|\\Z)` style lookahead (the approach `war/scrape.py` used before
C2) terminate a template's content at the *first* `}}` they see, which is wrong as soon as that
content contains a nested template of its own — e.g. a `{{efn|...}}` citation whose own closing
`}}` appears before the outer template's. Real Wikipedia infobox fields nest templates routinely
(citations inside `{{ubl|...}}` breakdowns, etc.), so matching needs to track brace depth instead
of guessing from the next literal `}}`. These helpers do that tracking once, for reuse by both
`war/scrape.py` (infobox field splitting) and `war/infobox_numbers.py` (numeric field parsing).
"""

import re

_TEMPLATE_NAME_RE = re.compile(r"\{\{\s*([^{}|]*)")


def template_name_at(text: str, open_pos: int) -> str:
    """Name of the template whose `{{` starts at `open_pos` (stripped, not case-normalized).

    >>> template_name_at("{{cite web|url=x}}", 0)
    'cite web'
    """
    match = _TEMPLATE_NAME_RE.match(text, open_pos)
    return match.group(1).strip() if match else ""


def balanced_template_end(text: str, open_pos: int) -> int:
    """Index just past the `}}` matching the `{{` at `open_pos`, tracking nested pairs.

    Falls back to `len(text)` if the template is never closed (truncated/malformed wikitext).

    >>> text = "{{a|{{b}}}} tail"
    >>> text[: balanced_template_end(text, 0)]
    '{{a|{{b}}}}'
    """
    depth = 0
    i, n = open_pos, len(text)
    while i < n - 1:
        two = text[i : i + 2]
        if two == "{{":
            depth += 1
            i += 2
        elif two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return n


def split_top_level(text: str, seps: str) -> list[str]:
    """Split `text` on any character in `seps`, ignoring occurrences nested inside `{{...}}` or
    `[[...]]`.

    Needed because a `{{ubl|a|[[X|b]]|c}}` template's items are pipe-separated, but a wikilink
    display alias (`[[X|b]]`) also uses `|` internally and must not be split on. Also needed for
    a wikilink *target* containing one of the separator characters itself (e.g.
    `[[Arthur Wellesley, 1st Duke of Wellington|Arthur Wellesley]]` has a comma before the `|`) —
    a plain `re.split` on `,` would break the link in two.

    >>> split_top_level("a|[[X|b]]|c", "|")
    ['a', '[[X|b]]', 'c']
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    i, n = 0, len(text)
    while i < n:
        two = text[i : i + 2]
        if two in ("{{", "[["):
            depth += 1
            current.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth = max(depth - 1, 0)
            current.append(two)
            i += 2
            continue
        if depth == 0 and text[i] in seps:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(text[i])
        i += 1
    parts.append("".join(current))
    return parts


def strip_templates(text: str, should_drop) -> str:
    """Delete every `{{...}}` template for which `should_drop(name)` is true.

    Recurses into templates that are kept, so a dropped template nested inside a kept one
    (e.g. a `{{sfn|...}}` citation inside a kept `{{ubl|...}}` breakdown) is still removed.

    >>> strip_templates("x {{sfn|a}} {{ubl|y {{sfn|b}}}}", lambda n: n == "sfn")
    'x  {{ubl|y }}'
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i : i + 2] == "{{":
            end = balanced_template_end(text, i)
            name = template_name_at(text, i)
            if should_drop(name):
                i = end
                continue
            inner = text[i + 2 : end - 2]
            out.append("{{" + strip_templates(inner, should_drop) + "}}")
            i = end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)
