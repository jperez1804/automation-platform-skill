#!/usr/bin/env python
"""Parse the wa.me pages fetched via scrapling bulk_get to validate WhatsApp.

Feed it the JSON the MCP returns/saves for a `bulk_get` over wa.me URLs
(`{"result":[{content:[...], url:"...api.whatsapp.com/send/?phone=NNN..."}]}`).

For each number it prints the WhatsApp status:
  Confirmed  -> the page shows a profile name (real WhatsApp account w/ public name)
  Unconfirmed-> the page shows only "Chat on WhatsApp with +54 ..." (bare number)

Note: "Unconfirmed" does NOT mean the number lacks WhatsApp (name may be hidden).
The only certainty is sending a message — don't.

Usage:
    py check_whatsapp.py <bulk_get_result.json>
"""
import json
import re
import sys


def profile_name(content):
    """Return the profile name shown before 'Open app', or None."""
    lines = [l.strip() for l in
             ("\n".join(content) if isinstance(content, list) else content).split("\n")]
    for i, line in enumerate(lines):
        if line == "Open app" and i > 0:
            prev = lines[i - 1]
            if prev.startswith("Chat on WhatsApp with") or not prev:
                return None            # bare number => no public profile
            return prev
    return None


def main(path):
    data = json.load(open(path, encoding="utf-8"))
    rows = data["result"] if isinstance(data, dict) else data
    for page in rows:
        m = re.search(r"phone=(\d+)", page.get("url", ""))
        num = m.group(1) if m else "?"
        name = profile_name(page.get("content", []))
        status = "Confirmed" if name else "Unconfirmed"
        print(f"[{status:11}] {num} {('-> ' + name) if name else ''}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
