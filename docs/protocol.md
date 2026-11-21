# Syrinx plugin protocol, version 1

> [Version française](protocole.md). To write a plugin without doing everything by hand: the [Python](../python/) or
> [JavaScript](../js/) SDK, and the checker [`syrinx_plugin_check.py`](../syrinx_plugin_check.py).

Syrinx contains no music. Everything it shows and plays comes from **plugins**: small web services that anyone can
write, in any language, and add to Syrinx by pasting an address. A plugin can be your library on a NAS, a radio
directory, a free-music site, a lyrics service… or all of these at once.

## 1. Principles

- **HTTP and JSON.** The app calls the plugin, the plugin answers in JSON (UTF-8). It never pushes anything to the app.
- **One address.** A plugin is added with the address of its manifest, which ends with `manifest.json`:
  `https://example.org/syrinx/manifest.json`. Every other address is **relative to the manifest's folder**
  (`https://example.org/syrinx/catalog/…`).
- **The account is in the address.** If the plugin needs to know who is calling, it puts a token in the path
  (`…/u/8f3c…/manifest.json`). The app handles no login or password for a plugin, it keeps the address.
- **Data, never code.** A plugin returns text, numbers and addresses (artwork, audio, pages). The app runs nothing
  it sends and shows everything with its own screens.
- **It declares what it can do.** The manifest lists the resources it provides; the app only asks for those and
  hides everything else (no dead buttons).
- **HTTPS is required**, except on the local network (`192.168.*`, `10.*`, `*.local`…) and on Tailscale
  (`100.64.0.0/10`, `*.ts.net`).
- **Several plugins at once.** Home rows and search results from every active plugin are mixed; each item stays tied
  to the plugin that provided it (that plugin is called to play it, like it…).
- **Errors**: an HTTP 4xx or 5xx status and, if possible, `{"error": "readable message"}`; the app shows it as is.
  `503` means "not ready" (starting up, a setting is missing): the app tries again later without alarming anyone.

### What the app sends with every call

| Header | Example | Meaning |
|---|---|---|
| `X-Syrinx-Lang` | `en` | interface language (`fr`, `en`): the plugin answers in it when it can |
| `User-Agent` | `Syrinx/3.0.4 (Android)` | app and version, for logs; in a browser, the browser's own |

The same language can also arrive as a `?lang=en` parameter (players that cannot add a header).

### Versions

`protocol: 1` in the manifest. What comes later arrives as **new resources** or **new optional fields**: a plugin
written for version 1 keeps working. A change that would break plugins would go through `protocol: 2`, and the app
would speak both.

## 2. The manifest

`GET manifest.json`

```json
{
  "protocol": 1,
  "id": "org.example.radios",
  "name": "World radios",
  "version": "1.2.0",
  "description": "Thousands of live radio stations, by genre and country",
  "color": "#3DA5FF",
  "resources": ["catalog", "search", "meta", "stream"],
  "catalogs": [
    { "id": "top", "name": "Most played", "type": "track", "section": "home" },
    { "id": "jazz", "name": "Jazz", "type": "track", "section": "home" }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `protocol` | yes | `1` |
| `id` | yes | stable identifier, a reversed domain name (`org.example.radios`). Two plugins with the same `id`: the app keeps the last one added (address update) |
| `name` | yes | displayed name |
| `version` | yes | plugin version (`1.2.0`), shown on its page |
| `description` | no | one sentence, shown when adding it |
| `color` | no | plugin color (`#RRGGBB`), for its badge |
| `resources` | yes | what it provides (chapter 4) |
| `catalogs` | no | its rows and tabs (`catalog` resource) |
| `import` | no | text of the "add from a link" field: `{"label": "Add", "hint": "Link to a Bandcamp album"}`; `help` (optional): what can be added, shown under the field, `[{"title", "text"}]` |
| `permissions` | no | what it asks to receive or to do (chapter 5) |

The manifest may change from one call to the next (a row that only appears once a setting is made, another
language): the app reads it again at startup and after every change to the plugin's settings.

### Catalogs

| Field | Meaning |
|---|---|
| `id` | identifier, in `catalog/<id>.json` |
| `name` | title of the row or tab |
| `type` | `track`, `album`, `artist`, `playlist`: what the row holds (shape of the cards) |
| `section` | `home` (a home row) or `library` (a library tab) |

## 3. Items

Everything the app shows is an **item**: a track, an album, an artist or a playlist, always in the same shape. Only
`id`, `type` and `title` are required; the rest makes the display richer.

```json
{
  "id": "a81f",
  "type": "track",
  "title": "Blue in Green",
  "subtitle": "Miles Davis",
  "artist": "Miles Davis",
  "album": "Kind of Blue",
  "albumId": "k7",
  "artistId": "md",
  "duration": 337,
  "artwork": "https://example.org/syrinx/cover/k7?size=600",
  "playable": true,
  "favorite": false
}
```

The `id` only means something to its plugin: the app does not read it, it sends it back as is (`stream/<id>.json`,
`meta/track/<id>.json`…). It may contain any character; the app encodes it in addresses.

### Common fields

| Field | Type | Meaning |
|---|---|---|
| `id` | text | identifier in this plugin |
| `type` | text | `track`, `album`, `artist`, `playlist` |
| `title` | text | title, name of the album, artist or playlist |
| `subtitle` | text | second line of the card (artist, "2019 · 12 songs"…); otherwise the app builds one |
| `artwork` | address | square image (600 px recommended); relative to the manifest or absolute |
| `playable` | boolean | "play" is offered (for an album, artist or playlist: play everything) |
| `favorite` | boolean | already liked (filled heart). **Missing: the item cannot be liked** (no heart: a radio, a free-music track…) |
| `badge` | text | small label on the card ("New", "Free music") |
| `notice` | text | note shown in the player while it plays |
| `source` | object | where the item comes from, when a license requires it: `{name, url, license, licenseUrl}`; the app shows the credit and the link |

### Tracks (`track`)

| Field | Meaning |
|---|---|
| `artist`, `album` | texts shown by the players (bar, notification, car) |
| `artistId`, `albumId` | to open the artist's or album's page in this plugin |
| `duration` | seconds |
| `live` | live radio: no duration, no like, no download |
| `explicit` | "E" badge |
| `loudness` | `{lufs, peak}`: perceived loudness, for even volume |
| `tempo` | approximate BPM (animations on the beat) |
| `bpm`, `key`, `mixIn`, `mixOut`, `energy` | for the DJ mix: precise tempo, Camelot key (`8A`), useful start and transition start (seconds), energy from 0 to 1 |

### Albums (`album`)

`artist`, `artistId`, `year`, `genre`, `format` ("FLAC · 24 bit"), `songCount` (tracks of the whole album),
`owned` (tracks the user has, if they only have part of the album), `description` (short text).

### Artists (`artist`)

`banner` (large photo for the top of their page), `description` (biography), `libraryId` / `onlineId` (the same
artist in another part of the plugin, to go from one page to the other).

### Playlists (`playlist`)

The common fields are enough; `subtitle` usually says how many tracks.

### What the app does itself

Colors taken from the artwork, animations, queue, offline (unless `stream` forbids it), equalizer, sharing: none of
this is for a plugin to provide.

## 4. Resources

Four families. A plugin provides only what it wants: a radio needs nothing more than `catalog`, `search` and
`stream`.

- **Source**: `catalog`, `search`, `meta`, `stream`, `similar`, `wave`.
- **Library**: `actions`, `import`, `jobs`, `upload`, `library`, `suggestions`.
- **Companions**: `lyrics`, `scrobble`, `stats`, `wrapped`, `dashboard`, `milestones`, `profiles`, `prefs`, `now`,
  `remote`, `jam`, `tastes`, `artist`, `update`, `voice`.
- **Settings**: `settings` (a form or a wizard described by the plugin, 4.13).

### 4.1 `catalog`: rows and tabs

`GET catalog/<id>.json?skip=0&limit=50`

```json
{ "items": [ { "id": "k7", "type": "album", "title": "Kind of Blue", "subtitle": "Miles Davis · 1959" } ] }
```

- `skip` and `limit` (50 by default, 500 at most): the app asks for more as the user scrolls. Fewer than `limit`
  items means "that's all". A catalog without pages (a current selection) ignores `skip` and returns an empty list
  for `skip > 0`.
- An empty row is not shown: a plugin can keep a catalog in its manifest and put nothing in it until it has
  something to show.

### 4.2 `search`

`GET search.json?q=blue%20in%20green`

```json
{
  "sections": [
    { "id": "mine", "title": "In your library", "items": [ … ] },
    { "id": "more", "title": "Elsewhere", "load": "search/more.json?q=blue%20in%20green" }
  ]
}
```

- **Sections**, shown in order. A section either has its `items` right away, or a `load` address (relative to the
  manifest) the app calls next: the page shows what is fast, the slow part arrives afterwards. `load` returns
  `{"items": [...], "errors": ["message"]}`; `errors` (optional) is shown under the section if part of the search
  failed.
- Empty `q`: `{"sections": []}`.
- `source` (optional): the user asked for a specific source by voice ("play jazz on Radio Browser"); the app sends
  the word as is. The plugin returns only that source's sections, or `{"sections": []}` if it does not know it (the
  app then runs a normal search).
- With several plugins, the app shows each one's sections under the plugin's name.

### 4.3 `meta`: pages (album, artist, playlist, track)

`GET meta/<type>/<id>.json` (`type`: `album`, `artist`, `playlist`, `track`)

```json
{
  "item": { "id": "k7", "type": "album", "title": "Kind of Blue", "artist": "Miles Davis", "year": 1959 },
  "tracks": [ { "id": "a81f", "type": "track", "title": "So What", "duration": 562 } ],
  "related": { "title": "By the same artist", "items": [ … ] },
  "facts": [ { "label": "Label", "value": "Columbia" } ]
}
```

| Field | Meaning |
|---|---|
| `item` | the item itself, more complete than on a card (banner, description…) |
| `tracks` | tracks, in order (album, playlist; artist: their best-known tracks) |
| `albums` | artist: their albums |
| `singles` | artist: singles and EPs, shown apart from the albums |
| `mine` | artist: their tracks the user already has ("Shuffle" button) |
| `popular` | artist: `true` if `tracks` are their popular tracks rather than all of them |
| `related` | a row at the bottom of the page: `{title, items}` |
| `facts` | small facts `{label, value}` shown as a list |

Page not found: `404`.

### 4.4 `stream`: playback

`GET stream/<id>.json?quality=raw`

```json
{ "url": "https://example.org/syrinx/audio/a81f?format=opus&maxBitRate=128", "cacheKey": "a81f-opus128" }
```

| Field | Meaning |
|---|---|
| `url` | address of the audio file or stream (relative or absolute); the app reads it directly, with the usual HTTP headers (`Range` requests to seek) |
| `cacheKey` | stable name of this file in this quality: the app keeps it in its cache and offline under that name |
| `live` | live stream (radio): no duration, no seeking, never kept |
| `noStore` | never keep this track on the device (neither cache nor offline), when the source's license requires it |
| `headers` | HTTP headers to send with the audio request (`{"Authorization": "…"}`), if the address needs them |

`quality` (chosen in the app's settings, depending on the network): `raw` (the original file), `opus256`,
`opus128`, `mp3320`. A plugin with a single quality ignores it and always returns the same.

Formats the app plays: MP3, AAC / M4A, Opus / Ogg, FLAC, WAV; continuous HTTP streams (radios, Icecast /
Shoutcast). Track unavailable: `404` or `502` with `{"error": "…"}`; the app skips to the next one and says so.

### 4.5 `similar`: continuous play

When the queue runs out, the app asks for more: tracks close to the one playing.

`GET similar/<id>.json?limit=15&exclude=a81f,b22c&context=x1,x2&discover=1`

```json
{ "items": [ { "id": "c903", "type": "track", "title": "Flamenco Sketches", "artist": "Miles Davis" } ] }
```

| Parameter | Meaning |
|---|---|
| `limit` | how many are wanted (15 by default, 50 at most); returning fewer is fine, the app will ask again |
| `exclude` | identifiers already queued or played, not to return |
| `context` | the last tracks heard (up to 5), most recent first: the mood of the session |
| `discover` | `0`: only tracks the user has; `1`: add some they don't have yet if there are not enough; `2`: mix them in regularly |
| `dj` | `1`: the DJ mix is on, order them so tempo and key flow (if the plugin can) |

Two special identifiers instead of a track: `random` (a random mix, no starting track) and `wave` (see `wave`). The
plugin of the current track is called; if it has no `similar` (a radio, free music…), the app asks
`similar/random.json` from the first active plugin that has it: the music goes on as a mix.

### 4.6 `wave`: personal radio and moods

Continuous play without a starting track, chosen from the user's tastes, with moods.

`GET wave.json`

```json
{
  "enabled": true,
  "moods": [ { "id": "calm", "name": "Calm", "count": 412, "ready": true, "learned": { "out": 3, "in": 12 } } ],
  "suggested": "calm"
}
```

- `moods`: the moods offered (`ready`: enough tracks to start it); `learned`: what the mood learned from listening
  (tracks removed because often skipped, tracks added because played).
- `suggested`: the mood to offer first at this time of day, or `null`.
- Playback itself goes through `similar/wave.json?mode=balanced&mood=calm&…`: `mode` is `familiar`, `balanced` or
  `discovery` (how many new tracks), `mood` is optional.
- `DELETE wave/learned?mood=calm`: forget what the mood learned (without `mood`: all of them).
- Optional, for the progress screen: `analyzed`, `total` (tracks analyzed out of the total).

### 4.7 `actions`: an item's menu

The plugin says what can be done with an item; the app shows the menu, the confirmations and the small forms, then
sends back the choice. No action is built into the app: liking, adding to a playlist, deleting, opening the original
page… everything goes through here.

`GET actions/<type>/<id>.json` (optional: `?playlist=<id>&index=<n>` when the item is opened from a playlist)

```json
{
  "actions": [
    { "id": "favorite", "label": "Add to liked songs", "context": { "type": "track", "id": "a81f" } },
    { "id": "add-to-playlist", "label": "Add to a playlist", "context": { "type": "track", "id": "a81f" },
      "fields": [
        { "key": "playlist", "label": "Playlist", "type": "choice", "default": "new",
          "options": [ { "value": "new", "label": "New playlist" }, { "value": "p1", "label": "Evening jazz" } ] },
        { "key": "name", "label": "Name of the new playlist", "type": "text",
          "showIf": { "key": "playlist", "equals": "new" } }
      ] },
    { "id": "delete", "label": "Delete from library", "style": "danger",
      "confirm": "The file is erased. This cannot be undone.", "context": { "type": "track", "id": "a81f" } }
  ]
}
```

| Action field | Meaning |
|---|---|
| `id` | name of the action, sent back as is |
| `label` | menu text |
| `context` | what the plugin wants to receive back (free form) |
| `style` | `danger`: in red |
| `confirm` | text of a confirmation before acting |
| `fields` | small form: `type` `text` or `choice` (with `options`), `default`, `showIf` (`{key, equals}` or `{key, notEquals}`: field shown depending on another) |
| `disabled` | greyed out (nothing to do for now) |

`POST action/<id>` with `{"context": {…}, "values": {"playlist": "p1"}}`

```json
{ "ok": true, "message": "Added to “Evening jazz”", "refresh": true }
```

| Answer field | What the app does |
|---|---|
| `ok`, `message` | shows the message (as an error if `ok` is `false`) |
| `refresh` | reloads the page and the rows on screen |
| `favorite` | updates the heart without reloading |
| `removed` | identifiers removed: taken off the page and the queue |
| `skip` | identifiers not to offer anymore: removed from the queue |
| `open` | address to open in the browser (original page, purchase) |
| `job` | a task started (see `jobs`) |

**Two actions the app calls without a menu**, if the plugin offers them:
- `favorite`: the heart in the player, the notification and the car, and "like" by voice. `values` may hold
  `{"on": "true"}` (like) or `{"on": "false"}`; without `on`, toggle.
- a track's `keep` action (the item's `keep` field, same shape as an action): for a discovery played by streaming,
  the app runs it by itself when the track is heard to the end ("heard in full = kept").

### 4.8 `import` and `jobs`: add from a link

For a plugin that can add something from a link (a purchase on a store, a public playlist, an archive
collection…). The manifest gives the field's text: `"import": {"label": "Add", "hint": "Link to an album bought on
Bandcamp"}`. Only the plugin decides which links it accepts.

`GET import/preview.json?url=<link>`

```json
{
  "item": { "id": "imp-42", "type": "playlist", "title": "Road trip", "subtitle": "28 songs", "artwork": "…" },
  "stats": [ { "label": "12 already in your library" }, { "label": "16 to add", "accent": true } ],
  "sample": [ "Song 1 · Artist", "Song 2 · Artist" ],
  "action": { "id": "import", "label": "Add 16 songs", "context": { "key": "imp-42" }, "fields": [ … ] }
}
```

The app shows the preview; the button is an ordinary action (`POST action/import`), which usually returns a `job`.
Link refused: `400` with `{"error": "This link is not supported"}`.

`GET jobs.json`: running and recent tasks, which the app shows with their progress.

```json
{ "items": [ { "id": "j7", "label": "Road trip", "status": "3 of 16", "done": 3, "total": 16,
               "finished": false, "errors": 0, "note": null } ] }
```

### 4.9 `upload`: send your own files

For a plugin that stores music (a NAS, a server): the user sends their purchases or ripped CDs from their phone or
their browser.

- `POST upload`: one file per request, the body is the file, its name in the `X-Filename` header. Audio (MP3, FLAC,
  M4A, OGG, Opus, WAV, AIFF) or a ZIP of an album. Answer:
  `{"added": [...], "rejected": [{"name", "reason"}], "fix": [...], "groups": [...]}`. `groups`: what was filed, by
  album (`folder`, `artist`, `album`, `files`, `titles`, `others`, `fix`); `fix`: files whose artist is unknown, for
  which the app offers "Fix the details".
- `POST upload/fix` `{path, artist, album, title}`: fix one file.
- `POST upload/fix-album` `{files, artist, album, year, titles}`: fix a whole album → `{group}`.
- `POST upload/undo` `{files}` → `{token}`; `POST upload/redo` `{token}` → `{groups}`: undo an upload and restore it
  (the plugin keeps the files for at least a few hours).

### 4.10 `library`: "something changed"

`GET library.json` → `{"rev": 1834}`. A number that changes when the library changes (tracks added, deleted,
moved). The app reads it from time to time and reloads its rows when it moves, without asking for everything again.

### 4.11 `suggestions`: "You might like"

- `GET suggestion.json?id=<current track>&exclude=<ids>` → `{"item": {…}}` or `{"item": null}`: a card in the queue,
  a track the user does not have, close to the one playing. It is not played: the card offers a preview.
- `GET preview.json?kind=song&title=&artist=` → `{found, title, artist, album, preview, store, artwork, credit}`:
  a 30-second preview (`preview`, streamed, never kept) and the page where to buy it (`store`). An item that is not
  playable can carry `store: {kind, title, artist}` so the app asks for that preview on demand.

### 4.12 Companions

Independent resources: a lyrics plugin provides only `lyrics`, a statistics plugin only `scrobble` and `stats`. When
several active plugins provide the same one, the app takes the first that provides it, in the order of the plugin
list.

#### `lyrics`

`GET lyrics.json?title=&artist=&album=&duration=` (duration in seconds)

```json
{ "synced": true, "instrumental": false, "lines": [ { "t": 12.4, "text": "First line" } ] }
```

`t`: start of the line in seconds, `null` if the lyrics are not synced. Empty `lines`: nothing found.

#### `scrobble`: plays

The app sends its plays in batches, including those made offline (sent later; the same batch may arrive twice, the
plugin ignores duplicates: same `id` and same `started`).

`POST scrobble` `{"plays": [{"id", "title", "artist", "album", "duration", "heard", "started", "kind"}]}` →
`{"ok": true, "received": 3}`. `started`: start date (Unix seconds); `heard`: seconds heard; `kind`: `listen` (more
than 30 s or half the track) or `skip`. Live radios are not sent. **Permission**: `plays`.

#### `stats`: your stats

`GET stats.json?period=month` (`month`, `year`, `all`): a page the app shows as is.

| Field | Meaning |
|---|---|
| `label` | title of the period ("November 2026") |
| `enough` | enough plays to say something about them |
| `highlights` | key figures `{label, value}` |
| `profile` | listener profile `{title, text}` or `null` |
| `chart`, `days` | bars `{title, values, labels, note}`: listening hours, days of the week |
| `sections` | lists `{id, title, items, hint, play}`; the `songs`, `artists` and `albums` ids (most played) get their own place at the top of the page, the others follow |
| `since` | date plays are counted from |
| `wave` | measure of the personal radio by mood, or `null` |

#### `wrapped`: the year in review

The review is a full page made by the plugin (animations, sharing): the app opens it as is. See appendix A.

#### `dashboard`: control room

`GET dashboard.json?days=7&profile=all`: live plays, today's figures, hours, artists, genres, server health,
activity. For the owner of a server. See appendix B.

#### `milestones`: milestones and anniversaries

`GET milestones.json` → `{"listens": 10012, "marks": [100, 1000, 5000, …], "anniversary": {…} | null}`. The app
celebrates each mark in `marks` passed by `listens`, once. `anniversary`: an album released on a day like today
(`{id, title, artist, artwork, year, years}`), offered for listening.

#### `profiles` and `prefs`: several people

For a plugin shared by a family ("Who's listening?"). Each profile has its own plugin address (its token):
switching profile means switching address.

- `GET profiles.json` → `{"me": "<id>", "profiles": [{"id", "name", "color", "main", "base"}]}`; `base`: the plugin
  address for that profile.
- `POST profiles` `{name, color?}`: create; `POST profiles/<id>` `{name?, color?}`: edit; `DELETE profiles/<id>`:
  delete (main profile only).
- `GET profiles/<id>/photo.jpg`; `POST profiles/<id>/photo` (image already cropped); `DELETE` to remove it.
- `GET prefs.json` / `POST prefs` `{key: value}`: settings that follow the person from one device to another
  (`waveMode`, `waveMood`, `discover`).

#### `now`: resume on another device

- `POST now` `{device, deviceId, playStart, items, index, position, playing, origin}`: the playing device sends it
  from time to time.
- `GET now.json`: the last state (or `{}`), for "continue here".
- One playback at a time per profile: if a more recent device started playing (`playStart`), the plugin answers
  `{"superseded": true, "device": "Phone"}` and the older one pauses.

#### `remote`: remote control

Each open device reports itself and waits for commands, without a permanent connection (long polling).

- `POST remote/sync` `{"device": {id, name, kind}, "state": {items, index, position, duration, playing, volume},
  "wait": 25}` → `{"commands": [...]}`: the plugin answers as soon as a command arrives for that device, otherwise
  after `wait` seconds. `wait: 0`: just send the state.
- `GET remote/devices.json?me=<id>` → `{"devices": [{id, name, kind, state, seen, online}]}`: the other devices.
- `POST remote/<id>/command` `{"type": …}`: `toggle`, `play`, `pause`, `next`, `previous`, `seek {position}`,
  `volume {value 0..1}`, `jump {index}`, `load {items, index, origin, position?}`, `wave {mood?}`, `mix`, `stop`.

#### `jam`: listen together

Built on `remote`: the plugin keeps each guest in step with the host's device (same track, same moment).

- `GET jam.json?me=<device>` → `{"jam": {…} | null, "invites": [...], "online": [...]}`.
- `POST jam/start {device}`, `jam/join {code, device}`, `jam/leave`, `jam/invite {profile}`, `jam/decline {code}`,
  `jam/add {items}`, `jam/control {type, …}`, `jam/settings {controlAll?, addAll?}`, `jam/live`.
- Shape of `jam`: appendix C.

#### `tastes`: welcome screen

- `GET tastes.json` → `{artists, genres, asked, ask, genreList: [{id, name}], suggestions}`; `ask`: offer it by
  itself (never filled in and the library is still small).
- `GET tastes/suggest.json?genres=` and `GET tastes/search.json?q=` → `{"items": [{name, id, artwork, inLibrary}]}`.
- `GET tastes/playlist.json?url=`: the artists that appear most in a public playlist.
- `POST tastes {artists, genres?}`: save; `POST tastes/top {name}`: add an artist's best-known tracks (a plugin that
  can add, see `import`).

#### `artist`: more about an artist

- `GET artist/info.json?name=` → `{"state": "building"}` during a first lookup (the app asks again a few seconds
  later), then `{"state": "ready", bio, photo, popular, albums, similar}`.
- `GET artist/rare.json?name=` → same idea, `{"state": "ready", "title", "text", "items": [...]}`: tracks by the
  artist found nowhere else, loaded separately because it is slow; `title` and `text` (optional): heading and
  sentence of the section.

#### `update`: app updates

For a plugin that distributes the Android app itself (friends without access to an app store).

`GET update.json` → `{"version": "3.0.4", "code": 141, "size": 41234567, "notes": "…", "url": "update/syrinx.apk"}`
or `{"version": null}`. The app offers the update if `code` is higher than its own. **Permission**: `update`.

#### `voice`: voice commands

`POST voice` (body: WAV 16 kHz, mono, 16 bit, 5 MB at most) → `{"text": "play some jazz"}`. The plugin transcribes
the request; the app understands it itself afterwards. **Permission**: `voice`.

### 4.13 `settings`: settings described by the plugin

A plugin that needs a key, an account or a choice **describes** it; the app shows it with its own screens, on the
plugin's page. A simple form (a few fields) or a multi-step wizard, with links to open, values to copy and a check
at the end.

`GET settings.json`

```json
{
  "groups": [
    {
      "id": "region",
      "title": "Your country",
      "text": "Adds a row with the most played stations of your country.",
      "status": { "ok": false, "text": "Not set" },
      "needed": false,
      "steps": [
        { "title": "Create your account", "text": "On the service's developer portal, free.",
          "link": { "label": "Open the portal", "url": "https://example.org/developers" } },
        { "title": "Create an application", "text": "Copy these values into the form.",
          "copy": [ { "label": "Name", "value": "Syrinx" }, { "label": "Website", "value": "https://syrinx.li" } ] },
        { "title": "Paste your key",
          "fields": [ { "key": "apiKey", "label": "API key", "type": "secret" } ] }
      ],
      "submit": { "label": "Check and enable" },
      "reset": { "label": "Disable", "confirm": "The row disappears from home." }
    }
  ]
}
```

| Group field | Meaning |
|---|---|
| `id` | identifier, in `settings/<id>` |
| `title`, `text` | title and one explaining sentence |
| `status` | current state `{ok, text}`: a green (`ok`) or neutral line under the title |
| `needed` | `true`: the plugin cannot work without it; the app opens it when the plugin is added and flags it on the plugin's page |
| `steps` | one or more steps; a single step = a simple form |
| `submit` | text of the final button; `null` when there is nothing to send (a command to type elsewhere) |
| `reset` | optional: a button to erase everything, with its confirmation |

A step has a `title` and may have a `text`, a `link` `{label, url}` (opened in the browser), a `copy` list of values
to copy (`{label, value}`, with a Copy button) and `fields`: the same as for actions (`text`, `choice`, `showIf`,
`default`), plus `secret` (hidden text), `toggle` (yes / no) and `number` (with `min`, `max`). Values already saved
come back as `default` (never `secret` ones: the plugin returns `"set": true` on the field to say "already filled
in"; an empty secret sent back means "keep the saved one").

`POST settings/<id>` with `{"values": {"apiKey": "…"}}`: the plugin checks (a real call, if possible) and saves.

```json
{ "ok": true, "message": "Enabled: 612,000 tracks available", "refresh": true }
```

`ok: false` with `message`: the app keeps the wizard open and shows the message under the button. `refresh`: the
app reads the manifest again (new rows may appear). `DELETE settings/<id>`: the `reset` button.

## 5. Permissions

Showing, searching, playing, and acting when the user asks (a like, an add, a delete) need no permission: the user
is the one pressing. A permission covers what a plugin **receives without being explicitly given it** or what it
**triggers on the device**.

| Permission | What it allows | Resources |
|---|---|---|
| `plays` | receive the listening history (what, when, for how long, skipped or not) | `scrobble` |
| `devices` | know the open devices, what they play, and control them remotely | `now`, `remote`, `jam` |
| `voice` | receive the recording of a voice command (a few seconds, after "Hey Syrinx") | `voice` |
| `files` | receive the files the user chooses to send | `upload` |
| `notifications` | show a notification (Jam invitation, add finished) | `jam`, `jobs` |
| `update` | offer to install a new version of the app | `update` |

The manifest declares them: `"permissions": ["plays", "devices"]`.

**What the app does**

- **When the plugin is added**, it shows what the plugin asks for, one line per permission, in plain words
  ("Receive what you listen to"), each with its switch. The user can refuse everything and keep the plugin for the
  rest.
- **By default**: everything asked is on, except `update`, which the user turns on themselves.
- **A refused permission**, or one that is not declared, cuts the resources it covers: the app does not call them,
  as if the plugin did not provide them. A manifest without a `permissions` field (written before permissions
  existed) is treated as asking for everything.
- **Later**, everything can be changed on the plugin's page.

**`update` in particular.** Android only installs an update signed with the same key as the installed app: a plugin
cannot replace Syrinx with something else. The user still always sees Android's install screen and can refuse.

**Outside content.** Artwork and audio files may be hosted elsewhere than on the plugin (absolute addresses): the
device then downloads them directly from that site, which sees the request. Plugins that care about discretion relay
these files themselves.

## Appendices

### A. `wrapped`: the review

The review is a web page served by the plugin, at `wrapped.html?period=year` (relative to the manifest), that the app
opens full screen. The plugin does what it wants there (animations, cards to share). `GET wrapped.json?period=`
(optional) gives the same figures as raw data (`minutes`, `listens`, `topSongs`, `topArtists`, `topAlbums`,
`streak`, `profile`…), for anyone who wants to show them differently.

### B. `dashboard`: the control room

```json
{
  "now": { "playing": [ { "id": "dev1", "profile": "p1", "name": "Alex", "color": "#ff6a3d", "photo": null,
                          "device": "PC", "kind": "web", "title": "So What", "artist": "Miles Davis", "artwork": "…",
                          "playing": true, "position": 42, "duration": 562, "origin": "wave", "jam": null } ],
           "jams": [ { "code": "K7Q2", "host": "Alex", "people": 3 } ] },
  "kpis": { "playing": 1, "inJam": 0, "today": 58, "todayLastWeek": 41, "hours": 3.2, "listens": 12034,
            "library": 8412, "added": 37, "skipShare": 0.18, "alerts": 0 },
  "hours": { "today": [24 numbers], "average": [24 numbers], "now": 16 },
  "heat": [7 rows of 24 numbers],
  "days": { "profiles": [ { "id", "name" } ], "days": [ { "date": "2026-11-21", "counts": [per profile] } ] },
  "artists": [ { "name", "count" } ], "genres": [ { "name", "count" } ], "untagged": 12,
  "sources": { "library": 0.82, "discoveries": 0.18 },
  "health": { "checks": [ { "name": "Music disk", "state": "ok", "text": "1.8 TB free", "used": 0.55 },
                          { "name": "Backup", "state": "ok", "text": "{ago}", "at": 1795250000 } ],
              "alerts": [ { "id", "title", "detail" } ] },
  "activity": [ { "at": 1795270000, "kind": "download", "text": "Road trip", "status": "16 of 16" } ],
  "profiles": [ { "id", "name", "color" } ],
  "period": 7, "at": 1795274000
}
```

`days` (parameter): the period in days; `profile`: one profile or `all`. Every part is optional: the app hides
those that are missing. `health.checks` is a free list: each server puts in it what it monitors. `state`: `ok`
(green), `warn` (orange), `bad` (red), `neutral`; `{ago}` in `text` is replaced by the app with the time since `at`
("3 min ago"); `used` (0 to 1) adds a gauge.

### C. `jam`: listen together

`GET jam.json?me=<device>`

```json
{
  "jam": {
    "code": "K7Q2", "host": { "id": "dev1", "name": "Alex's PC" }, "isHost": false,
    "people": [ { "id": "p1", "name": "Alex", "host": true }, { "id": "p2", "name": "Léa", "host": false } ],
    "settings": { "controlAll": false, "addAll": true }, "canControl": false, "canAdd": true,
    "items": [ { "id": "a81f", "type": "track", "title": "…", "addedBy": "Léa" } ],
    "playing": true, "position": 63.2, "duration": 214, "expires": 1795290000, "live": true
  },
  "invites": [ { "code": "Z9P1", "host": "Léa" } ],
  "online": [ { "id": "p3", "name": "Sam", "color": "#7c4dff", "invited": false } ]
}
```

`items`: the current track then what follows, with who added it. `live: false`: this guest paused on their side
("Back to live"). `invites`: invitations received; `online`: profiles that can be invited. `POST jam/join` returns
the same `jam` object, enough to start playing right away.
