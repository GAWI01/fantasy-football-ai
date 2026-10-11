# Lærdommer fra Fantasy Football AI

Erfaringer fra å bygge og drifte Fantasy Football AI (FastAPI + Next.js +
ML-modell, live på Vercel/Railway). Fila er skrevet så den kan gis direkte til
en annen AI-agent (Codex, Claude Code) eller brukes som sjekkliste når du
starter noe nytt.

Hvert punkt har tre deler: **hva som gikk galt**, **hvorfor**, og **regelen
for neste gang**.

> Dette er praktisk erfaring, ikke juridisk rådgivning. Ved betalte tjenester,
> reklame eller store brukertall: få en jurist til å se på vilkår og personvern.

---

## 1. Juss, personvern og data (viktigst, fordi alt er offentlig)

### 1.1 Personopplysninger havnet i et offentlig repo
- **Hva:** Et benchmark-opptak av ekte FPL-svar inneholdt fulle navn, land og
  ligaer for 11 andre managere. Testfiler brukte ekte liganavn, lagnavn og
  etternavn fra en privat liga. Alt var offentlig på GitHub.
- **Hvorfor:** Opptaket lagret hele API-svar ukritisk. Testdata ble kopiert fra
  virkeligheten fordi det var raskest.
- **Regel:**
  - Anonymiser **i det du tar opp**, ikke etterpå: fjern navn, region, logo-URL
    og ligaer, og bytt ID-er til syntetiske.
  - Bruk alltid oppdiktede navn i tester, fixtures og skjermbilder, også for
    "bare venner".
  - Sjekk med et søk før commit: `git grep -i` etter kjente navn, e-poster,
    telefonnumre.

### 1.2 Git-historikk glemmer ingenting
- **Hva:** Å fjerne navnene fra filene var lett. Å fjerne dem fra
  historikken krever omskriving og force-push av alle grener, og GitHub
  beholder fortsatt kopier i PR-referanser og cache til Support sletter dem.
- **Regel:** Forebygg. Ikke-sensitive testdata fra dag én, `.gitignore` for
  opptak, og en rask pre-commit-sjekk. Har noe sensitivt allerede sluppet ut:
  rens nåværende filer straks, og vurder historikk-rens pluss GitHub Support.

### 1.3 Dataminimering: vis bare det funksjonen trenger
- **Hva:** Appen viste etternavn på rivaler i mini-ligaer og på eget lag.
  Det var offentlig hos FPL, men å republisere navn er likevel behandling av
  personopplysninger.
- **Regel:** Lagnavn holder. Ikke vis eller returner personnavn med mindre
  funksjonen faktisk krever det. Fjern feltet i API-et også, ikke bare i UI-et.

### 1.4 Logger er personopplysninger
- **Hva:** Request-logger inneholdt Team ID i URL-en. Uvicorns tilgangslogg
  koblet klient-IP og full URL.
- **Regel:**
  - Masker ID-er i loggede stier (`/dashboard/{id}`).
  - Slå av tilgangslogger som lagrer IP (`uvicorn --no-access-log`).
  - Logg rute, status og tid, ikke hvem.

### 1.5 Personvernside, vilkår og kontakt fra dag én
- **Hva:** Appen var live uten personvernerklæring, vilkår eller kontaktpunkt
  for fjerning.
- **Regel:** En enkel `/privacy` før lansering:
  - hvem som drifter, og hvordan man kontakter dem;
  - hvilke data som brukes, og hvor de kommer fra;
  - hva som lagres i nettleseren (list `localStorage`-nøkler) og at det ikke
    brukes cookies eller analyse;
  - hostingens logger og rettslig grunnlag (GDPR art. 6(1)(f), berettiget
    interesse);
  - bruksvilkår ("som det er", ingen garanti, ikke skrap);
  - fjerningsrutine for rettighetshavere.

  Lenk den fra bunnen av hver side. «Koble fra» skal slette **alt** appen har
  lagret.

### 1.6 Data fra andre: tillatelse, kreditering, lisens
- **Hva:**
  - Historiske data kom fra et offentlig GitHub-repo (vaastav). Tillatelse ble
    innhentet etterpå, med krav om kreditering og lenke.
  - Understat-data uten åpen lisens lå i repoet uten å være i bruk.
  - Repoet hadde ingen LICENSE-fil.
- **Regel:**
  - Spør eieren **før** du bruker dataene, noter svaret med dato og vilkår, og
    krediter med lenke både i README og i appen.
  - Ikke commit data du ikke har rett til eller ikke bruker.
  - Ha alltid en LICENSE for koden, med en setning om at data ikke dekkes.
  - Skill kode og data med en `DATA_NOTICE.md`.
  - Rådata fra en offisiell tjeneste (her FPL) eies av tjenesten. Republiser
    helst ikke store dumper, og hold appen gratis og ikke-kommersiell med
    mindre du har avtale.

### 1.7 Varemerker og logoer
- **Riktig gjort:**
  - ingen Premier League- eller FPL-logoer, klubbmerker eller spillerbilder;
  - egne, forenklede drakter i klubbfarger;
  - produktnavn uten andres varemerke;
  - ansvarsfraskrivelse ("ikke tilknyttet …") på hver side.
- **Feil:** Kildemerket «Official» kunne leses som at appen var offisiell.
- **Regel:** Bruk andres navn bare beskrivende ("for Fantasy Premier League").
  Skriv aldri «Official» om din egen app eller dine merker; skriv «FPL data»
  eller lignende.

### 1.8 Misbruk og belastning på kilden
- **Hva:** API-et hadde ingen grense per klient, så én bruker kunne tømme
  appens felles kvote mot FPL eller laste ned alt.
- **Regel:**
  - Rate limit per klient-IP fra start.
  - Bak en proxy (Railway, Vercel, Cloudflare) er `request.client` proxyen.
    Bruk **siste** oppføring i `X-Forwarded-For`, den proxyen selv la til.
  - Vær høflig mot kilden: cache, egen User-Agent med kontakt-URL, maks
    forespørsler per minutt, få parallelle tråder i skript.

---

## 2. Domenelogikk og korrekthet

### 2.1 Én kilde til sannhet for beslutninger
- **Hva:** UI-et og motoren regnet hver sin overgang. Gevinster ble talt to
  ganger, kaptein ble valgt blant spillere planen solgte, og frontend
  "korrigerte" backend.
- **Regel:** Backend tar beslutningen én gang. Frontend viser den og regner
  aldri på nytt. Alle alternativer, inkludert «gjør ingenting», scores på samme
  skala.

### 2.2 «Ikke gjør noe» må være et reelt alternativ
- **Hva:** Motoren brukte alltid alle gratis overganger og anbefalte aldri å
  vente.
- **Regel:** Gi det å vente en verdi (en spart overgang er verdt noe). Kostnader
  som minuspoeng (hits) skal ha en tydelig terskel. Erstatt påstander i UI-et
  om "terskler" som ikke finnes, med de reelle reglene.

### 2.3 Modellér hva som faktisk teller
- **Hva:** Benkspillere ble verdsatt som startere, så motoren kjøpte
  reservekeeper. Skader ble trukket fra for alle fem rundene selv om utestengelsen
  bare gjaldt én.
- **Regel:**
  - Vekt etter reell effekt: benken teller bare som reserve.
  - Tilgjengelighet per runde, med returdatoer fra offisielle nyheter.
  - Selgepriser etter regelen (kjøpspris pluss halve økningen), ikke markedspris.

### 2.4 Live-tilstander er mer enn ferdig eller ikke ferdig
- **Hva:**
  - Kamper på 90' ble vist som «spiller» fordi FPLs `finished` venter på en
    datakontroll i flere timer.
  - Jeg antok at bonus var foreløpig, men FPL legger den inn kort tid etter
    kampslutt.
  - Planlegging av neste runde var blokkert mens runden pågikk.
- **Regel:**
  - Kartlegg kildens faktiske tilstander (`finished_provisional`, når bonus
    legges inn) med ekte data. Ikke gjett.
  - Støtt overlappende faser: planlegg runde N+1 mens N er live, med en
    foreløpig prognose som er tydelig merket.

### 2.5 Vis usikkerhet ærlig
- **Regel:**
  - Merk hvert tall med kilde (offisiell, modell, utledet).
  - Si «ukjent» heller enn å late som.
  - Sikkerhetsnivå skal ha et mål (margin mot neste beste alternativ), ikke
    være «høy» overalt.

---

## 3. Deploy, drift og infrastruktur

### 3.1 Byggtids-variabler
- **Hva:** `NEXT_PUBLIC_API_URL` bakes inn i Next.js ved bygging. Et lokalt
  bygg uten variabelen pekte på feil sted og ga 404.
- **Regel:** Dokumenter hvilke variabler som brukes ved bygging og hvilke ved
  kjøring. Sett dem eksplisitt i bygg-kommandoen.

### 3.2 Frontend og backend deployes ikke samtidig
- **Hva:** Vercel kan være ute før Railway. Ny frontend møter gammel backend
  med manglende felt.
- **Regel:** Nye felt er valgfrie i frontend, med en fornuftig fallback. Fjern
  felt fra backend først når frontend ikke bruker dem.

### 3.3 Planlagte jobber kjører ikke ved merge
- **Hva:** Siden manglet prognose etter merge, fordi den planlagte jobben
  (hver tredje time) hadde kjørt før.
- **Regel:** Gi jobben `workflow_dispatch`, og kjør den manuelt etter
  endringer den avhenger av. Siden skal tåle at dataene ikke finnes ennå.

### 3.4 Docker og tillatelseslister
- **Hva:** Next.js standalone-bilde kopierte ikke `public/`, så ikonene
  manglet. Backend-bildet bruker en allowlist i `.dockerignore`, og nye moduler
  må legges til der.
- **Regel:** Test produksjonsbildet, eller simuler det: installer bare
  kjøretidsavhengigheter, kopier bare tillatte filer og importer appen.

### 3.5 Branch og PR etter merge
- **Hva:** En PR ble merget mens arbeidet fortsatte på samme branch. Nye
  commits havnet utenfor master.
- **Regel:** Sjekk om PR-en er merget før du fortsetter. Start ny branch fra
  oppdatert master for oppfølgingsarbeid.

---

## 4. UI og mobil

### 4.1 Test med ekte variasjon, ikke bare ditt eget eksempel
- **Hva:**
  - Formasjoner med 5 i en rad (3-5-2) sprengte banen på smale telefoner.
    Utviklerens eget lag hadde 4 i hver rad, så feilen ble ikke sett.
  - Lange navn og mange gjentatte hendelser ga rotete visning.
- **Regel:** Test på 320, 360 og 390 px og på desktop, med ytterpunkter i dataene
  (maks antall per rad, lange navn, null-verdier, før kampstart, live og etter
  kampslutt).

### 4.2 CSS-feller vi gikk i
- **Faste kolonner i en tabell som scroller:** `position: sticky` låses
  innenfor scroll-beholderens padding. Sett `left: -<padding>`, ellers skimtes
  innholdet i gapet.
- **Flex og grid som skal krympe:** barn trenger `min-width: 0`, og
  grid-spor `minmax(0, 1fr)`. Ellers blir alt bredere enn forelderen.
- **Popover inne i `overflow: hidden`:** rendres i en portal med `position:
  fixed` og klemmes inn i viewporten.
- **Mange menypunkter:** bruk korte etiketter, og test bredden når du legger
  til ett.

### 4.3 iPhone-hjemskjerm (PWA)
- **Hva:** Lagt til på hjemskjermen havnet headeren under klokka, og menyen
  fløt over hjem-indikatoren.
- **Regel:**
  - Bruk `viewport-fit=cover` og `env(safe-area-inset-*)`.
  - Legg reglene under `@media (display-mode: standalone)`, så vanlig nettleser
    ikke endres.
  - `apple-touch-icon` skal være 180 px, ugjennomsiktig og fylle hele flaten.
    iOS runder hjørnene selv.

### 4.4 App-ikon
- **Hva:** En detaljert illustrasjon så ikke ut som en app-logo og ble grøt i
  16–32 px.
- **Regel:**
  - Ett enkelt symbol på flat bakgrunn, laget som vektor (SVG), og lesbart i
    16 px.
  - Én kildefil og et skript som genererer favicon, apple-icon og
    manifest-ikoner (inkludert maskable med 80 % trygg sone).
  - Har brukeren allerede lagt appen på hjemskjermen, må snarveien legges til
    på nytt for å få nytt ikon.

### 4.5 Enkelhet slår mengde
- **Regel:**
  - Ikke vis samme informasjon to ganger på én side.
  - Bruk vanlig språk i stedet for tekniske feilmeldinger ("No certified …
    artifact").
  - Åpne visninger på et utgangspunkt som faktisk har data.

---

## 5. Testing og verifisering

- **Opptak og replay:** Ta opp ekte API-svar og spill dem av i en benchmark.
  Det fanger feil enhetstester ikke ser, men anonymiser opptaket (se 1.1).
- **Bevis før du påstår:** Reproduser feilen, vis at den er borte, og ta
  skjermbilde eller mål (for eksempel «0 spillere kuttet på 320/360/390 px»).
- **Skjermbilder i README:** anonymiser andres navn med en avlyttet API-respons
  før opptak.
- **Tester som låser feil oppførsel:** Når du retter logikk, oppdater testene
  som forventet den gamle, feilaktige oppførselen. Ikke la dem bestemme.

---

## 6. Arbeidsflyt med AI-agenter

- **Gi agenten en tydelig spesifikasjon:** problem, krav (P0/P1), hva som ikke
  skal gjøres ennå, og hvordan resultatet skal verifiseres.
- **Be om en «gjort, verifisert, ikke verifisert, gjenstår»-rapport** etter
  hver fase.
- **Irreversible handlinger** (force-push, sletting, merge til produksjon) skal
  bekreftes av et menneske. Sett opp tillatelser bevisst.
- **Be agenten sjekke egne antakelser mot ekte data.** Feilen om foreløpig
  bonus var en antakelse.
- **Små og hyppige PR-er** med tydelig beskrivelse er lettere å gå gjennom og
  rulle tilbake.

---

## 7. Sjekklister

### Ved start av nytt prosjekt
- [ ] LICENSE for koden, med en setning om at data ikke dekkes
- [ ] `DATA_NOTICE.md`: datakilder, eiere, tillatelser med dato, kreditering
- [ ] Tillatelse fra dataeiere innhentet **før** bruk, og kreditering i app og README
- [ ] Testdata og fixtures er oppdiktede; opptak anonymiseres automatisk
- [ ] `.gitignore` for opptak, `.env`, cache og store datafiler
- [ ] Ingen andres logoer, merker eller bilder; eget navn og ikon (SVG)
- [ ] API: rate limit per IP (riktig IP bak proxy), cache mot kilden,
      User-Agent med kontakt-URL
- [ ] Logger uten ID-er og IP; tilgangslogg av
- [ ] Én kilde til sannhet for forretningslogikk (backend)

### Før lansering
- [ ] `/privacy` med vilkår og kontakt eller fjerningsrutine, lenket fra hver side
- [ ] Ansvarsfraskrivelse: «ikke tilknyttet …» på hver side
- [ ] Ingen «Official» eller lignende om egne data og merker
- [ ] Ingen personnavn vises uten at funksjonen krever det
- [ ] «Koble fra» eller «slett» fjerner alt lagret i nettleseren
- [ ] Ingen analyse eller cookies uten samtykke (ellers trengs samtykkebanner)
- [ ] Testet på 320, 360 og 390 px og desktop, i nettleser og som hjemskjerm-app
- [ ] Ikoner: favicon, apple-touch-icon 180 px og manifest med maskable
- [ ] Produksjonsbygg testet: byggtids-variabler satt, Docker-bilde med alle filer
- [ ] Planlagte jobber kan startes manuelt og er kjørt minst én gang
- [ ] `git grep` etter navn og hemmeligheter i hele repoet før det gjøres offentlig

### Hvis appen skal tjene penger senere
- [ ] Les vilkårene til datakildene på nytt (kommersiell bruk er ofte forbudt)
- [ ] Skriftlig avtale med dataeiere
- [ ] Juridisk gjennomgang av vilkår, personvern og varemerker
