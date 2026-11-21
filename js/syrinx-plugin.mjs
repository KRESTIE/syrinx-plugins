/**
 * syrinx-plugin — write a Syrinx plugin in a few lines of JavaScript (protocol version 1, see docs/protocol.md).
 *
 * Node.js 18+, no dependencies. One file: copy it next to your plugin, or install the kit with npm.
 *
 *   import { Plugin, track } from './syrinx-plugin.mjs';
 *
 *   const plugin = new Plugin({ id: 'org.example.tones', name: 'Tones', version: '1.0.0' });
 *   plugin.catalog({ id: 'notes', name: 'Notes', type: 'track' }, (req, skip, limit) =>
 *     [track('a4', 'A4', { subtitle: '440 Hz', playable: true })]);
 *   plugin.stream((req, id, quality) => ({ url: `audio/${id}.wav` }));
 *   plugin.serve({ port: 8702 });
 *
 * Same API as the Python SDK (python/syrinx_plugin.py): manifest built for you, every protocol URL routed to your
 * function, JSON and errors in the right shape, CORS, Range for audio, optional account token in the path.
 * Handlers may be async. plugin.handler is a plain (req, res) function for Node's http, Express or Fastify.
 */
import { createServer } from 'node:http';
import { createReadStream, statSync } from 'node:fs';
import { extname } from 'node:path';

export const PROTOCOL = 1;
const TYPES = ['track', 'album', 'artist', 'playlist'];
const QUALITIES = ['raw', 'opus256', 'opus128', 'mp3320'];
const PERMISSIONS = ['plays', 'devices', 'voice', 'files', 'notifications', 'update'];

// ===================================================================== items

function item(type, id, title, fields = {}) {
  const out = { id: String(id), type, title: String(title) };
  for (const [k, v] of Object.entries(fields)) if (v !== undefined && v !== null) out[k] = v;
  return out;
}
/** A track. Leave `favorite` out for items that cannot be liked (a radio). */
export const track = (id, title, fields) => item('track', id, title, fields);
export const album = (id, title, fields) => item('album', id, title, fields);
export const artist = (id, title, fields) => item('artist', id, title, fields);
export const playlist = (id, title, fields) => item('playlist', id, title, fields);
/** A search section: its items right away, or a `load` URL the app calls next. */
export const section = (id, title, items = [], load) => (load ? { id, title, load } : { id, title, items });

// ===================================================================== errors and raw answers

/** Throw it in a handler: the app shows `message` as is. 503 means "not ready, try later". */
export class PluginError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
export class NotFound extends PluginError {
  constructor(message = 'Not found') { super(message, 404); }
}

const MIME = { '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg',
  '.opus': 'audio/ogg', '.wav': 'audio/wav', '.jpg': 'image/jpeg', '.png': 'image/png', '.html': 'text/html' };

/** A non-JSON answer (audio, image, page). Give `body` (Buffer) or `path` (a file). Ranges are handled for you. */
export class Raw {
  constructor({ body, path, contentType, status = 200, headers = {} }) {
    if ((body === undefined) === (path === undefined)) throw new Error('Raw needs body or path');
    Object.assign(this, { body, path, status, headers });
    this.contentType = contentType || (path && MIME[extname(path).toLowerCase()]) || 'application/octet-stream';
  }
  size() { return this.body !== undefined ? this.body.length : statSync(this.path).size; }
}

function range(raw, header) {
  const size = raw.size();
  const m = /^bytes=(\d*)-(\d*)$/.exec(header || '');
  if (raw.status !== 200 || !m || size === 0) return [raw.status, 0, size - 1, size];
  let start, end;
  if (m[1] === '') { start = Math.max(0, size - Number(m[2] || 0)); end = size - 1; }
  else { start = Number(m[1]); end = Math.min(m[2] ? Number(m[2]) : size - 1, size - 1); }
  if (start > end || start >= size) return null;
  return [206, start, end, size];
}

// ===================================================================== the plugin

export class Plugin {
  /** @param {{id: string, name: string, version: string, description?: string, color?: string,
   *          permissions?: string[], prefix?: string}} o  prefix "/u/<account>" hands the token as req.account */
  constructor({ id, name, version, description, color, permissions = [], prefix = '' }) {
    const bad = permissions.filter((p) => !PERMISSIONS.includes(p));
    if (bad.length) throw new Error(`unknown permissions: ${bad.join(', ')}`);
    Object.assign(this, { id, name, version, description, color, permissions, prefix: prefix.replace(/\/$/, '') });
    this.catalogs = []; this.catalogFns = {}; this.resources = []; this.routes = []; this.fns = {};
    this.importDef = null; this.manifestHook = null;
    this.handler = (req, res) => this.#serveHttp(req, res);
  }

  #declare(r) { if (!this.resources.includes(r)) this.resources.push(r); }

  /** A home row or library tab. fn(req, skip, limit) -> items. */
  catalog({ id, name, type = 'track', section = 'home' }, fn) {
    if (!TYPES.includes(type) || !['home', 'library'].includes(section)) throw new Error('bad catalog type or section');
    this.#declare('catalog'); this.catalogs.push({ id, name, type, section }); this.catalogFns[id] = fn; return this;
  }
  /** fn(req, q, source) -> sections, or a plain list of items (one section). */
  search(fn) { this.#declare('search'); this.fns.search = fn; return this; }
  /** fn(req, type, id) -> {item, tracks?, …} or null (404). */
  meta(fn) { this.#declare('meta'); this.fns.meta = fn; return this; }
  /** fn(req, id, quality) -> {url, live?, noStore?, cacheKey?, headers?} or null (404). */
  stream(fn) { this.#declare('stream'); this.fns.stream = fn; return this; }
  /** fn(req, id, limit, exclude: Set, context: string[]) -> tracks. id may be "random" or "wave". */
  similar(fn) { this.#declare('similar'); this.fns.similar = fn; return this; }
  /** fn(req, title, artist, album, duration) -> {synced, lines}. */
  lyrics(fn) { this.#declare('lyrics'); this.fns.lyrics = fn; return this; }
  /** fn(req, type, id) -> actions; then plugin.action(id, fn) for each. */
  actions(fn) { this.#declare('actions'); this.fns.actions = fn; return this; }
  /** fn(req, context, values) -> {ok, message, refresh?, favorite?, …}. */
  action(id, fn) { this.fns[`action:${id}`] = fn; return this; }
  /** Settings described by the plugin (protocol 4.13): groups(req), save(req, id, values), reset?(req, id). */
  settings(groups, save, reset) {
    this.#declare('settings'); Object.assign(this.fns, { settings: groups, 'settings:save': save });
    if (reset) this.fns['settings:reset'] = reset; return this;
  }
  /** Add from a link: preview(req, url) -> {item, stats, sample, action}. */
  importer(label, hint, preview) { this.#declare('import'); this.importDef = { label, hint }; this.fns.import = preview; return this; }
  /** Declare a resource you serve yourself with route(). */
  resource(name) { this.#declare(name); return this; }
  /** Any other URL relative to the manifest; patterns take :name parts ("audio/:id.wav").
   *  fn(req) -> object (JSON), Raw, or null (204). */
  route(method, pattern, fn, resource) {
    if (resource) this.#declare(resource);
    const rx = new RegExp('^' + pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$');
    this.routes.push([method.toUpperCase(), rx, fn]); return this;
  }
  /** fn(req, manifest) may change the manifest per call (translate names, hide a row). */
  onManifest(fn) { this.manifestHook = fn; return this; }

  async manifest(req) {
    const m = { protocol: PROTOCOL, id: this.id, name: this.name, version: this.version };
    if (this.description) m.description = this.description;
    if (this.color) m.color = this.color;
    m.resources = [...this.resources];
    if (this.catalogs.length) m.catalogs = this.catalogs.map((c) => ({ ...c }));
    if (this.importDef) m.import = { ...this.importDef };
    m.permissions = [...this.permissions];
    if (this.manifestHook) await this.manifestHook(req, m);
    return m;
  }

  /** [status, body] for a request whose path is relative to the manifest folder. */
  async handle(req) {
    try { return await this.#dispatch(req); }
    catch (e) {
      if (e instanceof PluginError) return [e.status, { error: e.message }];
      console.error(e);
      return [500, { error: `Plugin error (${e?.name ?? 'Error'})` }];
    }
  }

  async #dispatch(req) {
    const { path: p, method: m } = req, f = this.fns;
    let hit;
    for (const [method, rx, fn] of this.routes) {
      if (method === m && (hit = rx.exec(p))) {
        req.params = { ...hit.groups };
        const out = await fn(req);
        return out == null ? [204, null] : [200, out];
      }
    }
    if (m === 'GET' && p === 'manifest.json') return [200, await this.manifest(req)];
    if (m === 'GET' && (hit = /^catalog\/(.+)\.json$/.exec(p))) {
      const fn = this.catalogFns[hit[1]];
      if (!fn) throw new NotFound('Unknown catalog');
      const limit = req.int('limit', 50, 1, 500);
      return [200, { items: ((await fn(req, req.int('skip', 0, 0), limit)) || []).slice(0, limit) }];
    }
    if (m === 'GET' && p === 'search.json' && f.search) {
      const q = (req.query.q || '').trim();
      if (!q) return [200, { sections: [] }];
      let out = (await f.search(req, q, req.query.source || null)) || [];
      if (out.length && out[0].type) out = [section('results', this.name, out)];
      return [200, { sections: out }];
    }
    if (m === 'GET' && (hit = /^meta\/(track|album|artist|playlist)\/(.+)\.json$/.exec(p)) && f.meta) {
      const out = await f.meta(req, hit[1], hit[2]);
      if (out == null) throw new NotFound();
      return [200, out];
    }
    if (m === 'GET' && (hit = /^stream\/(.+)\.json$/.exec(p)) && f.stream) {
      const quality = QUALITIES.includes(req.query.quality) ? req.query.quality : 'raw';
      const out = await f.stream(req, hit[1], quality);
      if (out == null) throw new NotFound('Track unavailable');
      return [200, out];
    }
    if (m === 'GET' && (hit = /^similar\/(.+)\.json$/.exec(p)) && f.similar) {
      const ids = (k) => (req.query[k] || '').split(',').filter(Boolean);
      const out = await f.similar(req, hit[1], req.int('limit', 15, 1, 50), new Set(ids('exclude')), ids('context'));
      return [200, { items: out || [] }];
    }
    if (m === 'GET' && p === 'lyrics.json' && f.lyrics) {
      const q = req.query;
      const out = await f.lyrics(req, q.title || '', q.artist || '', q.album || '', q.duration ? Number(q.duration) : null);
      return [200, out || { synced: false, lines: [] }];
    }
    if (m === 'GET' && (hit = /^actions\/(track|album|artist|playlist)\/(.+)\.json$/.exec(p)) && f.actions)
      return [200, { actions: (await f.actions(req, hit[1], hit[2])) || [] }];
    if (m === 'POST' && (hit = /^action\/(.+)$/.exec(p))) {
      const fn = f[`action:${hit[1]}`];
      if (!fn) throw new NotFound('Unknown action');
      const body = req.json() || {};
      return [200, await fn(req, body.context || {}, body.values || {})];
    }
    if (m === 'GET' && p === 'import/preview.json' && f.import) {
      const url = (req.query.url || '').trim();
      if (!url) throw new PluginError('Missing link');
      return [200, await f.import(req, url)];
    }
    if (m === 'GET' && p === 'settings.json' && f.settings) return [200, { groups: (await f.settings(req)) || [] }];
    if ((hit = /^settings\/([\w.-]+)$/.exec(p)) && f.settings) {
      if (m === 'POST') return [200, await f['settings:save'](req, hit[1], (req.json() || {}).values || {})];
      if (m === 'DELETE' && f['settings:reset']) return [200, await f['settings:reset'](req, hit[1])];
    }
    throw new NotFound();
  }

  #split(rawPath) {
    let path = decodeURIComponent(rawPath), account = null;
    const prefix = this.prefix;
    if (prefix.includes('<account>')) {
      const rx = new RegExp('^' + prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace('<account>', '(?<account>[^/]+)') + '/');
      const hit = rx.exec(path);
      if (!hit) return null;
      account = hit.groups.account; path = path.slice(hit[0].length);
    } else if (prefix) {
      if (!path.startsWith(prefix + '/')) return null;
      path = path.slice(prefix.length + 1);
    } else path = path.replace(/^\/+/, '');
    return { path, account };
  }

  async #serveHttp(req, res) {
    const cors = { 'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type, X-Syrinx-Lang, X-Filename, Range',
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
      'Access-Control-Expose-Headers': 'Content-Range, Content-Length, Accept-Ranges' };
    if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
    const url = new URL(req.url, 'http://plugin');
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const body = Buffer.concat(chunks);
    const split = this.#split(url.pathname);
    let status, out;
    if (!split) [status, out] = [404, { error: 'Not found' }];
    else {
      const query = Object.fromEntries(url.searchParams);
      const r = {
        method: req.method === 'HEAD' ? 'GET' : req.method, path: split.path, query, headers: req.headers, body,
        account: split.account, params: {},
        get lang() { return (query.lang || req.headers['x-syrinx-lang'] || 'en').split('-')[0].toLowerCase(); },
        json() {
          try { return JSON.parse(body.toString('utf8') || 'null'); } catch { throw new PluginError('Body is not JSON'); }
        },
        int(name, def, lo, hi) {
          let v = query[name] === undefined ? def : Number(query[name]);
          if (!Number.isFinite(v)) throw new PluginError(`${name} must be a number`);
          v = Math.trunc(v); if (lo !== undefined) v = Math.max(lo, v); if (hi !== undefined) v = Math.min(hi, v);
          return v;
        },
      };
      [status, out] = await this.handle(r);
    }
    if (out instanceof Raw) {
      const rg = range(out, req.headers.range);
      if (!rg) { res.writeHead(416, { ...cors, 'Content-Range': `bytes */${out.size()}` }); return res.end(); }
      const [st, start, end, size] = rg;
      const h = { ...cors, ...out.headers, 'Content-Type': out.contentType, 'Accept-Ranges': 'bytes',
        'Content-Length': Math.max(0, end - start + 1) };
      if (st === 206) h['Content-Range'] = `bytes ${start}-${end}/${size}`;
      res.writeHead(st, h);
      if (req.method === 'HEAD' || size === 0) return res.end();
      if (out.body !== undefined) return res.end(out.body.subarray(start, end + 1));
      return createReadStream(out.path, { start, end }).pipe(res);
    }
    if (status === 204) { res.writeHead(204, cors); return res.end(); }
    const data = Buffer.from(JSON.stringify(out), 'utf8');
    res.writeHead(status, { ...cors, 'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': data.length, 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : data);
  }

  /** Small HTTP server. For the internet, put it behind a reverse proxy with HTTPS. Resolves with the server. */
  serve({ host = '0.0.0.0', port = 8702, quiet = false } = {}) {
    const server = createServer(this.handler);
    return new Promise((resolve) => server.listen(port, host, () => {
      const p = server.address().port;
      if (!quiet) console.log(`${this.name} ${this.version}: http://localhost:${p}${this.prefix.replace('<account>', '<token>')}/manifest.json`);
      resolve(server);
    }));
  }
}
