# KItrusselen - Innsiktsforbedringer

## Bakgrunn

KItrusselen viser KI-eksponering for 599 norske yrker i et interaktivt treemap. Hovedverdien er makroinnsikt - aggregeringer som viser trender i det norske arbeidsmarkedet, ikke presisjon per enkeltyrke. Brainstorming avdekket at de to mest interessante innsiktene (utdanningsparadokset og mismatch) har svakest datagrunnlag, mens sysselsetting/lønn-dimensjonen er solid.

## Mål

Styrke innsiktskvaliteten ved å:
1. Fjerne misvisende data/filtre som gir falsk presisjon
2. Løfte de sterkeste innsiktene ut av about-siden og inn i hovedvisualiseringen
3. Fikse datahull som forurenser aggregeringer
4. Vise bransjedata som allerede finnes men ikke er synlig

## Endringer

### 1. Fjern misvisende studenttrend-data fra per-yrke-nivå

**Problem:** Studenttrender har kun 7 unike verdier (SSB fagfelt-nivå). Alle 195 "Akademiske yrker" deler trenden 5.2%. Mismatch-filteret er en kategorifilter forkledd som innsikt.

**Løsning:**
- Fjern `student_trend` fra per-yrke-oppføringer i `site/data.json` (i `build_site_data.py`)
- Fjern mismatch-filteret (`data-filter="mismatch"`) og populær-utdanning-filteret (`data-filter="popular_edu"`) fra hurtigfiltre i HTML
- Fjern studenttrend-visning fra tooltip i JS (hvis den vises der)
- Fjern JS-logikk for mismatch/popular_edu-filtre
- Behold `students_data.json` og `fetch_students.py` uendret for eventuell fremtidig bruk
- "Sårbare yrker" og "Transformasjon"-filtrene beholdes (de bruker ikke studentdata)

### 2. Legg til headline-innsikter over treemapet

**Problem:** Brukeren ser treemap uten kontekst. De sterkeste innsiktene (utdanningsparadokset, lønnsmasse-eksponering) sitter gjemt i about-siden.

**Løsning:** Vis 2-3 dynamisk beregnede nøkkeltall i en kompakt bar over treemapet:
- "X% av norsk lønnsmasse er i høyt eksponerte yrker (6+)"
- "Mastergrader: snitt X.X eksponering vs. fagbrev: Y.Y"
- "N yrker med høy eksponering og 500k+ lønn"

Designet skal være kompakt (en linje, mørk bakgrunn som resten) og ikke ta plass fra treemapet. Tallene beregnes dynamisk fra data.json og oppdateres når filtre er aktive (viser da filtrerte tall).

### 3. Fiks 46 yrker uten kategori

**Problem:** 46 yrker (med sysselsettingsdata) mangler STYRK-kategori, noe som forurenser aggregeringer og gjør at de faller utenfor kategorifiltre.

**Løsning:** Forbedre kategori-lookup i `build_data.py`:
1. Nåværende logikk sjekker kun eksakte STYRK-koder i `styrk_categories.json`. Utvid til å prøve kortere prefiks (4→3→2→1 siffer) for å finne major group.
2. STYRK-08 major groups (1-siffer) mapper direkte til kategorier: 1=Ledere, 2=Akademiske yrker, 3=Høyskoleyrker, 4=Kontoryrker, 5=Salgs- og serviceyrker, 6=Bønder/fiskere, 7=Håndverkere, 8=Prosess/maskin/transport, 9=Renholdere/hjelpearbeidere, 0=Militære.
3. Yrker helt uten STYRK-kode (sannsynligvis svært få) plasseres i "Uspesifisert" og ekskluderes fra kategori-aggregeringer.

### 4. Vis bransjedata i UIet

**Problem:** `site/industries.json` med 16 bransjer er bygd men aldri vist. Bransjedata gir "stor-Norge"-innsikt.

**Løsning:** Legg til en toggle i sidebaren: "Yrker | Bransjer". Bransjevisningen viser:
- Et eget treemap der størrelse = sysselsatte (thousands) og farge = disruption_risk
- Tooltip med bransjenavn, sysselsatte, antall virksomheter, omsetning, og LLM-begrunnelse (rationale)
- Sidebaren viser bransje-aggregeringer i stedet for yrke-aggregeringer

Bransje-scorene er flate (5.1-5.8 for topp 5), men visualiseringen gir likevel verdi fordi størrelseforskjellene mellom bransjer er store.

### 5. Styrk troverdighets-kommunikasjonen

**Problem:** Metode-boksen sier bare "scoret av en KI-modell" uten referansepunkt.

**Løsning:**
- Legg til en setning i about-modalen og about.html: "Tilnærmingen er inspirert av Andrej Karpathys AI Job Exposure-analyse, tilpasset norske yrker med data fra utdanning.no og SSB."
- Flytt "Transformasjon, ikke apokalypse"-perspektivet fra about-siden til en kort tekst i sidebaren eller headline-baren: "Indikator for eksponering, ikke prediksjon om jobbtap"

## Utenfor scope

- Regional dimensjon (SSB per fylke) - fremtidig forbedring
- NAV stillingsdata - krever API-tilgang, separat oppgave
- Validering mot OECD/Frey & Osborne - forskningsarbeid, ikke kodeendring
- Forbedret studentdata (SSB utdanningsprogram) - besluttet å bruke alternativ A (bakgrunn)
- Endring av navnet "KI Trusselen" - fungerer for SEO, spenningen mot innholdet er tilsiktet

## Berørte filer

- `build_data.py` - forbedret kategori-lookup (endring 3)
- `build_site_data.py` - fjern student_trend fra per-yrke (endring 1)
- `site/index.html` - fjern mismatch/populær-filtre (1), legg til headline-innsikter (2), legg til bransje-toggle og treemap (4), oppdater about-modal (5)
- `site/about.html` - oppdater kildekrediteringer (5)
