# Carnet de bord — Mon Compte (dépôt « Suivi »)

Journal des opérations réalisées sur le projet, à relire pour savoir où il en est.
Les entrées les plus récentes sont en haut. À chaque intervention, ajouter une entrée datée.

## État actuel (2026-11-19)

- **Version 33** : patrimoine net (carte repliée sur l'Accueil), types « Épargne bloquée » et « Bien ». 9 suites de tests, toutes vertes (`tests/test_patrimoine.py` : 37 vérifications). Points ouverts : voir l'entrée du 2026-11-19.

### Rappel de l'état au 2026-11-16

- App PWA locale d'abord (un seul fichier `index.html`), publiée sur GitHub Pages, utilisée sur iPhone et iPad. **Synchronisation chiffrée** (validée sur appareils le 2026-11-12), **rappel de sauvegarde partagé** (même logique que Plan du jour) et **bannière « Hors ligne »** ajoutés le 2026-11-12 (à valider sur iPhone et iPad). Service worker en version `compte-v32` (numéro affiché en bas de Réglages). **Réglages : menus repliables** depuis le 2026-11-17 (à valider sur iPhone et iPad).
- Plan en 3 étapes entièrement présent dans le code : comptes multiples + virements, paiements en plusieurs fois, emprunts / livrets / cartes.
- Reste à faire : tester l'import CSV avec l'export réel de la banque (point en attente depuis la première version) ; valider la synchronisation sur appareil.
- Aucune donnée réelle n'est stockée dans le dépôt.

## État au 2026-11-03 (avant la synchronisation)

- App PWA 100 % locale (un seul fichier `index.html`), publiée sur GitHub Pages, utilisée sur iPhone.
- Plan en 3 étapes entièrement présent dans le code : comptes multiples + virements, paiements en plusieurs fois, emprunts / livrets / cartes.
- Service worker en version `compte-v17`.
- Reste à faire : tester l'import CSV avec l'export réel de la banque (point en attente depuis la première version).
- Aucune donnée réelle n'est stockée dans le dépôt.

## 2026-11-19 — Patrimoine net, Épargne bloquée et Bien (version 33)

- Demande : les parts sociales sont du capital (ta richesse), comme l'emprunt face à la valeur de la maison ; l'app mélangeait liquidités et patrimoine.
- Choix de l'utilisateur : carte « Patrimoine » repliée sur l'Accueil (total net sur la ligne repliée) ; type « Bien » avec valeur estimée et date, modifiable ; type dédié « Épargne bloquée ».
- Réalisé : deux types (`bloque`, `bien`) ; carte `patrimoineHTML` (liquidités, épargne, épargne bloquée, biens, total possédé, emprunts, cartes de crédit dû, achats différés en attente, total dû, patrimoine net) ; ces deux types sont **toujours** hors reste à vivre, budget du jour, solde des comptes cochés, « Sortir du découvert » (`isLiquid`, `scopeAccs`, `inScope`), retirés des comptes cochés et des listes de choix de compte ; on y saisit une valeur (solde de référence), pas des lignes.
- Choix faits sans question (modifiables) : le patrimoine compte tous les comptes, cochés ou non ; dettes = emprunts, carte de crédit (plafond − disponible) et achats différés en attente ; un compte passé en Épargne bloquée / Bien est décoché automatiquement.
- Tests : `tests/test_patrimoine.py`, 37 vérifications ; les 8 autres suites inchangées et vertes.
- Limites : pas de lignes sur ces deux types (virement vers une assurance-vie à saisir en mettant à jour sa valeur) ; pas d'historique de l'évolution du patrimoine.

## 2026-11-17 — Réglages : menus repliables, groupes d'organismes repliables (version 23)

- Demande : dans Réglages, des menus qui se replient, et pareil pour les organismes.
- Lecture retenue : chaque carte de Réglages se replie (touche sur le titre, chevron à droite), et dans la carte Comptes chaque organisme (Caisse d'épargne, etc.) se replie aussi, son solde restant visible dans le titre.
- Choix faits sans question (modifiables) : par défaut Comptes et les organismes sont ouverts, les autres cartes (budgets, règles, synchronisation, sauvegarde, zone dangereuse) repliées ; l'état est mémorisé **par appareil** (iPhone et iPad indépendants, rien dans les données synchronisées ni dans l'export).
- Fait : `foldCard` et l'objet `FOLD` (`localStorage`, clé `compte-replis`) dans `index.html` ; `<details>` natifs. Service worker `compte-v23`, `APP_VERSION = '23'`.
- Tests : `tests/test_replis.py` (34 vérifications) ; `go_settings` de `tests/test_sync.py` déplie désormais toutes les cartes pour que les anciens tests atteignent leurs champs ; les trois anciennes suites passent toujours (57, 50, 30).
- Reste à valider sur iPhone et iPad.

## 2026-11-19 (suite 3) — Même carte repliable sur Lignes et Récurrent (version 32)

- Réponse « Oui » à la question : étendre la liste repliable à Lignes et Récurrent.
- Fait : `accFoldHTML` remplace `accBar` sur les trois vues ; l'ancienne rangée de puces (`accBar`, styles `.chips` / `.chip`) est supprimée du code. L'état ouvert / replié et celui des groupes sont communs aux trois vues. Service worker `compte-v32`, `APP_VERSION = '32'`.
- Tests : `tests/test_comptes_accueil.py` passe à 27 vérifications (cocher / décocher sur Lignes et Récurrent, état partagé) ; `test_replis.py` adapté ; les autres suites passent.

## 2026-11-19 (suite 2) — Choix des comptes de l'Accueil en liste repliable (version 31)

- Réponses sur la version 30 : les 847,23 € de la CB **comptent** dans le plafond ; retraits : **on laisse** (non réduits par le dépassement). Les deux points ouverts de la version 30 sont donc clos.
- Demande : sur la première page, un affichage différent des cases à cocher des comptes, par exemple une liste rétractable.
- Décisions : **Accueil seulement** (Lignes et Récurrent gardent la rangée de puces) ; ligne repliée = **nombre de comptes + solde total** ; liste dépliée = **groupée par organisme, groupes repliables** ; **repliée au démarrage**.
- Choix non demandé : groupes d'organismes **ouverts** par défaut à l'intérieur de la carte (pour voir les comptes dès qu'on la déplie), modifiable.
- Fait : `accFoldHTML` (carte `hacc`), cases ☑/☐ avec solde, « Tout cocher » / « Tout décocher » (`allacc`), même `S.shown` pour toutes les pages. Service worker `compte-v31`, `APP_VERSION = '31'`.
- Tests : `tests/test_comptes_accueil.py` (23 vérifications) ; `test_replis.py` adapté (marge haute) ; les sept autres suites passent.

## 2026-11-19 (suite) — Règle de la carte corrigée, achats non détaillés comptés (version 30)

- Retour de l'utilisateur sur la version 29 (capture : Caisse d'épargne › Compte courant, solde −2 495,18 €, découvert autorisé 2 000 €, plafonds 1 500 €) : l'app affichait « 1 500 € restants » et « disponible 0 € » ; il attendait **1 500 − 495,18** et signalait que ses paiements par carte n'étaient pas comptés alors qu'il a un compte CB (débit différé, débité sur ce compte, jour 5, solde de référence −847,23 € au 18 nov 2026).
- Règle donnée par l'utilisateur : « J'ai une autorisation de découvert de 2000 et un plafond CB de 1500. Tant que les 2000 ne sont pas atteints j'ai 1500. Si je dépasse les 2000, j'ai 1500 − le dépassement. » Pour les retraits : « pas impacté par le découvert dans l'app de la banque, même si je suppose que ça ne doit pas fonctionner ».
- Cause du compteur à 0 : le solde de référence de la carte (−847,23) n'est pas un achat détaillé ; seules les lignes comptaient.
- Fait : disponible par carte = plafond de paiement restant − dépassement (plancher 0) ; la marge du compte ne limite plus tant que le découvert n'est pas dépassé ; retrait = plafond de retrait restant, non réduit ; achats non détaillés d'une carte différée comptés dans le plafond (solde en attente − lignes détaillées depuis le dernier prélèvement) ; carte : état sur sa propre ligne, « plafond X · utilisé Y » ; explication du dépassement. `debitDates(carte, date)` accepte une date. Service worker `compte-v30`, `APP_VERSION = '30'`.
- Exemple de sa situation (données inventées équivalentes) : plafond 1 500, utilisé 847,23 (solde en attente de la carte) → restant 652,77 ; dépassement 495,18 → disponible par carte 157,59 (et non 1 004,82, car 847,23 € du plafond sont déjà utilisés).
- Tests : `tests/test_decouvert_plafonds.py` passe à 48 vérifications ; toutes les autres suites passent.
- Points ouverts : (1) l'utilisateur a dit « 1500 − 495,18 » en pensant à un plafond intact ; l'app y soustrait aussi les 847,23 € déjà utilisés, ce qui est à confirmer avec lui ; (2) retrait : la règle réelle de la banque reste inconnue.

## 2026-11-19 — Autorisation de découvert, plafonds de carte, disponible réel (version 29)

- Demande : enregistrer les plafonds (carte bancaire) et les autorisations de découvert ; l'utilisateur comprend qu'un dépassement du découvert impacte le plafond de la carte bancaire. Il précise que sa situation financière est tendue en ce moment (passager, à étudier plus tard) : le découvert ne doit donc pas gonfler le budget.
- Décisions : enregistrer **autorisation de découvert, plafond de paiement et plafond de retrait** ; l'app **calcule un disponible réel** (solde + découvert, limité par le plafond de carte restant) ; le découvert **ne compte pas** dans le budget du jour ni le reste à vivre (« limite à ne pas atteindre », option recommandée).
- Fait : champs sur la fiche d'un compte courant (`od`, `payLim`/`payDays`, `wdLim`/`wdDays`, fenêtres de 30 et 7 jours modifiables) ; carte par compte sur l'Accueil (état, marge, plafonds restants, disponible par carte et en retrait, solde le plus bas prévu avant la paie, alerte de dépassement) ; sous-catégorie **Divers › Retrait d'espèces** ; mention « découvert autorisé » dans la liste des comptes. Les champs voyagent avec `accounts` (synchronisés). Service worker `compte-v29`, `APP_VERSION = '29'`.
- Tests : `tests/test_decouvert_plafonds.py` (48 vérifications) ; toutes les autres suites passent.
- Limites connues : la règle réelle de la banque (réduction du plafond de carte après dépassement, frais) n'est pas modélisée — au-delà du découvert, l'app met simplement le disponible à 0 ; un prélèvement importé non rapproché d'une récurrence compte comme paiement par carte ; les retraits n'entrent dans le plafond de retrait que s'ils sont classés en Retrait d'espèces.
- Question restée ouverte : la règle exacte de la banque de l'utilisateur sur le plafond après un dépassement du découvert.

## 2026-11-18 (nuit) — Budget du jour façon Money Coach (version 28)

- Demande : aimait dans Money Coach le solde mensuel, hebdomadaire (mensuel ÷ nombre de semaines) et journalier (hebdomadaire ÷ nombre de jours), « avec l'ajustement en fonction de la conso par jour ». Question posée avant : « le reste à vivre est calculé à quelle échéance ? » (réponse : à la date d'aujourd'hui, sans échéances à venir ; il n'existait pas de prévisionnel de fin de période).
- Décisions de l'utilisateur : montant de départ = **reste à vivre d'aujourd'hui + échéances à venir** ; période **de salaire à salaire** ; consommation = **toutes les dépenses sauf fixes et virements** ; ajustement **report en continu** ; semaine **du lundi au dimanche** ; carte de crédit **ignorée** (case « Compter dans le reste à vivre » décochée : ses remboursements prévus comptent déjà comme dépenses à venir, la déduire aussi les compterait deux fois). Jour de paie : **2 jours ouvrés avant le dernier jour ouvré du mois** (lundi à vendredi hors fériés), **décembre : 7 jours plus tôt** (le 22 au lieu du 29), **modifiable** mois par mois.
- Fait : carte « Budget du jour » en tête de l'Accueil (aujourd'hui, cette semaine, jusqu'à la paie, par jour, détail reste à vivre + échéances à venir) ; Réglages › Jours de paie (14 mois, touche un mois pour changer la date, « Rétablir la règle ») ; champ `payDates` synchronisé. Service worker `compte-v28`, `APP_VERSION = '28'`. Détail du calcul dans ARCHITECTURE.md (« Budget du jour »).
- Exemple vérifié : paie novembre 2026 = jeudi 26 ; décembre 2026 = mardi 22 ; période du 28 oct au 25 nov (8 jours restants le 18 nov).
- Tests : `tests/test_budget_jour.py` (60 vérifications) ; `test_replis.py` adapté (sept cartes) ; les autres suites passent.
- Hypothèses non confirmées : jours fériés français uniquement (pas de jours fériés locaux), pas de jour de solidarité ; l'app ne sait pas si une paie est effectivement arrivée (la période change à la date, pas à la réception) ; une dépense à venir non validée mais déjà passée dans la période est comptée comme à venir.

## 2026-11-18 (suite) — Correction : poids de la carte dans les totaux (version 27)

- Remarque de l'utilisateur : le traitement de la carte dans le reste à vivre « dépend de comment est calculé le reste à vivre ». Relecture du code : « Solde des comptes cochés » additionne tous les comptes cochés (sans tenir compte de la case « Compter dans le reste à vivre »), et « Reste à vivre » additionne seulement ceux dont la case est cochée.
- **Erreur de la version 26** : avec le nouveau sens du solde (disponible), la carte entrait dans ces totaux à +2500 au lieu de −500 (sa dette). Corrigé dans `openingSum` : une carte de crédit pèse solde − plafond dans tout total (solde des comptes cochés, reste à vivre, solde courant de la liste des lignes). Les totaux sont ainsi identiques à ceux d'avant la version 26.
- Conséquence : la case « Compter dans le reste à vivre » d'une carte décide maintenant si sa dette est déduite du reste à vivre (cochée : déduite ; décochée : ignorée).
- Service worker `compte-v27`, `APP_VERSION = '27'`. Tests : `tests/test_cartes_credit.py` passe à 23 vérifications.
- Question posée à l'utilisateur : la dette de la carte doit-elle être déduite du reste à vivre (case cochée) ou ignorée (case décochée) ?

## 2026-11-18 — Cartes de crédit : dette = plafond − solde (version 26)

- Retour de l'utilisateur : « J'ai le droit à 3000, je suis à 2500, je dois donc 500 » ; l'app affichait 5 500 € de crédit disponible (plafond + solde), ce qui est faux.
- Cause : `creditInfo` supposait un solde négatif quand on doit de l'argent (disponible = plafond + solde, dû = −solde si négatif).
- Fait : **le solde d'une carte de crédit est le montant encore disponible** ; dû = plafond − solde (jamais négatif), disponible = solde (négatif = plafond dépassé). Aucune migration : le solde que l'utilisateur avait saisi (2500) est déjà dans ce sens, donc l'affichage devient juste tout de suite. Les achats (lignes négatives) font baisser le disponible, les remboursements le font remonter, comme avant.
- Fiche de compte : texte d'aide séparé pour la carte de crédit (saisir ce qu'il reste à utiliser, en positif) ; choisir ce type décoche « Compter dans le reste à vivre » (sinon la réserve disponible serait comptée comme de l'argent).
- Service worker `compte-v26`, `APP_VERSION = '26'`. Tests : `tests/test_cartes_credit.py` (15 vérifications) ; les quatre autres suites passent toujours.
- Point resté ouvert (voir l'entrée suivante) : une carte déjà créée avec la case « Compter dans le reste à vivre » cochée garde cette case (l'app ne la décoche pas toute seule) ; si l'utilisateur veut que la dette de la carte pèse sur le reste à vivre, la règle reste à définir.

## 2026-11-17 (soir) — Marge en haut des pages (version 25)

- Retour : les puces de comptes à cocher (Accueil, Lignes, Récurrent) sont « trop haut », « comme on a eu pour les autres app » ; précisé par l'utilisateur : **collées en haut de l'écran** (pas trop loin du pouce). Ces puces ne sont pas nouvelles : elles existent depuis l'étape 1 (comptes multiples) ; sur l'Accueil elles sont le tout premier élément, donc à 12 px du bord.
- Fait : marge haute de `#app` portée de 12 px à 32 px (en plus de la zone sûre de l'écran), pour toutes les vues, pour garder une mise en page homogène. Service worker `compte-v25`, `APP_VERSION = '25'`.
- Test : `tests/test_replis.py` vérifie que les puces sont à au moins 30 px du haut (34 vérifications au total).
- Non vérifié : le rendu réel sur iPhone (zone sûre, encoche) ; la valeur de 32 px est un choix de départ, à ajuster selon son retour.

## 2026-11-17 (suite) — Tout replié par défaut (version 24)

- Réponses de l'utilisateur : « organismes » = les groupes de la carte Comptes (lecture confirmée) ; il **préfère tout fermé** par défaut.
- Fait : Comptes, ses organismes et toutes les autres cartes sont repliés au départ (`foldCard(..., false)` et `foldOpen('g:'+nom, false)`). Un menu que l'utilisateur a déjà ouvert ou fermé garde son choix mémorisé. Service worker `compte-v24`, `APP_VERSION = '24'`.
- Tests : `tests/test_replis.py` adapté (état par défaut, dépliage de Comptes puis des organismes), 31 vérifications.

## 2026-11-12 (soir, suite) — Version affichée, rappel sur toutes les vues

- Retour de test : le rappel partagé et la bannière « Hors ligne » **fonctionnent sur iPhone et iPad**. Demandes : afficher la version de l'app « ça aidera à suivre les modifications » ; afficher le rappel de sauvegarde sur **tous les onglets** (« on ne sait jamais lequel je vais consulter »).
- Fait : constante `APP_VERSION = '21'` affichée en bas de Réglages (« Mon Compte · version 21 »), à incrémenter avec `V` de `sw.js` (`compte-v21`) à chaque livraison ; carte « Sauvegarde conseillée » ajoutée en tête de toutes les vues par `render()` (retirée de `homeHTML`, sinon elle serait en double).
- Tests : `test_rappel_et_hors_ligne.py` (50 vérifications : rappel sur les cinq vues, version affichée = version du service worker) ; `test_sync.py` inchangé, passe.

## 2026-11-12 (soir) — Rappel de sauvegarde comme Plan du jour, bannière « Hors ligne »

- Réponses de l'utilisateur : (1) il veut le **même rappel que Plan du jour** (délai réglable, déclenché par les modifications non sauvegardées) ; (2) une **bannière** qui annonce l'absence de réseau **sans empêcher d'utiliser l'app** ; (3) placée **en bas, au-dessus des onglets**.
- Fait : état `bk` (`since`, `snooze`, `every`) dans les données et la ligne `meta` synchronisée ; `save(true)` pour les enregistrements qui ne sont pas des modifications (cocher un compte, régler le rappel, exporter, restaurer) ; carte « Sauvegarde conseillée » avec « Plus tard » ; délai réglable dans Réglages › Sauvegarde (jamais, 3, 7, 14, 30 jours ; 7 par défaut). L'ancienne règle « 30 jours sans export » est supprimée.
- Fait : bannière `#offbar` visible sur toutes les vues, `pointer-events: none`, bouton « + » et bas de page décalés quand elle est affichée. Elle n'apparaît que si un compte est connecté. Détection : événement `offline` **et** échec réseau de la synchro (le Wi-Fi sans internet n'est pas vu par `navigator.onLine`).
- Le rappel était d'abord limité à l'Accueil ; il est passé sur toutes les vues dans l'entrée ci-dessus.
- Service worker `compte-v20`. Tests : `tests/test_rappel_et_hors_ligne.py` (44 vérifications au départ, 50 ensuite) ; `tests/test_sync.py` inchangé (57 vérifications, passent).
- Reste à valider sur iPhone et iPad : rappel (sauvegarde sur un appareil, ~10 s, rappel disparu sur l'autre) ; bannière (mode avion : apparition immédiate ; retour du réseau : disparition en quelques secondes).
- Non testé en conditions réelles : le vrai service Supabase (faux serveur uniquement) et le comportement exact d'iOS en Wi-Fi sans internet.

## 2026-11-16 — Catégorie Animaux, tiers en majuscules, règles gérées dans Réglages (version 22)

- Demande : pas de catégorie pour les animaux ; pouvoir ajouter des règles de classement directement dans Réglages ; éviter la multiplication des tiers (majuscules forcées, tiers existants proposés) ; question sur l'utilité du libellé.
- Décisions de l'utilisateur : sous-catégories d'Animaux validées telles que proposées ; à la création d'une règle, un **aperçu des lignes concernées** avec validation avant reclassement ; ajouter, modifier et réordonner les règles ; mot-clé « contient » suffisant pour l'instant ; passage de tous les tiers existants en majuscules ; suggestions de tiers pendant la frappe suffisantes (pas de liste déroulante dédiée).
- Fait : catégorie **Animaux** (Alimentation, Vétérinaire / pharmacie, Assurance / mutuelle, Toilettage / garde, Accessoires / jouets) ; **tiers en majuscules** à la saisie (ligne, modification groupée, paiement en plusieurs fois, règles, import CSV) et migration des tiers existants (enregistrée une fois au démarrage, donc synchronisée) ; **libellé facultatif** en saisie manuelle (le tiers en tient lieu, et n'est plus affiché deux fois) ; Réglages › Règles : bouton « Ajouter une règle », touche une règle pour la modifier ou la supprimer, flèches ▲ ▼ pour l'ordre (la première règle qui correspond l'emporte), aperçu à cocher avant reclassement des lignes existantes. Service worker `compte-v22`.
- Tests : `tests/test_regles_et_tiers.py` (30 vérifications) ; les deux anciennes suites passent toujours (57 et 50).
- Point de vigilance : en corrigeant une ligne, l'app propose toujours de créer une règle à partir du tiers (ex. « LECLERC → Animaux »). Pour un supermarché qui vend de tout, répondre Non, ou créer à la main une règle plus précise (« LECLERC PET »).

## 2026-11-12 — La dernière sauvegarde est partagée entre appareils

- Retour de test : la synchronisation fonctionne sur iPhone et iPad. Remarque de l'utilisateur : la sauvegarde était attendue séparément sur chaque appareil, « un peu bête » puisque les données sont les mêmes.
- Fait : `lastExport` rejoint les données synchronisées (clé `meta`) ; seuls les comptes cochés restent propres à l'appareil. Une sauvegarde faite sur un appareil supprime le rappel sur les autres. Service worker `compte-v19`. Test adapté.
- Point ouvert : le rappel de l'accueil se déclenche seulement après 30 jours sans export (ou jamais exporté) quand il y a des lignes ; il disparaît donc après un export, ce qui est normal. À comparer avec Plan du jour (délai réglable, rappel basé sur les modifications) si l'utilisateur le souhaite.

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
