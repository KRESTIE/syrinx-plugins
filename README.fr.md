# Plugins Syrinx

[English version](README.md)

Syrinx est un lecteur de musique qui ne contient aucune musique. Tout ce qu'il affiche et joue vient de **plugins** :
de petits services web qui répondent à quelques requêtes JSON. Chacun peut en écrire un, dans n'importe quel langage,
et l'ajouter à Syrinx en collant son adresse.

Un plugin peut être une bibliothèque de musique sur ton NAS, un annuaire de radios, un catalogue de musique libre, un
service de paroles, un suivi de statistiques… ou plusieurs à la fois.

## Ce qu'il y a ici

| | |
|---|---|
| [`docs/protocole.md`](docs/protocole.md) | Le protocole, version 1 : chaque requête de l'app et la réponse attendue |
| [`python/syrinx_plugin.py`](python/syrinx_plugin.py) | SDK Python : un seul fichier, bibliothèque standard seulement (Python 3.10+) |
| [`js/syrinx-plugin.mjs`](js/syrinx-plugin.mjs) | SDK JavaScript : un seul fichier, sans dépendance (Node.js 18+) |
| [`examples/radio-browser`](examples/radio-browser/) | Un plugin complet en Python : les radios de radio-browser.info, avec recherche, fiches et un réglage |
| [`examples/tones`](examples/tones/) | Le plus petit plugin utile, en JavaScript : des notes et des accords générés en fichiers audio |
| [`syrinx_plugin_check.py`](syrinx_plugin_check.py) | L'outil de vérification : appelle ton plugin comme l'app et dit ce qui ne va pas |

## Ton premier plugin en 5 minutes

```python
from syrinx_plugin import Plugin, track

plugin = Plugin("org.exemple.salut", "Salut", "1.0.0", description="Mon premier plugin")

@plugin.catalog("choix", "Mes choix")
def choix(req, skip, limit):
    return [track("titre-1", "Un titre libre", artist="Quelqu'un", playable=True)]

@plugin.stream
def stream(req, id, quality):
    return {"url": "https://exemple.org/musique/titre-1.mp3", "cacheKey": "titre-1"}

plugin.serve(port=8700)
```

```sh
python3 salut.py
python3 syrinx_plugin_check.py http://localhost:8700/manifest.json
```

Puis dans Syrinx : **Plugins**, colle `http://<adresse de ton ordinateur>:8700/manifest.json`, **Ajouter**. Une
rangée « Mes choix » apparaît sur l'accueil.

Pas de Python ni de JavaScript ? Les SDK évitent seulement de tout taper : n'importe quel serveur web qui répond le
JSON décrit dans [le protocole](docs/protocole.md) est un plugin.

## Bon à savoir

- **HTTPS** est obligatoire, sauf sur ton réseau local et sur Tailscale. Pour ouvrir un plugin sur internet, mets-le
  derrière un proxy inverse (Caddy, nginx, Traefik) ou un tunnel avec certificat.
- **Comptes** : si ton plugin doit savoir qui appelle, mets un jeton dans son adresse
  (`Plugin(..., prefix="/u/<account>")`, puis `req.account`). L'app garde l'adresse, jamais un mot de passe.
- **Réglages** : une clé ou un choix à faire est décrit par le plugin (`plugin.settings(...)`) ; l'app dessine le
  formulaire ou l'assistant étape par étape. Voir l'exemple Radio Browser.
- **Permissions** : recevoir l'historique d'écoute, piloter les appareils, recevoir les commandes vocales ou des
  fichiers, proposer des mises à jour de l'app demandent une permission déclarée dans le manifeste, que
  l'utilisateur peut refuser.
- **Langue** : `req.lang` donne la langue de l'app (`fr`, `en`) ; réponds dans cette langue si tu peux.

## Règles pour les plugins référencés par le projet

Les plugins sont indépendants de Syrinx et leurs auteurs en sont responsables. Le projet ne référence que des
plugins qui utilisent des contenus qu'ils ont le droit de diffuser : tes propres fichiers, de la musique du domaine
public ou sous Creative Commons, des services sous licence utilisés selon leurs conditions. Les plugins qui
contournent des DRM ou téléchargent depuis des services qui l'interdisent ne sont pas référencés.

## Licence

Les SDK, exemples, l'outil de vérification et la documentation sont sous [licence MIT](LICENSE).
