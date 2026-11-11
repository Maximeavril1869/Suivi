# Carnet de bord — Mon Compte (dépôt « Suivi »)

Journal des opérations réalisées sur le projet, à relire pour savoir où il en est.
Les entrées les plus récentes sont en haut. À chaque intervention, ajouter une entrée datée.

## État actuel (2026-11-11)

- App PWA locale d'abord (un seul fichier `index.html`), publiée sur GitHub Pages, utilisée sur iPhone. **Synchronisation chiffrée** ajoutée le 2026-11-11 (à valider sur iPhone et iPad). Service worker en version `compte-v18`.
- Plan en 3 étapes entièrement présent dans le code : comptes multiples + virements, paiements en plusieurs fois, emprunts / livrets / cartes.
- Reste à faire : tester l'import CSV avec l'export réel de la banque (point en attente depuis la première version) ; valider la synchronisation sur appareil.
- Aucune donnée réelle n'est stockée dans le dépôt.

## État au 2026-11-03 (avant la synchronisation)

- App PWA 100 % locale (un seul fichier `index.html`), publiée sur GitHub Pages, utilisée sur iPhone.
- Plan en 3 étapes entièrement présent dans le code : comptes multiples + virements, paiements en plusieurs fois, emprunts / livrets / cartes.
- Service worker en version `compte-v17`.
- Reste à faire : tester l'import CSV avec l'export réel de la banque (point en attente depuis la première version).
- Aucune donnée réelle n'est stockée dans le dépôt.

## 2026-11-11 — Synchronisation chiffrée entre appareils

- Demande : retrouver les mêmes comptes sur iPhone et iPad, comme pour Plan du jour. Décisions de l'utilisateur : même projet Supabase et même compte que Plan du jour, **chiffrement oui**, le Honor ne servira que pour les jeux, données de test à vider avant usage réel, volume inconnu (l'app est donc découpée par mois).
- Fait : section « synchronisation chiffrée » dans `index.html` (connexion, phrase secrète, AES-GCM, découpage `meta` / `tx:AAAA-MM`, envoi 1,5 s après un enregistrement, relève toutes les 5 s, conflits, suppressions) ; carte Réglages › Synchronisation ; `save()` déclenche l'envoi. Service worker : requêtes vers d'autres adresses ignorées, version `compte-v18`.
- Le même projet Supabase et la même table que Plan du jour : rien à créer côté Supabase (colonne `app = 'suivi'`).
- Tests : `tests/test_sync.py` (57 vérifications, faux serveur sans déchiffrement : rien de lisible reçu, échange de lignes refusé, deux appareils, hors ligne, jeton expiré, saisie en cours, déconnexion).
- Non testé en conditions réelles : le vrai service Supabase (non joignable depuis l'espace de travail de Claude). À valider sur appareil : connexion et création de la phrase sur l'iPhone, saisie de la phrase sur l'iPad, ligne ajoutée d'un côté qui apparaît de l'autre.
- Points de vigilance : la phrase secrète n'est récupérable nulle part ; le palier gratuit Supabase n'a pas de sauvegardes automatiques (garder l'export JSON) ; projet gratuit mis en pause après une semaine d'inactivité.

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
