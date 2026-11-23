# Tests

Vérifications automatiques en navigateur (Chromium piloté par Python et Playwright). Elles ne servent pas à utiliser l'app, seulement à vérifier qu'une modification n'a rien cassé.

## Lancer

Depuis la racine du dépôt (Python 3 requis) :

```
pip install playwright
playwright install chromium
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_sync.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_rappel_et_hors_ligne.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_regles_et_tiers.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_replis.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_cartes_credit.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_budget_jour.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_decouvert_plafonds.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_debordements.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_comptes_accueil.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_paie.py
```

Le script affiche `OK` ou `ECHEC` pour chaque vérification et se termine par le nombre d'échecs.

## Contenu

| Fichier | Vérifie |
|---|---|
| `test_sync.py` | Synchronisation chiffrée (faux serveur Supabase en mémoire, deux appareils simulés) : carte sans compte et aucun appel réseau, mauvais mot de passe, création de la phrase secrète (trop courte, deux phrases différentes), rien de lisible reçu par le serveur, ni mot de passe ni phrase stockés, second appareil (mauvaise puis bonne phrase), relève automatique et envoi du seul mois modifié, mois supprimé propagé, champs propres à l'appareil, échange de lignes par le serveur refusé, première synchro (le serveur l'emporte, copie gardée), modification juste après la connexion, hors ligne puis retour, jeton expiré, session perdue, déconnexion, fenêtre de saisie ouverte |
| `test_rappel_et_hors_ligne.py` | Rappel de sauvegarde (anciennes données, durée affichée, « Plus tard » et report échu, délai réglable dont « Jamais », cocher un compte ne compte pas, export et restauration remettent à zéro) et partagé entre deux appareils ; bannière « Hors ligne » (apparition immédiate, position au-dessus des onglets, aucun toucher intercepté, cinq vues, modification possible hors ligne, Wi-Fi sans internet, retour du réseau, absente sans compte) |
| `test_patrimoine.py` | Patrimoine net : carte repliée sur l'Accueil, total et détail (liquidités, épargne, épargne bloquée, biens, dettes), bloqué et bien exclus du reste à vivre et des soldes cochés, création et modification d'un bien, livret passé en épargne bloquée |
| `test_comptes_accueil.py` | Carte « Comptes » (Accueil, Lignes, Récurrent) : repliée au départ, titre (nombre et solde), groupes par organisme, cocher / décocher sur chaque page, montants des cartes de chiffres alignés (390 à 320 px), Tout cocher / Tout décocher, état partagé entre les pages et conservé (clic, rechargement), sans organisme, un seul compte |
| `test_decouvert_plafonds.py` | Découvert et plafonds de carte : disponible réel (règle de l'utilisateur : plafond restant − dépassement, dans le découvert seul le plafond limite, plancher à 0, retrait non réduit, sans réglage), achats non détaillés d'une carte différée (solde de référence, pas de double comptage), fenêtres glissantes (30 et 7 jours, bornes), retraits, lignes exclues, cartes différées, prévision du solde le plus bas, budget du jour inchangé, carte sur l'Accueil, fiche du compte (saisie, validation, effacement, changement de type) |
| `test_budget_jour.py` | Budget du jour : règle de paie (novembre, octobre, décembre, janvier, jours fériés, Pâques), modification et rétablissement d'une date, périodes de paie à paie, calcul (par jour, aujourd'hui, semaine, recalage le lendemain, virements et récurrences exclus, carte hors reste à vivre, budget négatif, dernier jour, dimanche, aucun compte), carte sur l'Accueil, carte « Jours de paie » dans Réglages, synchronisation du champ |
| `test_cartes_credit.py` | Cartes de crédit : dette = plafond − solde (cas 2500 sur 3000), carte pleine, vide, plafond dépassé, centimes, achats et remboursements, poids de la carte dans les totaux (solde des comptes cochés, reste à vivre, liste des lignes), affichage Accueil et Réglages, fiche de compte (explication, case « reste à vivre » décochée à la sélection du type) |
| `test_debordements.py` | Aucun débordement horizontal à 390, 375, 360 et 320 px (et montants à six chiffres à 390 et 320), puis en paysage à 844 × 390, 1 024 × 768 et 1 194 × 834 (app plus large que 640 px, une seule colonne) : 5 vues (dont Lignes en sélection, Import avec fichier), rappel de sauvegarde et bannière « Hors ligne », 13 fenêtres et les 7 types de compte ; repère les éléments hors écran, hors de leur carte ou coupés |
| `test_paie.py` | Module Bulletin de paye (dont lignes calculées : points tronqués au centime vérifiés sur trois bulletins, points ACF (valeur par point, arrondi normal, valeur datée), ordre de la liste de base (gains, retenues, totaux), suppression rapide d'une ligne ponctuelle (✕), taux, base cochée avec retenue retranchée, plafond, recalcul des fiches) : migration et restauration (champ absent ou invalide), carte d'entrée sur Récurrent, création des lignes du modèle, mois à valider (aucun mois futur), fiche pré-remplie, montant invalide, ignorer puis valider, « Tout valider », tableau (ordre gains / retenues / totaux, montant changé en gras, totaux sur toute la période choisie, sélecteurs « Du / Au », bornes inversées, courbe limitée à la période, « Toute la période »), courbe (ligne par défaut, choix, toucher un point), changement d'échelon daté avec motif (fiches d'avant inchangées, mois suivant au nouveau montant), propagation aux mois suivants depuis une fiche (question, « Retour », « à partir de ce mois », « ce mois seulement », fiche ponctuelle rouverte sans question, prime jamais propagée, fiche nouvelle) et depuis la fenêtre d'une ligne (confirmation du nombre de fiches), primes ponctuelles (libellé obligatoire, même série d'un mois à l'autre, doublon refusé), net à payer sur chaque fiche (libellés, plusieurs lignes, repli, tiret, message d'aide), net calculé (gains − retenues, jamais sans ligne de gain, négatif affiché), ligne créée dans le modèle proposée aux fiches déjà validées (nombre, début avancé, renommage sans question, mois vide volontaire, refus, ligne future), sélection et suppression de fiches (cases, compteur, tout sélectionner, confirmation refusée puis acceptée, mois qui reviennent à valider ou sont ignorés selon la réponse à « Ignorer aussi », quitter en pleine sélection), suppression d'une fiche et d'une ligne (fiches conservées, clé d'origine gardée), sélection et suppression de lignes du modèle (cases, compteur, confirmation refusée puis acceptée, fiches conservées, refus si une base disparaît, base et plafond nettoyés), option « retirer aussi des fiches validées » (refusée : fiches intactes ; acceptée : ligne retirée, CSG recalculée ; absente des fiches : pas de question), proratisation d'un mois (du … au …, base 30 jours : 20 et 21 jours, fin de mois, période invalide, montant saisi conservé, recalcul, retour au mois complet), bulletin réel (rappel de CSG, transfert négatif), recalcul de toutes les fiches et historique daté d'une ligne, ponctuelles « soumises aux taux » (case, recalcul en direct, gain ajouté / retenue retranchée, ✕, fiche rouverte, ligne à taux qui ne l'accepte pas, case « inclure » par défaut, recalcul des fiches), fin de ligne, contrôles du formulaire, aucun effet sur comptes, soldes et échéances, synchronisation chiffrée entre deux appareils |
| `test_replis.py` | Marge en haut des pages (puces de comptes) ; menus repliables de Réglages : six cartes, état par défaut, plier / déplier, état conservé après nouveau rendu, changement d'onglet et rechargement, état propre à l'appareil (absent des données), état illisible ignoré, groupes d'organismes (replier un groupe, modifier un compte du groupe, un seul groupe, comptes sans organisme), menu Synchronisation non refermé par son rafraîchissement |
| `test_regles_et_tiers.py` | Catégorie Animaux, tiers existants passés en majuscules (et enregistrés), saisie sans libellé (le tiers en tient lieu), règles dans Réglages : ajout, doublon refusé, aperçu à cocher avant reclassement, modification, ordre (la première règle l'emporte), suppression |

## Règles

- Aucune donnée réelle : libellés, montants et identifiants inventés.
- Le faux serveur ne répond que pendant que Playwright traite des événements : on attend par la page (`wait_for_timeout`), jamais par `time.sleep`.
