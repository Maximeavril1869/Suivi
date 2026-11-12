# Tests

Vérifications automatiques en navigateur (Chromium piloté par Python et Playwright). Elles ne servent pas à utiliser l'app, seulement à vérifier qu'une modification n'a rien cassé.

## Lancer

Depuis la racine du dépôt (Python 3 requis) :

```
pip install playwright
playwright install chromium
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_sync.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_rappel_et_hors_ligne.py
```

Le script affiche `OK` ou `ECHEC` pour chaque vérification et se termine par le nombre d'échecs.

## Contenu

| Fichier | Vérifie |
|---|---|
| `test_sync.py` | Synchronisation chiffrée (faux serveur Supabase en mémoire, deux appareils simulés) : carte sans compte et aucun appel réseau, mauvais mot de passe, création de la phrase secrète (trop courte, deux phrases différentes), rien de lisible reçu par le serveur, ni mot de passe ni phrase stockés, second appareil (mauvaise puis bonne phrase), relève automatique et envoi du seul mois modifié, mois supprimé propagé, champs propres à l'appareil, échange de lignes par le serveur refusé, première synchro (le serveur l'emporte, copie gardée), modification juste après la connexion, hors ligne puis retour, jeton expiré, session perdue, déconnexion, fenêtre de saisie ouverte |
| `test_rappel_et_hors_ligne.py` | Rappel de sauvegarde (anciennes données, durée affichée, « Plus tard » et report échu, délai réglable dont « Jamais », cocher un compte ne compte pas, export et restauration remettent à zéro) et partagé entre deux appareils ; bannière « Hors ligne » (apparition immédiate, position au-dessus des onglets, aucun toucher intercepté, cinq vues, modification possible hors ligne, Wi-Fi sans internet, retour du réseau, absente sans compte) |

## Règles

- Aucune donnée réelle : libellés, montants et identifiants inventés.
- Le faux serveur ne répond que pendant que Playwright traite des événements : on attend par la page (`wait_for_timeout`), jamais par `time.sleep`.
