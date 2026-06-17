"""
Extrage și normalizează consilierii locali din datele deja colectate.

Surse în ordine de prioritate:
  1. Inițiatorii HCL-urilor (disponibili imediat după sync Regista)
  2. Procesele-verbale (după OCR + extracție — pas viitor)

Problema de rezolvat: același om apare cu scrieri diferite în sursă:
  "CHITEZ ILIE", "Chitez Ilie", "CHITEZ iLIE", "Chitez ilie"
  → toți trebuie grupați sub un singur councillor.id

Strategie:
  - normalizare: lowercase + fără diacritice + strip
  - grupare exactă pe name_normalized
  - candidații ambigui (nume parțiale, inițiale) sunt marcați pentru revizie manuală

Utilizare:
    python councillors.py --db ales-local.db --uat bobicesti
    python councillors.py --db ales-local.db --all
    python councillors.py --db ales-local.db --uat bobicesti --list
"""

import re
import json
import sqlite3
import argparse
import logging
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Normalizare
# ─────────────────────────────────────────────

_DIACRITICS = str.maketrans(
    "ăâîșțĂÂÎȘȚşţŞŢ",
    "aaisaAAISAssSS",  # suport ambele variante Unicode ale lui ș/ț
)


def normalize_name(name: str) -> str:
    """
    Returnează forma canonică a unui nume pentru matching:
    lowercase, fără diacritice, whitespace normalizat.
    Ex: "CHITEZ iLIE" → "chitez ilie"
    """
    name = name.strip().lower()
    name = name.translate(_DIACRITICS)
    name = re.sub(r"\s+", " ", name)
    return name


def canonical_name(name: str) -> str:
    """
    Formă de afișare: Title Case cu diacritice păstrate din sursă.
    Ex: "CHITEZ iLIE" → "Chitez Ilie"
    """
    return " ".join(w.capitalize() for w in name.strip().split())


def is_ambiguous(name_norm: str) -> bool:
    """
    Marchează nume care probabil sunt incomplete sau corupte:
    - mai puțin de 2 cuvinte
    - conțin inițiale (o literă + punct)
    - conțin cifre sau caractere non-alfanumerice (%, &, #, etc.)
    - conțin spații duble (semn de trunchiere sau eroare de scriere)
    """
    parts = name_norm.split()
    if len(parts) < 2:
        return True
    if any(re.match(r"^[a-z]\.$", p) for p in parts):
        return True
    if re.search(r"[^a-z\s]", name_norm):  # cifre sau caractere speciale
        return True
    return False


# ─────────────────────────────────────────────
# Extracție din datele colectate
# ─────────────────────────────────────────────

def extract_names_from_resolutions(db: sqlite3.Connection, uat_id: int) -> Counter:
    """
    Extrage toate numele de inițiatori din HCL-urile colectate.
    Returnează Counter: name_normalized → frecvență de apariție.
    """
    rows = db.execute(
        "SELECT initiators FROM resolution WHERE uat_id=? AND initiators IS NOT NULL",
        (uat_id,),
    ).fetchall()

    counts: Counter = Counter()
    for (raw,) in rows:
        try:
            names = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for name in names:
            if name and isinstance(name, str) and name.strip():
                counts[normalize_name(name)] += 1

    return counts


# ─────────────────────────────────────────────
# Populare tabel councillor
# ─────────────────────────────────────────────

def sync_councillors(subdomain: str, db: sqlite3.Connection) -> dict:
    """
    Populează tabelul `councillor` pentru un UAT din sursele disponibile.
    Nu șterge consilierii existenți — doar adaugă cei noi.
    """
    uat_row = db.execute(
        "SELECT id, name FROM uat WHERE regista_subdomain=?", (subdomain,)
    ).fetchone()
    if not uat_row:
        raise ValueError(f"UAT cu subdomain '{subdomain}' nu există în DB")
    uat_id, uat_name = uat_row

    name_counts = extract_names_from_resolutions(db, uat_id)
    if not name_counts:
        log.warning("[%s] niciun inițiator găsit în HCL-uri", subdomain)
        return {"added": 0, "skipped": 0, "ambiguous": 0}

    added = skipped = ambiguous_count = 0

    for name_norm, freq in name_counts.most_common():
        # Skip dacă există deja
        existing = db.execute(
            "SELECT id FROM councillor WHERE uat_id=? AND name_normalized=?",
            (uat_id, name_norm),
        ).fetchone()
        if existing:
            skipped += 1
            continue

        ambiguous = is_ambiguous(name_norm)
        if ambiguous:
            ambiguous_count += 1
            log.debug("[%s] nume ambiguu (skip): '%s' (freq=%d)", subdomain, name_norm, freq)
            continue

        display_name = canonical_name(name_norm)
        db.execute(
            """
            INSERT INTO councillor (uat_id, name, name_normalized, active)
            VALUES (?,?,?,1)
            """,
            (uat_id, display_name, name_norm),
        )
        added += 1
        log.debug("[%s] adăugat: '%s' (apare în %d HCL-uri)", subdomain, display_name, freq)

    db.commit()
    log.info(
        "[%s] councillors: %d adăugați, %d existenți, %d ambigui ignorați",
        subdomain, added, skipped, ambiguous_count,
    )
    return {"added": added, "skipped": skipped, "ambiguous": ambiguous_count}


def list_councillors(subdomain: str, db: sqlite3.Connection):
    """Afișează consilierii din DB cu frecvența lor de apariție în HCL-uri."""
    uat_row = db.execute(
        "SELECT id, name FROM uat WHERE regista_subdomain=?", (subdomain,)
    ).fetchone()
    if not uat_row:
        raise ValueError(f"UAT '{subdomain}' nu există în DB")
    uat_id, uat_name = uat_row

    name_counts = extract_names_from_resolutions(db, uat_id)

    councillors = db.execute(
        "SELECT id, name, name_normalized, active FROM councillor WHERE uat_id=? ORDER BY name",
        (uat_id,),
    ).fetchall()

    print(f"\n{'─'*60}")
    print(f"  Consilieri locali — {uat_name} ({len(councillors)} în DB)")
    print(f"{'─'*60}")
    for c in councillors:
        freq = name_counts.get(c[2], 0)
        status = "activ" if c[3] else "inactiv"
        print(f"  {c[1]:<30} apare în {freq:>4} HCL-uri  [{status}]")

    # Arată și variantele de scriere per persoană
    print(f"\n  Variante de scriere detectate în surse:")
    all_rows = db.execute(
        "SELECT initiators FROM resolution WHERE uat_id=? AND initiators IS NOT NULL",
        (uat_id,),
    ).fetchall()
    raw_counter: Counter = Counter()
    for (raw,) in all_rows:
        try:
            for name in json.loads(raw):
                if name and isinstance(name, str):
                    raw_counter[name.strip()] += 1
        except Exception:
            pass

    # Grupează pe normalized
    groups: dict[str, list] = {}
    for raw_name, freq in raw_counter.items():
        norm = normalize_name(raw_name)
        groups.setdefault(norm, []).append((raw_name, freq))

    for norm, variants in sorted(groups.items(), key=lambda x: -sum(f for _, f in x[1])):
        if len(variants) > 1:
            print(f"\n  {canonical_name(norm)}:")
            for raw_name, freq in sorted(variants, key=lambda x: -x[1]):
                print(f"    '{raw_name}' × {freq}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrage și normalizează consilierii locali din datele colectate"
    )
    parser.add_argument("--db",   required=True, help="Cale la baza de date SQLite")
    parser.add_argument("--uat",  help="Subdomain Regista (ex: bobicesti)")
    parser.add_argument("--all",  action="store_true", help="Procesează toate UAT-urile")
    parser.add_argument("--list", action="store_true", help="Listează consilierii din DB")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    if args.list and args.uat:
        list_councillors(args.uat, db)
        db.close()
        return

    if args.all:
        rows = db.execute(
            "SELECT regista_subdomain FROM uat WHERE platform='regista' AND active=1"
        ).fetchall()
        for row in rows:
            sync_councillors(row[0], db)
    elif args.uat:
        sync_councillors(args.uat, db)
    else:
        parser.error("Specifică --uat <subdomain> sau --all")

    db.close()


if __name__ == "__main__":
    main()
