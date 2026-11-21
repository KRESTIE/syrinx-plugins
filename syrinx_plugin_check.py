#!/usr/bin/env python3
"""
syrinx_plugin_check.py — Vérifie qu'un plugin suit le protocole Syrinx (docs/protocol.md, version 1).

    python3 syrinx_plugin_check.py https://exemple.org/syrinx/manifest.json
    python3 syrinx_plugin_check.py <adresse> --lang en --json rapport.json

Ce qu'il fait, sans rien modifier chez le plugin (seulement des GET, jamais POST ni DELETE) :
  1. lit le manifeste et vérifie ses champs ;
  2. pour chaque ressource déclarée, fait les appels de lecture qu'une app ferait (catalogues, recherche, fiches,
     lecture, lecture continue, paroles, stats…) en prenant ses exemples dans les réponses précédentes (le premier
     titre d'un catalogue sert à tester stream, similar, actions…) ;
  3. vérifie la forme de chaque réponse : champs obligatoires, types, valeurs permises ;
  4. pour stream : le fichier audio répond-il (premiers octets, plages Range) ?

Chaque point est rangé en OK, AVERTISSEMENT (permis mais à corriger : un champ facultatif mal formé, une ressource
inconnue) ou ERREUR (une app ne pourrait pas s'en servir). Code de sortie : 0 sans erreur, 1 sinon.

Python 3.10 ou plus récent, rien à installer (bibliothèque standard seulement).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROTOCOL = 1
TYPES = {"track", "album", "artist", "playlist"}
KNOWN = {
    # Source
    "catalog", "search", "meta", "stream", "similar", "wave",
    # Bibliothèque
    "actions", "import", "jobs", "upload", "library", "suggestions",
    # Compagnons
    "lyrics", "scrobble", "stats", "wrapped", "dashboard", "milestones", "profiles", "prefs", "now", "remote", "jam",
    "tastes", "artist", "update", "voice",
    # Réglages
    "settings",
}
PERMISSIONS = {"plays", "devices", "voice", "files", "notifications", "update"}
NEEDS = {"scrobble": "plays", "now": "devices", "remote": "devices", "jam": "devices", "voice": "voice",
         "upload": "files", "update": "update"}
QUALITIES = ("raw", "opus256", "opus128", "mp3320")
FIELD_TYPES = {"text", "choice", "secret", "toggle", "number"}


class Report:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str, str]] = []      # (niveau, où, message)

    def ok(self, where: str, msg: str) -> None:
        self.lines.append(("OK", where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.lines.append(("AVERTISSEMENT", where, msg))

    def err(self, where: str, msg: str) -> None:
        self.lines.append(("ERREUR", where, msg))

    @property
    def errors(self) -> int:
        return sum(1 for x in self.lines if x[0] == "ERREUR")

    @property
    def warnings(self) -> int:
        return sum(1 for x in self.lines if x[0] == "AVERTISSEMENT")


class Plugin:
    """Appels HTTP au plugin, comme une app : adresses relatives au dossier du manifeste, en-têtes Syrinx."""

    def __init__(self, manifest_url: str, lang: str, timeout: float) -> None:
        if not manifest_url.endswith("manifest.json"):
            raise SystemExit("L'adresse doit se terminer par manifest.json")
        self.manifest_url = manifest_url
        self.base = manifest_url[: -len("manifest.json")]
        self.lang = lang
        self.timeout = timeout

    def url(self, path: str) -> str:
        return urllib.parse.urljoin(self.base, path)

    def request(self, path: str, headers: dict | None = None) -> tuple[int, dict, bytes, float]:
        req = urllib.request.Request(self.url(path), headers={
            "X-Syrinx-Lang": self.lang, "User-Agent": "Syrinx-plugin-check/1", **(headers or {})})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read(2_000_000)
                return r.status, dict(r.headers), body, time.monotonic() - start
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {}), e.read(200_000), time.monotonic() - start

    def get_json(self, rep: Report, where: str, path: str, *, allow: tuple[int, ...] = ()) -> object | None:
        """GET et JSON ; rien (None) si l'appel échoue (l'erreur est déjà notée)."""
        try:
            status, headers, body, took = self.request(path)
        except Exception as e:                   # réseau, délai dépassé, adresse illisible
            rep.err(where, f"appel impossible : {e}")
            return None
        if status in allow:
            return None
        if status >= 400:
            msg = ""
            try:
                msg = json.loads(body).get("error", "")
            except Exception:
                pass
            if status == 503:
                rep.warn(where, f"503 (pas prêt) {msg}".strip())
            else:
                rep.err(where, f"HTTP {status} {msg}".strip())
            return None
        ctype = headers.get("Content-Type", headers.get("content-type", ""))
        if "json" not in ctype:
            rep.warn(where, f"Content-Type « {ctype} » au lieu de application/json")
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            rep.err(where, f"réponse qui n'est pas du JSON UTF-8 : {e}")
            return None
        if took > 5:
            rep.warn(where, f"réponse lente ({took:.1f} s) : l'app attend sans rien afficher")
        return data


# ===================================================================== formes

def check_item(rep: Report, where: str, it: object) -> bool:
    if not isinstance(it, dict):
        rep.err(where, "un élément n'est pas un objet")
        return False
    good = True
    for k in ("id", "type", "title"):
        if not isinstance(it.get(k), str) or not it.get(k):
            rep.err(where, f"élément sans « {k} » (texte obligatoire) : {json.dumps(it)[:120]}")
            good = False
    if it.get("type") not in TYPES:
        rep.err(where, f"type « {it.get('type')} » inconnu (track, album, artist, playlist)")
        good = False
    texts = ("subtitle", "artist", "album", "albumId", "artistId", "artwork", "badge", "notice", "key", "genre",
             "format", "banner", "description", "libraryId", "onlineId")
    for k in texts:
        if k in it and it[k] is not None and not isinstance(it[k], str):
            rep.warn(where, f"« {k} » devrait être du texte (élément {it.get('id')})")
    for k in ("duration", "year", "tempo", "bpm", "mixIn", "mixOut", "energy", "songCount", "owned"):
        if k in it and it[k] is not None and not isinstance(it[k], (int, float)):
            rep.warn(where, f"« {k} » devrait être un nombre (élément {it.get('id')})")
    for k in ("playable", "favorite", "live", "explicit"):
        if k in it and not isinstance(it[k], bool):
            rep.warn(where, f"« {k} » devrait être true ou false (élément {it.get('id')})")
    src = it.get("source")
    if src is not None and (not isinstance(src, dict) or not src.get("name") or not src.get("url")):
        rep.warn(where, "« source » doit avoir au moins name et url (crédit de licence)")
    if "keep" in it and it["keep"] is not None:
        check_action(rep, where + " (keep)", it["keep"])
    return good


def check_items(rep: Report, where: str, items: object, *, empty_ok: bool = True) -> list[dict]:
    if not isinstance(items, list):
        rep.err(where, "« items » doit être une liste")
        return []
    if not items and not empty_ok:
        rep.warn(where, "liste vide")
    good = [it for it in items if check_item(rep, where, it)]
    ids = [it["id"] for it in good]
    if len(ids) != len(set(ids)):
        rep.warn(where, "le même identifiant revient plusieurs fois dans la liste")
    return good


def check_fields(rep: Report, where: str, fields: object) -> None:
    if not isinstance(fields, list):
        rep.err(where, "« fields » doit être une liste")
        return
    for f in fields:
        if not isinstance(f, dict) or not f.get("key") or not f.get("label"):
            rep.err(where, "un champ sans key ou label")
            continue
        if f.get("type", "text") not in FIELD_TYPES:
            rep.warn(where, f"type de champ « {f.get('type')} » inconnu ({', '.join(sorted(FIELD_TYPES))})")
        if f.get("type") == "choice" and not isinstance(f.get("options"), list):
            rep.err(where, f"champ « {f['key']} » : un choix sans « options »")


def check_action(rep: Report, where: str, a: object) -> None:
    if not isinstance(a, dict) or not a.get("id") or not isinstance(a.get("label"), str):
        rep.err(where, "action sans id ou label")
        return
    if a.get("style") not in (None, "danger"):
        rep.warn(where, f"action « {a['id']} » : style « {a['style']} » inconnu (seulement danger)")
    if "fields" in a:
        check_fields(rep, where + f" ({a['id']})", a["fields"])


# ===================================================================== manifeste

def check_manifest(rep: Report, m: object) -> dict | None:
    w = "manifest.json"
    if not isinstance(m, dict):
        rep.err(w, "le manifeste n'est pas un objet JSON")
        return None
    if m.get("protocol") != PROTOCOL:
        rep.err(w, f"protocol vaut {m.get('protocol')!r} au lieu de {PROTOCOL}")
    for k in ("id", "name", "version"):
        if not isinstance(m.get(k), str) or not m.get(k):
            rep.err(w, f"« {k} » manquant (texte obligatoire)")
    if isinstance(m.get("id"), str) and not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", m["id"]):
        rep.warn(w, f"id « {m['id']} » : un nom de domaine à l'envers est conseillé (org.exemple.radios)")
    if "color" in m and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(m["color"])):
        rep.warn(w, "color doit être #RRGGBB")
    res = m.get("resources")
    if not isinstance(res, list) or not all(isinstance(x, str) for x in res):
        rep.err(w, "« resources » doit être une liste de textes")
        res = []
    for r in res:
        if r not in KNOWN:
            rep.warn(w, f"ressource « {r} » inconnue du protocole {PROTOCOL} : l'app l'ignorera")
    perms = m.get("permissions", [])
    if not isinstance(perms, list):
        rep.err(w, "« permissions » doit être une liste")
        perms = []
    for p in perms:
        if p not in PERMISSIONS:
            rep.warn(w, f"permission « {p} » inconnue")
    for r, p in NEEDS.items():
        if r in res and p not in perms:
            rep.warn(w, f"« {r} » sans la permission « {p} » : l'app ne l'appellera pas")
    cats = m.get("catalogs", [])
    if "catalog" in res and not cats:
        rep.warn(w, "ressource catalog déclarée, mais aucun catalogue")
    for c in cats if isinstance(cats, list) else []:
        if not isinstance(c, dict) or not c.get("id") or not c.get("name"):
            rep.err(w, "un catalogue sans id ou name")
            continue
        if c.get("type") not in TYPES:
            rep.err(w, f"catalogue « {c['id']} » : type « {c.get('type')} » inconnu")
        if c.get("section") not in ("home", "library"):
            rep.err(w, f"catalogue « {c['id']} » : section doit être home ou library")
    imp = m.get("import")
    if "import" in res and not (isinstance(imp, dict) and imp.get("label")):
        rep.warn(w, "ressource import sans « import »: {label, hint} dans le manifeste")
    rep.ok(w, f"{m.get('name')} {m.get('version')} ({m.get('id')}), {len(res)} ressources")
    return m


# ===================================================================== ressources

def run(p: Plugin, rep: Report, search_q: str) -> None:
    m = p.get_json(rep, "manifest.json", "manifest.json")
    m = check_manifest(rep, m) if m is not None else None
    if not m:
        return
    has = set(m.get("resources") or [])
    q = urllib.parse.quote
    seen: dict[str, list[dict]] = {t: [] for t in TYPES}

    def collect(items: list[dict]) -> None:
        for it in items:
            seen[it["type"]].append(it)

    # ---- catalogues
    if "catalog" in has:
        for c in m.get("catalogs") or []:
            w = f"catalog/{c.get('id')}"
            d = p.get_json(rep, w, f"catalog/{q(str(c.get('id')), safe='')}.json?skip=0&limit=10")
            if isinstance(d, dict):
                items = check_items(rep, w, d.get("items"))
                bad = [it for it in items if it["type"] != c.get("type")]
                if bad:
                    rep.warn(w, f"{len(bad)} élément(s) d'un autre type que celui du catalogue ({c.get('type')})")
                if len(items) > 10:
                    rep.warn(w, "plus d'éléments que limit=10")
                collect(items)
                rep.ok(w, f"{len(items)} élément(s)")

    # ---- recherche
    if "search" in has:
        d = p.get_json(rep, "search", f"search.json?q={q(search_q)}")
        if isinstance(d, dict):
            secs = d.get("sections")
            if not isinstance(secs, list):
                rep.err("search", "« sections » doit être une liste")
                secs = []
            n = 0
            for s in secs:
                w = f"search ({s.get('id') if isinstance(s, dict) else '?'})"
                if not isinstance(s, dict) or not s.get("title"):
                    rep.err(w, "section sans title")
                    continue
                if "items" in s:
                    items = check_items(rep, w, s["items"])
                elif "load" in s:
                    dd = p.get_json(rep, w + " load", s["load"])
                    items = check_items(rep, w + " load", dd.get("items")) if isinstance(dd, dict) else []
                    if isinstance(dd, dict) and "errors" in dd and not isinstance(dd["errors"], list):
                        rep.warn(w, "« errors » doit être une liste de textes")
                else:
                    rep.err(w, "section sans items ni load")
                    items = []
                collect(items)
                n += len(items)
            rep.ok("search", f"{len(secs)} section(s), {n} élément(s) pour « {search_q} »")
            empty = p.get_json(rep, "search (vide)", "search.json?q=")
            if isinstance(empty, dict) and empty.get("sections"):
                rep.warn("search (vide)", "q vide devrait donner {\"sections\": []}")

    track = next(iter(seen["track"]), None)
    if not track and any(seen.values()):
        rep.warn("exemples", "aucun titre trouvé dans les catalogues ni la recherche : stream et similar non testés")

    # ---- fiches
    if "meta" in has:
        for t in ("album", "artist", "playlist", "track"):
            it = next(iter(seen[t]), None)
            if not it:
                continue
            w = f"meta/{t}"
            d = p.get_json(rep, w, f"meta/{t}/{q(it['id'], safe='')}.json")
            if not isinstance(d, dict):
                continue
            if not check_item(rep, w, d.get("item")):
                continue
            for k in ("tracks", "albums", "singles", "mine"):
                if k in d:
                    collect(check_items(rep, f"{w} {k}", d[k]))
            rel = d.get("related")
            if rel is not None and not (isinstance(rel, dict) and isinstance(rel.get("items"), list)):
                rep.warn(w, "« related » doit être {title, items}")
            facts = d.get("facts")
            if facts is not None and not all(isinstance(f, dict) and "label" in f and "value" in f for f in facts):
                rep.warn(w, "« facts » doit être une liste de {label, value}")
            rep.ok(w, f"« {d['item'].get('title')} »")
        status, *_ = p.request("meta/track/syrinx-check-introuvable.json")
        if status != 404:
            rep.warn("meta (introuvable)", f"un identifiant inconnu devrait donner 404, pas {status}")
        track = next(iter(seen["track"]), track)

    # ---- lecture
    if "stream" in has and track:
        live = bool(track.get("live"))
        for quality in ("raw", "opus128") if not live else ("raw",):
            w = f"stream ({quality})"
            d = p.get_json(rep, w, f"stream/{q(track['id'], safe='')}.json?quality={quality}")
            if not isinstance(d, dict):
                continue
            if not isinstance(d.get("url"), str) or not d["url"]:
                rep.err(w, "pas d'« url »")
                continue
            if not d.get("live") and not d.get("cacheKey"):
                rep.warn(w, "pas de « cacheKey » : l'app ne pourra pas garder ce titre en cache")
            try:
                status, headers, body, _ = p.request(d["url"], {"Range": "bytes=0-4095"})
                ctype = headers.get("Content-Type", headers.get("content-type", ""))
                if status >= 400 and d.get("live") and status in (502, 503, 504):
                    rep.warn(w, f"flux en direct injoignable pour l'instant (HTTP {status}) : la source est peut-être hors ligne")
                elif status >= 400:
                    rep.err(w, f"l'adresse audio répond HTTP {status}")
                elif not body:
                    rep.err(w, "l'adresse audio ne renvoie rien")
                else:
                    if not d.get("live") and status != 206:
                        rep.warn(w, "pas de plages Range (206) : avancer dans le titre sera lent")
                    if ctype and not (ctype.startswith("audio/") or ctype in ("application/ogg",
                                                                           "application/octet-stream")):
                        rep.warn(w, f"Content-Type « {ctype} » inattendu pour de l'audio")
                    rep.ok(w, f"audio joignable ({ctype or 'type inconnu'}, {len(body)} octets lus)")
            except Exception as e:
                rep.err(w, f"adresse audio injoignable : {e}")

    # ---- lecture continue
    if "similar" in has:
        for seed in ([track["id"]] if track else []) + ["random"]:
            w = f"similar ({'random' if seed == 'random' else 'titre'})"
            d = p.get_json(rep, w, f"similar/{q(seed, safe='')}.json?limit=5&exclude={q(seed)}&discover=1")
            if isinstance(d, dict):
                items = check_items(rep, w, d.get("items"))
                if any(it["type"] != "track" for it in items):
                    rep.err(w, "la lecture continue ne doit renvoyer que des titres")
                if any(it["id"] == seed for it in items):
                    rep.warn(w, "renvoie un identifiant de « exclude »")
                rep.ok(w, f"{len(items)} titre(s)")

    if "wave" in has:
        d = p.get_json(rep, "wave", "wave.json")
        if isinstance(d, dict):
            moods = d.get("moods")
            if not isinstance(moods, list) or not all(isinstance(x, dict) and x.get("id") and x.get("name")
                                                      for x in moods):
                rep.err("wave", "« moods » doit être une liste de {id, name, …}")
            else:
                rep.ok("wave", f"{len(moods)} humeur(s)")

    # ---- bibliothèque
    if "actions" in has:
        for t in ("track", "album", "playlist"):
            it = next(iter(seen[t]), None)
            if not it:
                continue
            w = f"actions/{t}"
            d = p.get_json(rep, w, f"actions/{t}/{q(it['id'], safe='')}.json")
            if isinstance(d, dict):
                acts = d.get("actions")
                if not isinstance(acts, list):
                    rep.err(w, "« actions » doit être une liste")
                    continue
                for a in acts:
                    check_action(rep, w, a)
                rep.ok(w, f"{len(acts)} action(s)")
    simple = {
        "jobs": ("jobs.json", "items"), "library": ("library.json", "rev"), "milestones": ("milestones.json", "marks"),
        "profiles": ("profiles.json", "profiles"), "prefs": ("prefs.json", None), "now": ("now.json", None),
        "remote": ("remote/devices.json?me=syrinx-check", "devices"), "jam": ("jam.json?me=syrinx-check", "online"),
        "tastes": ("tastes.json", "artists"), "update": ("update.json", "version"),
        "dashboard": ("dashboard.json?days=7&profile=all", None), "stats": ("stats.json?period=month", "highlights"),
        "settings": ("settings.json", "groups"),
    }
    for r, (path, key) in simple.items():
        if r not in has:
            continue
        d = p.get_json(rep, r, path)
        if not isinstance(d, dict):
            if d is not None:
                rep.err(r, "la réponse doit être un objet")
            continue
        if key and key not in d:
            rep.err(r, f"« {key} » manquant")
            continue
        if r == "jobs":
            for j in d["items"]:
                if not isinstance(j, dict) or not {"id", "label", "done", "total", "finished"} <= set(j):
                    rep.err(r, "une tâche sans id, label, done, total ou finished")
        if r == "stats":
            for s in d.get("sections") or []:
                check_items(rep, f"stats ({s.get('id') or s.get('title')})", s.get("items", []))
        if r == "settings":
            for g in d["groups"]:
                gw = f"settings ({g.get('id') if isinstance(g, dict) else '?'})"
                if not isinstance(g, dict) or not g.get("id") or not g.get("title") or not isinstance(g.get("steps"), list):
                    rep.err(gw, "un groupe sans id, title ou steps")
                    continue
                for st in g["steps"]:
                    if "fields" in st:
                        check_fields(rep, gw, st["fields"])
        if r == "update" and d.get("version") is not None and not isinstance(d.get("code"), int):
            rep.err(r, "« code » (nombre entier) manquant")
        rep.ok(r, "forme correcte")

    if "lyrics" in has and track:
        path = (f"lyrics.json?title={q(track['title'])}&artist={q(track.get('artist') or '')}"
                f"&album={q(track.get('album') or '')}&duration={track.get('duration') or ''}")
        d = p.get_json(rep, "lyrics", path)
        if isinstance(d, dict):
            lines = d.get("lines")
            if not isinstance(lines, list) or not isinstance(d.get("synced"), bool):
                rep.err("lyrics", "il faut « synced » (true/false) et « lines » (liste)")
            elif not all(isinstance(x, dict) and "text" in x and "t" in x for x in lines):
                rep.err("lyrics", "chaque ligne doit être {t, text}")
            else:
                rep.ok("lyrics", f"{len(lines)} ligne(s) pour « {track['title']} »")

    if "artist" in has and seen["artist"]:
        name = seen["artist"][0]["title"]
        d = p.get_json(rep, "artist", f"artist/info.json?name={q(name)}")
        if isinstance(d, dict) and d.get("state") not in ("building", "ready"):
            rep.err("artist", "« state » doit valoir building ou ready")
        elif isinstance(d, dict):
            rep.ok("artist", f"{name} : {d.get('state')}")

    if "suggestions" in has and track:
        d = p.get_json(rep, "suggestions", f"suggestion.json?id={q(track['id'])}")
        if isinstance(d, dict) and "item" in d:
            if d["item"] is not None:
                check_item(rep, "suggestions", d["item"])
            rep.ok("suggestions", "forme correcte")
        elif isinstance(d, dict):
            rep.err("suggestions", "« item » manquant (null s'il n'y a rien)")

    for r in ("scrobble", "voice", "upload", "import"):
        if r in has:
            rep.ok(r, "déclarée (écriture : non testée ici, l'outil ne modifie rien chez le plugin)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Vérifie qu'un plugin suit le protocole Syrinx.")
    ap.add_argument("url", help="adresse du manifeste (…/manifest.json)")
    ap.add_argument("--lang", default="fr", help="langue demandée (fr, en)")
    ap.add_argument("--search", default="a", help="texte cherché pour tester la recherche (par défaut : a)")
    ap.add_argument("--timeout", type=float, default=30, help="délai par appel, en secondes")
    ap.add_argument("--json", help="écrire aussi le rapport dans ce fichier JSON")
    ap.add_argument("--quiet", action="store_true", help="n'afficher que les avertissements et les erreurs")
    a = ap.parse_args()

    rep = Report()
    run(Plugin(a.url, a.lang, a.timeout), rep, a.search)
    width = max((len(w) for _, w, _ in rep.lines), default=10)
    for level, where, msg in rep.lines:
        if a.quiet and level == "OK":
            continue
        print(f"{level:<14} {where:<{width}}  {msg}")
    print(f"\n{rep.errors} erreur(s), {rep.warnings} avertissement(s)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump([{"level": l, "where": w, "message": m} for l, w, m in rep.lines], f, ensure_ascii=False, indent=1)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
