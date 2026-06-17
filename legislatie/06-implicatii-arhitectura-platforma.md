# Implicații pentru arhitectura platformei civice

**Sinteză după Fazele 1 și 2A — 18 iunie 2026**

Aceasta este o analiză a ce înseamnă cadrul legislativ documentat pentru **designul tehnic și funcțional** al platformei de monitorizare a consilierilor locali.

---

## Concluzia esențială

**Datele există și sunt obligatoriu publice prin lege.** Problema nu este accesul legal, ci accesul tehnic — primăriile rurale respectă rar obligațiile de publicare online.

---

## 1. Surse de date — ce este obligatoriu public și unde

| Date | Obligație legală | Unde se publică | Regularitate |
|------|-----------------|-----------------|-------------|
| Minuta ședinței cu **votul individual** al fiecărui consilier | **Ex officio** (Art. 11 Legea 52/2003) | Site primărie | După fiecare ședință |
| Anunț ședință + ordine de zi | **Ex officio** (Art. 8 Legea 52/2003) | Site primărie, avizier | ≥3 zile înainte |
| Proiecte de HCL înainte de adoptare | **Ex officio** (Art. 7 Legea 52/2003) | Site primărie | ≥30 zile lucrătoare |
| Hotărârile adoptate (HCL) | **Ex officio** (Legea 544/2001 Art. 5) | Site primărie | La adoptare |
| Declarații de avere și interese | **Ex officio** (Legea 176/2010 Art. 6) | Site primărie + portal ANI | 30 zile de la depunere |
| Lista nedepunerilor declarații | **Ex officio** (Legea 176/2010 Art. 6(2)) | Portal ANI | Anual, până la 1 august |

---

## 2. Scenarii de colectare a datelor

### Scenariul A — Primărie conformă (publică pe site)
Platforma poate funcționa ca **agregator/monitor automat**:
- Scraper pe site-ul primăriei → extrage minuta, HCL-uri, anunțuri
- Monitor ANI → extrage declarații
- Alertă dacă o obligație de publicare nu este respectată la termen

### Scenariul B — Primărie neconformă (nu publică pe site)
Platforma funcționează ca **facilitator de acces prin Legea 544/2001**:
- Generator automat de cereri Legea 544 pre-completate
- Tracker al termenelor de răspuns (10 zile → 30 zile max)
- Posibilitate de sesizare ANI/Prefectură dacă primăria nu răspunde

**Realitatea practică:** Majoritatea primăriilor rurale sunt în Scenariul B pentru cel puțin o parte din obligații. Platforma trebuie să gestioneze ambele scenarii simultan.

---

## 3. Indicatori de monitorizare — ce poți măsura

### 3.1 Indicatori de prezență și participare
| Indicator | Sursă | Periodicitate |
|-----------|-------|-------------|
| Rata de prezență la ședințele de consiliu | Minutele ședințelor | Per ședință / per trimestru |
| Număr ședințe la care a lipsit nemotivat | Minutele ședințelor | Cumulativ |
| A organizat ≥1 întâlnire trimestrială cu cetățenii? | Informare prezentată în consiliu | Per trimestru |

### 3.2 Indicatori de vot
| Indicator | Sursă | Periodicitate |
|-----------|-------|-------------|
| Distribuția voturilor (pentru/contra/abținere) | Minutele ședințelor (Art. 11 Legea 52/2003) | Per HCL / cumulativ |
| Voturi contra față de colegii de grup politic | Minutele + componența grupurilor | Per mandant |
| Număr HCL-uri inițiate de consilier | Documentele HCL | Per mandat |
| Comisii din care face parte + prezența la comisii | Hotărâri constituire comisii + procese verbale comisii | Per mandat |

### 3.3 Indicatori de integritate
| Indicator | Sursă | Periodicitate |
|-----------|-------|-------------|
| A depus declarația de avere în 30 zile? | Portal ANI | La debut mandat |
| A depus declarația anuală până la 15 iunie? | Portal ANI | Anual |
| Apare pe lista nedepunerilor ANI? | Portal ANI (până la 1 august) | Anual |
| Există decizii ANI de incompatibilitate/conflict? | Site ANI | Per mandat |
| Evoluția declarată a averii pe mandate | Portal ANI — comparare an cu an | Per mandat |

### 3.4 Indicatori de transparență instituțională
*(Acestea monitorizează primăria, nu consilierul individual, dar sunt relevante pentru context)*
| Indicator | Sursă | Periodicitate |
|-----------|-------|-------------|
| Publică minuta cu voturi în termen rezonabil? | Site primărie (Art. 11 Legea 52/2003) | Per ședință |
| Anunță ședințele cu ≥3 zile înainte? | Site primărie | Per ședință |
| Publică proiectele HCL cu ≥30 zile înainte? | Site primărie | Per HCL |

---

## 4. Ce NU se poate automatiza (necesită intervenție umană)

- **Absențele nemotivate** — pragul legal e „mai mult de 3 ședințe ordinare/extraordinare consecutive în 3 luni calendaristice" (Art. 204(2) lit. d OUG 57/2019), dar distincția motivat/nemotivat rămâne la latitudinea consiliului; nu poți automatiza această judecată
- **Conflictele de interese** — necesită analiză a relațiilor de business, nu doar citirea declarațiilor
- **Calitatea voturilor** — dacă un consilier a votat în favoarea unui proiect care îl avantajează indirect
- **Participarea activă la dezbateri** — procesul verbal integral poate conține intervenții orale, dar nu este obligatoriu publicat online

---

## 5. Gap-uri legislative critice pentru platformă

| Gap | Impact | Workaround |
|-----|--------|-----------|
| Absențele nemotivate — motivat vs. nemotivat nedefinit legal | Nu poți automatiza alerta „risc încetare mandat" — platforma poate număra absențele, nu le poate califica | Afișează numărul brut + alertă informativă la >3 absențe consecutive în 3 luni |
| PV integral — nu e obligatoriu online | Nu poți automatiza extragerea intervențiilor orale | Solicită PV prin Legea 544 pentru consilieri de interes |
| Conformarea ANI pentru comune mici — rate necunoscute | Portalul ANI poate fi incomplet | Permite raportare manuală de utilizatori („lipsă din portal") |
| HG 123/2002 — procedura exactă de solicitare necunoscută | Nu poți genera cereri Legea 544 perfect conforme | Folosește modelul generic din Legea 544/2001 |

---

## 6. Recomandare pentru arhitectura minimă (MVP)

Un MVP al platformei poate funcționa cu:

1. **Profil consilier** — date statice: UAT, mandat, grup politic, comisii
2. **Tracker declarații ANI** — link direct la declarațiile de pe portal ANI + alertă dacă lipsesc
3. **Jurnal ședințe** — intrare manuală sau scraper, cu prezență și vot per consilier
4. **Generator cereri Legea 544** — formular pre-completat pentru solicitarea documentelor
5. **Scor de conformare** — bazat pe indicatorii din secțiunea 3 care pot fi verificați

**Datele cu volum mic și calitate ridicată sunt mai valoroase decât acoperire completă cu date nesigure.**

---

## Surse pentru această analiză

- [01-statut-consilier-local.md](01-statut-consilier-local.md)
- [02-activitatea-consiliului-local.md](02-activitatea-consiliului-local.md)
- [03-legea-544-acces-informatii.md](03-legea-544-acces-informatii.md)
- [04-legea-52-transparenta-decizionala.md](04-legea-52-transparenta-decizionala.md)
- [05-ani-declaratii-avere-interese.md](05-ani-declaratii-avere-interese.md)
