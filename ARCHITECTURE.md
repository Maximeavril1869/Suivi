# Architecture — Mon Compte

Application de suivi de budget **locale d'abord** : une PWA sans framework et sans dépendance. Tout le code applicatif tient dans `index.html` (HTML + CSS + JavaScript). Les données restent dans le `localStorage` de l'appareil ; depuis la synchronisation (voir plus bas), une copie **chiffrée** peut être envoyée à un compte personnel pour retrouver les mêmes comptes sur plusieurs appareils.

## Fichiers du dépôt

| Fichier | Rôle |
|---|---|
| `index.html` | Toute l'application : styles, structure, logique, rendu |
| `manifest.json` | Déclaration PWA (nom « Mon Compte », affichage plein écran, couleur `#0f766e`, icônes) |
| `sw.js` | Service worker : réseau d'abord, cache en secours pour le hors ligne |
| `icon-180.png`, `icon-512.png` | Icônes de l'app (iPhone et maskable) |
| `LICENSE`, `README.md` | Mention « Tous droits réservés » |
| `tests/test_sync.py` | Tests de la synchronisation (faux serveur, deux appareils simulés) ; voir `tests/README.md` |
| `tests/test_rappel_et_hors_ligne.py` | Tests du rappel de sauvegarde partagé et de la bannière « Hors ligne » |
| `JOURNAL.md` | Carnet de bord du projet |
| `ARCHITECTURE.md` | Ce document |

## Vue d'ensemble

```mermaid
flowchart TD
    U[Utilisateur sur iPhone] --> UI[index.html : 5 vues + modales]
    UI -->|act : actions du clavier et des boutons| S[(Etat S en mémoire)]
    S -->|save| LS[(localStorage<br/>clé compte-salaire-v1)]
    LS -->|load + migrate| S
    S -->|render| UI
    CSV[Fichier CSV de la banque] -->|impParse + règles| S
    S <-->|exportJSON / doImport| JSON[Sauvegarde JSON]
    SW[sw.js] -->|cache hors ligne| UI
```

Principe : une seule variable d'état `S`, modifiée par les actions, enregistrée par `save()`, puis l'écran est entièrement reconstruit par `render()` (pas de rendu partiel, sauf `refreshList` pour la liste des lignes).

## Stockage et données

- Stockage : `localStorage`, clé `compte-salaire-v1`. Sans connexion à un compte, rien n'est envoyé sur le réseau.
- Sauvegarde manuelle : export JSON (feuille de partage iOS) et restauration depuis un fichier. **Rappel de sauvegarde** (depuis `compte-v20`, sur toutes les vues depuis `compte-v21`) : même logique que Plan du jour, voir « Rappel de sauvegarde » plus bas.
- `migrate()` met à niveau les anciennes données à chaque chargement (version de schéma `v:2`).

Contenu de l'état `S` :

| Champ | Contenu |
|---|---|
| `accounts` | Comptes : nom, type (`courant`, `livret`, `credit`, `differe`, `emprunt`), solde repère (`anchor`), inclusion dans le reste à vivre (`cash`), plafond, compte et jour de débit pour le différé |
| `shown` | Comptes cochés dans la vue consolidée |
| `tx` | Lignes réelles : date, libellé, montant, catégorie, sous-catégorie, tiers, compte, lien de virement, clé de récurrence |
| `rec` | Récurrences : fréquence, jour, début/fin, montant (avec changements datés), compte, mot-clé CSV |
| `plans` | Paiements en plusieurs fois : liste d'échéances mensuelles |
| `rules` | Règles de classement automatique (mot-clé vers catégorie) |
| `budgets` | Budgets par catégorie ou sous-catégorie |
| `csvMaps` | Correspondance de colonnes mémorisée par format de CSV |
| `skips` | Échéances ignorées |
| `lastExport` | Date de la dernière sauvegarde |
| `bk` | État du rappel de sauvegarde : `since` (date de la première modification non sauvegardée), `snooze` (rappel reporté jusqu'à), `every` (délai en jours : 0, 3, 7, 14 ou 30 ; 7 par défaut) |

Catégories (constante `CATS`) : Revenus, Logement, Voiture, Alimentation, Santé, Loisirs, Finances, Divers, chacune avec ses sous-catégories. Les restaurants et bars sont volontairement dans Loisirs.

## Interface

Navigation en bas, 5 vues (objet `VIEWS`) :

| Vue | Fonction | Contenu |
|---|---|---|
| Accueil | `homeHTML` | Solde, graphique, répartition, bloc « Sortir du découvert », échéances à valider (le rappel de sauvegarde est en tête de toutes les vues) |
| Lignes | `linesHTML` | Liste filtrable, sélection multiple et modification groupée |
| Récurrent | `recHTML` | Échéances à valider, récurrences, paiements en plusieurs fois |
| Import | `impHTML` | Import CSV avec choix des colonnes |
| Réglages | `setHTML` | Comptes, budgets, règles, sauvegarde et restauration |

Les formulaires sont des modales (`openTx`, `openAcc`, `openRec`, `openPlan`, `openXfer`, `openBulk`), enregistrées par les fonctions `save…`. Un seul gestionnaire d'événements, `act()`, répartit les actions via les attributs `data-a`.

## Logique métier

| Domaine | Fonctions clés |
|---|---|
| Soldes | `balanceAt`, `accBalance`, `adjRows` (ligne « Ajustement de solde » recalculée pour que le solde repère reste juste), `withBalance` |
| Virements et emprunts | `createTransfer`, `linkTransfer`, `unlinkTransfer`, `xferOther` : deux lignes liées, montant et date répercutés |
| Récurrences | `occ` (dates d'une récurrence dans un mois), `amountAt` (montant à une date), `dueItems` / `dueRange` (échéances non encore validées ni ignorées), `changeAmount` (nouveau montant à partir d'une date) |
| Paiements en plusieurs fois | `makePlanItems`, `planStats`, `planKeys` |
| Débit différé | `debitDates`, `creditInfo` (cartes et crédits) |
| Classement | `autoCat`, `kwFrom`, `linkRec` (rapprochement d'une ligne avec une récurrence) |
| Import CSV | `parseCSV`, `parseAmount`, `parseDate`, `guessCol`, `impParse`, `doImport`, `onFile` |
| Période | `range`, `setAnchor`, `shiftPeriod`, `periodLabel` (jour, semaine, mois, année) |

Cycle d'une échéance : la récurrence génère une échéance « à valider » ; **Valider** ouvre une ligne pré-remplie que l'on confirme, **Ignorer** l'ajoute à `skips`. Dans les deux cas elle disparaît de la liste (clé `recKey` ou `skips`).

## Mise à jour et déploiement

- Hébergement : GitHub Pages à partir du dépôt (branche par défaut `main`).
- Le service worker (`sw.js`) a une version de cache (constante `V`, actuellement `compte-v21`). **À chaque modification publiée, incrémenter cette version** pour que l'iPhone récupère la nouvelle app, **et la constante `APP_VERSION` de `index.html`** (même numéro : `21` pour `compte-v21`), affichée en bas de Réglages (« Mon Compte · version 21 ») pour vérifier quelle version tourne sur l'appareil.
- Aucune étape de build : modifier `index.html`, commiter, pousser.

## Synchronisation chiffrée

**Principe.** Local d'abord : le `localStorage` reste la référence et l'app marche hors ligne. Connecté (Réglages › Synchronisation), l'app envoie une copie **chiffrée dans le navigateur** vers Supabase (projet `plan-du-jour`, table `donnees`, colonne `app = 'suivi'`) et relit les changements toutes les 5 secondes. Aucune bibliothèque : `fetch` et WebCrypto.

```mermaid
flowchart LR
  A[Appareil A<br/>localStorage] -->|chiffre AES-GCM<br/>puis envoie| T[(table donnees<br/>valeurs illisibles)]
  T -->|relève toutes les 5 s| B[Appareil B<br/>déchiffre et applique]
  B -->|chiffre et envoie| T
  P[Phrase secrète<br/>jamais envoyée] -.dérive la clé PBKDF2.-> A
  P -.-> B
```

| Élément | Détail |
|---|---|
| Compte | Même utilisateur Supabase que Plan du jour (un seul projet pour les apps perso), inscriptions fermées. Mot de passe du compte ≠ phrase secrète |
| Découpage | `meta` (comptes, récurrences, plans, règles, budgets, correspondances CSV, échéances ignorées) et `tx:AAAA-MM` (les lignes d'un mois) : seul ce qui change est envoyé ou relu |
| Local à l'appareil | `shown` (comptes cochés) n'est pas synchronisé. `lastExport` (date de la dernière sauvegarde) et `bk` (état et délai du rappel) le sont : une sauvegarde faite sur un appareil vaut pour tous, le rappel disparaît partout |
| Chiffrement | AES-GCM 256, clé dérivée de la phrase par PBKDF2-SHA-256 (600 000 itérations, sel public dans la ligne `sel`). Le nom de la ligne est authentifié : le serveur ne peut pas échanger deux lignes. Ligne `verif` : témoin qui valide la phrase |
| Clé sur l'appareil | La clé dérivée est gardée dans le `localStorage` (`compte-sync-cle`) pour ne demander la phrase qu'une fois ; les données y sont déjà en clair, donc aucun risque de plus. Se déconnecter l'efface |
| Ce que voit le serveur | L'e-mail du compte, les noms de ligne (`tx:AAAA-MM` : quels mois ont de l'activité), la taille et la date des envois. Aucun libellé, montant, nom de compte |
| Conflits | Jamais de modification simultanée voulue : la version de l'appareil est envoyée ; ce qui est écrasé est gardé dans `compte-sync-conflits` (5 copies). Première synchro d'un appareil : le serveur l'emporte, la version locale est gardée |
| Suppression | Un mois vidé ici l'est partout. « Restaurer » et « Tout effacer » s'appliquent aussi aux autres appareils connectés |
| Saisie en cours | Rien n'est appliqué tant qu'une fenêtre de saisie est ouverte ; l'écran se rafraîchit quand aucun champ n'est actif |
| Perte de la phrase | Les données en ligne sont irrécupérables ; celles de l'appareil et l'export JSON restent valables |
| Sauvegarde | La synchronisation n'est **pas** une sauvegarde (le palier gratuit n'a pas de sauvegardes automatiques) : l'export JSON reste indispensable |

## Rappel de sauvegarde

Décidé le 2026-11-12 : même comportement que Plan du jour. L'état `S.bk` fait partie des données (donc exporté, et synchronisé avec la ligne `meta`).

- `save()` date la première modification non sauvegardée (`bk.since`). `save(true)` (mode « silencieux ») ne la date pas : utilisé pour cocher un compte, régler le délai, reporter le rappel, exporter et restaurer.
- Un export (`bkSaved`) remet `since` et `snooze` à zéro et date `lastExport`. Une restauration depuis un fichier remet aussi `since` à zéro (l'appareil est identique au fichier).
- La carte « Sauvegarde conseillée » apparaît **en tête de toutes les vues** (ajoutée par `render()`) quand `since` existe depuis au moins `every` jours (`bkDue`), sauf report (« Plus tard » : jusqu'au lendemain) ou délai « Jamais ». Réglage dans Réglages › Sauvegarde.
- Migration : des données d'avant le rappel, sans `bk` et jamais exportées, démarrent le compte aujourd'hui ; si `lastExport` existe, rien n'est dû tant qu'on ne modifie pas. L'ancienne règle « 30 jours sans export » n'existe plus.

## Bannière « Hors ligne »

Barre fine fixée juste au-dessus des onglets (`#offbar`), visible sur les cinq vues, qui **ne bloque aucun toucher** (`pointer-events: none`). Le bouton « + » et le bas de page montent d'autant tant qu'elle est affichée (classe `off` sur `body`).

- Affichée seulement si un compte est connecté avec sa phrase (sinon il n'y a rien à synchroniser) **et** que le réseau manque : événement `offline` du navigateur, ou dernière tentative de synchronisation tombée en échec réseau (`syncState.status === 'offline'`). Le second cas couvre un Wi-Fi sans internet, où `navigator.onLine` reste vrai.
- Mise à jour par `offbarUpdate()` : à chaque changement d'état de synchro, aux événements `offline` et `resize`, à chaque relève (5 s) et au rendu de la carte de synchronisation (connexion, déconnexion).
- Disparaît quand une synchronisation réussit. Le détail (« Hors ligne : tes modifications partiront dès le retour du réseau ») reste dans Réglages › Synchronisation.

Clés de stockage propres à l'appareil, jamais exportées : `compte-sync-session` (jetons), `compte-sync-meta` (curseur et empreintes), `compte-sync-cle`, `compte-sync-conflits`.
Le service worker ignore désormais les requêtes vers d'autres adresses (aucun appel au compte dans le cache).

