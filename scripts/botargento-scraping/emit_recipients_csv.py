#!/usr/bin/env python
"""Turn enriched scraped rows into the seed-ready outreach.recipients CSV.

Handoff to `bot-argento-sales/Sales Automation/scripts/seed-recipients.mjs`.
It classifies each phone (drops landlines), then uses checknumber.ai's definitive
yes/no (the module's primary validation backend) to keep only numbers that are on
WhatsApp, and writes TWO files:

  1. <out>.csv          -- seed contract, exactly:
       wa_id,business_name,contact_name,vertical,source,opt_in_basis
     `opt_in_basis` is LEFT BLANK on purpose (seed-recipients.mjs skips blank-basis
     rows until you set a deliberate, defensible basis per batch).
  2. <out>.review.csv   -- richer human-review file (Telefono/Localidad/Direccion/
     Confianza/WhatsApp). The Source column is always populated.

Validation source (primary): --checknumber <map.csv> with header `wa_id,whatsapp`
(produced by checknumber_validate.py). Only `whatsapp=yes` rows are kept.

checknumber returns only yes/no, NOT a profile name, so `contact_name` is blank by
default. Optionally enrich it from a free wa.me pass: --wa-names <bulk_get.json>
(parsed by check_whatsapp.py's profile_name; legacy/optional).

Input: enriched listing CSV (header, case-insensitive). Recognized columns:
name|nombre, phone|telefono, address|direccion, localidad, source|fuente.

Usage:
  py emit_recipients_csv.py prospects.in.csv --vertical architecture \
     --source "Cylex+Google Maps" --checknumber wa_map.csv \
     [--wa-names wa.json] [--keep-unknown] --out prospects-architecture
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify_phones import classify          # noqa: E402


def col(header, *names):
    low = [h.strip().lower() for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    return -1


def load_checknumber(path):
    """map.csv (wa_id,whatsapp) -> {digits: 'yes'/'no'}."""
    import re
    out = {}
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    if not rows:
        return out
    h = [c.strip().lower() for c in rows[0]]
    ni = h.index("wa_id") if "wa_id" in h else 0
    wi = h.index("whatsapp") if "whatsapp" in h else 1
    for r in rows[1:]:
        if r and len(r) > max(ni, wi):
            out[re.sub(r"\D", "", r[ni])] = r[wi].strip().lower()
    return out


def load_wa_names(path):
    """Optional contact_name enrichment from a wa.me bulk_get JSON."""
    import re
    from check_whatsapp import profile_name
    data = json.load(open(path, encoding="utf-8"))
    rows = data["result"] if isinstance(data, dict) else data
    out = {}
    for page in rows:
        m = re.search(r"phone=(\d+)", page.get("url", ""))
        if m:
            out[m.group(1)] = profile_name(page.get("content", [])) or ""
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv")
    ap.add_argument("--vertical", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--checknumber", help="checknumber map CSV (wa_id,whatsapp) — primary validation")
    ap.add_argument("--wa-names", dest="wa_names", help="optional wa.me bulk_get JSON for contact_name")
    ap.add_argument("--keep-unknown", action="store_true",
                    help="also keep mobiles absent from the checknumber map (validation unknown)")
    ap.add_argument("--out", default="prospects")
    a = ap.parse_args()

    cn = load_checknumber(a.checknumber) if a.checknumber else {}
    names = load_wa_names(a.wa_names) if a.wa_names else {}
    if not cn:
        print("WARNING: no --checknumber map given; validation is unknown for all rows.")

    rows = list(csv.reader(open(a.input_csv, encoding="utf-8-sig")))
    if not rows:
        sys.exit("Empty input CSV")
    h = rows[0]
    ci = {"name": col(h, "name", "nombre", "business_name"),
          "phone": col(h, "phone", "telefono", "teléfono"),
          "addr": col(h, "address", "direccion", "dirección"),
          "loc": col(h, "localidad", "locality"),
          "src": col(h, "source", "fuente")}
    if ci["name"] == -1 or ci["phone"] == -1:
        sys.exit("Input CSV needs at least name and phone columns")

    seed, review = [], []
    for r in rows[1:]:
        get = lambda k: (r[ci[k]].strip() if ci[k] != -1 and ci[k] < len(r) else "")
        name, phone = get("name"), get("phone")
        if not name or not phone:
            continue
        conf, wadigits = classify(phone)
        if not wadigits:                        # landline/undetectable → not WhatsApp-eligible
            continue
        status = cn.get(wadigits)               # 'yes' / 'no' / None(unknown)
        if cn:
            if status == "no":
                continue
            if status is None and not a.keep_unknown:
                continue
        contact = names.get(wadigits, "")
        source = get("src") or a.source
        seed.append([wadigits, name, contact, a.vertical, source, ""])   # opt_in_basis blank
        review.append([wadigits, name, contact, a.vertical, source,
                       phone, get("loc"), get("addr"), conf,
                       status or ("unknown" if cn else "not-checked")])

    base = a.out
    with open(base + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["wa_id", "business_name", "contact_name", "vertical", "source", "opt_in_basis"])
        w.writerows(seed)
    with open(base + ".review.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["wa_id", "business_name", "contact_name", "vertical", "source",
                    "Telefono", "Localidad", "Direccion", "Confianza", "WhatsApp"])
        w.writerows(review)

    print(f"seed   -> {base}.csv ({len(seed)} rows, opt_in_basis blank by design)")
    print(f"review -> {base}.review.csv")
    print("NEXT: set a defensible opt_in_basis per batch, then "
          "seed-recipients.mjs --campaign <id> " + base + ".csv > seed.sql")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
