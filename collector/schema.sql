-- Schema baza de date pentru platforma civică „Alesul meu local"
-- Motor: SQLite (MVP) — migrabil la PostgreSQL fără modificări majore
-- Versiune: 0.2

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────
-- 1. UAT-uri
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS uat (
    id                  INTEGER PRIMARY KEY,
    siruta              TEXT UNIQUE,            -- cod INS SIRUTA
    name                TEXT NOT NULL,
    county              TEXT NOT NULL,
    type                TEXT NOT NULL CHECK(type IN ('comună','oraș','municipiu')),
    platform            TEXT NOT NULL DEFAULT 'unknown'
                            CHECK(platform IN ('regista','wordpress','custom','none','unknown')),
    regista_subdomain   TEXT UNIQUE,            -- ex: 'bobicesti'
    official_site_url   TEXT,
    population          INTEGER,               -- populație conform recensamant 2021
    council_size        INTEGER,               -- nr. consilieri conform OUG 57/2019
    active              INTEGER DEFAULT 1,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Date inițiale pentru UAT-urile pilot
INSERT OR IGNORE INTO uat (siruta, name, county, type, platform, regista_subdomain, official_site_url, population, council_size)
VALUES
    -- population = alegători înscriși conform ROAEP 2024; council_size conform OUG 57/2019 Art.89(2)(b)
    ('106065', 'Bobicești', 'Olt', 'comună', 'regista', 'bobicesti', 'https://www.bobicesti.ro', 2624, 11),
    ('106249', 'Balș',      'Olt', 'oraș',   'regista', 'bals',      'https://bals.regista.ro', 18200, 17);

-- ─────────────────────────────────────────────
-- 2. Registre Regista descoperite per UAT
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regista_registry (
    id              INTEGER PRIMARY KEY,
    uat_id          INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    registry_type   TEXT NOT NULL,
    registry_id     INTEGER NOT NULL,
    slug            TEXT NOT NULL,
    discovered_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(uat_id, registry_type)
);

-- Registry IDs descoperite pentru UAT-urile pilot
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'hcl', 21932, 'hotararile-autoritatii-deliberative/registrul-pentru-evidenta-hotararilor-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106065';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'proiecte_hcl', 21933, 'hotararile-autoritatii-deliberative/registrul-pentru-evidenta-proiectelor-de-hotarari-ale-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106065';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'pv', 21944, 'alte-documente/procesele-verbale-ale-sedintelor-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106065';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'minute', 21943, 'alte-documente/minutele-in-care-se-consemneaza-in-rezumat-punctele-de-vedere-exprimate-de-participanti-la-o-sedinta-publica'
  FROM uat u WHERE u.siruta = '106065';

INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'hcl', 4284, 'hotararile-autoritatii-deliberative/registrul-pentru-evidenta-hotararilor-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106249';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'proiecte_hcl', 8500, 'hotararile-autoritatii-deliberative/registrul-pentru-evidenta-proiectelor-de-hotarari-ale-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106249';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'pv', 8509, 'alte-documente/procesele-verbale-ale-sedintelor-autoritatii-deliberative'
  FROM uat u WHERE u.siruta = '106249';
INSERT OR IGNORE INTO regista_registry (uat_id, registry_type, registry_id, slug)
SELECT u.id, 'minute', 8508, 'alte-documente/minutele-in-care-se-consemneaza-in-rezumat-punctele-de-vedere-exprimate-de-participanti-la-o-sedinta-publica'
  FROM uat u WHERE u.siruta = '106249';

-- ─────────────────────────────────────────────
-- 3. Consilieri locali
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS councillor (
    id                      INTEGER PRIMARY KEY,
    uat_id                  INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    name_normalized         TEXT,
    party                   TEXT,
    electoral_list_position INTEGER,           -- poziție pe lista electorală BEC 2024
    mandate_start           DATE,
    mandate_end             DATE,
    active                  INTEGER DEFAULT 1,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(uat_id, name_normalized, mandate_start)
);

-- ─────────────────────────────────────────────
-- 4. Hotărâri de Consiliu Local (HCL)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resolution (
    id                  INTEGER PRIMARY KEY,
    uat_id              INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    regista_doc_id      INTEGER UNIQUE,
    number              TEXT,
    title               TEXT,
    adopted_date        DATE,
    character           TEXT CHECK(character IN ('Normativ','Individual',NULL)),
    initiators          TEXT,               -- JSON: ["Chitez Ilie"]
    pdf_url             TEXT,
    pdf_hash            TEXT,
    source_registry_id  INTEGER REFERENCES regista_registry(id),
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resolution_uat_date ON resolution(uat_id, adopted_date);

-- ─────────────────────────────────────────────
-- 5. Documente generale (PV, minute, proiecte HCL, etc.)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document (
    id                  INTEGER PRIMARY KEY,
    uat_id              INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    regista_doc_id      INTEGER UNIQUE,
    doc_type            TEXT NOT NULL
                            CHECK(doc_type IN ('pv','minuta','proiect_hcl',
                                               'dispozitie','financiar','alt')),
    title               TEXT,
    doc_date            DATE,
    pdf_url             TEXT,
    pdf_hash            TEXT,
    ocr_text            TEXT,
    processed           INTEGER DEFAULT 0,  -- 0=nou, 1=OCR done, 2=extras structurat
    source_registry_id  INTEGER REFERENCES regista_registry(id),
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_uat_type_date ON document(uat_id, doc_type, doc_date);

-- ─────────────────────────────────────────────
-- 6. Prezența consilierilor la ședințe
--    (populat după extracție din PV/minute)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_attendance (
    id              INTEGER PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    councillor_id   INTEGER NOT NULL REFERENCES councillor(id),
    present         INTEGER NOT NULL CHECK(present IN (0,1)),
    absence_type    TEXT CHECK(absence_type IN ('motivat','nemotivat','necunoscut',NULL)),
    UNIQUE(document_id, councillor_id)
);

-- ─────────────────────────────────────────────
-- 7. Voturi individuale per HCL per consilier
--    (populat după extracție din PV/minute)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vote (
    id              INTEGER PRIMARY KEY,
    resolution_id   INTEGER NOT NULL REFERENCES resolution(id) ON DELETE CASCADE,
    councillor_id   INTEGER NOT NULL REFERENCES councillor(id),
    vote_value      TEXT NOT NULL CHECK(vote_value IN ('for','against','abstain','absent','secret')),
    UNIQUE(resolution_id, councillor_id)
);

-- ─────────────────────────────────────────────
-- 8. Declarații avere/interese (sursa: portal ANI)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ani_declaration (
    id                  INTEGER PRIMARY KEY,
    councillor_id       INTEGER NOT NULL REFERENCES councillor(id),
    year                INTEGER NOT NULL,
    decl_type           TEXT NOT NULL CHECK(decl_type IN ('avere','interese')),
    submitted_date      DATE,
    ani_url             TEXT,
    present_on_ani      INTEGER DEFAULT 0,
    present_on_primarie INTEGER DEFAULT 0,
    checked_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(councillor_id, year, decl_type)
);

-- ─────────────────────────────────────────────
-- 9. Log rulări colector
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS collector_run (
    id              INTEGER PRIMARY KEY,
    uat_id          INTEGER REFERENCES uat(id),
    registry_type   TEXT,
    run_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    docs_found      INTEGER DEFAULT 0,
    docs_new        INTEGER DEFAULT 0,
    error           TEXT
);

-- ─────────────────────────────────────────────
-- 10. Componența politică a consiliului local
--     (sursa: BEC/AEP — rezultate alegeri locale 2024)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS council_group (
    id              INTEGER PRIMARY KEY,
    uat_id          INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    party           TEXT NOT NULL,             -- abreviere: PSD, PNL, USR, etc.
    party_full      TEXT,                      -- denumire completă
    seats           INTEGER NOT NULL,
    mandate_start   DATE NOT NULL,             -- data alegerilor: 2024-06-09
    source          TEXT DEFAULT 'bec',
    UNIQUE(uat_id, party, mandate_start)
);

-- ─────────────────────────────────────────────
-- 11. Rezultate alegeri locale (prezență, voturi)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS election_result (
    id                  INTEGER PRIMARY KEY,
    uat_id              INTEGER NOT NULL REFERENCES uat(id) ON DELETE CASCADE,
    election_date       DATE NOT NULL,
    registered_voters   INTEGER,
    votes_cast          INTEGER,
    valid_votes         INTEGER,
    turnout_pct         REAL,
    source              TEXT DEFAULT 'bec'
);

-- Date seed componență politică 2024 (sursa: api.rezultatevot.ro BallotId=116)
INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'PSD', 'Partidul Social Democrat',         8, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106065';
INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'AUR', 'Alianța pentru Unirea Românilor',  2, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106065';
INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'PNL', 'Partidul Național Liberal',         1, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106065';

INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'PSD', 'Partidul Social Democrat',         10, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106249';
INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'PNL', 'Partidul Național Liberal',         5, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106249';
INSERT OR IGNORE INTO council_group (uat_id, party, party_full, seats, mandate_start, source)
SELECT u.id, 'AUR', 'Alianța pentru Unirea Românilor',  2, '2024-06-09', 'roaep' FROM uat u WHERE u.siruta='106249';

-- Date seed alegeri 2024 (prezență + voturi valabile)
INSERT OR IGNORE INTO election_result (uat_id, election_date, registered_voters, votes_cast, valid_votes, turnout_pct, source)
SELECT u.id, '2024-06-09', 2624, 1521, 1481, 57.97, 'roaep' FROM uat u WHERE u.siruta='106065';
INSERT OR IGNORE INTO election_result (uat_id, election_date, registered_voters, votes_cast, valid_votes, turnout_pct, source)
SELECT u.id, '2024-06-09', 16422, 7769, 7358, 47.31, 'roaep' FROM uat u WHERE u.siruta='106249';

-- ─────────────────────────────────────────────
-- VIEW: Dashboard consiliu local
-- ─────────────────────────────────────────────
CREATE VIEW IF NOT EXISTS v_council_dashboard AS
WITH hcl_2026 AS (
    SELECT uat_id,
           COUNT(*) AS hcl_count_2026,
           COUNT(CASE WHEN character = 'Normativ'   THEN 1 END) AS normative_2026,
           COUNT(CASE WHEN character = 'Individual' THEN 1 END) AS individual_2026,
           MIN(adopted_date) AS first_hcl_2026,
           MAX(adopted_date) AS last_hcl_2026
    FROM resolution
    WHERE adopted_date LIKE '2026%'
    GROUP BY uat_id
),
pv_2026 AS (
    SELECT uat_id, COUNT(*) AS sessions_2026
    FROM document
    WHERE doc_type = 'pv' AND doc_date LIKE '2026%'
    GROUP BY uat_id
),
party_composition AS (
    SELECT uat_id,
           SUM(seats) AS seats_accounted,
           -- GROUP_CONCAT fără ORDER BY în SQLite — subquery pentru sortare descrescătoare
           (SELECT GROUP_CONCAT(g2.party || ':' || g2.seats, ' | ')
            FROM (SELECT party, seats FROM council_group g3
                  WHERE g3.uat_id = council_group.uat_id
                    AND g3.mandate_start = '2024-06-09'
                  ORDER BY g3.seats DESC) g2
           ) AS party_breakdown
    FROM council_group
    WHERE mandate_start = '2024-06-09'
    GROUP BY uat_id
)
SELECT
    u.name,
    u.county,
    u.type,
    u.population,
    u.council_size,
    COALESCE(pc.party_breakdown, 'BEC: nedisponibil') AS componenta_partide,
    COALESCE(h.hcl_count_2026,  0) AS hcl_2026,
    COALESCE(h.normative_2026,  0) AS normative_2026,
    COALESCE(h.individual_2026, 0) AS individuale_2026,
    COALESCE(s.sessions_2026,   0) AS sedinte_pv_2026,
    h.first_hcl_2026,
    h.last_hcl_2026
FROM uat u
LEFT JOIN hcl_2026          h  ON h.uat_id  = u.id
LEFT JOIN pv_2026           s  ON s.uat_id  = u.id
LEFT JOIN party_composition pc ON pc.uat_id = u.id
WHERE u.active = 1;
