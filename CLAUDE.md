# webstats – analýza návštěvnosti našich webů

Nástroj na analýzu návštěvnosti ~21 webů (GA4, Google Search Console, Ahrefs). **Komunikuj česky.**

## Přístupy (obsah klíčů nikdy nevypisuj, necommituj)

- Google: service account `claude-seo-sa@claude-seo-492911.iam.gserviceaccount.com`, čtecí přístup do všech GA4 property a GSC webů.
  - Klíč: proměnná `GA_SERVICE_ACCOUNT_JSON` (JSON nebo base64, pro claude.ai/code), jinak `secrets/ga-service-account.json`, jinak jediný service-account JSON v `secrets/` (lokálně teď `secrets/claude-seo-492911-…json`).
- Ahrefs: proměnná `AHREFS_API_KEY`, lokálně řádek `AHREFS_API_KEY=…` v `.env`, `secrets/.env` nebo `secrets/.env.txt` (teď je v `secrets/.env.txt`).
- `secrets/` a `.env*` jsou v `.gitignore`.

## Příkazy

Spouštěj `py -m webstats …` (Windows) nebo `python3 -m webstats …` (cloud). U každého příkazu je `--help`.

| příkaz | co dělá |
|---|---|
| `check` | seznam GA4 property (Admin API) a GSC webů spárovaných podle domény, uloží `.cache/sites.json` |
| `traffic [--organic] [--exclude-country Singapore] [--days 7]` | sessions všech webů vs. předchozí období |
| `ga WEB -d dims -m metriky -f filtr` | libovolný GA4 report (např. `ga punishworld -d country,deviceCategory -f "sessionDefaultChannelGroup==Organic Search"`) |
| `gsc WEB -d query,page,country,device,date -f filtr` | libovolný GSC report (např. `gsc punishworld -d query -f "country==fra" --sort delta`) |
| `ga-drill WEB [--organic]` | kde spadly sessions: kanál, zdroj, země, zařízení, vstupní stránky (`--gains` = růsty) |
| `gsc-drill WEB` | kde spadly kliky: země, zařízení, stránky, dotazy |
| `gsc-pages [WEB…]` | URL, které za týden spadly na ~0 kliků / prudce vyrostly; u spadlých HTTP stav + URL Inspection; v indexu a bez zobrazení = „DMCA / ruční odstranění?“ |
| `updates [--days 30]` | Google Search updaty/incidenty ze status.search.google.com |
| `ahrefs limits` | zbývající units (zdarma) |
| `ahrefs overview WEB [--vs KONKURENT]` | DR, Ahrefs rank, organický traffic, klíčová slova, refdomény, backlinky |
| `ahrefs history WEB [--months 12] [--vs …]` | vývoj trafficu a DR |
| `ahrefs keywords/pages/competitors/refdomains WEB [--country fr] [--limit 20]` | klíčová slova, top stránky, konkurence, refdomény |
| `ahrefs raw ENDPOINT klíč=hodnota …` | libovolný endpoint API v3 |

- WEB = část domény (`punishworld`), u GA i číslo property, u GSC i `sc-domain:…`.
- Období: `--days N` (výchozí 7), `--start/--end`, `--compare prev|yoy|none|YYYY-MM-DD`. `prev` posouvá o celé týdny, takže se vždy srovnávají stejné dny v týdnu.
- Filtry: `dim==x`, `dim!=x`, `dim~x` (obsahuje), `dim!~x`, `dim=~regex`, `dim!=~regex`, `dim^=začátek`. GA země anglicky (`France`), GSC kódem ISO-3 (`fra`).
- Výstup v JSON: `--json`.

## Pravidla analýzy

- **GSC**: data za poslední 2–3 dny jsou neúplná. Výchozí konec období je dnes − 3 dny, porovnávej jen dokončené dny.
- **GA**: den je obvykle kompletní za pár hodin, garantovaně za 24–48 h. Výchozí konec je včera; u čerstvých závěrů radši `--end` o den dřív.
- Srovnávej stejné dny v týdnu (týden vs. týden), ne víkend s všedními dny.
- Bot traffic ze Singapuru (~30–40k sessions/den na punishworld a xanimu) nadhodnocuje GA → `--exclude-country Singapore`.
- GA4 sessions jsou odhad (HyperLogLog). Stejné období vrací podle tvaru dotazu (jiné metriky, filtr, rozpad po dnech) čísla lišící se až o ~7 % (darknessporn 12.–18. 10.: 5,56M / 5,20M / 5,52M). Srovnávej jen dotazy stejného tvaru. Změny pod ~5 % ber jako šum a ověř je v GSC.
- GSC u dimenze `query` vynechává anonymizované dotazy, součet řádků je menší než celkový počet kliků.
- URL Inspection API má kvótu 2000 dotazů/den na web (`gsc-pages --inspect N`).

## Ahrefs – úspora units

- Každý požadavek stojí min. 50 units. Skutečná cena je v hlavičkách `x-api-units-cost-*`, které nástroj vypisuje. Naměřeno: řádek s 5 poli ≈ 14–23 units.
- Vždy jen potřebná pole (`--select`) a rozumný `--limit`.
- Nástroj odhaduje units a nad 1000 (`AHREFS_CONFIRM_UNITS`) chce `--yes`. **Před takovým dotazem se nejdřív zeptej uživatele a řekni mu odhad.**
- Při vývoji testuj zdarma s `ahrefs.com` (nebo `wordcount.com`). Předplatné: Standard, 800 000 units/měsíc, reset 18. dne v měsíci.

## Kontext webů

- Adult weby: punishworld, xanimu, darknessporn, transjizz, lesbosland, iamsissy, pornbaker a další (seznam: `check`).
- Od 12. 8. 2026 mají tube weby age verifikaci pro UK a FR.
- darknessporn.com má od 6. 10. 2026 nové `/fr/` stránky, které kanibalizují punishworld (FR dotazy „dark porn“).
- Bez GA4: ebonyonly, pmvtube, porncado, porngecko, salsaporn, spicypinay, thegaylinks. Bez GSC: babecock.app, darkpornsites, extremesexstories, femdom-stories.

## Zjištění (průběžně doplňovat, s datem)

### 2026-10-19 (první průchod)
- GA týden 12.–18. 10. vs 5.–11. 10.: všechny weby celkem −0,9 % sessions; punishworld −8,5 %, xanimu −6,0 %, lesbosland −5,9 %, bbwbaker −23 %; cockdude +65 %, familyporner +8,7 %, pisshamster +9 %.
- Organic Search za 14 dní (5.–18. 10. vs 21. 9.–4. 10.): punishworld −16 %, xanimu −13 %, lesbosland −16 %, transjizz −22 %. Překrývá se se **September 2026 spam update (24. 9.–8. 10.)**.
- punishworld organic: 90 % propadu je z Googlu, rovnoměrně napříč zeměmi i zařízeními; nejvíc Francie (−16 % GA, −20 % kliků GSC).
- punishworld FR: u dotazů „darkporn“, „dark porn“, „darknessporn“ spadlo CTR zhruba na polovinu a pozice je mírně horší. Odpovídá kanibalizaci novými `/fr/` stránkami darknessporn.
- punishworld: **nový bot traffic z Hong Kongu**, za týden 6,5k → 82k sessions s engagement rate 2,6 % (stejný vzor jako Singapur). Nadhodnocuje GA.
- gsc-pages (10.–16. 10.): u punishworld i darknessporn je řada URL v indexu, ale s 0 zobrazeními → podezření na DMCA / ruční odstranění (např. darknessporn `/tag/4667-big-black-cock/` 4,8k kliků → 0). Ověřit v Lumen / GSC „Odstranění“.

### 2026-10-19 – organic týden 12.–18. 10. vs 5.–11. 10.
- Největší ztráty organic sessions (GA): punishworld −288k (−12,2 %), xanimu −125k (−4,9 %), thepornlinks −63k (−3,4 %), lesbosland −57k (−9,6 %), transjizz −31k (−11,8 %), iamsissy −25k (−6,1 %), cosxplay −22k (−6,0 %). Celkem všechny weby −2,5 %.
- GSC kliky 10.–16. 10. vs 3.–9. 10. to potvrzují: punishworld −10 %, xanimu −7,9 %, lesbosland −14,8 %, transjizz −18,8 % (u transjizz zobrazení −24 %, pozice 11,2 → 12,1).
- Růst: darknessporn +2,1 % (podle tvaru dotazu −5 % až +2 %, GSC −0,2 % → v podstatě stagnace), pornbaker +2,4 %, familyporner +3,2 %.
- darknessporn má v Organic Search ~47k sessions/týden ze SG+HK s engagement ~80 %, tedy spíš skuteční uživatelé, ne boti (boti z SG na punishworld mají engagement ~5 %). Týden od týdne stabilní.
- GSC všech 24 webů (10.–16. 10. vs 3.–9. 10.): celkem −3,9 % kliků (−751k). Pořadí ztrát: punishworld −241k, xanimu −170k, lesbosland −95k, thepornlinks −94k (zobrazení −17 %!), transjizz −53k, pisshamster −39k (−5,4 %, v GA organic jen −0,4 %), iamsissy −28k, freepublicporn −16k, cockdude −12k (−8,8 %). Weby bez GA4 jsou zanedbatelné, největší pmvtube má 12k kliků/týden (−4 %).

### 2026-10-19 – příčiny propadu (GSC 10.–16. 10. vs 26. 9.–2. 10., tj. před pádem)
- **Skokový pád 6.–8. 10.**, od 9. 10. stabilně nižší úroveň: punishworld −16 %, xanimu −15 %, lesbosland −21 %, transjizz −30 %, pisshamster −9 % kliků. Pozor: srovnávací týden 3.–9. 10. obsahuje ještě dny před pádem, proto týdenní srovnání ztrátu podhodnocuje.
- Pád je rovnoměrný napříč zeměmi, zařízeními i jazykovými sekcemi URL a zobrazení klesají stejně jako kliky (pozice mírně horší) → ztráta viditelnosti/rankingu celého webu, ne CTR ani technika. Časově sedí s koncem **September 2026 spam update** (dokončen 8. 10.). Korelace, ne důkaz. darknessporn, pornbaker, familyporner, xfemaledom zasaženy nebyly.
- **punishworld FR navíc kanibalizace darknessporn**: sekce /fr/ punishworld −39 % (ostatní sekce ~−17 %), FR dotazy s „dark“ punishworld 14,2k → 5,8k (pozice 1,3 → 2,7), darknessporn 0,2k → 14,0k. darknessporn /fr/ celkem 73k → 521k kliků/týden.
- URL spadlé na ~0 (DMCA/vyřazení z indexu) tvoří jen malou část ztráty: punishworld 4 %, lesbosland 3 %, pisshamster 3 %, transjizz 0,5 %, **xanimu 10 %** (599 URL, 582 bez zobrazení → zkontrolovat DMCA v Lumen / GSC).
- thepornlinks není skutečná ztráta: ve srovnávacím týdnu měl špičku 7.–8. 10. Proti 26. 9.–2. 10. má +7,8 %. Jeho vlastní skokový pokles (~−12 %) přišel 28. 9.

### 2026-10-19 – xanimu: spadlé URL (10.–16. 10. vs 26. 9.–2. 10.)
- 599 URL spadlo na ~0 kliků, předtím měly 27,8k kliků/týden (~10 % celkové ztráty xanimu). HTTP: 597× 200, 2× 301, technické chyby žádné.
- URL Inspection u 200 největších: 190 je „Odesláno a indexováno“, ale **173 z nich má 0 zobrazení**. Stránka je v indexu a Google ji vůbec neukazuje, což je typický vzorec **DMCA / ruční odstranění**. Jen 10 URL je mimo index (neindexováno / jiná kanonická), 17 má zobrazení, ale propadlo v pozicích.
- Zobrazení nemizela najednou, ale postupně od 29. 9. do 9. 10. (nejvíc 2.–3. a 9. 10.) → spíš průběžné vlny stížností než jeden zásah.
- Typ: 283 videí, 127 tagů + lokalizované tagy, napříč jazyky (en 195, vi 79, es 62, ar 59, fr 46). V URL se opakují chráněné postavy: Rapunzel 11, Gwen 7, Samsung (Sam) 6, Pokémon 6, Elsa 4, Disney 4.
- Potvrzení: zprávy v GSC (Google posílá oznámení o odstranění kvůli DMCA) a lumendatabase.org (hledat xanimu.com). Seznam URL: `out/xanimu_dropped.json` (skript `out/xanimu_check.py`, mimo git).

### 2026-10-19 – bot traffic na všech webech (GA 12.–18. 10.)
- Boti nejsou jen ze Singapuru a ne jen na punishworld/xanimu. Země s engagement < 15 % a > 3k sessions/týden: Hong Kong, Singapur, Japonsko, Čína. Tvoří ~2,1M z 22,3M sessions/týden (~9,5 %). Chodí převážně jako Direct (organic skoro nezkreslují).
- Podíl bot zemí na sessions: famecop 51 %, cockdude 41 %, lesbosland 38 %, familyporner 27 %, pisshamster 20 %, bbwbaker 20 %, iamsissy 18 %, transjizz 14 %, punishworld 12 %, xanimu 8 %, xfemaledom 8 %, pornbaker 6 %.
- **Nová vlna z Hong Kongu tento týden** (+~430k): cockdude 0,4k → 127k, pisshamster 97k → 184k, familyporner 101k → 179k, punishworld 6,5k → 82k, lesbosland 99k → 158k. Japonsko: iamsissy 50k → 108k, transjizz 31k → 48k.
- Důsledek: „růst“ cockdude +65 % a pisshamster +9 % v celkových GA sessions je bot traffic. bbwbaker −23 % je úbytek botů z Direct/SG, ne ztráta uživatelů. Celkové GA sessions proto nepoužívat bez vyřazení bot zemí; organic je OK.
- Řádek `(other)` v rozpadu po zemích (darknessporn 565k) je GA limit kardinality, ne boti.
