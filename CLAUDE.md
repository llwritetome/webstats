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
