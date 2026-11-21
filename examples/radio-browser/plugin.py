"""
Radio Browser — a complete example plugin: thousands of live radio stations from radio-browser.info,
a free, community-run directory (data under the Open Database License).

    python3 plugin.py                       # serves http://localhost:8701/manifest.json
    python3 plugin.py --port 9000 --data ./data

It shows most of what a "source" plugin does with the Python SDK:
  - catalogs (home rows), one that only appears once a setting is made (on_manifest);
  - search, with a fast section;
  - meta (a station page with facts), stream (a live stream, never stored);
  - settings (a one-step form, checked before saving, with a reset button);
  - answers in the app's language (English or French).

Radio Browser asks clients to send a descriptive User-Agent and to report plays with /json/url/<uuid>
(it ranks stations by clicks). Both are done below.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "python"))
from syrinx_plugin import NotFound, Plugin, PluginError, Request, section, track  # noqa: E402

API = os.environ.get("RADIO_BROWSER_API", "https://de1.api.radio-browser.info").rstrip("/")
USER_AGENT = "SyrinxRadioBrowserExample/1.0 (+https://github.com/KRESTIE/syrinx-plugins)"
GENRES = ["jazz", "classical", "rock", "electronic", "hiphop", "lofi"]

TEXT = {
    "en": {"top": "Most played radios", "near": "Radios near you", "jazz": "Jazz", "classical": "Classical",
           "rock": "Rock", "electronic": "Electronic", "hiphop": "Hip-hop", "lofi": "Lo-fi",
           "desc": "Thousands of live radio stations from around the world",
           "radios": "Radios", "country": "Country", "format": "Format", "tags": "Genres", "site": "Website",
           "region": "Your country", "region_text": "Adds a row with the most played stations of your country.",
           "code": "Country code (two letters, e.g. CH, FR, US)", "save": "Save", "off": "Not set",
           "bad_code": "Two letters please, like CH or FR.", "unknown": "No station found for {code}.",
           "saved": "Saved: {n} stations in {code}", "reset": "Remove", "reset_confirm": "The row disappears from home.",
           "removed": "Removed", "down": "Radio Browser does not answer right now."},
    "fr": {"top": "Radios les plus écoutées", "near": "Radios près de chez toi", "jazz": "Jazz",
           "classical": "Classique", "rock": "Rock", "electronic": "Électro", "hiphop": "Rap", "lofi": "Lo-fi",
           "desc": "Des milliers de radios en direct du monde entier",
           "radios": "Radios", "country": "Pays", "format": "Format", "tags": "Genres", "site": "Site",
           "region": "Ton pays", "region_text": "Ajoute une rangée avec les radios les plus écoutées de ton pays.",
           "code": "Code du pays (deux lettres, ex. CH, FR, BE)", "save": "Enregistrer", "off": "Pas réglé",
           "bad_code": "Deux lettres, comme CH ou FR.", "unknown": "Aucune radio trouvée pour {code}.",
           "saved": "Enregistré : {n} radios en {code}", "reset": "Retirer",
           "reset_confirm": "La rangée disparaît de l'accueil.", "removed": "Retiré",
           "down": "Radio Browser ne répond pas pour le moment."},
}


def t(req: Request, key: str, **kw) -> str:
    return TEXT.get(req.lang, TEXT["en"])[key].format(**kw)


# ===================================================================== Radio Browser API

_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def api(path: str, params: dict | None = None, ttl: float = 600) -> object:
    """GET on the Radio Browser API, cached a few minutes (the lists change slowly)."""
    url = f"{API}/json/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with _lock:
        hit = _cache.get(url)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        raise PluginError(TEXT["en"]["down"], 503) from None
    with _lock:
        _cache[url] = (time.time(), data)
    return data


def stations(params: dict, skip: int, limit: int) -> list[dict]:
    return api("stations/search", {"order": "clickcount", "reverse": "true", "hidebroken": "true",
                                   "offset": skip, "limit": limit, **params})  # type: ignore[return-value]


def item(s: dict) -> dict:
    """A station as a Syrinx item: a live track, no like (radios are not liked), no download."""
    tags = [x for x in (s.get("tags") or "").split(",") if x][:2]
    logo = s.get("favicon") or ""
    return track(
        s["stationuuid"], s.get("name", "").strip() or "Radio",
        subtitle=" · ".join([x for x in [s.get("country")] + tags if x]) or None,
        artwork=logo if logo.startswith("https://") else None,      # http images would be blocked in the web app
        live=True, playable=True,
    )


# ===================================================================== settings (a small JSON file)

class Store:
    def __init__(self, folder: str) -> None:
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, "settings.json")

    def get(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def set(self, **values) -> None:
        data = {**self.get(), **values}
        data = {k: v for k, v in data.items() if v is not None}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)


# ===================================================================== the plugin

def build(data_dir: str) -> Plugin:
    store = Store(data_dir)
    plugin = Plugin("org.radiobrowser.syrinx-example", "Radio Browser", "1.0.0",
                    description=TEXT["en"]["desc"], color="#3DA5FF", permissions=[])

    @plugin.on_manifest
    def translate(req: Request, m: dict) -> None:
        m["description"] = t(req, "desc")
        for c in m["catalogs"]:
            c["name"] = t(req, c["id"])
        if not store.get().get("country"):                     # no country yet: no "near you" row
            m["catalogs"] = [c for c in m["catalogs"] if c["id"] != "near"]

    @plugin.catalog("top", "Most played radios")
    def top(req, skip, limit):
        return [item(s) for s in stations({}, skip, limit)]

    @plugin.catalog("near", "Radios near you")
    def near(req, skip, limit):
        code = store.get().get("country")
        return [item(s) for s in stations({"countrycode": code}, skip, limit)] if code else []

    def genre_row(tag: str):
        @plugin.catalog(tag, tag)
        def row(req, skip, limit):
            return [item(s) for s in stations({"tag": tag, "tagExact": "true"}, skip, limit)]

    for g in GENRES:
        genre_row(g)

    @plugin.search
    def search(req, q, source):
        if source and source.lower() not in ("radio", "radios", "radio browser"):
            return []                                          # the user asked for another source by voice
        found = stations({"name": q}, 0, 30)
        return [section("radios", t(req, "radios"), [item(s) for s in found])] if found else []

    @plugin.meta
    def meta(req, type_, id):
        if type_ != "track":
            return None
        found = api(f"stations/byuuid/{urllib.parse.quote(id)}")
        if not found:
            return None
        s = found[0]
        facts = [
            {"label": t(req, "country"), "value": s.get("country") or "?"},
            {"label": t(req, "format"), "value": " · ".join(x for x in [s.get("codec"),
                                                                     f"{s['bitrate']} kbps" if s.get("bitrate") else ""] if x) or "?"},
        ]
        if s.get("tags"):
            facts.append({"label": t(req, "tags"), "value": s["tags"].replace(",", ", ")})
        if s.get("homepage"):
            facts.append({"label": t(req, "site"), "value": s["homepage"]})
        return {"item": item(s), "facts": facts}

    @plugin.stream
    def stream(req, id, quality):
        # /json/url/<uuid> counts the click (Radio Browser ranks stations with it) and gives the stream address
        try:
            info = api(f"url/{urllib.parse.quote(id)}", ttl=0)
        except PluginError:
            info = None
        url = isinstance(info, dict) and info.get("url")
        if not url:
            found = api(f"stations/byuuid/{urllib.parse.quote(id)}")
            if not found:
                raise NotFound()
            url = found[0].get("url_resolved") or found[0].get("url")
        return {"url": url, "live": True, "noStore": True}

    # ---- settings: one group, one step, checked before saving

    def groups(req):
        code = store.get().get("country")
        return [{
            "id": "region", "title": t(req, "region"), "text": t(req, "region_text"),
            "status": {"ok": bool(code), "text": code or t(req, "off")}, "needed": False,
            "steps": [{"title": t(req, "region"),
                       "fields": [{"key": "country", "label": t(req, "code"), "type": "text", "default": code or ""}]}],
            "submit": {"label": t(req, "save")},
            "reset": {"label": t(req, "reset"), "confirm": t(req, "reset_confirm")} if code else None,
        }]

    def save(req, group, values):
        if group != "region":
            raise NotFound()
        code = str(values.get("country", "")).strip().upper()
        if len(code) != 2 or not code.isalpha():
            return {"ok": False, "message": t(req, "bad_code")}
        n = len(stations({"countrycode": code}, 0, 50))           # a real check before saving
        if not n:
            return {"ok": False, "message": t(req, "unknown", code=code)}
        store.set(country=code)
        return {"ok": True, "message": t(req, "saved", n=n if n < 50 else "50+", code=code), "refresh": True}

    def reset(req, group):
        if group != "region":
            raise NotFound()
        store.set(country=None)
        return {"ok": True, "message": t(req, "removed"), "refresh": True}

    plugin.settings(groups, save, reset)
    return plugin


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Radio Browser plugin for Syrinx")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8701)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    a = ap.parse_args()
    build(a.data).serve(a.host, a.port)
