#!/usr/bin/env python
"""Validate WhatsApp presence via checknumber.ai (the module's primary backend).

Submit E.164 numbers -> poll -> download -> emit a `wa_id,whatsapp` map CSV that
`emit_recipients_csv.py` consumes. Definitive yes/no (replaces the wa.me heuristic).

Key from env CHECKNUMBER_API_KEY (never hardcoded). API: POST /tasks (multipart
file + task_type=ws) -> POST /gettasks (task_id) until status=exported -> download
result_url (a .zip containing all.csv with columns number,activated).

IMPORTANT: checknumber requires a MINIMUM BATCH OF 100 numbers per job. Pre-filter
landlines with classify_phones.py first (don't pay to confirm a fijo), then
accumulate >=100 mobile candidates across localities/verticals before validating.

Usage:
  # input: one E.164 (or digits) per line, OR a CSV with a wa_id/phone column
  py checknumber_validate.py --in candidates.txt --out wa_map.csv
  py checknumber_validate.py --in prospects.review.csv --col wa_id --out wa_map.csv
  # offline re-parse of a previously saved result archive (no API call):
  py checknumber_validate.py --from result.zip --out wa_map.csv
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import uuid
import zipfile
import urllib.request
import urllib.error

API_BASE = "https://api.checknumber.ai/v1"
MIN_BATCH = 100


def die(m):
    print("ERROR:", m); sys.exit(1)


def key():
    k = os.environ.get("CHECKNUMBER_API_KEY")
    return k or die("set CHECKNUMBER_API_KEY in the environment")


def multipart(fields, files):
    b = "----cn" + uuid.uuid4().hex
    buf = io.BytesIO()
    for n, v in fields.items():
        buf.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode())
    for n, (fn, c) in files.items():
        buf.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"; filename=\"{fn}\"\r\n".encode())
        buf.write(b"Content-Type: text/plain\r\n\r\n")
        buf.write(c if isinstance(c, bytes) else c.encode()); buf.write(b"\r\n")
    buf.write(f"--{b}--\r\n".encode())
    return f"multipart/form-data; boundary={b}", buf.getvalue()


def post(path, fields, files=None):
    ct, body = multipart(fields, files or {})
    req = urllib.request.Request(API_BASE + path, data=body, method="POST")
    req.add_header("X-API-Key", key()); req.add_header("Content-Type", ct)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        die(f"{path} HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")


def download(url):
    req = urllib.request.Request(url); req.add_header("X-API-Key", key())
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def parse_result(data: bytes):
    """Return dict digits->status from the result .zip (all.csv: number,activated)."""
    rows = []
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        m = next((n for n in z.namelist() if n.endswith(".csv")), None)
        if m:
            rows = list(csv.reader(io.StringIO(z.read(m).decode("utf-8-sig", "replace"))))
    else:
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", "replace"))))
    if not rows:
        return {}
    h = [c.strip().lower() for c in rows[0]]
    ni = h.index("number") if "number" in h else 0
    wi = next((h.index(c) for c in ("activated", "whatsapp", "status") if c in h), 1)
    out = {}
    for r in rows[1:]:
        if r and len(r) > max(ni, wi):
            out[re.sub(r"\D", "", r[ni])] = r[wi].strip().lower()
    return out


def read_numbers(path, col):
    raw = open(path, encoding="utf-8-sig").read()
    if path.lower().endswith(".csv") or col:
        rows = list(csv.reader(io.StringIO(raw)))
        hdr = [c.strip().lower() for c in rows[0]]
        ci = hdr.index(col.lower()) if (col and col.lower() in hdr) else \
            next((hdr.index(c) for c in ("wa_id", "phone", "number", "telefono") if c in hdr), 0)
        vals = [r[ci] for r in rows[1:] if r and len(r) > ci]
    else:
        vals = raw.splitlines()
    nums, seen = [], set()
    for v in vals:
        d = re.sub(r"\D", "", v)
        if d and d not in seen:
            seen.add(d); nums.append(d)
    return nums


def fillers(have, need):
    out, n, seen = [], 90000000, set(have)
    while len(out) < need:
        c = f"54911{n:08d}"
        if c not in seen:
            out.append(c); seen.add(c)
        n += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--col", default=None, help="CSV column with the number")
    ap.add_argument("--from", dest="frm", help="offline: parse a saved result file")
    ap.add_argument("--out", required=True, help="output map CSV: wa_id,whatsapp")
    ap.add_argument("--pad", action="store_true",
                    help="pad to 100 with synthetic fillers (WASTES credits; prefer accumulating real numbers)")
    a = ap.parse_args()

    if a.frm:
        parsed = parse_result(open(a.frm, "rb").read())
    else:
        if not a.inp:
            die("need --in <file> or --from <saved result>")
        nums = read_numbers(a.inp, a.col)
        if not nums:
            die("no numbers parsed from input")
        real = list(nums)
        if len(nums) < MIN_BATCH:
            if not a.pad:
                die(f"only {len(nums)} numbers; checknumber needs >= {MIN_BATCH}. "
                    f"Accumulate more mobile candidates, or pass --pad (wastes credits).")
            nums = nums + fillers(set(nums), MIN_BATCH - len(nums))
            print(f"padded to {len(nums)} with synthetic fillers (excluded from output)")
        txt = "\n".join(nums) + "\n"
        job = post("/tasks", {"task_type": "ws"}, {"file": ("numbers.txt", txt)})
        tid = job.get("task_id") or job.get("id") or die(f"no task_id: {job}")
        print("submitted task", tid, "total", job.get("total"))
        deadline, last, status = time.time() + 600, None, None
        while time.time() < deadline:
            last = post("/gettasks", {"task_id": tid})
            status = (last.get("status") or "").lower()
            print(f"  status={status} success={last.get('success')} failure={last.get('failure')}")
            if status in ("exported", "failed", "error"):
                break
            time.sleep(5)
        if status != "exported":
            die(f"not exported: {json.dumps(last)}")
        url = last.get("result_url") or last.get("resultUrl") or die("no result_url")
        parsed = parse_result(download(url))
        parsed = {k: v for k, v in parsed.items() if k in set(real)}  # drop fillers

    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["wa_id", "whatsapp"])
        for d, v in parsed.items():
            w.writerow([d, v])
    yes = sum(1 for v in parsed.values() if v == "yes")
    print(f"wrote {a.out}: {len(parsed)} numbers | yes={yes} no={len(parsed)-yes}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
