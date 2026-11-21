/**
 * Tones — the smallest useful plugin, in JavaScript: musical notes and chords generated on the fly as WAV files.
 * No outside service, no copyright: perfect to try the protocol, test a player, or start your own plugin.
 *
 *   node plugin.mjs                 # serves http://localhost:8702/manifest.json
 *   node plugin.mjs --port 9000
 *
 * It shows: two catalogs (tracks and albums), search, meta (an album page with its tracks), stream with a stable
 * cacheKey (the app may keep these files offline), similar (continuous play), a "favorite" action that remembers
 * likes in memory, and audio served by a route with Range support (seeking).
 */
import { Plugin, Raw, album, track } from '../../js/syrinx-plugin.mjs';

const NOTES = { C4: 261.63, D4: 293.66, E4: 329.63, F4: 349.23, G4: 392.0, A4: 440.0, B4: 493.88, C5: 523.25 };
const CHORDS = { major: ['C4', 'E4', 'G4'], minor: ['A4', 'C5', 'E4'], sus: ['D4', 'G4', 'A4'] };
const SECONDS = 8;
const likes = new Set();

/** 16-bit mono WAV, 22 050 Hz, with a soft fade in and out. */
function wav(freqs) {
  const rate = 22050, n = rate * SECONDS, data = Buffer.alloc(n * 2);
  for (let i = 0; i < n; i++) {
    const fade = Math.min(1, i / 2000, (n - i) / 4000);
    const v = freqs.reduce((s, f) => s + Math.sin((2 * Math.PI * f * i) / rate), 0) / freqs.length;
    data.writeInt16LE(Math.round(v * fade * 0.4 * 32767), i * 2);
  }
  const h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVEfmt ', 8); h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22); h.writeUInt32LE(rate, 24); h.writeUInt32LE(rate * 2, 28);
  h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34); h.write('data', 36); h.writeUInt32LE(data.length, 40);
  return Buffer.concat([h, data]);
}

const noteTrack = (id) => track(id, id, {
  subtitle: `${NOTES[id]} Hz`, artist: 'Tones', album: 'Notes', albumId: 'notes', duration: SECONDS,
  playable: true, favorite: likes.has(id),
});
const chordTrack = (id) => track(`chord-${id}`, `${id[0].toUpperCase()}${id.slice(1)} chord`, {
  subtitle: CHORDS[id].join(' · '), artist: 'Tones', album: 'Chords', albumId: 'chords', duration: SECONDS,
  playable: true, favorite: likes.has(`chord-${id}`),
});
const allTracks = () => [...Object.keys(NOTES).map(noteTrack), ...Object.keys(CHORDS).map(chordTrack)];
const freqsOf = (id) => (id.startsWith('chord-') ? CHORDS[id.slice(6)]?.map((n) => NOTES[n]) : NOTES[id] && [NOTES[id]]);
const albums = () => [
  album('notes', 'Notes', { artist: 'Tones', year: 2026, songCount: Object.keys(NOTES).length, playable: true }),
  album('chords', 'Chords', { artist: 'Tones', year: 2026, songCount: Object.keys(CHORDS).length, playable: true }),
];

const plugin = new Plugin({
  id: 'org.syrinx.example.tones', name: 'Tones', version: '1.0.0', color: '#FFB347',
  description: 'Notes and chords generated on the fly: a plugin to learn from',
});

plugin.catalog({ id: 'notes', name: 'Notes', type: 'track' }, (req, skip, limit) => allTracks().slice(skip, skip + limit));
plugin.catalog({ id: 'albums', name: 'Albums', type: 'album', section: 'library' }, (req, skip) => (skip ? [] : albums()));

plugin.search((req, q) => allTracks().filter((t) => `${t.title} ${t.subtitle}`.toLowerCase().includes(q.toLowerCase())));

plugin.meta((req, type, id) => {
  if (type === 'album') {
    const a = albums().find((x) => x.id === id);
    if (!a) return null;
    return { item: a, tracks: allTracks().filter((t) => t.albumId === id),
      facts: [{ label: 'Format', value: 'WAV · 16 bits · 22 kHz' }] };
  }
  if (type === 'track') {
    const t = allTracks().find((x) => x.id === id);
    return t ? { item: t } : null;
  }
  return null;
});

plugin.stream((req, id) => (freqsOf(id) ? { url: `audio/${encodeURIComponent(id)}.wav`, cacheKey: `tones-${id}` } : null));
plugin.route('GET', 'audio/:id.wav', (req) => {
  const f = freqsOf(req.params.id);
  return f ? new Raw({ body: wav(f), contentType: 'audio/wav' }) : null;
});

plugin.similar((req, id, limit, exclude) => {
  const pool = allTracks().filter((t) => t.id !== id && !exclude.has(t.id));
  return pool.sort(() => Math.random() - 0.5).slice(0, limit);
});

plugin.actions((req, type, id) => (type !== 'track' ? [] : [
  { id: 'favorite', label: likes.has(id) ? 'Remove from liked songs' : 'Add to liked songs', context: { id } },
]));
plugin.action('favorite', (req, ctx, values) => {
  const on = values.on === undefined ? !likes.has(ctx.id) : values.on === 'true';
  if (on) likes.add(ctx.id); else likes.delete(ctx.id);
  return { ok: true, message: on ? 'Liked' : 'Removed from liked songs', favorite: on };
});

const port = Number(process.argv[process.argv.indexOf('--port') + 1]) || 8702;
if (import.meta.url === `file://${process.argv[1]}`) plugin.serve({ port });

export default plugin;
