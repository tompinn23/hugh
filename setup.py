#!/usr/bin/env python3
import csv

import polib
import pathlib

LOCALE_DIR = pathlib.Path("locales")


def load_csv(name: str, lang: str = "en"):
    po = polib.POFile()

    # Optional header
    po.metadata = {
        "Project-Id-Version": f"{name}",
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": lang,
    }

    with open(f"locales/{lang}/{name}.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = polib.POEntry(
                msgid=row["symbol"].lower(),
                msgstr=row["name"],
            )
            po.append(entry)

    po.save(f"locales/{lang}/LC_MESSAGES/{name}.po")
    print(f"Wrote locales/{lang}/LC_MESSAGES/{name}.po")


def compile_po():
    for po in LOCALE_DIR.rglob("*.po"):
        mo = po.with_suffix(".mo")
        print(f"Compiling {po} → {mo}")
        polib.pofile(str(po)).save_as_mofile(str(mo))


load_csv("commodity")
compile_po()
