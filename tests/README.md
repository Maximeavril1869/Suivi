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
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_comptes_accueil.py
```

Le script affiche `OK` ou `ECHEC` pour chaque vérification et se termine par le nombre d'échecs.

## Contenu

| Fichier | Vérifie |
|---|---|
| `test_sync.py` | Synchronisation chiffrée (faux serveur Supabase en mémoire, deux appareils simulés) : carte sans compte et aucun appel réseau, mauvais mot de passe, création de la phrase secrète (trop courte, deux phrases différentes), rien de lisible reçu par le serveur, ni mot de passe ni phrase stockés, second appareil (mauvaise puis bonne phrase), relève automatique et envoi du seul mois modifié, mois supprimé propagé, champs propres à l'appareil, échange de lignes par le serveur refusé, première synchro (le serveur l'emporte, copie gardée), modification juste après la connexion, hors ligne puis retour, jeton expiré, session perdue, déconnexion, fenêtre de saisie ouverte |
| `test_rappel_et_hors_ligne.py` | Rappel de sauvegarde (anciennes données, durée affichée, « Plus tard » et report échu, délai réglable dont « Jamais », cocher un compte ne compte pas, export et restauration remettent à zéro) et partagé entre deux appareils ; bannière « Hors ligne » (apparition immédiate, position au-dessus des onglets, aucun toucher intercepté, cinq vues, modification possible hors ligne, Wi-Fi sans internet, retour du réseau, absente sans compte) |
| `test_comptes_accueil.py` | Carte « Comptes » de l'Accueil : repliée au départ, titre (nombre et solde), groupes par organisme, cocher / décocher, Tout cocher / Tout décocher, état conservé (clic, rechargement), Lignes et Récurrent inchangés, sans organisme, un seul compte |
| `test_decouvert_plafonds.py` | Découvert et plafonds de carte : disponible réel (règle de l'utilisateur : plafond restant − dépassement, dans le découvert seul le plafond limite, plancher à 0, retrait non réduit, sans réglage), achats non détaillés d'une carte différée (solde de référence, pas de double comptage), fenêtres glissantes (30 et 7 jours, bornes), retraits, lignes exclues, cartes différées, prévision du solde le plus bas, budget du jour inchangé, carte sur l'Accueil, fiche du compte (saisie, validation, effacement, changement de type) |
| `test_budget_jour.py` | Budget du jour : règle de paie (novembre, octobre, décembre, janvier, jours fériés, Pâques), modification et rétablissement d'une date, périodes de paie à paie, calcul (par jour, aujourd'hui, semaine, recalage le lendemain, virements et récurrences exclus, carte hors reste à vivre, budget négatif, dernier jour, dimanche, aucun compte), carte sur l'Accueil, carte « Jours de paie » dans Réglages, synchronisation du champ |
| `test_cartes_credit.py` | Cartes de crédit : dette = plafond − solde (cas 2500 sur 3000), carte pleine, vide, plafond dépassé, centimes, achats et remboursements, poids de la carte dans les totaux (solde des comptes cochés, reste à vivre, liste des lignes), affichage Accueil et Réglages, fiche de compte (explication, case « reste à vivre » décochée à la sélection du type) |
| `test_replis.py` | Marge en haut des pages (puces de comptes) ; menus repliables de Réglages : six cartes, état par défaut, plier / déplier, état conservé après nouveau rendu, changement d'onglet et rechargement, état propre à l'appareil (absent des données), état illisible ignoré, groupes d'organismes (replier un groupe, modifier un compte du groupe, un seul groupe, comptes sans organisme), menu Synchronisation non refermé par son rafraîchissement |
| `test_regles_et_tiers.py` | Catégorie Animaux, tiers existants passés en majuscules (et enregistrés), saisie sans libellé (le tiers en tient lieu), règles dans Réglages : ajout, doublon refusé, aperçu à cocher avant reclassement, modification, ordre (la première règle l'emporte), suppression |

## Règles

- Aucune donnée réelle : libellés, montants et identifiants inventés.
- Le faux serveur ne répond que pendant que Playwright traite des événements : on attend par la page (`wait_for_timeout`), jamais par `time.sleep`.
