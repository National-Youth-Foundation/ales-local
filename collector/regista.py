"""
Colector date pentru primăriile pe platforma Regista (regista.ro).

Toate registrele publice din Monitorul Oficial Local expun un API DataTables
la același URL ca pagina HTML, cu parametri draw/columns/start/length.
Nu necesită browser sau OCR — returnează JSON structurat direct.

Utilizare:
    python regista.py --db ales-local.db --uat bobicesti
    python regista.py --db ales-local.db --uat bals --year 2025
    python regista.py --db ales-local.db --all
"""

import re
import html
import json
import sqlite3
import argparse
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Sluguri standard pentru categoriile din Monitorul Oficial Local
REGISTRY_SLUGS = {
    "hcl":          "hotararile-autoritatii-deliberative/registrul-pentru-evidenta-hotararilor-autoritatii-deliberative",
    "proiecte_hcl": "hotararile-autoritatii-deliberative/registrul-pentru-evidenta-proiectelor-de-hotarari-ale-autoritatii-deliberative",
    "pv":           "alte-documente/procesele-verbale-ale-sedintelor-autoritatii-deliberative",
    "minute":       "alte-documente/minutele-in-care-se-consemneaza-in-rezumat-punctele-de-vedere-exprimate-de-participanti-la-o-sedinta-publica",
    "dispozitii":   "dispozitiile-autoritatii-executive/registrul-pentru-evidenta-dispozitiilor-autoritatii-executive",
    "financiar":    "documente-si-informatii-financiare",
}

# Tipul de document pentru tabelul `document`
REGISTRY_TO_DOC_TYPE = {
    "proiecte_hcl": "proiect_hcl",
    "pv":           "pv",
    "minute":       "minuta",
    "dispozitii":   "dispozitie",
    "financiar":    "financiar",
}


# ─────────────────────────────────────────────
# Utilități
# ─────────────────────────────────────────────

def clean_text(t: Optional[str]) -> Optional[str]:
    """Decodează entitățile HTML (&icirc; → î, &ldquo; → ") și normalizează spațiile."""
    if not t:
        return t
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def extract_timestamp(raw: str) -> Optional[int]:
    """Extrage unix timestamp din codul JS generat de moment.js în răspunsul DataTables."""
    match = re.search(r"moment\.unix\((\d+)\)", raw)
    return int(match.group(1)) if match else None


def extract_pdf_url(html: str, base_url: str) -> Optional[str]:
    """Extrage URL-ul de download PDF din coloana de acțiuni a răspunsului DataTables."""
    match = re.search(r'href="(/counter/download[^"]+)"', html)
    return base_url + match.group(1) if match else None


def normalize_name(name: str) -> str:
    """Normalizează un nume pentru fuzzy matching (lowercase, fără diacritice)."""
    replacements = str.maketrans("ăâîșțĂÂÎȘȚ", "aaisaAAISA")
    return name.lower().translate(replacements).strip()


# ─────────────────────────────────────────────
# Descoperire registre
# ─────────────────────────────────────────────

def discover_registries(subdomain: str, session: requests.Session) -> dict[str, int]:
    """
    Crawlează pagina Monitorul Oficial Local și extrage ID-urile registrelor.
    Returnează dict: registry_type -> registry_id (număr din URL).
    """
    url = f"https://{subdomain}.regista.ro/monitorul-oficial-local"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()

    found = {}
    for reg_type, slug in REGISTRY_SLUGS.items():
        short_slug = slug.split("/")[-1]
        match = re.search(rf"{re.escape(short_slug)}/(\d+)", resp.text)
        if match:
            found[reg_type] = int(match.group(1))
            log.debug("  %s → registry_id=%s", reg_type, match.group(1))

    log.info("[%s] registre descoperite: %s", subdomain, list(found.keys()))
    return found


# ─────────────────────────────────────────────
# Fetch date din API DataTables
# ─────────────────────────────────────────────

def _hcl_params(start: int, length: int, year: str = "") -> dict:
    return {
        "draw": 1,
        "columns[0][data]": "approvedRegistrationNumberPattern",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "false",
        "columns[0][search][value]": "",
        "columns[1][data]": "councilDecisionMetadata.approvedCouncilDecisionTitle",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "false",
        "columns[1][search][value]": "",
        "columns[2][data]": "councilDecisionMetadata.debateDate",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "false",
        "columns[2][search][value]": year,
        "columns[3][data]": "initiators[, ].name",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "false",
        "columns[3][search][value]": "",
        "columns[4][data]": "character",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "false",
        "columns[4][search][value]": "",
        "start": start,
        "length": length,
        "search[value]": "",
        "_": 1,
    }


def _doc_params(start: int, length: int) -> dict:
    return {
        "draw": 1,
        "columns[0][data]": "registrationNumberPattern",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "false",
        "columns[0][search][value]": "",
        "columns[1][data]": "subject",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "false",
        "columns[1][search][value]": "",
        "columns[2][data]": "registrationDate",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "false",
        "columns[2][search][value]": "",
        "start": start,
        "length": length,
        "search[value]": "",
        "_": 1,
    }


def fetch_all_from_registry(
    subdomain: str,
    slug: str,
    registry_id: int,
    reg_type: str,
    session: requests.Session,
    year: str = "",
    page_size: int = 500,
) -> list[dict]:
    """Fetch toate înregistrările dintr-un registru, paginat."""
    base_url = f"https://{subdomain}.regista.ro"
    endpoint = f"{base_url}/monitorul-oficial-local/{slug}/{registry_id}"
    headers = {"X-Requested-With": "XMLHttpRequest"}

    is_hcl = reg_type in ("hcl", "proiecte_hcl")
    all_records = []
    start = 0

    while True:
        params = _hcl_params(start, page_size, year) if is_hcl else _doc_params(start, page_size)
        resp = session.get(endpoint, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        records = data.get("data", [])
        all_records.extend(records)

        total = data.get("recordsTotal", 0)
        start += len(records)

        if start >= total or not records:
            break

    log.info("[%s] %s: %d înregistrări", subdomain, reg_type, len(all_records))
    return all_records


# ─────────────────────────────────────────────
# Procesare și salvare în DB
# ─────────────────────────────────────────────

def save_hcl(db: sqlite3.Connection, uat_id: int, reg_row_id: int,
             subdomain: str, records: list[dict]) -> tuple[int, int]:
    """Salvează HCL-uri în tabelul `resolution`. Returnează (găsite, noi)."""
    base_url = f"https://{subdomain}.regista.ro"
    new_count = 0

    for item in records:
        regista_id = item.get("id")
        if not regista_id:
            continue

        if db.execute("SELECT 1 FROM resolution WHERE regista_doc_id=?", (regista_id,)).fetchone():
            continue

        meta = item.get("councilDecisionMetadata") or {}
        ts = extract_timestamp(meta.get("debateDate", ""))
        adopted_date = datetime.fromtimestamp(ts).date().isoformat() if ts else None

        action_html = item.get("5", "")
        pdf_url = extract_pdf_url(action_html, base_url)

        initiators = json.dumps(
            [i["name"] for i in item.get("initiators", []) if isinstance(i, dict)],
            ensure_ascii=False,
        )

        db.execute(
            """
            INSERT INTO resolution
                (uat_id, regista_doc_id, number, title, adopted_date, character, initiators,
                 pdf_url, source_registry_id)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                uat_id,
                regista_id,
                item.get("approvedRegistrationNumberPattern"),
                clean_text(meta.get("approvedCouncilDecisionTitle")),
                adopted_date,
                item.get("character"),
                initiators,
                pdf_url,
                reg_row_id,
            ),
        )
        new_count += 1

    db.commit()
    return len(records), new_count


def save_document(db: sqlite3.Connection, uat_id: int, reg_row_id: int,
                  subdomain: str, doc_type: str, records: list[dict]) -> tuple[int, int]:
    """Salvează documente (PV, minute, etc.) în tabelul `document`."""
    base_url = f"https://{subdomain}.regista.ro"
    new_count = 0

    for item in records:
        regista_id = item.get("id")
        if not regista_id:
            continue

        if db.execute("SELECT 1 FROM document WHERE regista_doc_id=?", (regista_id,)).fetchone():
            continue

        ts = extract_timestamp(item.get("registrationDate", ""))
        doc_date = datetime.fromtimestamp(ts).date().isoformat() if ts else None

        # coloana de acțiuni poate fi "3", "4" sau "5" în funcție de numărul de coloane
        action_html = item.get("4") or item.get("3") or item.get("5") or ""
        pdf_url = extract_pdf_url(action_html, base_url)

        title = clean_text(item.get("otherDetails") or item.get("subject") or "")

        db.execute(
            """
            INSERT INTO document
                (uat_id, regista_doc_id, doc_type, title, doc_date, pdf_url, source_registry_id)
            VALUES (?,?,?,?,?,?,?)
            """,
            (uat_id, regista_id, doc_type, title, doc_date, pdf_url, reg_row_id),
        )
        new_count += 1

    db.commit()
    return len(records), new_count


# ─────────────────────────────────────────────
# Punct de intrare principal
# ─────────────────────────────────────────────

def sync_uat(subdomain: str, db: sqlite3.Connection,
             year: str = "", registry_types: list[str] | None = None) -> dict:
    """
    Sincronizează toate registrele unui UAT Regista.
    Returnează statistici per tip de registru.
    """
    uat_row = db.execute(
        "SELECT id FROM uat WHERE regista_subdomain=?", (subdomain,)
    ).fetchone()
    if not uat_row:
        raise ValueError(f"UAT cu subdomain '{subdomain}' nu există în schema.sql")
    uat_id = uat_row[0]

    session = requests.Session()
    session.headers.update({"User-Agent": "ales-local-collector/0.1"})

    # Descoperă registrele dacă nu le avem în DB
    existing = {
        r[0]: {"id": r[1], "slug": r[2]}
        for r in db.execute(
            "SELECT registry_type, registry_id, slug FROM regista_registry WHERE uat_id=?",
            (uat_id,),
        )
    }

    if not existing:
        discovered = discover_registries(subdomain, session)
        for reg_type, reg_id in discovered.items():
            slug = REGISTRY_SLUGS.get(reg_type, "")
            db.execute(
                "INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug) VALUES (?,?,?,?)",
                (uat_id, reg_type, reg_id, slug),
            )
        db.commit()
        existing = {
            r[0]: {"id": r[1], "slug": r[2]}
            for r in db.execute(
                "SELECT registry_type, registry_id, slug FROM regista_registry WHERE uat_id=?",
                (uat_id,),
            )
        }

    types_to_sync = registry_types or list(existing.keys())
    stats = {}

    for reg_type in types_to_sync:
        if reg_type not in existing:
            log.warning("[%s] registru '%s' nu e în DB — skip", subdomain, reg_type)
            continue

        reg = existing[reg_type]
        reg_row = db.execute(
            "SELECT id FROM regista_registry WHERE uat_id=? AND registry_type=?",
            (uat_id, reg_type),
        ).fetchone()
        reg_row_id = reg_row[0] if reg_row else None

        try:
            records = fetch_all_from_registry(
                subdomain, reg["slug"], reg["id"], reg_type, session, year=year
            )

            if reg_type in ("hcl", "proiecte_hcl"):
                found, new = save_hcl(db, uat_id, reg_row_id, subdomain, records)
            else:
                doc_type = REGISTRY_TO_DOC_TYPE.get(reg_type, "alt")
                found, new = save_document(db, uat_id, reg_row_id, subdomain, doc_type, records)

            stats[reg_type] = {"found": found, "new": new}
            db.execute(
                "INSERT INTO collector_run (uat_id, registry_type, docs_found, docs_new) VALUES (?,?,?,?)",
                (uat_id, reg_type, found, new),
            )
            db.commit()
            log.info("[%s] %s → %d găsite, %d noi", subdomain, reg_type, found, new)

        except Exception as exc:
            log.error("[%s] eroare la %s: %s", subdomain, reg_type, exc)
            stats[reg_type] = {"error": str(exc)}
            db.execute(
                "INSERT INTO collector_run (uat_id, registry_type, error) VALUES (?,?,?)",
                (uat_id, reg_type, str(exc)),
            )
            db.commit()

    return stats


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Colector Regista pentru platforma Alesul meu local")
    parser.add_argument("--db",   required=True, help="Cale la baza de date SQLite (ex: ales-local.db)")
    parser.add_argument("--uat",  help="Subdomain Regista (ex: bobicesti)")
    parser.add_argument("--all",  action="store_true", help="Sincronizează toate UAT-urile Regista din DB")
    parser.add_argument("--year", default="", help="Filtrează după an (ex: 2025)")
    parser.add_argument("--type", dest="reg_type", help="Tip registru (hcl, pv, minute, etc.)")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    types = [args.reg_type] if args.reg_type else None

    if args.all:
        rows = db.execute(
            "SELECT regista_subdomain FROM uat WHERE platform='regista' AND active=1 AND regista_subdomain IS NOT NULL"
        ).fetchall()
        for row in rows:
            subdomain = row[0]
            log.info("=== Sincronizare: %s ===", subdomain)
            result = sync_uat(subdomain, db, year=args.year, registry_types=types)
            log.info("Rezultat %s: %s", subdomain, result)

    elif args.uat:
        result = sync_uat(args.uat, db, year=args.year, registry_types=types)
        log.info("Rezultat: %s", result)

    else:
        parser.error("Specifică --uat <subdomain> sau --all")

    db.close()


if __name__ == "__main__":
    main()
