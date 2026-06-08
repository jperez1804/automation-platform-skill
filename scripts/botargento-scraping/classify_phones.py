#!/usr/bin/env python
"""Classify Argentine phone numbers (mobile vs landline) and build wa.me links.

Mobile = WhatsApp-capable. See references/phone-validation.md for the rules and
the two bugs this code guards against (the '15' substring trap and dropping the
area code).

    from classify_phones import classify
    conf, wa = classify("011 15-5383-6814")   # -> ("Alta", "5491153836814")
    conf, wa = classify("011 4244-3667")       # -> ("No (fijo)", "")

Run directly to self-test:
    py classify_phones.py
"""
import re


def classify(ph):
    """Return (confidence, wa_digits). wa_digits is "" when not a WhatsApp pick.

    confidence in: "Alta" (mobile 15 group), "Media" (011 starting 2/3/6/7),
    "No (fijo)" (011 starting 4/5), "Desconocida".
    """
    toks = re.split(r"[\s\-]+", ph.strip())
    has15 = "15" in toks                       # only as a separate group, not substring
    d = re.sub(r"\D", "", ph)

    if d.startswith("011"):
        rest = d[3:]                           # "011" already contains area 11
        if rest.startswith("15"):
            rest = rest[2:]
        sub = rest                             # should be the 8-digit subscriber
        first = sub[0] if sub else ""
        if has15:
            conf = "Alta"
        elif first in "2367":
            conf = "Media"
        elif first in "45":
            conf = "No (fijo)"
        else:
            conf = "Desconocida"
        wa = "549" + "11" + sub if conf in ("Alta", "Media") and len(sub) == 8 else ""
        return conf, wa

    # provincial: 0<area><subscriber>
    if has15:
        area = re.match(r"0(\d+)", d).group(1)
        sub = d[1 + len(area):].replace("15", "", 1)
        return "Media", "549" + area + sub
    return "Desconocida", ""


def walink(wa_digits):
    return "https://wa.me/" + wa_digits if wa_digits else ""


if __name__ == "__main__":
    tests = [
        ("011 15-5383-6814", "Alta", "5491153836814"),   # mobile 15
        ("011 5152-3422",    "No (fijo)", ""),            # '15' substring trap
        ("011 2276-8374",    "Media", "5491122768374"),   # 011 starting 2
        ("011 4244-3667",    "No (fijo)", ""),            # landline
        ("03467 63-7758",    "Desconocida", ""),          # provincial, no 15
    ]
    ok = True
    for ph, ec, ew in tests:
        c, w = classify(ph)
        flag = "OK " if (c == ec and w == ew) else "FAIL"
        if flag == "FAIL":
            ok = False
        print(f"{flag} {ph:18} -> {c:11} {w}")
    print("ALL PASS" if ok else "SOME FAILED")
