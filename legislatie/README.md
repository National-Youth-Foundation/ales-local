# Faza 1 — Cadrul legislativ pentru monitorizarea consilierilor locali

Documentație pentru un sistem civic de monitorizare a activității consilierilor locali din mediul rural în România.

**Sursă:** Cercetare pe surse exclusiv oficiale, verificare adversarială (104 agenți, 22 surse, 25 afirmații verificate independent).
**Faza 2C — Verificare directă:** Toate articolele citate verificate direct pe legislatie.just.ro prin browser (Playwright). 1 eroare găsită și corectată (Art. 16 → Art. 7 Legea 544/2001).
**Data:** 18 iunie 2026

---

## Structura documentației

| Fișier | Conținut |
|--------|----------|
| [01-statut-consilier-local.md](01-statut-consilier-local.md) | Alegere, eligibilitate, drepturi, obligații, sancțiuni |
| [02-activitatea-consiliului-local.md](02-activitatea-consiliului-local.md) | Tipuri ședințe, HCL, vot, comisii, publicare documente |
| [03-legea-544-acces-informatii.md](03-legea-544-acces-informatii.md) | Dreptul la informații publice, proceduri, termene |
| [04-legea-52-transparenta-decizionala.md](04-legea-52-transparenta-decizionala.md) | Transparența adoptării HCL-urilor, participare publică |
| [05-ani-declaratii-avere-interese.md](05-ani-declaratii-avere-interese.md) | Declarații avere/interese, portal ANI, acces public |
| [06-implicatii-arhitectura-platforma.md](06-implicatii-arhitectura-platforma.md) | Indicatori de monitorizare + scenarii colectare date + gap-uri MVP |
| [NOTE-neverificate-intrebari.md](NOTE-neverificate-intrebari.md) | Afirmații neconfirmate + 1 întrebare deschisă rămasă + 4 subîntrebări noi |

---

## Acte normative de bază

| Act normativ | Obiect | Link oficial |
|-------------|--------|-------------|
| OUG 57/2019 — Codul Administrativ | Cadrul general al administrației publice locale | https://legislatie.just.ro/Public/DetaliiDocument/215925 |
| Legea 393/2004 — Statutul aleșilor locali | Drepturi, obligații, sancțiuni ale aleșilor locali | https://legislatie.just.ro/Public/DetaliiDocument/55664 |
| Legea 115/2015 — Alegerea autorităților APL | Modul de alegere a consilierilor locali | https://legislatie.just.ro/Public/DetaliiDocument/177937 |
| Legea 161/2003 — Transparență în demnități publice | Incompatibilități, interdicții cumul mandate | https://legislatie.just.ro/Public/DetaliiDocument/43323 |
| Legea 544/2001 — Acces la informații publice | Dreptul de a solicita orice document public | https://legislatie.just.ro/Public/DetaliiDocument/31413 |
| Legea 52/2003 — Transparență decizională | Publicarea proiectelor HCL, participare publică | https://legislatie.just.ro/Public/DetaliiDocumentAfis/153210 |
| HG 123/2002 — Norme metodologice Legea 544/2001 | Proceduri detaliate pentru solicitări | https://legislatie.just.ro/Public/DetaliiDocumentAfis/41571 |
| Legea 176/2010 — Integritate în funcții publice | Regimul declarațiilor de avere și interese | https://legislatie.just.ro/Public/DetaliiDocument/121924 |

---

## Metodologie de verificare

Fiecare afirmație inclusă în aceste fișiere a primit minim **2 voturi din 3** de la verificatori independenți (sistem adversarial). Afirmațiile cu vot 0-3 sau 1-2 sunt excluse din text și listate în [NOTE-neverificate-intrebari.md](NOTE-neverificate-intrebari.md).

**Legendă:**
- ✅ `[3-0]` — confirmat unanim
- ✅ `[2-1]` — confirmat cu rezervă minoră
- ⚠️ `[1-2]` / `[0-3]` — neconfirmat, exclus din text principal
