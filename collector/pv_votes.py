"""
Extrage voturile nominale din procesele-verbale (PV) ale ședințelor de consiliu.

Multe primării pe Regista publică PV-uri care consemnează, per hotărâre:
  - numărul de voturi pentru / împotrivă / abțineri
  - NUMELE consilierilor care s-au opus sau abținut

Două formate întâlnite în PV-uri (variază chiar și în aceeași primărie):
  1. liniuță:  „- abțineri – 1 vot – Statie George."
  2. paranteze: „-abtineri - 3(Statie George, Sticlea Ion, Dumitru Anton)"

Scriptul:
  1. ia lista PV-urilor din registrul Regista (URL-uri de download proaspete)
  2. descarcă fiecare PDF și extrage textul (pdfplumber)
  3. parsează blocurile de vot și le leagă de HCL prin „Hotărârea ... nr. N /data"
  4. potrivește numele disidenților cu consilierii din DB (fuzzy, fără diacritice)
  5. populează tabelul `vote` (doar disidenți) + numărătorile pe `resolution`

Votul „pentru" individual NU e listat nominal — se deduce: cine nu apare la
împotrivă/abținere și e prezent a votat cu majoritatea.

Utilizare:
    python pv_votes.py --db ales-local.db --uat bals --year 2026
"""

import re
import sqlite3
import argparse
import logging
import subprocess
import tempfile

import requests

try:
    import pdfplumber
except ImportError:
    raise SystemExit("Lipsește pdfplumber. Rulează: pip install pdfplumber")

from councillors import normalize_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PV_SLUG = "alte-documente/procesele-verbale-ale-sedintelor-autoritatii-deliberative"

# ─────────────────────────────────────────────
# Parsare text PV
# ─────────────────────────────────────────────

def _norm_dashes(s: str) -> str:
    return s.replace("–", "-").replace("—", "-").replace("‐", "-")

# Bloc de vot: de la „Votează" până la „Hotărârea Consiliului Local nr. N /data"
_BLOCK_RE = re.compile(
    r"[Vv]ote[aă]z[aă]\s*:?(.*?)(?:[Ee]ste\s+adoptat[aă]\s+)?"
    r"Hot[aă]r[aâ]rea\s+Consiliului\s+Local\s+nr\.?\s*(\d+)\s*/\s*(\d{1,2}\.\d{1,2}\.\d{4})",
    re.S,
)
_LABELS = [("for", r"pentru"), ("against", r"[iî]mpotriv\w*"), ("abstain", r"ab[tțţ]iner\w*")]
# nume după liniuță: „- Statie George" sau „- Nume1, Nume2"
_NAME_DASH = re.compile(
    r"-\s*([A-ZȘȚÎÂ][\w]*(?:[\s-][A-ZȘȚÎÂa-zșțîâă]+)+"
    r"(?:\s*,\s*[A-ZȘȚÎÂ][\w]*(?:[\s-][A-ZȘȚÎÂa-zșțîâă]+)+)*)\s*$"
)


def _parse_segment(seg: str) -> tuple[int, list[str]]:
    """Dintr-un segment de etichetă întoarce (număr_voturi, [nume disidenți])."""
    seg = seg.strip()
    cnt = re.search(r"(\d+)", seg)
    count = int(cnt.group(1)) if cnt else 0

    names: list[str] = []
    par = re.search(r"\(([^)]+)\)", seg)          # format paranteze
    if par:
        names = [x.strip().rstrip(".,") for x in par.group(1).split(",")]
    else:                                          # format liniuță
        nm = _NAME_DASH.search(seg.rstrip(".;,"))
        if nm:
            names = [x.strip() for x in nm.group(1).split(",")]

    # filtrează fragmente non-nume (titluri gen „BLOC 6", „anexa nr.1")
    names = [n for n in names if len(n) > 3 and not re.search(r"\d", n)
             and n.lower() not in ("anexa", "bloc")]
    return count, names


def parse_vote_blocks(text: str) -> list[dict]:
    """Întoarce o listă de dict-uri per hotărâre cu numărători + disidenți."""
    text = _norm_dashes(text)
    results = []
    for detail, hcl_nr, hcl_date in _BLOCK_RE.findall(text):
        positions = []
        for key, pat in _LABELS:
            m = re.search(pat, detail, re.I)
            if m:
                positions.append((m.start(), m.end(), key))
        positions.sort()

        vals = {"for": None, "against": 0, "abstain": 0}
        names = {"against": [], "abstain": []}
        for idx, (_s, end, key) in enumerate(positions):
            seg_end = positions[idx + 1][0] if idx + 1 < len(positions) else len(detail)
            count, seg_names = _parse_segment(detail[end:seg_end])
            vals[key] = count
            if key in names:
                names[key] = seg_names

        results.append({
            "hcl_nr": hcl_nr, "hcl_date": hcl_date,
            "for": vals["for"], "against": vals["against"], "abstain": vals["abstain"],
            "against_names": names["against"], "abstain_names": names["abstain"],
        })
    return results


# ─────────────────────────────────────────────
# Descărcare PV-uri din Regista
# ─────────────────────────────────────────────

def fetch_pv_list(subdomain: str, registry_id: int, session: requests.Session, year: str) -> list[dict]:
    """Lista PV-urilor dintr-un an, cu URL-uri de download proaspete."""
    base = f"https://{subdomain}.regista.ro"
    url = f"{base}/monitorul-oficial-local/{PV_SLUG}/{registry_id}"
    params = {
        "draw": 1,
        "columns[0][data]": "registrationNumberPattern",
        "columns[1][data]": "subject",
        "columns[2][data]": "registrationDate",
        "columns[2][search][value]": year,
        "start": 0, "length": 100, "search[value]": year, "_": 1,
    }
    resp = session.get(url, params=params, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=20)
    resp.raise_for_status()
    out = []
    for item in resp.json().get("data", []):
        action = item.get("4") or item.get("3") or item.get("5") or ""
        m = re.search(r'href="(/counter/download[^"]+)"', action)
        if m:
            out.append({"id": item.get("id"), "url": base + m.group(1)})
    return out


def download_pdf_text(url: str, session: requests.Session) -> str | None:
    """Descarcă un PDF și întoarce textul, sau None dacă e corupt/scanat."""
    resp = session.get(url, timeout=30)
    if resp.status_code != 200 or b"%PDF" not in resp.content[:1024]:
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(resp.content)
        tmp.flush()
        try:
            with pdfplumber.open(tmp.name) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:  # noqa: BLE001
            log.warning("PDF ilizibil (%s): %s", url[-20:], exc)
            return None


# ─────────────────────────────────────────────
# Potrivire nume + populare DB
# ─────────────────────────────────────────────

def build_name_matcher(db: sqlite3.Connection, uat_id: int):
    councillors = {normalize_name(r[1]): r[0]
                   for r in db.execute("SELECT id, name FROM councillor WHERE uat_id=?", (uat_id,))}

    def match(raw: str):
        n = normalize_name(raw)
        if n in councillors:
            return councillors[n]
        parts = set(n.split())
        for cn, cid in councillors.items():
            if len(parts & set(cn.split())) >= 2:   # cel puțin nume+prenume comune
                return cid
        return None

    return match


def ensure_vote_columns(db: sqlite3.Connection):
    for col, typ in [("votes_for", "INTEGER"), ("votes_against", "INTEGER"),
                     ("votes_abstain", "INTEGER"), ("votes_present", "INTEGER"),
                     ("vote_source", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE resolution ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass


def sync_votes(subdomain: str, db: sqlite3.Connection, year: str = "2026") -> dict:
    uat = db.execute("SELECT id FROM uat WHERE regista_subdomain=?", (subdomain,)).fetchone()
    if not uat:
        raise ValueError(f"UAT '{subdomain}' inexistent")
    uat_id = uat[0]
    reg = db.execute("SELECT registry_id FROM regista_registry WHERE uat_id=? AND registry_type='pv'",
                     (uat_id,)).fetchone()
    if not reg:
        raise ValueError(f"Registru PV negăsit pentru '{subdomain}'")

    ensure_vote_columns(db)
    match_name = build_name_matcher(db, uat_id)
    session = requests.Session()
    session.headers.update({"User-Agent": "ales-local-pv/0.1"})

    # reset date vot pentru acest an
    db.execute("""UPDATE resolution SET votes_for=NULL, votes_against=NULL, votes_abstain=NULL,
                  votes_present=NULL, vote_source=NULL WHERE uat_id=? AND adopted_date LIKE ?""",
               (uat_id, f"{year}%"))
    db.execute("""DELETE FROM vote WHERE resolution_id IN
                  (SELECT id FROM resolution WHERE uat_id=? AND adopted_date LIKE ?)""",
               (uat_id, f"{year}%"))

    pv_list = fetch_pv_list(subdomain, reg[0], session, year)
    log.info("[%s] %d PV-uri în %s", subdomain, len(pv_list), year)

    n_hcl = n_dissent = n_unreadable = 0
    for pv in pv_list:
        text = download_pdf_text(pv["url"], session)
        if not text:
            n_unreadable += 1
            continue
        for block in parse_vote_blocks(text):
            res = db.execute(
                "SELECT id FROM resolution WHERE uat_id=? AND number=? AND adopted_date LIKE ?",
                (uat_id, block["hcl_nr"], f"{year}%"),
            ).fetchone()
            if not res:
                continue
            rid = res[0]
            present = (block["for"] or 0) + block["against"] + block["abstain"]
            db.execute("""UPDATE resolution SET votes_for=?, votes_against=?, votes_abstain=?,
                          votes_present=?, vote_source='pv' WHERE id=?""",
                       (block["for"], block["against"], block["abstain"], present, rid))
            n_hcl += 1
            for value, key in [("against", "against_names"), ("abstain", "abstain_names")]:
                for nm in block[key]:
                    cid = match_name(nm)
                    if cid:
                        db.execute("INSERT OR REPLACE INTO vote (resolution_id, councillor_id, vote_value) VALUES (?,?,?)",
                                   (rid, cid, value))
                        n_dissent += 1
                    else:
                        log.debug("nume nepotrivit: %s", nm)
    db.commit()
    log.info("[%s] %d hotărâri cu vot, %d voturi disidente, %d PV-uri ilizibile",
             subdomain, n_hcl, n_dissent, n_unreadable)
    return {"hcl_voted": n_hcl, "dissent_votes": n_dissent, "unreadable": n_unreadable}


def main():
    ap = argparse.ArgumentParser(description="Extrage voturi nominale din PV-uri Regista")
    ap.add_argument("--db", required=True)
    ap.add_argument("--uat", required=True, help="subdomain Regista (ex: bals)")
    ap.add_argument("--year", default="2026")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    result = sync_votes(args.uat, db, args.year)
    db.close()
    log.info("Rezultat: %s", result)


if __name__ == "__main__":
    main()
