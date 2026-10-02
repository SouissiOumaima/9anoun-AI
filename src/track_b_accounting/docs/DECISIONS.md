# DECISIONS.md — Journal des décisions techniques

Format par entrée : **Décision** · **Alternatives envisagées** · **Raison**

---

## 2026 — DS5 (Track B, Oumaima Souissi)

### D1 — Abandon de la réparation section par section du JSON OCR

**Décision** : au lieu de corriger les 56 sections signalées par
`audit_ocr_quality.py` une par une dans les fichiers JSON existants, on
construit directement des fichiers **propres et structurés**
(`data/processed/smig_smag/`, `data/processed/salary_grids/`) en lisant
les PDF originaux, qui contiennent une vraie couche de texte exploitable
(ce ne sont pas des scans photo, mais des exports Word → PDF).

**Alternatives envisagées** :
- Corriger le texte OCR directement dans les fichiers `data/raw/txt/*.json`
  → rejeté : demande de re-parser du texte déjà cassé, risque de
  réintroduire des erreurs, et certaines sections contiennent des valeurs
  totalement incohérentes avec le PDF (pas juste un caractère mal lu).

**Raison** : les PDF sources permettent une extraction fiable à 100% via
`pymupdf`/`fitz` (texte natif, pas d'OCR nécessaire), donc repartir du
PDF est plus sûr et plus rapide que de déboguer l'OCR existant.

**Source des données** : uniquement `data.zip` fourni par Tradrly
(PDF + JSON). Aucune source externe consultée, conformément à la
consigne de l'équipe de travailler exclusivement sur les données
partagées.

---

### D2 — Correction confirmée : SMIG régime 40h/48h (décret n°769/2022)

**Fichier concerné** : `data/raw/txt/الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.json`, section 2

**Source de vérification** : `data/raw/pdf/الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.pdf`,
page 2 (décret gouvernemental n°769 du 19 octobre 2022), lue directement
en image (200 dpi, via `pymupdf`) pour éviter toute ambiguïté d'ordre de
lecture RTL dans le texte extrait.

**Problème identifié** : l'OCR n'a pas juste mal reconnu un caractère —
il a produit des valeurs entièrement incohérentes avec le document
source pour cette section.

| Catégorie | Régime | Valeur OCR (JSON, erronée) | Valeur réelle (PDF, confirmée) |
|---|---|---|---|
| Salariés payés au mois | 48h/semaine | incohérente | **459.264 DT** |
| Salariés payés au mois | 40h/semaine | incohérente | **390.692 DT** |
| Salariés payés à l'heure | 48h/semaine | incohérente | **2.208 DT** |
| Salariés payés à l'heure | 40h/semaine | incohérente | **2.254 DT** |

**Entrée en vigueur** : 1er octobre 2022 (texte daté du 19/10/2022,
Fasl 6 du décret précise l'effet au 1er du mois).

**Statut** : ✅ confirmé visuellement sur le PDF par Oumaima Souissi (DS5),
via inspection directe de l'image de la page — pas de source externe.

---

*Prochaine entrée : D3 — à ajouter après la construction du fichier
`smig_smag.json` complet (tous les textes SMIG/SMAG du corpus).*

---

### D3 — Construction de `smig_smag.json`

**Fichier créé** : `data/processed/smig_smag/smig_smag.json`

**Contenu** : 3 blocs reconstruits depuis le PDF source (pages 2 à 4) :
- `smig_non_agricole` (décret n°769/2022, effet 01/10/2022) — 4 valeurs
  (mensuel/horaire × régime 48h/40h)
- `smag_agricole` (décret n°768/2022, effet 01/10/2022) — SMAG journalier
  + primes technique/compétence
- `prime_transport` (décret n°35/2015, effet 01/05/2015, qui remplace le
  décret n°2906/2014) — montant mensuel fixe

**Statut** : ✅ toutes les valeurs confirmées visuellement sur les PDF
correspondants par Oumaima Souissi (DS5).

**Prochaine étape** : D4 sera ouverte après le traitement des grilles
salariales des conventions collectives sectorielles (étape 3 du plan DS5).

### D4 — Grille salariale METALLURGIE_BATIMENT (pages 16, 30-35)

**Fichier créé** : data/processed/salary_grids/metallurgie_batiment.json Source : الاتفاقية المشتركة القطاعية للبناء المعدني.pdf — p.30-35 (6 tableaux), p.16 (primes, art. 50/51 nouveaux)

Constat qui corrige D1 : les pages 30-35 sont des images sans couche texte (scan), pas du texte natif. pymupdf.get_text() y retourne 0 caractère → l'extraction « 100 % fiable » de D1 ne s'applique pas à ces pages. Seule la p.16 a une couche texte (utilisée comme contrôle croisé des primes).

**Méthode** : lecture visuelle des tableaux, saisie en code, contrôles automatiques (tests/test_grid_bm.py, 16 tests) : croissance par ancienneté, croissance par catégorie, ratio inter-années stable (~+6,6 %), cohérence des primes.

**Contenu**: 3 dates d'effet (01/12/2021, 01/01/2023, 01/01/2024) × 2 populations (admin/techniciens : 19 catégories, TND/mois ; exécution : 7 catégories, TND/heure) × 11 degrés d'ancienneté, régime 42 h. Primes : transport, présence, logement, panier (قفة), déplacement chantier, travail en hauteur.

**Statut** : ⏳ à confirmer par DS5 sur le PDF (échantillon recommandé : 2 lignes par page, + cellules 1B et 18).