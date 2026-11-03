# Carnet de bord — Mon Compte (dépôt « Suivi »)

Journal des opérations réalisées sur le projet, à relire pour savoir où il en est.
Les entrées les plus récentes sont en haut. À chaque intervention, ajouter une entrée datée.

## État actuel (2026-11-03)

- App PWA 100 % locale (un seul fichier `index.html`), publiée sur GitHub Pages, utilisée sur iPhone.
- Plan en 3 étapes entièrement présent dans le code : comptes multiples + virements, paiements en plusieurs fois, emprunts / livrets / cartes.
- Service worker en version `compte-v17`.
- Reste à faire : tester l'import CSV avec l'export réel de la banque (point en attente depuis la première version).
- Aucune donnée réelle n'est stockée dans le dépôt.

## 2026-11-03 — Reprise du projet

- Dépôt cloné et code relu.
- Constat : ni carnet de bord ni description de l'architecture dans le dépôt.
- Ajout de `JOURNAL.md` (ce fichier) et `ARCHITECTURE.md`.
- README complété avec des liens vers ces deux fichiers.
- Aucun changement dans le code de l'app ni dans le service worker.

## 2026-11-02 — Licence

- Ajout de la mention « Tous droits réservés » : fichier `LICENSE` et section Licence du README (commit `007ff43`).

## Avant le 2026-11-02 — Historique reconstitué

Cette partie est reconstituée à partir des échanges de travail antérieurs ; les dates exactes n'ont pas été conservées et l'historique git local n'a pas été relu en détail.

- Choix d'une PWA gratuite et locale (plutôt qu'une app SwiftUI) pour un suivi de budget type Money Coach sur iPhone.
- Dépôt public `Suivi` créé, nom volontairement neutre.
- Première version livrée : suivi du compte salaire ligne par ligne, récurrences, catégories (Revenus, Logement, Voiture, Alimentation, Santé, Loisirs, Finances, Divers, avec sous-catégories), import CSV.
- Restaurants / bars classés en Loisirs et non en Alimentation (choix volontaire).
- Étape 1 du plan : comptes multiples (carte, PayPal, livrets, emprunts), virements entre comptes, vue consolidée avec cases à cocher par compte pour les rapprochements.
- Étape 2 : paiements en plusieurs fois (mensuels, sans frais, dernière échéance modifiable).
- Étape 3 : emprunts et livrets (remboursement lié à un emprunt, option d'exclure du reste à vivre).
- Ajouts demandés : champ « tiers » (commerçant) par ligne, modification de plusieurs lignes à la fois, changement du montant d'une récurrence à partir d'une date.
- Sauvegarde / restauration en JSON (export via le partage iOS).
