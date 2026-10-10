# Vérification manuelle du corpus juridique — DS2

- **Auteur** : Abd Mouhib Souri (DS2 — Legal Knowledge & Retrieval)
- **Date** : 2026-10-10
- **Périmètre** : les 9 sources de `data/raw/` (7 conventions sectorielles, convention cadre, grille SMIG)
- **Statut** : vérification visuelle terminée pour 7 conventions sur 7 ; SMIG en cours

---

## 1. Pourquoi cette vérification

L'ingestion du Sprint 1 a découpé **492 articles**, mais le rapport automatique signalait
**37 numéros d'articles manquants** répartis sur 7 fichiers. Avant d'indexer le corpus,
il fallait savoir pour chaque trou s'il s'agissait :

- d'une **erreur du code** (en-tête non reconnu) ;
- d'une **erreur de l'OCR** (texte mal lu) ;
- ou d'une **réalité juridique** (article abrogé, absent du texte officiel).

Règle appliquée : *« Citation ou Silence »* — on ne corrige rien sans avoir vu la source.

## 2. Méthode

1. Rapport automatique `ingestion_report.json` → liste des numéros manquants par fichier.
2. Outil `tools/inspect_headers.py` → recherche de chaque numéro dans le texte OCR, avec sa position.
3. **Vérification visuelle dans le PDF original** pour chaque trou (captures d'écran de l'en-tête).
4. Classement de chaque trou dans une cause unique.

> La recherche `Ctrl+F` ne fonctionne pas dans ces PDF : leur texte arabe est stocké en
> glyphes Unicode « Private Use » (`U+F2xx`, constat D5 de DS5, complété par D16). La vérification est donc visuelle.

## 3. Résultats par fichier

| Fichier | Articles manquants (rapport) | Constat dans le PDF | Cause |
|---|---|---|---|
| Construction métallique | 38-41 | `الفصول 38-39-40-41: (ألغيت بمقتضى الملحق التعديلي عدد 5)` | abrogés |
| | 46-52 | en-têtes normaux (`الفصل 46:`, `الفصل 47 (جديد):` …) | OCR (zone de texte inversé, `reversed=0.19`) — à confirmer |
| BTP | 2 | `الفصل2: المدة، المراجعة والتراجع` | en-tête sans espace |
| | 38-41 | `الفصول 38 – 39 – 40 – 41 : (ألغيت … عدد 5)` | abrogés |
| | 51 | `الفصل 51 (جديد): منح القفة …` collé en milieu de ligne | en-tête en milieu de ligne |
| Assurance | 6-10 (+ 10 مكرر) | `الفصول 6 و7 و8 و9 و10 و10 مكرر: (ألغيت … عدد 4)` | abrogés |
| | 40 | `الفصل 40 :` présent dans le PDF, introuvable dans l'OCR | numéro mal lu par l'OCR |
| Enseignement privé | 38-41 | `الفصول 38-39-40-41 : (ألغيت … عدد 4)` | abrogés |
| | 52-53 | `الفصلان 52 و53 : (ألغيا … عدد 6)` | abrogés (forme du **duel**) |
| | 56, 58 | `الفصل56:` · `الفصل58:` | en-têtes sans espace |
| Gardiennage | 31-33 | `الفصول 31-32-33 (ألغيت … عدد 2)` — **sans « : »** | abrogés |
| Convention cadre | 5 | `الفصل5 (جديد): الحق النقابي وحرية الرأي` | en-tête sans espace |
| | 40 | **absent du PDF** | absent de la source |
| Associations | 20 | **absent du PDF** | absent de la source |
| Banques | — | aucun trou | — |
| SMIG | — | aucun trou ; `dup=6` | vérification en cours (plusieurs décrets ?) |

## 4. Synthèse par cause

| Cause | Articles | Part | Responsable de la correction |
|---|---|---|---|
| **Abrogés par un avenant** | 22 | 59 % | DS2 — créer des entrées `abroge` |
| **En-tête sans espace** (`الفصل56`) | 4 | 11 % | DS2 — regex |
| **OCR / en-tête en milieu de ligne** | 9 | 24 % | DS2 — regex + inspection |
| **Absents du PDF source** | 2 | 5 % | Tradrly — PDF complet ? |
| **Total** | **37 / 37 expliqués** | 100 % | |

**Aucun trou n'est une perte de texte non expliquée.**

## 5. Analyse (avis DS2)

### 5.1 Le corpus est de bonne qualité — le code était trop strict
Les trous ne venaient pas d'un corpus abîmé : 35 sur 37 sont soit des articles abrogés
(information juridique valide), soit des variantes d'écriture que le découpage ne
reconnaissait pas. Une fois les règles de la section 6 codées, on attend **0 trou non
expliqué** sur les 7 conventions.

### 5.2 Les abrogations sont une information, pas un manque
59 % des « trous » (22 sur 37) sont des articles abrogés. Le système doit pouvoir répondre :
*« L'article 39 de la convention Construction métallique a été abrogé par l'avenant n° 5 »*,
au lieu de *« article introuvable »*. C'est exactement ce que mesure la métrique
**précision temporelle (≥ 90 %)**.

### 5.3 Les textes sont des versions consolidées
La mention **« (جديد) »** est très fréquente : les PDF intègrent les modifications des
avenants successifs. Conséquence : on dispose de la **version actuelle**, mais **pas du
texte des anciennes versions**. Pour toute question portant sur une date antérieure à
l'avenant, le système doit **s'abstenir** (*« version antérieure non disponible »*) plutôt
que de renvoyer la version actuelle — sinon, hallucination temporelle.
*(À confirmer : vérifier qu'un article (جديد) n'apparaît qu'une fois dans son PDF.)*

### 5.4 Chaque convention a sa propre numérotation d'avenants
Au moins 6 avenants distincts sont cités (n° 2, 4, 5, 6 selon les conventions). Un avenant
doit donc être identifié par sa convention : `CCS-BTP-AVENANT-5` ≠ `CCS-CONSTRUCTION-METALLIQUE-AVENANT-5`.
**Sans leurs dates, le filtre temporel ne peut pas fonctionner.**

### 5.5 Risque identifié : deux absences dans les sources
Cadre art. 40 et Associations art. 20 n'existent pas dans les PDF fournis. Soit une page
manque, soit le texte d'origine saute un numéro. Tant que ce n'est pas tranché, le système
doit répondre *« article absent du document source fourni »*.

## 6. Règles de découpage à coder (Sprint 2)

| # | Forme réelle | Règle |
|---|---|---|
| R1 | `الفصل56:` | espace optionnel entre « الفصل » et le numéro |
| R2 | `الفصول 38-39-40-41 : (ألغيت بمقتضى الملحق التعديلي عدد 5)` | liste abrogée : `الفصل`/`الفصلان`/`الفصول` + numéros séparés par `-` `–` `و` + « : » **optionnel** + `ألغي`/`ألغيا`/`ألغيت` + numéro d'avenant |
| R3 | `… و10 مكرر` | « مكرر » accepté dans une liste abrogée |
| R4 | `… الفصل 51 (جديد): …` | en-tête accepté en milieu de ligne **seulement** s'il est suivi de « : » |
| R5 | `بالفصل 51 فقرة` · `من الفصل 7` · `الفصل 12 من هذه` | renvoi : ne jamais couper |
| R6 | `الفصل 47 (جديد)` | version actuelle, `modified: true` ; **toutes les versions sont renvoyées et annoncées** (D17) ; si l'ancien texte manque : `previous_version_available: false`, annoncé à l'utilisateur |
| R7 | avenant n° N | identifiant d'avenant préfixé par la convention |
| R8 | trous vérifiés à la main | `manual_checks.json` : verdict, auteur, date — exclus des alertes du rapport |

Chaque règle sera couverte par un test construit à partir de la forme réelle trouvée.

## 7. Plan d'action

### Immédiat (DS2)
- [ ] Commit du Sprint 1 (ingestion hybride, contrat v0, diagnostics) + ce rapport
- [ ] Inspecter la structure du JSON OCR (`sections` / `structure`) → corriger le chargeur
- [ ] Inspecter Construction 46-52 et Assurance 40 → confirmer la cause OCR
- [ ] Coder R1-R8 avec leurs tests, relancer l'ingestion, viser 0 trou non expliqué

### À remonter à l'équipe
| À qui | Sujet |
|---|---|
| **Salah Sammari (Tradrly)** | PDF complets ? (Cadre art. 40, Associations art. 20) · liste des avenants de chaque convention **avec leurs dates** · le Code du travail est absent du corpus |
| **Oumaima (DS5)** | ses décisions D4/D5 et ce rapport se recoupent (articles 50/51 de la métallurgie bâtiment déjà exploités en D4) · le fichier SMIG contient plusieurs décrets (769/2022, 768/2022, 35/2015, 2906/2014, texte 2019 p.5 — cf. D3/D6) : DS2 doit les identifier séparément pour éviter les « doublons » d'articles · double contrôle DS2 des montants D2/D3 |
| **Hadil & Wiem (DS3)** | les PDF utilisateurs auront probablement le même problème de glyphes `U+F2xx` : la couche texte ne suffira pas, prévoir l'OCR |
| **Achref (DS1)** | le contrat de réponse doit pouvoir exprimer `abroge` et « version antérieure non disponible » |

### En cours (vérification manuelle)
- [ ] SMIG : rattacher chaque article à son décret (769/2022, 768/2022, 35/2015, 2906/2014, texte 2019 — déjà identifiés par DS5 en D3/D6) ; double contrôle des montants D2/D3
- [ ] Cadre 39 → 41 et Associations 19 → 21 : saut de page ?
- [ ] Un article « (جديد) » apparaît-il une seule fois dans son PDF ?
