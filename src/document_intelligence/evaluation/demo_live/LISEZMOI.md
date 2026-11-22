# Démonstration DS3 live : stockage de test pour l'intégration DS1 → DS3 live → DS5

Documents **fictifs** uniquement. Aucun document réel n'est envoyé à Gemini (règle NDA).

Les identifiants sont **ceux de DS1** (`data/mock_cards/orchestrator_cards_demo.json`) : carte `company-demo-001`.
DS1 n'accepte que la référence exacte de sa propre carte, donc DS1 et ce stockage doivent rester identiques.

## Contenu

| storage_ref | Fichier (`file_name` à déclarer côté DS1) | Ce que DS3 renvoie |
|---|---|---|
| `tradrly://cards/company-demo-001/documents/doc-company-payslip-01` | `ds3_stockage/cards/company-demo-001/documents/doc-company-payslip-01/paie_fictive_01_fr.pdf` | Cas normal (grille METALLURGIE_BATIMENT / admin_tech, catégorie 3) : base 641.013, brut 733.013, CNSS 67.291, tous lus et cités ; régime imprimé « 42 h/semaine » renvoyé à `null` (`valeur_incoherente`, ni 40 ni 48), donc `complete = false` et aucun parcours SMIG. |
| `tradrly://cards/company-demo-001/documents/doc-company-payslip-02` | `ds3_stockage/cards/company-demo-001/documents/doc-company-payslip-02/paie_fictive_04_pieges.pdf` | Cas avec pièges : date d'entrée « 01/09/19 », « CDD » et « 195 h » reviennent à `null` avec leur raison. Sert à tester l'étape de confirmation. |

Pour le live, la carte DS1 doit déclarer, pour chaque document : `file_name` exactement comme ci-dessus et
`mime_type` = `application/pdf`. DS3 cherche `<dossier du document>/<file_name>`. Un fichier image (`.jpg`) est
refusé en live (`HORS_SCOPE` : seuls les PDF le sont pour l'instant). `doc-company-payslip-02` n'existe pas
encore dans la carte DS1 : à ajouter si on veut tester le cas avec pièges.

Requêtes prêtes : `requete_doc-company-payslip-01.json`, `requete_doc-company-payslip-02.json`. Avec une autre
carte active, DS3 répond `ACCES_REFUSE` sans lire le fichier (voulu).

`requete_fiche_01.json` (en `local://`) est l'ancienne démo : elle sert seulement à tester DS3 seul, pas DS1.

## Variables d'environnement

```powershell
$env:DS3_HANDLER_MODE = "live"
$env:DS3_STORAGE_ROOT = "<racine du dépôt>\src\document_intelligence\evaluation\demo_live\ds3_stockage"
# GEMINI_API_KEY : dans le .env de chacun (clé donnée par l'encadrant), jamais dans le code ni dans un message.
```

## Vérifier DS3 seul (depuis la racine du dépôt)

```powershell
python -m src.document_intelligence.service src\document_intelligence\evaluation\demo_live\requete_doc-company-payslip-01.json --root src\document_intelligence\evaluation\demo_live\ds3_stockage
```

Résultat attendu : `"status": "ok"`, `"mode": "live"`, et les valeurs du tableau.
Sans `DS3_STORAGE_ROOT` ni `--root` : `"status": "erreur"`, `INTERNAL_ERROR` (jamais d'exception).
Clé Gemini absente ou refusée : `"status": "erreur"`, réessayable.

Le test `test_document_intelligence_demo_storage.py` vérifie ces requêtes à chaque `pytest`, avec un faux Gemini.
