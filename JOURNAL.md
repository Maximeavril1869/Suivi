# Carnet de bord — Mon Compte (dépôt « Suivi »)

Journal des opérations réalisées sur le projet, à relire pour savoir où il en est.
Les entrées les plus récentes sont en haut. À chaque intervention, ajouter une entrée datée.

## 2026-11-21 (après-midi, suite 2) — Bulletin de paye : menu « Mois ignorés » repliable (version 60)

- Demande : un menu pour refermer « Mois ignorés ». Fait : la section est un menu repliable imbriqué dans « Fiches validées » (`details[data-fold="paie-skips"]`), titre « Mois ignorés (N) », ouvert par défaut, état ouvert/fermé gardé sur l'appareil (`FOLD`, comme les autres menus). Sélection et boutons « Remettre à valider » inchangés.
- Tests : `test_paie` 311 vérifications (ouvert par défaut, fermeture, état conservé après un nouvel affichage, réouverture). `test_replis` reste instable (1 échec sur 3 ou 4 passages, constaté aussi sur la version 59 sans ce changement) : cause à examiner à part, sans lien avec la paie. Service worker `compte-v60`.

## 2026-11-21 (après-midi, suite) — Bulletin de paye : proratisation d'un mois (version 59)

- Demande : reprendre l'historique depuis la toute première fiche (juin 2018, entrée le 11, brut 1 024,67 = 2/3 de 1 537,01). Constat : le brut se retrouve en proratisant le **montant** avant de tronquer (328 pts × 5 623,23 ÷ 12 × 20/30 = 1 024,6775 → 1 024,67) ; arrondir les points (218,67) donne 1 024,69, d'où l'écart observé.
- Réponses de l'utilisateur : période saisie par date de début / date de fin (11 au 30 = 20 jours) ; proratisation de tout ce qui ne vient pas d'un taux ; servira aussi pour une maladie.
- Fait : bloc « Période payée » (du … au …) en haut de la fenêtre d'une fiche, en jours du mois, **base 30 jours** (le dernier jour du mois, 28 à 31, compte pour le 30 ; `paDays`, `paQ`, `paDim`). Quotité = jours ÷ 30, appliquée par `paCompute(ym, ov, xs, q)` aux lignes points (avant troncature), ACF (avant arrondi) et fixes (arrondi normal) ; les lignes à taux suivent la base proratisée (RAFP : plafond calculé sur le traitement proratisé). Les lignes ponctuelles ne sont pas proratisées. La période est conservée dans la fiche (`slips[m].pr = {d, f}`, absente si mois complet) et respectée par `paRecalcMonth`.
- Comportement : changer la période met à jour les lignes fixes encore au montant du modèle × ancienne quotité (un montant saisi à la main reste), et recalcule les lignes calculées ; une période invalide (début après fin, hors du mois) bloque l'enregistrement ; **un mois proratisé ne pose jamais la question de propagation** au modèle.
- Tests : `test_proratisation` (20 jours, 21 jours, fin de mois, invalide, saisie manuelle conservée, recalcul avec nouvelle valeur du point, retour au mois complet), `test_paie` 307 vérifications, service worker `compte-v59`.
- Non fait : indicateur de période dans la liste des fiches, case « non proratisée » par ligne.

## 2026-11-21 (après-midi) — Bulletin de paye : montants négatifs dans les fiches (version 58)

- Demande : l'utilisateur n'arrive pas à retrouver les montants d'un bulletin réel (CSG déd. 138,55 ; non déd. 48,90 ; CRDS 10,19 ; RAFP 15,37). Analyse du bulletin : base de CSG/CRDS = 2 073,79 = gains 2 064,51 (dont « rappel indemnité compensatrice CSG année courante » 25,62) **plus** 9,28, le « transfert primes/points » étant **négatif** (−9,28), donc une retenue négative qui élargit la base. RAFP : base plafonnée à 20 % du traitement (307,40 × 5 % = 15,37).
- Cause trouvée dans l'app : `saveSlip` et `paLive` forçaient `Math.abs` sur les montants de fiche, donc −9,28 devenait +9,28 (base rétrécie). Corrigé : le signe est conservé dans les fiches (lignes du modèle et ponctuelles) ; le modèle reste en valeur absolue (« le type porte le sens »). Une retenue négative s'ajoute à la base, un gain négatif la réduit.
- Pour reproduire ce bulletin : (1) cocher « Inclure les lignes ponctuelles soumises aux taux » sur CSG déductible, CSG non déductible et CRDS (lignes existantes : décoché par défaut) ; (2) dans la fiche, saisir −9,28 sur « Transfert prime/point » (répondre « Ce mois seulement » à la question de propagation) ; (3) ajouter la ponctuelle « Rappel … » 25,62 en gain, case « Soumise aux taux » cochée.
- Tests : `test_bulletin_reel` (parcours complet de ce bulletin), `test_paie` 291 vérifications. Service worker `compte-v58`.
- Non résolu : CSG non déductible à 137,28 dans une fiche (voir v57), toujours à éclaircir avec l'historique de la ligne.

## 2026-11-21 (reprise, suite 3) — Bulletin de paye : historique daté visible et supprimable (version 57)

- Retour de l'utilisateur : le recalcul (fiche ou global) « n'a rien changé », CSG non déductible à 137,28 au lieu de 47,75 sur tous les mois. Les deux boutons passent par `paCompute` : la valeur est donc bien celle que donne le calcul pour ces mois. Hypothèse (non confirmée) : un ancien taux dans l'historique daté `hist` de la ligne (`paAmt(l, mois)`), invisible jusqu'ici dans l'app.
- Fait : fenêtre d'une ligne du modèle → menu « Historique des valeurs (N) » (« Au départ » / « À partir de mois »), bouton ✕ par entrée (confirmation, recalcul des fiches de la ligne si elle est calculée, `pahistdel`). Service worker `compte-v57`. `test_paie` 276 vérifications.
- À confirmer avec l'utilisateur : ce que montre l'historique de « CSG non déductible ».

## 2026-11-21 (reprise, suite 2) — Bulletin de paye : recalculer toutes les fiches validées (version 56)

- Constat sur captures de l'utilisateur : dans une fiche, CSG non déductible à 137,28 alors que le modèle donne 47,75 (2,4 % × 98,25 % × 2 024,97) ; les autres lignes à taux sont cohérentes ; « tous les mois sont touchés ». Hypothèse : fiches validées qui gardent d'anciens montants calculés (aucun recalcul global n'existait, seulement fiche par fiche ou à la modification d'une ligne). Cause non confirmée : si la valeur reste fausse après le nouveau bouton, regarder l'historique daté (`hist`) de la ligne « CSG non déductible » (ancien taux).
- Fait : bouton « Recalculer toutes les fiches validées » en bas du modèle (visible s'il y a une ligne calculée et au moins une fiche), `paRecalcAll()` : confirmation, recalcul de toutes les lignes calculées de toutes les fiches (fixes et ponctuelles intactes), compte rendu du nombre de montants modifiés. Service worker `compte-v56`. `test_paie` 273 vérifications.
- Question ouverte : « les supprimer définitivement » (mois ignorés ? fiches ? lignes ?) en attente de précision.

## 2026-11-21 (reprise, suite) — Bulletin de paye : supprimer une fiche et ignorer le mois (version 55)

- Demande (proposition de Claude acceptée par l'utilisateur) : à la suppression d'une fiche, choisir entre « remettre à valider » et « supprimer et ignorer », pour ne plus ignorer les mois un par un. Valable en suppression unitaire (fenêtre de la fiche) et en masse (sélection).
- Fait : après la confirmation de suppression, seconde question « Ignorer aussi ce mois / ces N mois ? » (OK = supprimer et ignorer : les mois vont dans `paie.skips` et apparaissent dans « Mois ignorés », remis à valider en un clic ; Annuler = supprimer et remettre à valider, comme avant). `paDelSlips(ms, ignore)`, `paAskIgnore(n)`. Texte d'aide de la sélection mis à jour.
- Tests : `test_paie` 266 vérifications (unitaire : les deux issues ; masse : refus puis ignorer, « Mois ignorés » à 2 lignes), service worker `compte-v55`.
- Toujours non codé : sélection en masse dans « À valider » et « Mois ignorés » (3b), l'utilisateur n'a pas tranché.

## 2026-11-21 (reprise) — Bulletin de paye : suppression dans les fiches validées, ponctuelles soumises aux taux (version 54)

- Réponses de l'utilisateur : (1) oui pour l'option « supprimer aussi des fiches validées » ; (2) rien à coder sur l'écart du bulletin 3 (« non c'est bon ») ; (3c) oui à la case « soumise aux taux » par ponctuelle, pour garder le détail d'une correction sur une ligne séparée sans fausser la base. (3a) traité ensuite (version 55) ; (3b) sélection en masse dans « À valider » et « Mois ignorés » : non codé. Précision de l'utilisateur : son « je ne sais pas » portait sur le fait que toutes les ponctuelles entrent ou non dans un taux, d'où la case.
- Suppression de lignes du modèle (unitaire ou en sélection) : après la confirmation, si des fiches validées contiennent ces lignes, une seconde question propose de les en retirer aussi (OK = retirer, Annuler = fiches conservées). En cas de retrait, les lignes à taux qui avaient la ligne en base ou en plafond (CSG…) sont recalculées dans ces fiches (`paDelLines(ids, inSlips)`, `paAskSlips`, `paSlipsWith`). Sert à nettoyer le doublon ACF (103,09).
- Ponctuelles soumises aux taux : case « Soumise aux taux (CSG, CRDS…) » sur chaque ligne ponctuelle (champ `rated` de la ligne de fiche) ; réglage « Inclure les lignes ponctuelles soumises aux taux » (`xp`) sur chaque ligne à taux, coché par défaut pour une **nouvelle** ligne, décoché pour les lignes existantes (leurs montants ne changent donc pas : à cocher sur CSG déductible, non déductible et CRDS). Une ponctuelle gain s'ajoute à la base, une ponctuelle retenue s'en retranche ; le plafond et le coefficient s'appliquent ensuite. Recalcul en direct dans la fenêtre de fiche, et dans `paRecalcMonth` (la fiche validée garde ses ponctuelles cochées). Changer `xp` compte comme un changement de structure (proposition de recalculer les fiches).
- Tests : `test_paie` 262 vérifications (2 nouvelles fonctions : `test_suppression_fiches_validees`, `test_ponctuelles_taux` ; `test_selection_lignes` et `test_parcours` adaptés à la nouvelle question), 11 suites vertes. Service worker `compte-v54`.
- À vérifier sur appareil : suppression de l'ancienne ligne ACF 103,09 avec retrait des fiches (CSG non déductible attendue 47,75 sur le bulletin concerné), puis cocher « Inclure les lignes ponctuelles » sur les lignes à taux voulues.

## 2026-11-21 (suite) — Bulletin de paye : supprimer vite une ligne ponctuelle (version 53)

- Demande : supprimer une ligne ponctuelle (prime) sans devoir vider son libellé.
- Chaque ligne ponctuelle de la fenêtre d'une fiche a un bouton ✕ qui la retire de la fenêtre ; la suppression devient effective à « Enregistrer » (fermer sans enregistrer ne change rien). Le dispatcher de clics transmet désormais l'élément cliqué à `act(a, ds, el)`.
- Cause du doublon ACF observé chez l'utilisateur (CSG non déductible à 50,18 au lieu de 47,75) : une ancienne ligne ACF en mode « points » d'indice (103,09) coexistait avec la nouvelle ligne « points ACF » (100,93). À supprimer avec « Sélectionner » ; les fiches validées gardent leurs lignes d'origine (option « supprimer aussi des fiches » proposée, en attente de réponse).
- Tests : test_paie 237 vérifications, 11 suites vertes.

## 2026-11-21 — Bulletin de paye : base de calcul triée gains puis retenues (version 52)

- Demande : dans le choix de la base (cases à cocher) d'une ligne à taux, afficher d'abord les gains puis les retenues, mis à jour avec les nouvelles lignes.
- La liste (et la liste du plafond « de la ligne… ») reprend l'ordre du modèle `paOrdered` : gains, puis retenues, puis totaux/information, chacun dans l'ordre réglé avec ▲▼. Elle est reconstruite à chaque ouverture de la fenêtre, donc les lignes créées depuis y figurent à leur place. La ligne modifiée n'y figure pas.
- Tests : test_paie 232 vérifications (`test_ordre_base`), 11 suites vertes.

## 2026-11-20 (suite 3) — Bulletin de paye : valeur du point ACF (version 51)

- Demande : une valeur du point ACF, saisie et datée comme celle du point d'indice.
- Formule déduite des bulletins : points × valeur annuelle **par point** (55,05 €) ÷ 12, **sans** ÷ 100. Vérifié : 22 pts → 100,925 payé 100,93 ; 80 pts → 367,00 ; 40 pts → 183,50 ; 20 pts → 91,75 (ACF technicité / encadrement). Le montant annuel de 1 211,10 € indiqué par l'utilisateur correspond à 22 points × 55,05.
- **Arrondi : normal** pour l'ACF (100,925 → 100,93), contrairement au traitement brut (tronqué). Un seul cas discriminant à ce jour (22 points) : à revérifier sur d'autres bulletins.
- Nouveau champ `paie.acf` ({amount, hist}), nouveau mode de ligne `acf` (« Nombre de points ACF »), ligne « Valeur du point ACF » dans le modèle (même fenêtre de saisie que le point d'indice, valeurs datées, recalcul des fiches validées).
- Tests : test_paie 227 vérifications (fonction `test_point_acf` et quatre cas de calcul). `test_replis` a échoué une fois sur 4 exécutions (comptes « Sans organisme ») puis repassé : test instable, sans lien avec la paie.

## 2026-11-20 (suite 2) — Bulletin de paye : sélectionner et supprimer des lignes du modèle (version 50)

- Demande : pouvoir sélectionner plusieurs lignes du modèle et les supprimer d'un coup (comme pour les fiches validées).
- Mon modèle de bulletin : bouton « Sélectionner » (visible dès qu'il y a une ligne) → cases ☐/☑, « Tout sélectionner / désélectionner », « Annuler », « Supprimer (n) » avec confirmation. En mode sélection, toucher une ligne la coche (elle ne s'ouvre pas), les flèches ▲▼ et la ligne « Valeur du point » sont masquées. Quitter la page abandonne la sélection.
- Les fiches déjà validées sont conservées. Les lignes supprimées sortent des bases et plafonds des lignes à taux ; si une ligne à taux restante n'aurait plus aucune base, la suppression est refusée avec le nom de la ligne concernée. La suppression d'une seule ligne (fenêtre de la ligne) suit la même règle (`paDelLines`).
- Tests : test_paie 214 vérifications (nouvelle fonction `test_selection_lignes`), 11 suites vertes.

## 2026-11-20 (suite) — Points tronqués au centime, retenues retranchées de la base (version 49)

- Constat de l'utilisateur sur ses bulletins réels : 5 623,23 × 328 points donne 1 537,01 sur la fiche, l'app affichait 1 537,02 (arrondi).
- Règle retenue après recoupement de trois bulletins (5 623,23 / 328 → 1 537,01 ; 5 907,34 / 435 → 2 141,41 ; 5 820,04 / 355 → 1 721,76) : **troncature au centime inférieur** du calcul exact (points × valeur ÷ 100 ÷ 12). L'arrondi unique est écarté par le 1er bulletin ; l'arrondi du mois à 2 décimales avant multiplication (468,60 × 3,28) est écarté par les 2e et 3e.
- Mode « taux » inchangé (arrondi normal) : les CSG/CRDS des bulletins 1 et 2 s'y accordent (56,2567 payé 56,26 ; 10,1875 payé 10,19), sous réserve de l'assiette reconstituée.
- **Base d'une ligne à taux** : une retenue cochée est désormais **retranchée** de la base (jusqu'ici elle s'ajoutait). Cas visé : « transfert primes/points », retenue qui vient en déduction de l'assiette CSG (bulletin 1 : −9,28 → base +9,28 ; bulletin 2 : 23,17 → base −23,17, au centime près). Les lignes non soumises (remboursement domicile-travail, forfait télétravail) se décochent de la base.
- **Point ouvert** : bulletin 3, assiette CSG reconstituée ≈ 3 258,60 € contre 3 222,93 € avec les mêmes règles (écart ≈ 35,67 €) ; piste : part employeur ALAN (34,90 €, mutuelle) à inclure, écart résiduel ≈ 0,77 € inexpliqué. Non codé tant que non confirmé.
- Les fiches déjà validées gardent leurs montants : pour les recalculer, ouvrir la ligne de points et l'enregistrer (proposition de recalcul).
- Tests : test_paie 202 vérifications (trois bulletins pour la troncature, base avec retenue retranchée).

## 2026-11-20 — Lignes calculées rétablies, valeur du point base indice 100 ; service worker réparé (version 48)

- Demande : reprendre la version 43 (lignes calculées), la valeur du point étant donnée en base annuelle indice 100, sans aucun arrondi intermédiaire. Traitement brut = points × valeur annuelle ÷ 100 ÷ 12, arrondi au centime une seule fois à la fin (ex. 500 points × 5 623,23 → 2 343,01). La valeur saisie n'est plus arrondie au centime.
- Le reste de la version 43 est rétabli tel quel (modes fixe / points / taux, base cochée, plafond, coefficient, recalcul des fiches), combiné aux ajouts des versions 45 à 47 (mois ignorés, brut / net avant impôt / net à payer / ratio, ordre ▲▼).
- **Défaut corrigé** : `sw.js` était vide depuis la version 46 (une réécriture de ma part l'avait tronqué), donc sans mise en cache hors ligne ni mise à jour fiable. Fichier rétabli depuis la version 45 ; un test vérifie désormais qu'il contient install, activate et fetch.
- Tests : test_paie 198, débordements 282, les 11 suites vertes.

## 2026-11-19 (suite) — Bulletin de paye : lignes calculées (version 43)

- Demande : calculer le traitement brut (valeur du point d'indice × nombre de points) et, pour chaque ligne, choisir « fixe » ou « taux » avec une base cochée dans une liste.
- Ajout de `paie.pt` (valeur annuelle du point, historique daté) et, par ligne, d'un `mode` : `fixed` (montant saisi), `points` (points × valeur ÷ 12) ou `rate` (taux % × base). Base d'une ligne à taux : somme des lignes cochées (`base`), plafond facultatif (`cap` : x % d'une autre ligne), puis coefficient (`coef`, ex. 98,25 % pour la CSG). Les lignes ponctuelles n'entrent jamais dans une base.
- `paCompute` évalue le tout avec détection des boucles (refusées à la saisie) ; `paRecalcMonth` / `paRecalcSlips` recalculent les lignes calculées des fiches validées après un changement (valeur du point, points, taux, base, ligne fixe propagée aux mois suivants).
- Fiche : les lignes calculées se recalculent en direct quand on change une ligne fixe d'une nouvelle fiche ; une fiche déjà validée est traitée comme saisie à la main (bouton « Recalculer les lignes calculées »). Une correction manuelle d'une ligne calculée reste propre à la fiche (pas de question de propagation).
- Choix à confirmer avec l'utilisateur : la Retenue PC IMT reste fixe (taux et base inconnus) ; le « transfert primes/points » se saisit comme un gain.
- Tests : 31 vérifications ajoutées (test_paie 174, test_debordements 282), 11 suites vertes.

## État actuel (2026-11-19)

- **Version 53** : bouton ✕ sur les lignes ponctuelles. **Version 52** : base et plafond triés gains / retenues / totaux. **Version 51** : valeur du point ACF et lignes « points ACF ». **Version 50** : sélection et suppression de plusieurs lignes du modèle de bulletin. **Version 49** : points tronqués au centime (règle des bulletins DGFiP), retenues cochées retranchées de la base d'une ligne à taux. **Version 48** : lignes calculées rétablies (valeur du point base indice 100, un seul arrondi), service worker réparé. **Version 47** : ordre des lignes du modèle réglable (▲▼). **Version 46** : fiches validées avec brut, net avant impôt, net à payer et retenues en % du brut. **Version 45** : bulletin de paye, section « Mois ignorés » pour les remettre à valider. **Version 44** : retour au bulletin de paye de la version 42 (lignes calculées retirées). **Version 42** : Bulletin de paye, l'affichage du « net à payer » lu dans une ligne (version 40) est retiré : seul le net calculé s'affiche ; 143 vérifications sur le module. **Version 41** : net calculé (gains − retenues) sur chaque fiche de paye, et montants des cartes de chiffres de l'Accueil alignés ; 149 vérifications sur le module, 36 sur l'Accueil. **Version 40** : Bulletin de paye, le net à payer s'affiche sur chaque fiche validée (et en haut de la fiche ouverte) ; 143 vérifications sur le module. **Version 39** : Bulletin de paye, une ligne créée dans le modèle est proposée aux fiches déjà validées (elle ne reste plus vide) ; 133 vérifications sur le module. **Version 38** : Bulletin de paye, sélection de fiches pour les supprimer (bouton « Sélectionner » dans Fiches validées) ; 122 vérifications sur le module, 258 d'affichage. **Version 37** : Bulletin de paye, **un changement de montant vaut pour les mois suivants** (comme les récurrences) ; 252 vérifications d'affichage et 106 sur le module. **Version 36** : module **Bulletin de paye** (suivi de l'évolution de chaque ligne du bulletin, à part des comptes ; nouvelle suite `tests/test_paie.py`, 11 suites, toutes vertes). **À valider sur iPhone et iPad** : la vue (page ouverte depuis Récurrent), les sélecteurs de mois (deux listes), le tableau à trois mois. Version 35 (audit des débordements d'écran : grilles de l'Accueil, bannière Hors ligne ; nouvelle suite `tests/test_debordements.py`, 10 suites, toutes vertes) ; version 34 (champs date iPhone) ; version 33 : patrimoine net (carte repliée sur l'Accueil), types « Épargne bloquée » et « Bien ». 9 suites de tests, toutes vertes (`tests/test_patrimoine.py` : 37 vérifications). Points ouverts : voir l'entrée du 2026-11-19.

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

## 2026-11-19 (nuit, suite 3) — Bulletin de paye : ordre des lignes du modèle (version 47)

- Demande : pouvoir classer le modèle de fiche. Choix de l'utilisateur : ordre à la main.
- Flèches ▲▼ sur chaque ligne du modèle : elles échangent la ligne avec sa voisine du même type (`paMove`). L'ordre s'affiche par type (gains, retenues, totaux) puis dans l'ordre choisi (`paOrdered`) ; il vaut pour le modèle, le tableau, la courbe et les fiches. Montants et fiches inchangés.
- Précision donnée à l'utilisateur : le type « Total / information » sert aux lignes imprimées qui ne s'additionnent pas (brut, net imposable, bases, plafonds, net imprimé) ; elles sont suivies mais n'entrent dans aucun total.
- Tests : `test_ordre_modele` (test_paie 167 vérifications).

## 2026-11-19 (nuit, suite 2) — Bulletin de paye : brut, net avant impôt, net à payer, ratio (version 46)

- Demande : afficher sur chaque fiche validée le brut (tous les gains), le net avant impôt (sans le prélèvement à la source), le net à payer (net global) et le ratio gain/retenues.
- `paSums(rows)` : brut = somme des gains ; net à payer = gains − retenues (l'ancien « net calculé ») ; net avant impôt = net à payer + ligne de retenue dont le libellé est « Prélèvement à la source » (insensible aux accents et à la casse, `paIsPas`) ; ratio = retenues ÷ brut, en % à une décimale. Choix de l'utilisateur : le PAS est repéré par son libellé, le ratio est exprimé en retenues en % du brut, affichage dans la liste des fiches validées.
- Sans ligne PAS, le net avant impôt s'affiche « — » ; sans gain, aucun total n'est affiché. L'intitulé « Net calculé » devient « Net à payer » dans la liste.
- Tests : `test_totaux_fiche` (test_paie 158 vérifications) ; débordements 258, tous verts.

## 2026-11-19 (nuit, suite) — Bulletin de paye : remettre à valider les mois ignorés (version 45)

- Constat : l'utilisateur ne voyait ses fiches qu'à partir de février 2019 alors que ses lignes commencent en juillet 2018. Aucune limite dans le code (101 fiches affichées au test) : les premiers mois étaient dans `paie.skips` (ignorés), ni à valider ni validés.
- Ajout, dans « Fiches validées », d'une section « Mois ignorés » avec « Remettre à valider » (par mois) et « Tout remettre à valider ».
- Tests : `test_mois_ignores` (test_paie).

## 2026-11-19 (nuit) — Retour au bulletin de paye de la version 42 (version 44)

- Les lignes calculées de la version 43 (valeur du point, points, taux sur base cochée, plafond) sont retirées à la demande de l'utilisateur : trop compliqué. Le code est celui de la version 42 ; le numéro passe à 44 pour que les appareils rechargent l'app.
- Les champs `paie.pt` et `mode` éventuellement enregistrés par la version 43 sont ignorés et sans effet. Les montants des lignes restent saisis à la main.

## 2026-11-19 — Retrait du « net à payer » lu dans une ligne, net calculé seul (version 42)

- Retour de l'utilisateur : le « net à payer » demandé correspondait au **net calculé**, pas à une ligne en particulier ; il faut enlever l'affichage fondé sur une ligne.
- Réalisé : suppression de `paNetRow` (lecture d'une ligne « net à payer » ou « net » par son libellé), du message d'aide « nomme une ligne Net à payer » et de la ligne « Net à payer enregistré » en tête de la fiche ouverte. La liste des fiches affiche désormais **un seul montant, le net calculé** (gains − retenues, `paNet`), étiqueté « Net calculé » ; tiret si la fiche n'a aucune ligne de gain. La fiche ouverte rappelle « Net calculé : X € (gains − retenues) ». Aucune ligne n'est plus lue d'après son nom.
- Tests : `test_net_a_payer` supprimé, `test_net_calcule` réécrit (12 vérifications : calcul, brut et net saisis ignorés, pas de message d'aide, fiche ouverte, tiret sans gain, négatif).

## 2026-11-19 — Net calculé sur les fiches, montants de l'Accueil alignés (version 41)

- Note : un commit de la version 40 (net à payer saisi affiché sur chaque fiche, `paNetRow`) était déjà sur main sans avoir été fait dans cette conversation ; j'ai construit dessus sans rien écraser.
- Demande 1 : « le montant total de chaque fiche ». Choix de l'utilisateur : **le net calculé**. Réalisé : `paNet` = somme des lignes de gain − somme des lignes de retenue (les lignes « total / information » ne comptent pas), affiché sous le net à payer saisi (« calculé : X € ») dans la liste des fiches ; sans ligne « net à payer », le tiret reste et le net calculé s'affiche quand même ; **jamais affiché si la fiche n'a aucune ligne de gain** (sinon on lirait un montant négatif inventé). Il peut différer du net à payer imprimé (lignes de base et de plafond qui ne s'additionnent pas).
- Demande 2 : sur l'Accueil, le solde prévu en fin de mois « plus haut que celui d'à côté, pas esthétique ». Cause : quand le libellé d'une carte passe sur deux lignes (« Solde des comptes cochés » sur écran étroit), le montant de sa voisine remontait de 16 à 17 px. Correction : les cartes de la grille (`.grid .card`) sont en colonne avec le libellé en haut et le montant en bas (`justify-content:space-between`), donc les montants d'une même rangée sont alignés. La carte « Solde prévu fin de mois » n'a pas été déplacée (elle reste à côté de « Recettes » quand « Reste à vivre » s'affiche) ; son calcul n'a pas changé.
- Vérifié : sans le correctif le décalage existe (mesuré à 390 et 320 px), avec il est nul.
- Tests : `test_net_calcule` (6 vérifications) dans `tests/test_paie.py` ; `test_alignement_montants` (9 vérifications, 390 à 320 px) dans `tests/test_comptes_accueil.py`.

## 2026-11-19 — Bulletin de paye : net à payer sur chaque fiche (version 40)

- Demande : afficher le montant net à payer sur chaque fiche.
- Réalisé : `paNetRow` retrouve la ligne du net : la **dernière** ligne dont le libellé contient « net à payer » (casse, accents et ponctuation ignorés), sinon la dernière ligne de type total dont le libellé contient « net ». Elle s'affiche en gras à droite de chaque fiche de « Fiches validées » (étiquette « Net à payer ») et en haut de la fiche ouverte. Sans ligne trouvée : un tiret (jamais un autre total à la place) ; si aucune fiche n'a de net, un message invite à nommer une ligne « Net à payer » dans le modèle.
- Choix fait sans question : plusieurs lignes « net à payer » (avant et après impôt, par exemple) → la dernière de la fiche l'emporte.
- Tests : `test_net_a_payer` (10 vérifications) dans `tests/test_paie.py`.

## 2026-11-19 — Bulletin de paye : une nouvelle ligne du modèle n'est plus vide (version 39)

- Retour de l'utilisateur : « dans le modèle, ça crée la ligne mais vide ». Cause : une ligne créée avec un mois de départ déjà couvert par des fiches validées n'apparaissait ni dans « À valider » (le mois a déjà sa fiche) ni dans les fiches existantes.
- Réalisé : à l'enregistrement d'une ligne du modèle, si des fiches déjà validées sont couvertes par la ligne (nouvelle ligne, début avancé, fin repoussée) et ne la contiennent pas, l'app propose de l'y ajouter avec le montant du modèle de chaque mois (confirmation avec le nombre de fiches et la période). Refus : la ligne est créée, les fiches restent intactes. Aucune question si la période couverte ne change pas : un mois laissé vide volontairement dans une fiche n'est pas ré-ajouté à chaque modification de la ligne.
- Tests : `test_ligne_dans_fiches_existantes` (11 vérifications) dans `tests/test_paie.py`.
- Point en suspens : le cas d'une ligne ajoutée dans une fiche (ponctuelle) ne se répète pas, comme décidé ; l'utilisateur a confirmé qu'il s'agissait du modèle.

## 2026-11-19 — Bulletin de paye : sélection et suppression de fiches (version 38)

- Demande : pouvoir sélectionner des fiches de paye pour les supprimer (erreur de saisie).
- Réalisé : dans « Fiches validées », bouton « Sélectionner » → cases ☐/☑ sur chaque fiche (toucher une fiche la coche, elle ne s'ouvre pas), « Tout sélectionner / désélectionner », « Annuler », « Supprimer (N) » (désactivé à 0, confirmation avec le nombre). État `paSelM` (ensemble de mois, hors des données, abandonné en quittant la page). Les mois supprimés reviennent dans « À valider » tant que le modèle les couvre (pour les ressaisir) ; le modèle n'est pas touché.
- Tests : `test_selection_suppression` (16 vérifications) dans `tests/test_paie.py` ; vue en sélection ajoutée à `tests/test_debordements.py`.
- Point ouvert : l'utilisateur a signalé qu'après avoir « écrit une nouvelle ligne » il n'y avait « aucune récurrence » ; en attente de sa réponse pour savoir s'il s'agit d'une ligne ajoutée dans une fiche (ponctuelle, qui ne se répète pas) ou d'une ligne ajoutée au modèle (aucun mois à valider quand les fiches existent déjà).

## 2026-11-19 — Bulletin de paye : un changement vaut pour les mois suivants (version 37)

- Retour de l'utilisateur : « modifier une écriture et que la modification court pour les suivantes » (mois 1 = 1000, mois 3 passé à 1500 : les mois 4, 5, 6… passent à 1500). Cela **remplace** mon choix de la version 36 (les fiches validées ne changeaient pas).
- Choix de l'utilisateur : (1) la propagation est proposée, « ce mois seulement » restant possible pour une variation ponctuelle ; (2) pas de règle compliquée : il reprend ses bulletins dans l'ordre, donc les fiches suivantes déjà validées sont simplement écrasées ; (3) les lignes ponctuelles (primes) ne se propagent jamais.
- Réalisé : à l'enregistrement d'une fiche, si le montant d'une ligne du modèle diffère de sa valeur d'avant (fiche existante) ou du modèle (fiche nouvelle), une seconde fenêtre (`openPropag`) demande pour chaque ligne « À partir de ce mois » (choix par défaut) ou « Ce mois seulement », avec le nombre de fiches suivantes touchées et un motif facultatif ; « Retour » rouvre la fiche avec les valeurs saisies. « À partir de ce mois » (`paApply`) ajoute l'entrée datée à l'historique du modèle et met à jour les fiches validées de ce mois et des suivants ; les mois à venir sont pré-remplis au nouveau montant. Même règle depuis la fenêtre d'une ligne du modèle (avec confirmation du nombre de fiches touchées, comme les récurrences).
- Une fiche rouverte et enregistrée sans toucher à un montant ne pose aucune question (comparaison avec la valeur de la fiche, pas avec le modèle) : une variation ponctuelle déjà saisie n'est pas « corrigée » par erreur.
- Limite connue : un changement daté enregistré plus tard dans l'historique (un échelon au mois 6, par exemple) est écrasé par une correction faite au mois 3, comme pour les récurrences.
- Tests : 20 vérifications de plus dans `tests/test_paie.py` (106), la nouvelle fenêtre ajoutée à `tests/test_debordements.py` (252) ; les autres suites inchangées et vertes.

## 2026-11-19 — Module Bulletin de paye (version 36)

- Demande : suivre l'évolution de la paie, ligne par ligne. Idée de départ (un groupe « Bulletin de paye » et un compte par ligne, avec des virements pour le solde) **écartée** : une ligne de bulletin est un flux, pas un endroit où il y a de l'argent ; il aurait fallu 15 à 25 virements par mois, et les faux comptes auraient faussé patrimoine, soldes cochés et budget du jour.
- Choix de l'utilisateur : un module séparé calqué sur les récurrences (le brut se répète chaque mois jusqu'à changement de montant) ; saisie de toutes les lignes à la main (brut, retenues, net à payer…) ; but = suivre l'évolution ; tableau **et** courbes ; lignes ponctuelles possibles (primes) ; changements de grade / d'échelon.
- Réalisé : `S.paie` = `lines` (modèle : libellé, type gain / retenue / total-information, montant, mois de début et de fin facultatif, historique de montants datés `hist` avec motif facultatif), `slips` (fiches validées par mois : lignes figées), `skips` (mois ignorés). Page ouverte depuis une carte de Récurrent (vue `paie`, onglet Récurrent resté actif) : « À valider » (Valider, Ignorer, « Tout valider avec les montants du modèle » pour rattraper des mois), tableau (3 mois à la fois, flèches pour reculer ; montant différent de la fiche précédente en gras et en couleur), courbe d'une ligne au choix (touche un point pour lire sa valeur, écart avec le mois précédent), historique de la ligne avec les motifs, fiches validées modifiables ou supprimables, modèle de lignes. Champ `paie` ajouté aux champs synchronisés (ligne `meta`).
- Choix faits sans question (modifiables) : un changement de montant du modèle ne touche **pas** les fiches déjà validées (c'est du réel) ; les mois pas encore validés prennent le nouveau montant ; une ligne supprimée du modèle reste dans les fiches ; la fiche d'un mois ne se propose qu'à partir du début du mois ; les montants se saisissent comme sur le bulletin (valeur absolue, le type donne le sens) ; sélecteurs de mois en deux listes (pas de champ `month` de Safari).
- Aucun effet sur les comptes, soldes, lignes, récurrences, budget du jour, patrimoine (vérifié par les tests).
- Tests : `tests/test_paie.py` (86 vérifications : données, parcours complet, contrôles de formulaire, synchronisation chiffrée) ; `tests/test_debordements.py` étendue à la vue et aux 4 fenêtres du module (246 vérifications, 390 à 320 px, montants à six chiffres).
- Pas fait (possibles ensuite) : contrôle d'écart brut − retenues = net, ordre des lignes modifiable, export tableur de l'évolution, saisie depuis un bulletin PDF.

## 2026-11-19 — Audit des débordements d'écran (version 35)

- Demande : vérifier qu'il n'y a pas d'autres endroits qui dépassent de la taille de l'écran (suite du champ date de « Paie de… »).
- Méthode : nouvelle suite `tests/test_debordements.py`. Pour 390, 375, 360 et 320 px, charge des données volontairement longues (noms de compte, libellés, organisme, montants à 5 puis 6 chiffres) et passe en revue 5 vues, Lignes en sélection, Import avec fichier, rappel de sauvegarde + bannière Hors ligne, 13 fenêtres et les 7 types de compte. Repère : défilement horizontal de la page, élément hors écran, élément hors de sa carte, contenu coupé (hors « … » voulu et hors champs de saisie).
- Trouvé et corrigé : (1) Accueil : les cartes « Reste à vivre » / « Recettes » et la 3ᵉ colonne du Budget du jour sortaient de l'écran dès 375 px avec des montants à 5 chiffres négatifs (grilles `1fr` qui ne rétrécissaient pas) ; à 360 px la page entière s'élargissait et le bouton « Réglages » sortait de l'écran, et toutes les fenêtres s'élargissaient avec la page → grilles en `minmax(0,1fr)`, chiffres en `clamp()` + retour à la ligne. (2) Bannière « Hors ligne » tronquée par « … » à 375 px et moins → elle passe à la ligne.
- Vérifié sans problème : toutes les fenêtres (champs date compris) à 390, 375, 360 et 320 px ; vue Import ; Réglages dépliés.
- Limite : Chromium, pas Safari iOS réel (comportement de `type=date` à confirmer sur l'iPhone, comme pour la version 34).
- Libellés de lignes, de comptes et de règles : toujours coupés par « … » dans les listes (voulu) ; le nom complet est dans la fenêtre de modification.

## 2026-11-19 — Champs date : débordement sur iPhone 16e (version 34)

- Constat (capture de l'utilisateur) : dans la fenêtre « Paie de … », le champ date dépassait à droite de l'écran sur iPhone 16e. Cause probable : largeur propre des champs date de Safari iOS.
- Correction : `input[type=date]` en `appearance:none`, `min-width:0`, `max-width:100%`, centré ; fenêtres sans défilement horizontal. Vérifié à 390 px de large dans Chromium (champ à l'intérieur de la fenêtre) ; **non vérifiable ici sur Safari iOS réel : à confirmer sur l'iPhone**.
- Aussi : la règle de paie (octobre 2026 = 28, octobre 2027 = 27) était correcte, c'était octobre 2027 sur la capture.

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
