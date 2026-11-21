# Protocole des plugins Syrinx, version 1

> [English version](protocol.md). Pour écrire un plugin sans tout refaire à la main : le SDK [Python](../python/) ou
> [JavaScript](../js/), et l'outil de vérification [`syrinx_plugin_check.py`](../syrinx_plugin_check.py).

Syrinx ne contient aucune musique. Tout ce qu'il affiche et joue vient de **plugins** : de petits services web que
chacun peut écrire, dans n'importe quel langage, et ajouter à Syrinx en collant une adresse. Un plugin peut être
ta bibliothèque sur un NAS, une radio, un site de musique libre, un service de paroles… ou tout cela à la fois.

## 1. Principes

- **HTTP et JSON.** L'app appelle le plugin, le plugin répond en JSON (UTF-8). Il ne pousse jamais rien vers l'app.
- **Une adresse.** On ajoute un plugin avec l'adresse de son manifeste, qui se termine par `manifest.json` :
  `https://exemple.org/syrinx/manifest.json`. Toutes les autres adresses sont **relatives au dossier du manifeste**
  (`https://exemple.org/syrinx/catalog/…`).
- **Le compte est dans l'adresse.** Si le plugin a besoin de savoir qui appelle, il met un jeton dans le chemin
  (`…/u/8f3c…/manifest.json`). L'app ne gère ni identifiants ni mots de passe pour un plugin, elle garde l'adresse.
- **Des données, jamais du code.** Un plugin renvoie du texte, des nombres et des adresses (pochettes, audio, pages).
  L'app n'exécute rien de ce qu'il envoie et affiche tout avec ses propres écrans.
- **Il déclare ce qu'il sait faire.** Le manifeste liste les ressources fournies ; l'app ne demande que celles-là et
  cache tout le reste (pas de bouton mort).
- **HTTPS obligatoire**, sauf sur le réseau local (`192.168.*`, `10.*`, `*.local`…) et sur Tailscale (`100.64.0.0/10`,
  `*.ts.net`).
- **Plusieurs plugins à la fois.** Les rangées d'accueil et les résultats de recherche de tous les plugins actifs se
  mélangent ; chaque élément reste lié au plugin qui l'a fourni (c'est lui qu'on appelle pour le lire, le liker…).
- **Les erreurs** : un code HTTP 4xx ou 5xx, et si possible `{"error": "message lisible"}` ; l'app l'affiche tel quel.
  `503` veut dire « pas prêt » (en cours de démarrage, réglage manquant) : l'app réessaie plus tard sans alarmer.

### Ce que l'app envoie à chaque appel

| En-tête | Exemple | Sens |
|---|---|---|
| `X-Syrinx-Lang` | `fr` | langue de l'interface (`fr`, `en`) : le plugin répond dans cette langue s'il peut |
| `User-Agent` | `Syrinx/3.0.4 (Android)` | app et version, pour les journaux ; dans un navigateur, celui du navigateur |

Le même choix de langue peut aussi arriver en paramètre `?lang=fr` (lecteurs qui ne peuvent pas ajouter d'en-tête).

### Versions

`protocol: 1` dans le manifeste. Ce qui s'ajoute plus tard arrive comme **nouvelles ressources** ou **nouveaux champs
facultatifs** : un plugin écrit pour la version 1 continue de marcher. Un changement qui casserait des plugins
passerait par `protocol: 2`, et l'app parlerait les deux.

## 2. Le manifeste

`GET manifest.json`

```json
{
  "protocol": 1,
  "id": "org.exemple.radios",
  "name": "Radios du monde",
  "version": "1.2.0",
  "description": "Des milliers de radios en direct, par genre et par pays",
  "color": "#3DA5FF",
  "resources": ["catalog", "search", "meta", "stream"],
  "catalogs": [
    { "id": "top", "name": "Les plus écoutées", "type": "track", "section": "home" },
    { "id": "jazz", "name": "Jazz", "type": "track", "section": "home" }
  ]
}
```

| Champ | Obligatoire | Sens |
|---|---|---|
| `protocol` | oui | `1` |
| `id` | oui | identifiant stable, à l'envers d'un nom de domaine (`org.exemple.radios`). Deux plugins de même `id` : l'app garde le dernier ajouté (mise à jour d'adresse) |
| `name` | oui | nom affiché |
| `version` | oui | version du plugin (`1.2.0`), affichée dans ses réglages |
| `description` | non | une phrase, affichée à l'ajout |
| `color` | non | couleur du plugin (`#RRGGBB`), pour son badge |
| `resources` | oui | ce qu'il fournit (chapitre 4) |
| `catalogs` | non | ses rangées et onglets (ressource `catalog`) |
| `import` | non | texte du champ « ajouter depuis un lien » : `{"label": "Ajouter", "hint": "Lien d'un album Bandcamp"}` ; `help` (facultatif) : ce qu'on peut ajouter, affiché sous le champ, `[{"title", "text"}]` |
| `permissions` | non | ce qu'il demande à recevoir ou à faire (chapitre 5) |

Le manifeste peut changer d'un appel à l'autre (une rangée qui n'apparaît qu'une fois un réglage fait, une langue
différente) : l'app le relit au démarrage et après chaque réglage du plugin.

### Catalogues

| Champ | Sens |
|---|---|
| `id` | identifiant, dans `catalog/<id>.json` |
| `name` | titre de la rangée ou de l'onglet |
| `type` | `track`, `album`, `artist`, `playlist` : ce que la rangée contient (forme des cartes) |
| `section` | `home` (rangée de l'accueil) ou `library` (onglet de la bibliothèque) |

## 3. Les éléments

Tout ce que l'app affiche est un **élément** : un titre, un album, un artiste ou une playlist, toujours dans la même
forme. Seuls `id`, `type` et `title` sont obligatoires ; le reste rend l'affichage plus riche.

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
  "artwork": "https://exemple.org/syrinx/cover/k7?size=600",
  "playable": true,
  "favorite": false
}
```

L'`id` n'a de sens que pour son plugin : l'app ne le lit pas, elle le renvoie tel quel (`stream/<id>.json`,
`meta/track/<id>.json`…). Il peut contenir n'importe quels caractères ; l'app l'encode dans les adresses.

### Champs communs

| Champ | Type | Sens |
|---|---|---|
| `id` | texte | identifiant dans ce plugin |
| `type` | texte | `track`, `album`, `artist`, `playlist` |
| `title` | texte | titre, nom de l'album, de l'artiste ou de la playlist |
| `subtitle` | texte | seconde ligne de la carte (artiste, « 2019 · 12 titres »…) ; sinon l'app la compose |
| `artwork` | adresse | image carrée (600 px conseillé) ; relative au manifeste ou absolue |
| `playable` | booléen | « lire » proposé (pour un album, un artiste ou une playlist : tout lire) |
| `favorite` | booléen | déjà liké (cœur plein). **Absent : l'élément ne se like pas** (pas de cœur : une radio, un titre de musique libre…) |
| `badge` | texte | petite étiquette sur la carte (« Inédit », « Musique libre ») |
| `notice` | texte | note affichée dans le lecteur pendant l'écoute |
| `source` | objet | d'où vient l'élément, quand une licence l'exige : `{name, url, license, licenseUrl}` ; l'app affiche le crédit et le lien |

### Titres (`track`)

| Champ | Sens |
|---|---|
| `artist`, `album` | textes affichés par les lecteurs (barre, notification, voiture) |
| `artistId`, `albumId` | pour ouvrir la page de l'artiste ou de l'album chez ce plugin |
| `duration` | secondes |
| `live` | radio en direct : pas de durée, ni like, ni téléchargement |
| `explicit` | badge « E » |
| `loudness` | `{lufs, peak}` : volume perçu, pour le volume homogène |
| `tempo` | BPM approximatif (animations au rythme) |
| `bpm`, `key`, `mixIn`, `mixOut`, `energy` | pour le Mix DJ : tempo précis, tonalité Camelot (`8A`), début utile et début de transition (secondes), énergie de 0 à 1 |

### Albums (`album`)

`artist`, `artistId`, `year`, `genre`, `format` (« FLAC · 24 bits »), `songCount` (titres de l'album entier),
`owned` (titres présents chez l'utilisateur, si l'album n'y est qu'en partie), `description` (court texte).

### Artistes (`artist`)

`banner` (grande photo pour le haut de sa page), `description` (biographie), `libraryId` / `onlineId` (le même
artiste dans une autre partie du plugin, pour passer d'une page à l'autre).

### Playlists (`playlist`)

Les champs communs suffisent ; `subtitle` dit en général le nombre de titres.

### Ce que l'app fait elle-même

Couleurs tirées de la pochette, animations, file d'attente, hors-ligne (sauf si `stream` l'interdit), égaliseur,
partage : rien de tout cela n'est à fournir par un plugin.

## 4. Les ressources

Quatre familles. Un plugin n'en fournit que ce qu'il veut : une radio se contente de `catalog`, `search` et `stream`.

- **Source** : `catalog`, `search`, `meta`, `stream`, `similar`, `wave`.
- **Bibliothèque** : `actions`, `import`, `jobs`, `upload`, `library`, `suggestions`.
- **Compagnons** : `lyrics`, `scrobble`, `stats`, `wrapped`, `dashboard`, `milestones`, `profiles`, `prefs`, `now`,
  `remote`, `jam`, `tastes`, `artist`, `update`, `voice`.
- **Réglages** : `settings` (formulaire ou assistant déclaré par le plugin, 4.13).

### 4.1 `catalog` : rangées et onglets

`GET catalog/<id>.json?skip=0&limit=50`

```json
{ "items": [ { "id": "k7", "type": "album", "title": "Kind of Blue", "subtitle": "Miles Davis · 1959" } ] }
```

- `skip` et `limit` (50 par défaut, 500 au plus) : l'app demande la suite en faisant défiler. Moins de `limit`
  éléments veut dire « c'est tout ». Un catalogue sans pages (une sélection du moment) ignore `skip` et renvoie une
  liste vide pour `skip > 0`.
- Une rangée vide n'est pas affichée : un plugin peut garder un catalogue dans son manifeste et ne rien y mettre
  tant qu'il n'a rien à montrer.

### 4.2 `search` : recherche

`GET search.json?q=blue%20in%20green`

```json
{
  "sections": [
    { "id": "mine", "title": "Dans ta bibliothèque", "items": [ … ] },
    { "id": "more", "title": "Ailleurs", "load": "search/more.json?q=blue%20in%20green" }
  ]
}
```

- Des **sections**, affichées dans l'ordre. Une section a soit ses `items` tout de suite, soit une adresse `load`
  (relative au manifeste) que l'app appelle ensuite : la page s'affiche avec ce qui est rapide, la partie lente
  arrive après. `load` renvoie `{"items": [...], "errors": ["message"]}` ; `errors` (facultatif) s'affiche sous la
  section si une partie de la recherche a échoué.
- `q` vide : `{"sections": []}`.
- `source` (facultatif) : l'utilisateur a demandé une source précise à la voix (« mets du jazz sur Radio Browser ») ; l'app envoie le mot tel quel. Le plugin ne renvoie que les sections de cette source, ou
  `{"sections": []}` s'il ne la connaît pas (l'app fait alors une recherche normale).
- Avec plusieurs plugins, l'app affiche les sections de chacun, sous le nom du plugin.

### 4.3 `meta` : fiches (album, artiste, playlist, titre)

`GET meta/<type>/<id>.json` (`type` : `album`, `artist`, `playlist`, `track`)

```json
{
  "item": { "id": "k7", "type": "album", "title": "Kind of Blue", "artist": "Miles Davis", "year": 1959 },
  "tracks": [ { "id": "a81f", "type": "track", "title": "So What", "duration": 562 } ],
  "related": { "title": "Du même artiste", "items": [ … ] },
  "facts": [ { "label": "Label", "value": "Columbia" } ]
}
```

| Champ | Sens |
|---|---|
| `item` | l'élément lui-même, plus complet que sur une carte (bannière, description…) |
| `tracks` | titres, dans l'ordre (album, playlist ; artiste : ses titres les plus connus) |
| `albums` | artiste : ses albums |
| `singles` | artiste : singles et EP, montrés à part des albums |
| `mine` | artiste : les titres de lui que l'utilisateur a déjà (bouton « Aléatoire ») |
| `popular` | artiste : `true` si `tracks` sont ses titres populaires plutôt que tous ses titres |
| `related` | une rangée en bas de page : `{title, items}` |
| `facts` | petites infos `{label, value}` affichées en liste |

Fiche introuvable : `404`.

### 4.4 `stream` : lecture

`GET stream/<id>.json?quality=raw`

```json
{ "url": "https://exemple.org/syrinx/audio/a81f?format=opus&maxBitRate=128", "cacheKey": "a81f-opus128" }
```

| Champ | Sens |
|---|---|
| `url` | adresse du fichier ou du flux audio (relative ou absolue) ; l'app la lit directement, avec les en-têtes HTTP habituels (plages `Range` pour avancer dans le titre) |
| `cacheKey` | nom stable de ce fichier dans cette qualité : l'app le garde en cache et hors ligne sous ce nom |
| `live` | flux en direct (radio) : pas de durée, pas d'avance rapide, jamais gardé |
| `noStore` | ne jamais garder ce titre sur l'appareil (cache ni hors ligne), quand la licence de la source l'exige |
| `headers` | en-têtes HTTP à envoyer avec la requête audio (`{"Authorization": "…"}`), si l'adresse en a besoin |

`quality` (choisie dans les réglages de l'app, selon le réseau) : `raw` (le fichier d'origine), `opus256`,
`opus128`, `mp3320`. Un plugin qui n'a qu'une qualité l'ignore et renvoie toujours la même.

Formats que l'app lit : MP3, AAC / M4A, Opus / Ogg, FLAC, WAV ; flux HTTP continus (radios, Icecast / Shoutcast). Titre indisponible : `404` ou `502` avec `{"error": "…"}`, l'app passe au suivant en le disant.

### 4.5 `similar` : lecture continue

Quand la file d'attente se vide, l'app demande la suite : des titres proches de celui qui joue.

`GET similar/<id>.json?limit=15&exclude=a81f,b22c&context=x1,x2&discover=1`

```json
{ "items": [ { "id": "c903", "type": "track", "title": "Flamenco Sketches", "artist": "Miles Davis" } ] }
```

| Paramètre | Sens |
|---|---|
| `limit` | nombre souhaité (15 par défaut, 50 au plus) ; en renvoyer moins est permis, l'app redemandera |
| `exclude` | identifiants déjà dans la file ou déjà joués, à ne pas renvoyer |
| `context` | les derniers titres écoutés (jusqu'à 5), du plus récent au plus ancien : l'ambiance de la session |
| `discover` | `0` : seulement des titres que l'utilisateur a ; `1` : en ajouter qu'il n'a pas encore s'il en manque ; `2` : en mêler régulièrement |
| `dj` | `1` : le Mix DJ est actif, ordonner pour que tempo et tonalité s'enchaînent (si le plugin sait le faire) |

Deux identifiants spéciaux à la place d'un titre : `random` (un mélange au hasard, sans titre de départ) et `wave`
(voir `wave`). Le plugin du titre en cours est appelé ; s'il n'a pas `similar` (une radio, de la musique libre…),
l'app demande `similar/random.json` au premier plugin actif qui l'a : la musique continue en mélange.

### 4.6 `wave` : radio personnelle et humeurs

Une lecture continue sans titre de départ, choisie selon les goûts de l'utilisateur, avec des humeurs.

`GET wave.json`

```json
{
  "enabled": true,
  "moods": [ { "id": "calm", "name": "Calme", "count": 412, "ready": true, "learned": { "out": 3, "in": 12 } } ],
  "suggested": "calm"
}
```

- `moods` : humeurs proposées (`ready` : assez de titres pour la lancer) ; `learned` : ce que l'humeur a appris des
  écoutes (titres retirés parce que souvent passés, titres ajoutés parce qu'écoutés).
- `suggested` : l'humeur à proposer en premier à ce moment de la journée, ou `null`.
- La lecture elle-même passe par `similar/wave.json?mode=balanced&mood=calm&…` : `mode` vaut `familiar`, `balanced`
  ou `discovery` (dosage de titres nouveaux), `mood` est facultatif.
- `DELETE wave/learned?mood=calm` : oublier ce que l'humeur a appris (sans `mood` : toutes).
- Facultatifs, pour l'écran de progression : `analyzed`, `total` (titres analysés sur le total).

### 4.7 `actions` : le menu d'un élément

Le plugin dit ce qu'on peut faire d'un élément ; l'app affiche le menu, les confirmations et les petits formulaires,
puis renvoie le choix. Aucune action n'est codée dans l'app : liker, ranger dans une playlist, supprimer, ouvrir la
page d'origine… tout passe par là.

`GET actions/<type>/<id>.json` (facultatif : `?playlist=<id>&index=<n>` quand l'élément est ouvert depuis une playlist)

```json
{
  "actions": [
    { "id": "favorite", "label": "Ajouter aux titres likés", "context": { "type": "track", "id": "a81f" } },
    { "id": "add-to-playlist", "label": "Ajouter à une playlist", "context": { "type": "track", "id": "a81f" },
      "fields": [
        { "key": "playlist", "label": "Playlist", "type": "choice", "default": "new",
          "options": [ { "value": "new", "label": "Nouvelle playlist" }, { "value": "p1", "label": "Jazz du soir" } ] },
        { "key": "name", "label": "Nom de la nouvelle playlist", "type": "text",
          "showIf": { "key": "playlist", "equals": "new" } }
      ] },
    { "id": "delete", "label": "Supprimer de la bibliothèque", "style": "danger",
      "confirm": "Le fichier est effacé. Impossible d'annuler.", "context": { "type": "track", "id": "a81f" } }
  ]
}
```

| Champ d'une action | Sens |
|---|---|
| `id` | nom de l'action, renvoyé tel quel |
| `label` | texte du menu |
| `context` | ce que le plugin veut recevoir en retour (libre) |
| `style` | `danger` : en rouge |
| `confirm` | texte d'une confirmation avant d'agir |
| `fields` | petit formulaire : `type` `text` ou `choice` (avec `options`), `default`, `showIf` (`{key, equals}` ou `{key, notEquals}` : champ visible selon un autre) |
| `disabled` | grisée (rien à faire pour l'instant) |

`POST action/<id>` avec `{"context": {…}, "values": {"playlist": "p1"}}`

```json
{ "ok": true, "message": "Ajouté à « Jazz du soir »", "refresh": true }
```

| Champ de la réponse | Ce que fait l'app |
|---|---|
| `ok`, `message` | affiche le message (en erreur si `ok` vaut `false`) |
| `refresh` | recharge la page et les rangées affichées |
| `favorite` | met le cœur à jour sans recharger |
| `removed` | identifiants retirés : enlevés de la page et de la file |
| `skip` | identifiants à ne plus proposer : retirés de la file d'attente |
| `open` | adresse à ouvrir dans le navigateur (page d'origine, achat) |
| `job` | une tâche a démarré (voir `jobs`) |

**Deux actions que l'app appelle sans menu**, si le plugin les propose :
- `favorite` : le cœur du lecteur, de la notification et de la voiture, et « like » à la voix. `values` peut
  contenir `{"on": "true"}` (liker) ou `{"on": "false"}` ; sans `on`, inverser.
- l'action `keep` d'un titre (champ `keep` de l'élément, même forme qu'une action) : pour une découverte jouée en
  streaming, l'app la lance d'elle-même quand le titre est écouté jusqu'au bout (« écouté en entier = gardé »).

### 4.8 `import` et `jobs` : ajouter depuis un lien

Pour un plugin qui sait ajouter quelque chose à partir d'un lien (un achat sur un site, une playlist publique, une
collection d'archives…). Le manifeste donne le texte du champ :
`"import": {"label": "Ajouter", "hint": "Lien d'un album acheté sur Bandcamp"}`. Le plugin seul décide quels liens il
accepte.

`GET import/preview.json?url=<lien>`

```json
{
  "item": { "id": "imp-42", "type": "playlist", "title": "Road trip", "subtitle": "28 titres", "artwork": "…" },
  "stats": [ { "label": "12 déjà chez toi" }, { "label": "16 à ajouter", "accent": true } ],
  "sample": [ "Titre 1 · Artiste", "Titre 2 · Artiste" ],
  "action": { "id": "import", "label": "Ajouter 16 titres", "context": { "key": "imp-42" }, "fields": [ … ] }
}
```

L'app montre l'aperçu ; le bouton est une action ordinaire (`POST action/import`), qui renvoie en général un `job`.
Lien refusé : `400` avec `{"error": "Ce lien n'est pas pris en charge"}`.

`GET jobs.json` : les tâches en cours et récentes, que l'app affiche avec leur avancement.

```json
{ "items": [ { "id": "j7", "label": "Road trip", "status": "3 sur 16", "done": 3, "total": 16,
               "finished": false, "errors": 0, "note": null } ] }
```

### 4.9 `upload` : envoyer ses fichiers

Pour un plugin qui range de la musique (un NAS, un serveur) : l'utilisateur envoie ses achats ou ses CD numérisés
depuis son téléphone ou son navigateur.

- `POST upload` : un fichier par requête, le corps est le fichier, son nom dans l'en-tête `X-Filename`. Audio (MP3,
  FLAC, M4A, OGG, Opus, WAV, AIFF) ou ZIP d'un album. Réponse :
  `{"added": [...], "rejected": [{"name", "reason"}], "fix": [...], "groups": [...]}`. `groups` : ce qui a été rangé,
  par album (`folder`, `artist`, `album`, `files`, `titles`, `others`, `fix`) ; `fix` : fichiers dont l'artiste est
  inconnu, pour lesquels l'app propose « Corriger les infos ».
- `POST upload/fix` `{path, artist, album, title}` : corriger un fichier.
- `POST upload/fix-album` `{files, artist, album, year, titles}` : corriger un album entier → `{group}`.
- `POST upload/undo` `{files}` → `{token}` ; `POST upload/redo` `{token}` → `{groups}` : annuler un envoi et le
  rétablir (le plugin garde les fichiers au moins quelques heures).

### 4.10 `library` : « quelque chose a changé »

`GET library.json` → `{"rev": 1834}`. Un nombre qui change quand la bibliothèque change (titres ajoutés, supprimés,
rangés). L'app le relit de temps en temps et recharge ses rangées quand il bouge, sans tout redemander.

### 4.11 `suggestions` : « Tu pourrais aimer »

- `GET suggestion.json?id=<titre en cours>&exclude=<ids>` → `{"item": {…}}` ou `{"item": null}` : une carte dans la
  file d'attente, un titre que l'utilisateur n'a pas, proche de celui qui joue. Il n'est pas joué : la carte propose
  un extrait.
- `GET preview.json?kind=song&title=&artist=` → `{found, title, artist, album, preview, store, artwork, credit}` :
  un extrait de 30 secondes (`preview`, lu en streaming, jamais gardé) et la page où l'acheter (`store`). Un élément
  qui n'est pas jouable peut porter `store: {kind, title, artist}` pour que l'app demande cet extrait à la demande.

### 4.12 Compagnons

Des ressources indépendantes : un plugin de paroles ne fournit que `lyrics`, un plugin de statistiques que `scrobble`
et `stats`. Quand plusieurs plugins actifs fournissent la même, l'app prend le premier qui la fournit, dans l'ordre
de la liste des plugins.

#### `lyrics` : paroles

`GET lyrics.json?title=&artist=&album=&duration=` (durée en secondes)

```json
{ "synced": true, "instrumental": false, "lines": [ { "t": 12.4, "text": "Première ligne" } ] }
```

`t` : début de la ligne en secondes, `null` si les paroles ne sont pas synchronisées. `lines` vide : rien trouvé.

#### `scrobble` : écoutes

L'app envoie ses écoutes par paquets, y compris celles faites hors ligne (envoyées plus tard ; un même envoi peut
arriver deux fois, le plugin ignore les doublons : même `id` et même `started`).

`POST scrobble` `{"plays": [{"id", "title", "artist", "album", "duration", "heard", "started", "kind"}]}` →
`{"ok": true, "received": 3}`. `started` : date de début (secondes Unix) ; `heard` : secondes écoutées ;
`kind` : `listen` (plus de 30 s ou la moitié du titre) ou `skip`. Les radios en direct ne sont pas envoyées.
**Permission** : `plays`.

#### `stats` : tes stats

`GET stats.json?period=month` (`month`, `year`, `all`) : une page que l'app affiche telle quelle.

| Champ | Sens |
|---|---|
| `label` | titre de la période (« Novembre 2026 ») |
| `enough` | assez d'écoutes pour en dire quelque chose |
| `highlights` | chiffres clés `{label, value}` |
| `profile` | profil d'auditeur `{title, text}` ou `null` |
| `chart`, `days` | barres `{title, values, labels, note}` : heures d'écoute, jours de la semaine |
| `sections` | listes `{id, title, items, hint, play}` ; les `id` `songs`, `artists` et `albums` (les plus écoutés) ont une place à part en haut de la page, les autres suivent |
| `since` | date depuis laquelle les écoutes sont comptées |
| `wave` | mesure de la radio perso par humeur, ou `null` |

#### `wrapped` : le bilan de l'année

Le bilan est une page à part entière, faite par le plugin (animations, partage) : l'app l'ouvre telle quelle. Voir
l'annexe A.

#### `dashboard` : salle de contrôle

`GET dashboard.json?days=7&profile=all` : écoutes en direct, chiffres du jour, heures, artistes, genres, santé du
serveur, activité. Pour le propriétaire d'un serveur. Voir l'annexe B.

#### `milestones` : paliers et anniversaires

`GET milestones.json` → `{"listens": 10012, "marks": [100, 1000, 5000, …], "anniversary": {…} | null}`.
L'app fête chaque palier de `marks` franchi par `listens` une seule fois. `anniversary` : un album sorti un jour comme
aujourd'hui (`{id, title, artist, artwork, year, years}`), proposé à l'écoute.

#### `profiles` et `prefs` : plusieurs personnes

Pour un plugin partagé par une famille (« Qui écoute ? »). Chaque profil a sa propre adresse de plugin (son jeton) :
changer de profil, c'est changer d'adresse.

- `GET profiles.json` → `{"me": "<id>", "profiles": [{"id", "name", "color", "main", "base"}]}` ; `base` : adresse
  du plugin pour ce profil.
- `POST profiles` `{name, color?}` : créer ; `POST profiles/<id>` `{name?, color?}` : modifier ;
  `DELETE profiles/<id>` : supprimer (profil principal seulement).
- `GET profiles/<id>/photo.jpg` ; `POST profiles/<id>/photo` (image déjà recadrée) ; `DELETE` pour la retirer.
- `GET prefs.json` / `POST prefs` `{clé: valeur}` : réglages qui suivent la personne d'un appareil à l'autre
  (`waveMode`, `waveMood`, `discover`).

#### `now` : reprendre sur un autre appareil

- `POST now` `{device, deviceId, playStart, items, index, position, playing, origin}` : l'appareil qui joue l'envoie
  de temps en temps.
- `GET now.json` : le dernier état (ou `{}`), pour « continuer ici ».
- Une seule écoute à la fois par profil : si un appareil plus récent a lancé la lecture (`playStart`), le plugin
  répond `{"superseded": true, "device": "Téléphone"}` et l'ancien se met en pause.

#### `remote` : télécommande

Chaque appareil ouvert se signale et attend ses commandes, sans connexion permanente (attente longue).

- `POST remote/sync` `{"device": {id, name, kind}, "state": {items, index, position, duration, playing, volume},
  "wait": 25}` → `{"commands": [...]}` : le plugin répond dès qu'une commande arrive pour cet appareil, sinon au bout
  de `wait` secondes. `wait: 0` : simple envoi de l'état.
- `GET remote/devices.json?me=<id>` → `{"devices": [{id, name, kind, state, seen, online}]}` : les autres appareils.
- `POST remote/<id>/command` `{"type": …}` : `toggle`, `play`, `pause`, `next`, `previous`, `seek {position}`,
  `volume {value 0..1}`, `jump {index}`, `load {items, index, origin, position?}`, `wave {mood?}`, `mix`, `stop`.

#### `jam` : écouter à plusieurs

Construit sur `remote` : le plugin recale chaque invité sur l'appareil de l'hôte (même titre, même moment).

- `GET jam.json?me=<appareil>` → `{"jam": {…} | null, "invites": [...], "online": [...]}`.
- `POST jam/start {device}`, `jam/join {code, device}`, `jam/leave`, `jam/invite {profile}`, `jam/decline {code}`,
  `jam/add {items}`, `jam/control {type, …}`, `jam/settings {controlAll?, addAll?}`, `jam/live`.
- Forme de `jam` : annexe C.

#### `tastes` : écran de bienvenue

- `GET tastes.json` → `{artists, genres, asked, ask, genreList: [{id, name}], suggestions}` ; `ask` : le proposer
  tout seul (jamais rempli et bibliothèque encore petite).
- `GET tastes/suggest.json?genres=` et `GET tastes/search.json?q=` → `{"items": [{name, id, artwork, inLibrary}]}`.
- `GET tastes/playlist.json?url=` : les artistes les plus présents d'une playlist publique.
- `POST tastes {artists, genres?}` : enregistrer ; `POST tastes/top {name}` : ajouter les titres phares d'un artiste
  (plugin qui sait ajouter, voir `import`).

#### `artist` : en savoir plus sur un artiste

- `GET artist/info.json?name=` → `{"state": "building"}` pendant une première recherche (l'app redemande quelques
  secondes plus tard), puis `{"state": "ready", bio, photo, popular, albums, similar}`.
- `GET artist/rare.json?name=` → même principe, `{"state": "ready", "title", "text", "items": [...]}` : des titres
  de l'artiste introuvables ailleurs, chargés à part parce que c'est lent ; `title` et `text` (facultatifs) : titre
  et phrase de la section.

#### `update` : mises à jour de l'app

Pour un plugin qui distribue lui-même l'app Android (amis sans accès au magasin d'applications).

`GET update.json` → `{"version": "3.0.4", "code": 141, "size": 41234567, "notes": "…", "url": "update/syrinx.apk"}`
ou `{"version": null}`. L'app propose la mise à jour si `code` est plus grand que le sien. **Permission** : `update`.

#### `voice` : commandes vocales

`POST voice` (corps : WAV 16 kHz, mono, 16 bits, 5 Mo au plus) → `{"text": "mets du jazz"}`. Le plugin transcrit
la demande ; l'app la comprend elle-même ensuite. **Permission** : `voice`.

### 4.13 `settings` : réglages déclarés par le plugin

Un plugin qui a besoin d'une clé, d'un compte ou d'un choix le **décrit** ; l'app l'affiche avec ses écrans, dans
la page du plugin. Un simple formulaire (quelques champs) ou un assistant en plusieurs étapes, avec des liens à
ouvrir, des valeurs à copier et une vérification à la fin.

`GET settings.json`

```json
{
  "groups": [
    {
      "id": "jamendo",
      "title": "Musique libre",
      "text": "Des centaines de milliers de titres d'artistes indépendants, gratuits.",
      "status": { "ok": false, "text": "Pas encore activée" },
      "needed": false,
      "steps": [
        { "title": "Crée ton compte", "text": "Sur le portail des développeurs de Jamendo, gratuit.",
          "link": { "label": "Ouvrir le portail", "url": "https://devportal.jamendo.com" } },
        { "title": "Crée une application", "text": "Recopie ces valeurs dans le formulaire.",
          "copy": [ { "label": "Name", "value": "Syrinx" }, { "label": "Website", "value": "https://syrinx.li" } ] },
        { "title": "Colle ton Client ID",
          "fields": [ { "key": "clientId", "label": "Client ID", "type": "secret" } ] }
      ],
      "submit": { "label": "Vérifier et activer" },
      "reset": { "label": "Désactiver", "confirm": "La rangée Musique libre disparaît de l'accueil." }
    }
  ]
}
```

| Champ d'un groupe | Sens |
|---|---|
| `id` | identifiant, dans `settings/<id>` |
| `title`, `text` | titre et phrase d'explication |
| `status` | état actuel `{ok, text}` : une ligne verte (`ok`) ou neutre sous le titre |
| `needed` | `true` : le plugin ne peut pas marcher sans ; l'app l'ouvre à l'ajout et le signale sur la page du plugin |
| `steps` | une ou plusieurs étapes ; une seule étape = un formulaire simple |
| `submit` | texte du bouton final ; `null` s'il n'y a rien à envoyer (une commande à taper ailleurs) |
| `reset` | facultatif : bouton pour tout effacer, avec sa confirmation |

Une étape a un `title` et peut avoir un `text`, un `link` `{label, url}` (ouvert dans le navigateur), une liste
`copy` de valeurs à recopier (`{label, value}`, avec un bouton Copier) et des `fields` : les mêmes que pour les
actions (`text`, `choice`, `showIf`, `default`), plus `secret` (texte masqué), `toggle` (oui / non) et `number`
(avec `min`, `max`). Les valeurs déjà enregistrées reviennent en `default` (jamais celles de type `secret` : le plugin
renvoie `"set": true` sur le champ pour dire « déjà rempli » ; un secret renvoyé vide veut dire « garder
l'ancien »).

`POST settings/<id>` avec `{"values": {"clientId": "…"}}` : le plugin vérifie (un vrai appel, si possible) et
enregistre.

```json
{ "ok": true, "message": "Musique libre activée : 612 000 titres disponibles", "refresh": true }
```

`ok: false` avec `message` : l'app garde l'assistant ouvert et affiche le message sous le bouton. `refresh` : l'app
relit le manifeste (de nouvelles rangées peuvent apparaître). `DELETE settings/<id>` : le bouton `reset`.

## 5. Permissions

Afficher, chercher, jouer, et agir quand l'utilisateur le demande (un like, un ajout, une suppression) ne demandent
aucune permission : c'est lui qui appuie. Une permission couvre ce qu'un plugin **reçoit sans qu'on le lui donne
explicitement** ou ce qu'il **déclenche sur l'appareil**.

| Permission | Ce qu'elle permet | Ressources concernées |
|---|---|---|
| `plays` | recevoir l'historique d'écoute (quoi, quand, combien de temps, passé ou non) | `scrobble` |
| `devices` | connaître les appareils ouverts, ce qu'ils jouent, et les piloter à distance | `now`, `remote`, `jam` |
| `voice` | recevoir l'enregistrement d'une commande vocale (quelques secondes, après « Hey Syrinx ») | `voice` |
| `files` | recevoir les fichiers que l'utilisateur choisit d'envoyer | `upload` |
| `notifications` | faire apparaître une notification (invitation à un Jam, ajout terminé) | `jam`, `jobs` |
| `update` | proposer d'installer une nouvelle version de l'app | `update` |

Le manifeste les déclare : `"permissions": ["plays", "devices"]`.

**Ce que fait l'app**

- **À l'ajout**, avant d'activer le plugin, elle montre ce qu'il demande, une ligne par permission, en mots simples
  (« Recevoir ce que tu écoutes »), chacune avec son interrupteur. L'utilisateur peut tout refuser et garder le
  plugin pour le reste.
- **Par défaut** : tout ce qui est demandé est coché, sauf `update`, qu'il faut cocher soi-même.
- **Une permission refusée**, ou non déclarée, coupe les ressources concernées : l'app ne les appelle pas, comme si
  le plugin ne les fournissait pas. Un manifeste sans champ `permissions` (écrit avant les permissions) est traité
  comme s'il demandait tout.
- **Plus tard**, tout se change sur la page du plugin.

**`update` en particulier.** Android n'installe une mise à jour que si elle est signée par la même clé que l'app
déjà installée : un plugin ne peut pas remplacer Syrinx par autre chose. L'utilisateur voit quand même toujours
l'écran d'installation d'Android et peut refuser.

**Contenus externes.** Pochettes et fichiers audio peuvent être hébergés ailleurs que chez le plugin (adresses
absolues) : l'appareil les télécharge alors directement depuis ce site, qui voit passer la demande. La page du
plugin dans l'app le signale quand c'est le cas. Les plugins qui tiennent à la discrétion relaient eux-mêmes ces
fichiers.

## Annexes

### A. `wrapped` : le bilan

Le bilan est une page web servie par le plugin, à `wrapped.html?period=year` (relative au manifeste), que l'app
ouvre en plein écran. Le plugin y fait ce qu'il veut (animations, cartes à partager). `GET wrapped.json?period=`
(facultatif) donne les mêmes chiffres en données brutes (`minutes`, `listens`, `topSongs`, `topArtists`,
`topAlbums`, `streak`, `profile`…), pour qui voudrait les afficher autrement.

### B. `dashboard` : la salle de contrôle

```json
{
  "now": { "playing": [ { "id": "dev1", "profile": "p1", "name": "Alex", "color": "#ff6a3d", "photo": null,
                          "device": "PC", "kind": "web", "title": "So What", "artist": "Miles Davis", "artwork": "…",
                          "playing": true, "position": 42, "duration": 562, "origin": "wave", "jam": null } ],
           "jams": [ { "code": "K7Q2", "host": "Alex", "people": 3 } ] },
  "kpis": { "playing": 1, "inJam": 0, "today": 58, "todayLastWeek": 41, "hours": 3.2, "listens": 12034,
            "library": 8412, "added": 37, "skipShare": 0.18, "alerts": 0 },
  "hours": { "today": [24 nombres], "average": [24 nombres], "now": 16 },
  "heat": [7 lignes de 24 nombres],
  "days": { "profiles": [ { "id", "name" } ], "days": [ { "date": "2026-11-21", "counts": [par profil] } ] },
  "artists": [ { "name", "count" } ], "genres": [ { "name", "count" } ], "untagged": 12,
  "sources": { "library": 0.82, "discoveries": 0.18 },
  "health": { "checks": [ { "name": "Disque Musique", "state": "ok", "text": "1,8 To libres", "used": 0.55 },
                          { "name": "Sauvegarde", "state": "ok", "text": "{ago}", "at": 1795250000 } ],
              "alerts": [ { "id", "title", "detail" } ] },
  "activity": [ { "at": 1795270000, "kind": "download", "text": "Road trip", "status": "16 sur 16" } ],
  "profiles": [ { "id", "name", "color" } ],
  "period": 7, "at": 1795274000
}
```

`days` (paramètre) : la période en jours ; `profile` : un profil ou `all`. Toutes les parties sont facultatives :
l'app cache celles qui manquent. `health.checks` est une liste libre : chaque serveur y met ce qu'il surveille.
`state` : `ok` (vert), `warn` (orange), `bad` (rouge), `neutral` ; `{ago}` dans `text` est remplacé par l'app par
le temps écoulé depuis `at` (« il y a 3 min ») ; `used` (de 0 à 1) ajoute une jauge.

### C. `jam` : écouter à plusieurs

`GET jam.json?me=<appareil>`

```json
{
  "jam": {
    "code": "K7Q2", "host": { "id": "dev1", "name": "PC d'Alex" }, "isHost": false,
    "people": [ { "id": "p1", "name": "Alex", "host": true }, { "id": "p2", "name": "Léa", "host": false } ],
    "settings": { "controlAll": false, "addAll": true }, "canControl": false, "canAdd": true,
    "items": [ { "id": "a81f", "type": "track", "title": "…", "addedBy": "Léa" } ],
    "playing": true, "position": 63.2, "duration": 214, "expires": 1795290000, "live": true
  },
  "invites": [ { "code": "Z9P1", "host": "Léa" } ],
  "online": [ { "id": "p3", "name": "Sam", "color": "#7c4dff", "invited": false } ]
}
```

`items` : le titre en cours puis la suite, avec qui l'a ajouté. `live: false` : cet invité a mis pause de son côté
(« Reprendre en direct »). `invites` : invitations reçues ; `online` : profils qu'on peut inviter.
`POST jam/join` renvoie le même objet `jam`, de quoi lancer la lecture tout de suite.

