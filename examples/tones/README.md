# Tones

The smallest useful plugin, in JavaScript: notes and chords generated on the fly as WAV files. No outside service and
nothing to license, so it is a good start for your own plugin or for testing a player.

```sh
node plugin.mjs              # http://localhost:8702/manifest.json
```

It shows catalogs (a home row and a library tab), search, album pages, stream with a `cacheKey` (the app may keep the
files offline), continuous play (`similar`), a like button through the `favorite` action, and audio served by a route
with Range support.
