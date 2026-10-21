---
name: xanimu-redirect
description: Přesměrování (301) a smazání (do koše) videí na xanimu.com přes WP admin v Chromu uživatelky. Použij, když uživatelka chce „redirectovat / přesměrovat záložky / videa na …“, „smazat videa“, nebo napíše jen „můžeš / opět můžeš“ po předchozí dávce.
---

# Přesměrování a smazání videí na xanimu.com

Pracuje se v **Chromu uživatelky přes rozšíření Claude in Chrome** (nástroje `mcp__claude-in-chrome__*`). Uživatelka je v Chromu přihlášená do administrace, heslo nikdy nezadávej. V cloudové session tento postup nefunguje, protože tam Chrome uživatelky není.

## Fakta o webu

- Administrace: `https://xanimu.com/nosotros/` (ne `/wp-admin/`). Redirection: `https://xanimu.com/nosotros/tools.php?page=redirection.php`.
- Plugin **Redirection**, skupina **„Redirections“ = `group_id: 1`** (výchozí, uživatelka ji chce).
- Číslo na začátku URL videa je ID příspěvku: `/155931-zelda-takes-a-thick-load/` → post 155931 (vždy ověř přes API).
- Cloudflare APO cachuje stránky až 20 h. Nepřihlášeně se proto staré video ukazuje ještě chvíli po smazání. **Cache nemazat**, uživatelka to nechce. Ověřuj s `credentials:'include'`, tím cache obejdeš.

## Záložky

1. Zavolej `tabs_context_mcp`. Pokud skupina neexistuje, zavolej ho s `createIfEmpty: true` a v nové záložce otevři stránku Redirection.
2. Vidíš jen záložky ve skupině Claude, které rozšíření eviduje. Fungují ty, které uživatelka přidá do skupiny k záložce Redirection („Přidat kartu do skupiny“), nebo které otevře Ctrl+klikem z ní. Když je nevidíš, zavolej `tabs_context_mcp` znovu a pak jí to vysvětli.
3. Ze záložek vezmi jen **videa** (`/ČÍSLO-slug/`). Přeskoč stránky kategorií (`/22-games/…`, `/16884-anime/…`, `/categories/`, `…/page/N/`) a administraci.
4. **Cílovou stránku redirectu nikdy nepřesměrovávej ani nemaž**, i když je otevřená v záložce.

## Cíl

- Uživatelka napíše cíl („vše na X, až na A → B“). Konkrétní dvojice mají přednost, „vše ostatní“ jde na hlavní cíl.
- Když napíše jen „můžeš / opět můžeš“, použij cíl z předchozí dávky ze stejné kategorie a řekni to v odpovědi. Pokud předchozí dávka neexistuje nebo jde o jinou kategorii, zeptej se.
- Video, které tematicky nesedí (např. Final Fantasy mezi GTA), proveď a v odpovědi na něj upozorni.

## Provedení

Spusť přes `javascript_tool` v záložce administrace. `jobs` = pole `[zdrojová cesta, cílová cesta]` (relativní cesty se `/` na konci). Skript:
- ověří, že cíl vrací 200, příspěvek je `publish` a jeho permalink sedí s URL a že pro ID ještě neexistuje redirect, jinak příspěvek přeskočí;
- založí 301 redirect, teprve potom přesune příspěvek do koše (`DELETE` bez `force` = koš; **nikdy trvale**);
- ověří, že URL vede na cíl.

```js
const n = wpApiSettings.nonce;
const jobs = [
  // ["/123-zdroj/", "/456-cil/"],
];
const tchk = {};
for (const t of new Set(jobs.map(j => j[1]))) { const r = await fetch(t, {credentials:'include', cache:'no-store', redirect:'manual'}); tchk[t] = r.status; }
const out = [];
for (const [u, target] of jobs) {
  const id = u.match(/^\/(\d+)-/)[1];
  const p = await fetch(`/wp-json/wp/v2/posts/${id}?context=edit&_fields=id,status,title,link`, {headers:{'X-WP-Nonce':n}}).then(r=>r.json());
  const ex = await fetch(`/wp-json/redirection/v1/redirect?filterBy%5Burl%5D=${id}-&per_page=5`, {headers:{'X-WP-Nonce':n}}).then(r=>r.json());
  if (!p.link || new URL(p.link).pathname !== u || p.status !== 'publish' || (ex.items||[]).length || tchk[target] !== 200) {
    out.push({id, skipped:true, status:p.status, link:p.link, existing:(ex.items||[]).map(i=>i.url), target:tchk[target]}); continue;
  }
  const r = await fetch('/wp-json/redirection/v1/redirect', {method:'POST', headers:{'X-WP-Nonce':n, 'Content-Type':'application/json'},
    body: JSON.stringify({url:u, match_type:'url', action_type:'url', action_code:301, action_data:{url:target}, group_id:1, title:'', regex:false})});
  const made = ((await r.json()).items||[]).find(i=>i.url===u);
  let trash = 'skipped';
  if (r.status===200 && made) { const d = await fetch(`/wp-json/wp/v2/posts/${id}`, {method:'DELETE', headers:{'X-WP-Nonce':n}}); trash = (await d.json()).status; }
  const v = await fetch(u, {credentials:'include', cache:'no-store'});
  out.push({id, title:p.title&&p.title.raw, r: made ? made.id : ('ERR '+r.status), trash, ok: new URL(v.url).pathname === target});
}
({tchk, bad: out.filter(o=>o.skipped || !o.ok || o.trash!=='trash'), out})
```

- **Timeout 45 s:** sekvenčně se vejde zhruba 25 videí. Větší dávky rozděl na části po ~20.
- Pokud `javascript_tool` přesto vyprší, skript ve stránce doběhne. **Nespouštěj ho naslepo znovu.** Počkej, pak dotazem ověř stav každého ID: `status` příspěvku a seznam redirectů s cílem. Hledej chybějící redirecty, duplicity a `trash` bez redirectu.
- U samotného ID si titul a kategorii zjistíš přes `/wp-json/wp/v2/posts/ID?context=edit&_fields=title,categories`.

## Po provedení

- Zavři záložky zpracovaných videí (`tabs_close_mcp`). Administraci, kategorie a cílové stránky nech otevřené.
- Odpověz česky, stručně: počet, tabulka ID / název / cíl, rozsah ID redirectů. Zmiň přeskočené položky a cokoli podezřelého.
