# Brouillon de l'entrée D42 (pour relecture par Hadil)

Brouillon à recopier dans `docs/DECISIONS.md` après relecture, à la suite de D41. `docs/DECISIONS.md` n'est pas
modifié par cette PR.

---

### D42 — OCR en arrière-plan : cache par carte, un seul OCR à la fois, échec non définitif

**Numéro** : D42, deuxième des numéros D41 à D45 réservés à DS3 (D40).

**Décision** : `reading/ocr_cache.py` lit un document par l'OCR **dans un processus séparé**
(`python -m src.document_intelligence.reading.ocr fichier --json sortie`), jamais dans le processus du service, et
garde le résultat dans un cache propre à DS3 : `<DS3_CACHE_DIR>/cards/<card_id>/documents/<document_id>/<sha256[:24]>_<code version>.json`,
écrit de façon atomique. `lookup_or_start` renvoie l'un de trois états : `pret` (document lu en cache), `en_cours`
(lecture en file d'attente ou en cours) ou `echec`. Sans `DS3_CACHE_DIR`, ou sans PaddleOCR, `default_backend()`
renvoie `None` et rien n'est lancé.
- **Un seul OCR par fichier** : le verrou du document (`<nom>.lock`, créé de façon atomique) empêche une seconde
  lecture du même fichier.
- **Un seul OCR à la fois pour tout le cache** : un OCR occupe tout le CPU (environ 27 s par page). Chaque demande
  crée le verrou de son document en état `attente`, qui sert aussi de ticket dans la file. Le verrou global
  `<DS3_CACHE_DIR>/ocr_actif.lock` désigne la seule lecture active. Quand elle se termine, ou à la question suivante,
  la plus ancienne demande en attente démarre (premier arrivé, premier servi). Les autres demandes restent `en_cours`.
  La file est sur disque : elle survit à un redémarrage du service et vaut entre plusieurs processus. Aucun fil ne
  tourne en permanence : un fil `daemon` n'existe que le temps d'une lecture, et il ne bloque jamais l'arrêt du service.
- **Échec non définitif** : un plantage, un délai dépassé, un JSON invalide ou une lecture abandonnée (verrou plus
  vieux que le délai maximal, processus mort) écrit un marqueur `.echec` qui contient la raison, l'heure et le nombre
  d'essais, **sans aucun texte du document**. Tant que le délai n'est pas passé (`DS3_OCR_RETRY_DELAY_S`, 600 s par
  défaut), `lookup_or_start` renvoie `echec`. Ensuite, un nouvel essai est lancé, au plus `DS3_OCR_MAX_ATTEMPTS`
  essais en tout (3 par défaut, premier essai compris) ; au-delà, l'échec est définitif. Le compteur et l'heure sont
  lus dans le marqueur : ils valent aussi après un redémarrage. Un marqueur illisible rend l'échec définitif (pas de
  relance en boucle). Un fichier modifié a une autre empreinte : il repart de zéro.
- **Demande en attente devenue sans objet** : si le fichier a été supprimé ou modifié pendant l'attente, la demande
  est retirée de la file sans OCR et sans marqueur.
- **Confidentialité et accès** (comme le stockage, D40) : `card_id` et `document_id` sont de simples noms, le chemin
  résolu reste dans `DS3_CACHE_DIR`, et une carte ne lit jamais le cache d'une autre. Le texte du document n'est
  jamais journalisé ; le JSON temporaire (`.part`) écrit par le processus OCR est supprimé dans tous les cas,
  y compris celui laissé par un processus mort.

**Limites connues** :
- **File bloquée environ 16 min si une lecture active meurt** : quand le processus de la lecture active meurt
  (redémarrage, plantage), son verrou n'est déclaré abandonné qu'après `lock_max_age_s` (délai de l'OCR + 60 s, soit
  environ 16 min par défaut). Jusqu'à cet abandon, la file est arrêtée : aucune autre lecture ne démarre, et les
  questions sur les documents en attente reçoivent `en_cours`. Ensuite, la lecture morte compte pour un essai et la
  file repart.
- Un processus OCR orphelin peut continuer de tourner après l'arrêt du service ; son `.part` est supprimé quand la
  lecture est déclarée abandonnée.
- La file est parcourue à chaque question qui n'a pas encore de résultat : à surveiller si le cache dépasse quelques
  milliers de documents.

**Alternatives envisagées** :
- File en mémoire avec un fil de travail permanent → rejeté : la file serait perdue au redémarrage (les documents
  en attente garderaient un verrou orphelin), elle ne vaudrait pas entre plusieurs processus du service, et un fil
  permanent peut retarder l'arrêt.
- Un OCR par document, en parallèle → rejeté : chaque OCR prend tout le CPU ; plusieurs à la fois ralentissent tout
  le monde et peuvent faire dépasser le délai maximal à toutes les lectures.
- Échec définitif tant que le fichier ne change pas (PR #46) → rejeté : une panne passagère (machine chargée, délai
  dépassé une fois) bloquait le document pour toujours.
- Relance immédiate après un échec → rejeté : un document qui fait planter Paddle relancerait l'OCR en boucle.

**Raison** : le service ne fait jamais tourner Paddle dans son propre processus, n'attend pas l'OCR pendant une
question (cible de 20 s, P95), ne charge jamais le CPU avec plusieurs OCR à la fois, se remet d'une panne
passagère sans intervention, et ne relance pas en boucle un document qui échoue toujours.

**Statut** : 🟡 proposée (PR `DS3_ocr_d42_cache`) ; prouvée par `test_document_intelligence_ocr_cache.py`, sur
données fictives et avec une horloge simulée (succès mis en cache, échecs sans texte et `.part` supprimé, nouvel
essai après le délai et au plus N essais, compteur et délai gardés après un redémarrage, essai en cours `en_cours`,
verrou abandonné compté comme un essai, ancien marqueur sans compteur, marqueur illisible, un seul OCR à la fois et
ordre de la file, échec qui ne bloque pas la file, file gardée après un redémarrage, demande en attente qui
n'expire pas, fichier modifié ou supprimé pendant l'attente, verrou global abandonné, vrais fils sans deux OCR à la
fois, fil `daemon`, contrôles d'accès, chemins courts sous Windows). Reste à faire : brancher ce backend dans le
pipeline (réponse `erreur` `TIMEOUT` réessayable pendant la lecture, section 7.1 de
`docs/PROPOSITION_INTEGRATION_OCR.md`), puis le déclenchement au téléversement (`prepare_document`) après accord de
DS1. Remplace, dans la section 7.1 de la proposition, la ligne « Un nouvel essai a lieu seulement si le fichier
change ».

---
