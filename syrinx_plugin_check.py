#!/usr/bin/env python3
"""
syrinx_plugin_check.py — checks that a plugin follows the Syrinx protocol (docs/protocol.md, version 1).

    python3 syrinx_plugin_check.py https://example.org/syrinx/manifest.json
    python3 syrinx_plugin_check.py <address> --lang fr --json report.json

What it does, without changing anything on the plugin (only GET requests, never POST or DELETE):
  1. reads the manifest and checks its fields;
  2. for each declared resource, makes the read calls an app would make (catalogs, search, pages, playback,
     continuous play, lyrics, stats…), taking its examples from earlier answers (the first track of a catalog is
     used to test stream, similar, actions…);
  3. checks the shape of each answer: required fields, types, allowed values;
  4. for stream: does the audio file answer (first bytes, Range requests)?

Each point is filed as OK, WARNING (allowed but worth fixing: a malformed optional field, an unknown resource) or
ERROR (an app could not use it). Exit code: 0 without errors, 1 otherwise.

Python 3.10 or newer, nothing to install (standard library only).
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
    # Library
    "actions", "import", "jobs", "upload", "library", "suggestions",
    # Companions
    "lyrics", "scrobble", "stats", "wrapped", "dashboard", "milestones", "profiles", "prefs", "now", "remote", "jam",
    "tastes", "artist", "update", "voice",
    # Settings
    "settings",
}
PERMISSIONS = {"plays", "devices", "voice", "files", "notifications", "update"}
NEEDS = {"scrobble": "plays", "now": "devices", "remote": "devices", "jam": "devices", "voice": "voice",
         "upload": "files", "update": "update"}
QUALITIES = ("raw", "opus256", "opus128", "mp3320")
FIELD_TYPES = {"text", "choice", "secret", "toggle", "number"}


class Report:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str, str]] = []      # (level, where, message)

    def ok(self, where: str, msg: str) -> None:
        self.lines.append(("OK", where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.lines.append(("WARNING", where, msg))

    def err(self, where: str, msg: str) -> None:
        self.lines.append(("ERROR", where, msg))

    @property
    def errors(self) -> int:
        return sum(1 for x in self.lines if x[0] == "ERROR")

    @property
    def warnings(self) -> int:
        return sum(1 for x in self.lines if x[0] == "WARNING")


class Plugin:
    """HTTP calls to the plugin, like an app: addresses relative to the manifest folder, Syrinx headers."""

    def __init__(self, manifest_url: str, lang: str, timeout: float) -> None:
        if not manifest_url.endswith("manifest.json"):
            raise SystemExit("The address must end with manifest.json")
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
        """GET and JSON; None if the call fails (the error is already reported)."""
        try:
            status, headers, body, took = self.request(path)
        except Exception as e:                   # network, timeout, unreadable address
            rep.err(where, f"call failed: {e}")
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
                rep.warn(where, f"503 (not ready) {msg}".strip())
            else:
                rep.err(where, f"HTTP {status} {msg}".strip())
            return None
        ctype = headers.get("Content-Type", headers.get("content-type", ""))
        if "json" not in ctype:
            rep.warn(where, f"Content-Type \"{ctype}\" instead of application/json")
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            rep.err(where, f"answer is not UTF-8 JSON: {e}")
            return None
        if took > 5:
            rep.warn(where, f"slow answer ({took:.1f} s): the app waits with nothing on screen")
        return data


# ===================================================================== shapes

def check_item(rep: Report, where: str, it: object) -> bool:
    if not isinstance(it, dict):
        rep.err(where, "an item is not an object")
        return False
    good = True
    for k in ("id", "type", "title"):
        if not isinstance(it.get(k), str) or not it.get(k):
            rep.err(where, f"item without \"{k}\" (required text): {json.dumps(it)[:120]}")
            good = False
    if it.get("type") not in TYPES:
        rep.err(where, f"unknown type \"{it.get('type')}\" (track, album, artist, playlist)")
        good = False
    texts = ("subtitle", "artist", "album", "albumId", "artistId", "artwork", "badge", "notice", "key", "genre",
             "format", "banner", "description", "libraryId", "onlineId")
    for k in texts:
        if k in it and it[k] is not None and not isinstance(it[k], str):
            rep.warn(where, f"\"{k}\" should be text (item {it.get('id')})")
    for k in ("duration", "year", "tempo", "bpm", "mixIn", "mixOut", "energy", "songCount", "owned"):
        if k in it and it[k] is not None and not isinstance(it[k], (int, float)):
            rep.warn(where, f"\"{k}\" should be a number (item {it.get('id')})")
    for k in ("playable", "favorite", "live", "explicit"):
        if k in it and not isinstance(it[k], bool):
            rep.warn(where, f"\"{k}\" should be true or false (item {it.get('id')})")
    src = it.get("source")
    if src is not None and (not isinstance(src, dict) or not src.get("name") or not src.get("url")):
        rep.warn(where, "\"source\" needs at least name and url (license credit)")
    if "keep" in it and it["keep"] is not None:
        check_action(rep, where + " (keep)", it["keep"])
    return good


def check_items(rep: Report, where: str, items: object, *, empty_ok: bool = True) -> list[dict]:
    if not isinstance(items, list):
        rep.err(where, "\"items\" must be a list")
        return []
    if not items and not empty_ok:
        rep.warn(where, "empty list")
    good = [it for it in items if check_item(rep, where, it)]
    ids = [it["id"] for it in good]
    if len(ids) != len(set(ids)):
        rep.warn(where, "the same id appears several times in the list")
    return good


def check_fields(rep: Report, where: str, fields: object) -> None:
    if not isinstance(fields, list):
        rep.err(where, "\"fields\" must be a list")
        return
    for f in fields:
        if not isinstance(f, dict) or not f.get("key") or not f.get("label"):
            rep.err(where, "a field without key or label")
            continue
        if f.get("type", "text") not in FIELD_TYPES:
            rep.warn(where, f"unknown field type \"{f.get('type')}\" ({', '.join(sorted(FIELD_TYPES))})")
        if f.get("type") == "choice" and not isinstance(f.get("options"), list):
            rep.err(where, f"field \"{f['key']}\": a choice without \"options\"")


def check_action(rep: Report, where: str, a: object) -> None:
    if not isinstance(a, dict) or not a.get("id") or not isinstance(a.get("label"), str):
        rep.err(where, "action without id or label")
        return
    if a.get("style") not in (None, "danger"):
        rep.warn(where, f"action \"{a['id']}\": unknown style \"{a['style']}\" (only danger)")
    if "fields" in a:
        check_fields(rep, where + f" ({a['id']})", a["fields"])


# ===================================================================== manifest

def check_manifest(rep: Report, m: object) -> dict | None:
    w = "manifest.json"
    if not isinstance(m, dict):
        rep.err(w, "the manifest is not a JSON object")
        return None
    if m.get("protocol") != PROTOCOL:
        rep.err(w, f"protocol is {m.get('protocol')!r} instead of {PROTOCOL}")
    for k in ("id", "name", "version"):
        if not isinstance(m.get(k), str) or not m.get(k):
            rep.err(w, f"\"{k}\" missing (required text)")
    if isinstance(m.get("id"), str) and not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", m["id"]):
        rep.warn(w, f"id \"{m['id']}\": a reversed domain name is recommended (org.example.radios)")
    if "color" in m and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(m["color"])):
        rep.warn(w, "color must be #RRGGBB")
    res = m.get("resources")
    if not isinstance(res, list) or not all(isinstance(x, str) for x in res):
        rep.err(w, "\"resources\" must be a list of strings")
        res = []
    for r in res:
        if r not in KNOWN:
            rep.warn(w, f"resource \"{r}\" unknown in protocol {PROTOCOL}: the app will ignore it")
    perms = m.get("permissions", [])
    if not isinstance(perms, list):
        rep.err(w, "\"permissions\" must be a list")
        perms = []
    for p in perms:
        if p not in PERMISSIONS:
            rep.warn(w, f"unknown permission \"{p}\"")
    for r, p in NEEDS.items():
        if r in res and p not in perms:
            rep.warn(w, f"\"{r}\" without the \"{p}\" permission: the app will not call it")
    cats = m.get("catalogs", [])
    if "catalog" in res and not cats:
        rep.warn(w, "catalog resource declared, but no catalogs")
    for c in cats if isinstance(cats, list) else []:
        if not isinstance(c, dict) or not c.get("id") or not c.get("name"):
            rep.err(w, "a catalog without id or name")
            continue
        if c.get("type") not in TYPES:
            rep.err(w, f"catalog \"{c['id']}\": unknown type \"{c.get('type')}\"")
        if c.get("section") not in ("home", "library"):
            rep.err(w, f"catalog \"{c['id']}\": section must be home or library")
    imp = m.get("import")
    if "import" in res and not (isinstance(imp, dict) and imp.get("label")):
        rep.warn(w, "import resource without \"import\": {label, hint} in the manifest")
    rep.ok(w, f"{m.get('name')} {m.get('version')} ({m.get('id')}), {len(res)} resources")
    return m


# ===================================================================== resources

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

    # ---- catalogs
    if "catalog" in has:
        for c in m.get("catalogs") or []:
            w = f"catalog/{c.get('id')}"
            d = p.get_json(rep, w, f"catalog/{q(str(c.get('id')), safe='')}.json?skip=0&limit=10")
            if isinstance(d, dict):
                items = check_items(rep, w, d.get("items"))
                bad = [it for it in items if it["type"] != c.get("type")]
                if bad:
                    rep.warn(w, f"{len(bad)} item(s) of another type than the catalog's ({c.get('type')})")
                if len(items) > 10:
                    rep.warn(w, "more items than limit=10")
                collect(items)
                rep.ok(w, f"{len(items)} item(s)")

    # ---- search
    if "search" in has:
        d = p.get_json(rep, "search", f"search.json?q={q(search_q)}")
        if isinstance(d, dict):
            secs = d.get("sections")
            if not isinstance(secs, list):
                rep.err("search", "\"sections\" must be a list")
                secs = []
            n = 0
            for s in secs:
                w = f"search ({s.get('id') if isinstance(s, dict) else '?'})"
                if not isinstance(s, dict) or not s.get("title"):
                    rep.err(w, "section without title")
                    continue
                if "items" in s:
                    items = check_items(rep, w, s["items"])
                elif "load" in s:
                    dd = p.get_json(rep, w + " load", s["load"])
                    items = check_items(rep, w + " load", dd.get("items")) if isinstance(dd, dict) else []
                    if isinstance(dd, dict) and "errors" in dd and not isinstance(dd["errors"], list):
                        rep.warn(w, "\"errors\" must be a list of strings")
                else:
                    rep.err(w, "section with neither items nor load")
                    items = []
                collect(items)
                n += len(items)
            rep.ok("search", f"{len(secs)} section(s), {n} item(s) for \"{search_q}\"")
            empty = p.get_json(rep, "search (empty)", "search.json?q=")
            if isinstance(empty, dict) and empty.get("sections"):
                rep.warn("search (empty)", "empty q should give {\"sections\": []}")

    track = next(iter(seen["track"]), None)
    if not track and any(seen.values()):
        rep.warn("examples", "no track found in catalogs or search: stream and similar not tested")

    # ---- pages
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
                rep.warn(w, "\"related\" must be {title, items}")
            facts = d.get("facts")
            if facts is not None and not all(isinstance(f, dict) and "label" in f and "value" in f for f in facts):
                rep.warn(w, "\"facts\" must be a list of {label, value}")
            rep.ok(w, f"\"{d['item'].get('title')}\"")
        status, *_ = p.request("meta/track/syrinx-check-not-found.json")
        if status != 404:
            rep.warn("meta (not found)", f"an unknown id should give 404, not {status}")
        track = next(iter(seen["track"]), track)

    # ---- playback
    if "stream" in has and track:
        live = bool(track.get("live"))
        for quality in ("raw", "opus128") if not live else ("raw",):
            w = f"stream ({quality})"
            d = p.get_json(rep, w, f"stream/{q(track['id'], safe='')}.json?quality={quality}")
            if not isinstance(d, dict):
                continue
            if not isinstance(d.get("url"), str) or not d["url"]:
                rep.err(w, "no \"url\"")
                continue
            if not d.get("live") and not d.get("cacheKey"):
                rep.warn(w, "no \"cacheKey\": the app cannot keep this track in its cache")
            try:
                status, headers, body, _ = p.request(d["url"], {"Range": "bytes=0-4095"})
                ctype = headers.get("Content-Type", headers.get("content-type", ""))
                if status >= 400 and d.get("live") and status in (502, 503, 504):
                    rep.warn(w, f"live stream unreachable for now (HTTP {status}): the source may be offline")
                elif status >= 400:
                    rep.err(w, f"the audio address answers HTTP {status}")
                elif not body:
                    rep.err(w, "the audio address returns nothing")
                else:
                    if not d.get("live") and status != 206:
                        rep.warn(w, "no Range requests (206): seeking in the track will be slow")
                    if ctype and not (ctype.startswith("audio/") or ctype in ("application/ogg",
                                                                           "application/octet-stream")):
                        rep.warn(w, f"unexpected Content-Type \"{ctype}\" for audio")
                    rep.ok(w, f"audio reachable ({ctype or 'unknown type'}, {len(body)} bytes read)")
            except Exception as e:
                rep.err(w, f"audio address unreachable: {e}")

    # ---- continuous play
    if "similar" in has:
        for seed in ([track["id"]] if track else []) + ["random"]:
            w = f"similar ({'random' if seed == 'random' else 'track'})"
            d = p.get_json(rep, w, f"similar/{q(seed, safe='')}.json?limit=5&exclude={q(seed)}&discover=1")
            if isinstance(d, dict):
                items = check_items(rep, w, d.get("items"))
                if any(it["type"] != "track" for it in items):
                    rep.err(w, "continuous play must return tracks only")
                if any(it["id"] == seed for it in items):
                    rep.warn(w, "returns an id from \"exclude\"")
                rep.ok(w, f"{len(items)} track(s)")

    if "wave" in has:
        d = p.get_json(rep, "wave", "wave.json")
        if isinstance(d, dict):
            moods = d.get("moods")
            if not isinstance(moods, list) or not all(isinstance(x, dict) and x.get("id") and x.get("name")
                                                      for x in moods):
                rep.err("wave", "\"moods\" must be a list of {id, name, …}")
            else:
                rep.ok("wave", f"{len(moods)} mood(s)")

    # ---- library
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
                    rep.err(w, "\"actions\" must be a list")
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
                rep.err(r, "the answer must be an object")
            continue
        if key and key not in d:
            rep.err(r, f"\"{key}\" missing")
            continue
        if r == "jobs":
            for j in d["items"]:
                if not isinstance(j, dict) or not {"id", "label", "done", "total", "finished"} <= set(j):
                    rep.err(r, "a job without id, label, done, total or finished")
        if r == "stats":
            for s in d.get("sections") or []:
                check_items(rep, f"stats ({s.get('id') or s.get('title')})", s.get("items", []))
        if r == "settings":
            for g in d["groups"]:
                gw = f"settings ({g.get('id') if isinstance(g, dict) else '?'})"
                if not isinstance(g, dict) or not g.get("id") or not g.get("title") or not isinstance(g.get("steps"), list):
                    rep.err(gw, "a group without id, title or steps")
                    continue
                for st in g["steps"]:
                    if "fields" in st:
                        check_fields(rep, gw, st["fields"])
        if r == "update" and d.get("version") is not None and not isinstance(d.get("code"), int):
            rep.err(r, "\"code\" (integer) missing")
        rep.ok(r, "shape OK")

    if "lyrics" in has and track:
        path = (f"lyrics.json?title={q(track['title'])}&artist={q(track.get('artist') or '')}"
                f"&album={q(track.get('album') or '')}&duration={track.get('duration') or ''}")
        d = p.get_json(rep, "lyrics", path)
        if isinstance(d, dict):
            lines = d.get("lines")
            if not isinstance(lines, list) or not isinstance(d.get("synced"), bool):
                rep.err("lyrics", "needs \"synced\" (true/false) and \"lines\" (list)")
            elif not all(isinstance(x, dict) and "text" in x and "t" in x for x in lines):
                rep.err("lyrics", "each line must be {t, text}")
            else:
                rep.ok("lyrics", f"{len(lines)} line(s) for \"{track['title']}\"")

    if "artist" in has and seen["artist"]:
        name = seen["artist"][0]["title"]
        d = p.get_json(rep, "artist", f"artist/info.json?name={q(name)}")
        if isinstance(d, dict) and d.get("state") not in ("building", "ready"):
            rep.err("artist", "\"state\" must be building or ready")
        elif isinstance(d, dict):
            rep.ok("artist", f"{name}: {d.get('state')}")

    if "suggestions" in has and track:
        d = p.get_json(rep, "suggestions", f"suggestion.json?id={q(track['id'])}")
        if isinstance(d, dict) and "item" in d:
            if d["item"] is not None:
                check_item(rep, "suggestions", d["item"])
            rep.ok("suggestions", "shape OK")
        elif isinstance(d, dict):
            rep.err("suggestions", "\"item\" missing (null when there is nothing)")

    for r in ("scrobble", "voice", "upload", "import"):
        if r in has:
            rep.ok(r, "declared (writes are not tested: this tool changes nothing on the plugin)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Checks that a plugin follows the Syrinx protocol.")
    ap.add_argument("url", help="address of the manifest (…/manifest.json)")
    ap.add_argument("--lang", default="en", help="language asked from the plugin (en, fr)")
    ap.add_argument("--search", default="a", help="text searched to test search (default: a)")
    ap.add_argument("--timeout", type=float, default=30, help="timeout per call, in seconds")
    ap.add_argument("--json", help="also write the report to this JSON file")
    ap.add_argument("--quiet", action="store_true", help="show only warnings and errors")
    a = ap.parse_args()

    rep = Report()
    run(Plugin(a.url, a.lang, a.timeout), rep, a.search)
    width = max((len(w) for _, w, _ in rep.lines), default=10)
    for level, where, msg in rep.lines:
        if a.quiet and level == "OK":
            continue
        print(f"{level:<8} {where:<{width}}  {msg}")
    print(f"\n{rep.errors} error(s), {rep.warnings} warning(s)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump([{"level": l, "where": w, "message": m} for l, w, m in rep.lines], f, ensure_ascii=False, indent=1)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
