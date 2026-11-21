# Syrinx plugins

[Version française](README.fr.md)

Syrinx is a music player that contains no music. Everything it shows and plays comes from **plugins**: small web
services that answer a few JSON requests. Anyone can write one, in any language, and add it to Syrinx by pasting its
address.

A plugin can be a music library on your NAS, a radio directory, a free-music catalog, a lyrics service, a statistics
tracker… or several of these at once.

## What is here

| | |
|---|---|
| [`docs/protocol.md`](docs/protocol.md) | The protocol, version 1: every request the app makes and the answer it expects |
| [`python/syrinx_plugin.py`](python/syrinx_plugin.py) | Python SDK: one file, standard library only (Python 3.10+) |
| [`js/syrinx-plugin.mjs`](js/syrinx-plugin.mjs) | JavaScript SDK: one file, no dependencies (Node.js 18+) |
| [`examples/radio-browser`](examples/radio-browser/) | A complete plugin in Python: live radio stations from radio-browser.info, with search, station pages and a setting |
| [`examples/tones`](examples/tones/) | The smallest useful plugin, in JavaScript: notes and chords generated as audio files |
| [`syrinx_plugin_check.py`](syrinx_plugin_check.py) | The checker: calls your plugin like the app would and reports what is wrong |

## Your first plugin in 5 minutes

```python
from syrinx_plugin import Plugin, track

plugin = Plugin("org.example.hello", "Hello", "1.0.0", description="My first plugin")

@plugin.catalog("picks", "My picks")
def picks(req, skip, limit):
    return [track("song-1", "A free song", artist="Someone", playable=True)]

@plugin.stream
def stream(req, id, quality):
    return {"url": "https://example.org/music/song-1.mp3", "cacheKey": "song-1"}

plugin.serve(port=8700)
```

```sh
python3 hello.py
python3 syrinx_plugin_check.py http://localhost:8700/manifest.json
```

Then in Syrinx: **Plugins**, paste `http://<your computer's address>:8700/manifest.json`, **Add**. A "My picks" row
appears on the home screen.

The same in JavaScript:

```js
import { Plugin, track } from './syrinx-plugin.mjs';

const plugin = new Plugin({ id: 'org.example.hello', name: 'Hello', version: '1.0.0' });
plugin.catalog({ id: 'picks', name: 'My picks' }, () => [track('song-1', 'A free song', { playable: true })]);
plugin.stream(() => ({ url: 'https://example.org/music/song-1.mp3', cacheKey: 'song-1' }));
plugin.serve({ port: 8700 });
```

Not using Python or JavaScript? The SDKs only save typing: any web server that answers the JSON described in
[the protocol](docs/protocol.md) is a plugin.

## Good to know

- **HTTPS** is required, except on your local network and on Tailscale. To open a plugin to the internet, put it
  behind a reverse proxy (Caddy, nginx, Traefik) or a tunnel with a certificate.
- **Accounts**: if your plugin needs to know who is calling, put a token in its address
  (`Plugin(..., prefix="/u/<account>")`, then `req.account`). The app keeps the address, never a password.
- **Settings**: a key or a choice the user must make is described by the plugin (`plugin.settings(...)`); the app
  draws the form or the step-by-step wizard. See the Radio Browser example.
- **Permissions**: receiving the listening history, controlling devices, receiving voice commands or files, offering
  app updates all need a permission declared in the manifest, which the user can refuse.
- **Language**: `req.lang` gives the app's language (`en`, `fr`); answer in it when you can.

## Rules for plugins listed by the project

Plugins are independent from Syrinx and their authors are responsible for them. The project only links to plugins
that use content they have the right to distribute: your own files, public-domain or Creative Commons music, licensed
services used according to their terms. Plugins that circumvent DRM or download from services that forbid it are not
listed.

## License

The SDKs, examples, checker and documentation are under the [MIT license](LICENSE).
