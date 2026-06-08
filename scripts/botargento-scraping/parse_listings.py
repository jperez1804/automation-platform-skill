#!/usr/bin/env python
"""Parse Cylex (markdown) listing pages saved by the scrapling MCP.

Usage:
    py parse_listings.py <tool-results-file.json> [<file2.json> ...]

Each input file is the JSON the MCP saves for big results:
    {"result": [{"status":200, "content": ["...markdown..."], "url": "..."}, ...]}

Prints one record per listing: name | phone | address | url
Adjust LOCALITIES / BAD_WORDS for your target area & category.
"""
import json
import re
import sys

PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{6,}\d$")
LINK_RE = re.compile(
    r"^\[([^\]]+)\]\((https://www\.cylex\.com\.ar/[^)]*"
    r"(?:-\d+\.html|p\?id=\d+[^)]*))\)$"
)

# Tune these for your run:
LOCALITIES = ["Banfield", "Lomas de Zamora", "Temperley", "Turdera", "Llavallol"]
BAD_WORDS = ["inmobiliaria", "propiedades", "hosting", "grabaci",
             "clx consulting", "laqueado", "tinglados", "planos municipales"]


def parse_page(content):
    text = "\n".join(content) if isinstance(content, list) else content
    items, cur = [], None
    for line in (l.strip() for l in text.split("\n")):
        m = LINK_RE.match(line)
        if m:
            cur = {"name": m.group(1), "url": m.group(2),
                   "phone": None, "addr": None}
            items.append(cur)
            continue
        if cur is None:
            continue
        if (cur["phone"] is None and PHONE_RE.match(line)
                and sum(c.isdigit() for c in line) >= 7):
            cur["phone"] = line
        elif (cur["addr"] is None and "," in line
              and not line.startswith(("!", "["))
              and "cylex" not in line.lower()):
            cur["addr"] = line
    return items


def main(paths):
    seen = {}
    for path in paths:
        data = json.load(open(path, encoding="utf-8"))
        for page in data["result"]:
            for it in parse_page(page["content"]):
                seen.setdefault(it["url"], it)  # dedup by company URL
    for it in seen.values():
        addr = it["addr"] or ""
        if LOCALITIES and not any(x in addr for x in LOCALITIES):
            continue
        if any(b in it["name"].lower() for b in BAD_WORDS):
            continue
        print(f"{it['name']} | {it['phone']} | {addr} | {it['url']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
