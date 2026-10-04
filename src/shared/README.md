# `src/shared/` — conventions communes aux 5 rôles

Ce dossier n'appartient à aucun rôle en particulier. Il contient seulement
ce que les rôles doivent avoir en commun pour échanger des messages sans
dépendre du code des autres.

| Dossier | Contenu |
|---|---|
| [`schemas/`](schemas/README.md) | Convention de nommage et de versionnement des JSON Schema échangés entre rôles. |

Règles :
- **Pas de code métier ici.** La logique de chaque rôle reste dans son dossier.
- Toute modification de ce dossier passe par une pull request relue par les
  rôles concernés, puisqu'elle les engage tous.
