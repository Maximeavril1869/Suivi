"""Tests : cartes de crédit (solde = montant encore disponible, dette = plafond − solde), Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : noms de comptes et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_cartes_credit.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402


def etat(pg, solde, plafond=3000, tx=None, courant=1000, cash=False):
    s = {
        'v': 2,
        'accounts': [
            {'id': 'a1', 'name': 'Compte test', 'type': 'courant', 'opening': 0, 'cash': True, 'anchor': {'date': '2020-01-01', 'amount': courant}},
            {'id': 'a2', 'name': 'Carte test', 'type': 'credit', 'opening': 0, 'cash': cash, 'limit': plafond,
             'anchor': {'date': '2020-01-01', 'amount': solde}},
        ],
        'shown': ['a1', 'a2'], 'tx': tx or [], 'rec': [], 'plans': [], 'rules': [], 'budgets': {}, 'csvMaps': {}, 'skips': [],
    }
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()


def info(pg):
    return pg.evaluate("() => { const c = creditInfo(accById('a2')); return [c.lim, c.due, c.avail]; }")


def test_calcul(browser):
    print('Carte de crédit : dette = plafond − solde')
    pg = device(browser, FauxSupabase())
    etat(pg, 2500)
    check('plafond 3000, solde 2500 : dû 500, disponible 2500 (et non 5500)', info(pg) == [3000, 500, 2500], info(pg))
    etat(pg, 3000)
    check('solde = plafond : aucune dette', info(pg) == [3000, 0, 3000], info(pg))
    etat(pg, 0)
    check('solde nul : toute la carte est utilisée', info(pg) == [3000, 3000, 0], info(pg))
    etat(pg, -200)
    check('solde négatif : plafond dépassé, dû supérieur au plafond', info(pg) == [3000, 3200, -200], info(pg))
    etat(pg, 3200)
    check('solde au-dessus du plafond : pas de dette négative', info(pg)[1] == 0, info(pg))
    etat(pg, 2500.1)
    check('pas d’erreur d’arrondi (centimes)', info(pg)[1] == 499.9, info(pg))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_mouvements(browser):
    print('Carte de crédit : achats et remboursements')
    pg = device(browser, FauxSupabase())
    achat = {'id': 't1', 'date': '2026-11-05', 'label': 'Achat test', 'amount': -300, 'cat': 'Divers', 'sub': 'Non classé', 'acc': 'a2', 'payee': ''}
    etat(pg, 2500, tx=[achat])
    check('un achat fait baisser le disponible et monter la dette', info(pg) == [3000, 800, 2200], info(pg))
    rembt = {'id': 't2', 'date': '2026-11-10', 'label': 'Remboursement test', 'amount': 500, 'cat': 'Divers', 'sub': 'Non classé', 'acc': 'a2', 'payee': ''}
    etat(pg, 2500, tx=[achat, rembt])
    check('un remboursement fait remonter le disponible et baisser la dette', info(pg) == [3000, 300, 2700], info(pg))


def totaux(pg):
    return pg.evaluate("() => [balanceAt(today(), false), balanceAt(today(), true), withBalance().slice(-1)[0].bal]")


def test_totaux(browser):
    print('Carte de crédit : poids dans les totaux (solde des comptes cochés, reste à vivre)')
    pg = device(browser, FauxSupabase())
    etat(pg, 2500, courant=1000, cash=False)
    t = totaux(pg)
    check('solde des comptes cochés : 1000 − 500 de dette = 500 (et non 3500)', t[0] == 500, t)
    check('carte hors reste à vivre : reste à vivre = 1000', t[1] == 1000, t)
    check('solde courant de la liste des lignes = solde des comptes cochés', t[2] == 500, t)
    etat(pg, 2500, courant=1000, cash=True)
    t = totaux(pg)
    check('carte comptée dans le reste à vivre : sa dette (−500) est déduite, reste à vivre = 500', t[1] == 500, t)
    etat(pg, 3000, courant=1000, cash=True)
    check('carte pleine (aucune dette) : aucun effet sur les totaux', totaux(pg)[:2] == [1000, 1000], totaux(pg))
    pg.evaluate("() => { S.shown = ['a1']; }")
    check('carte décochée : n’entre pas dans le total', pg.evaluate("() => balanceAt(today(), false)") == 1000)
    etat(pg, 2500, courant=1000, cash=False)
    pg.click('[data-a=nav][data-v=home]')
    txt = pg.inner_text('#app').replace('\u202f', ' ').replace('\xa0', ' ')
    check('Accueil : « Solde des comptes cochés » 500,00 et « Reste à vivre » 1 000,00', '500,00' in txt and '1 000,00' in txt and '3 500' not in txt, txt)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_affichage(browser):
    print('Carte de crédit : affichage')
    pg = device(browser, FauxSupabase())
    etat(pg, 2500)
    pg.click('[data-a=nav][data-v=home]')
    txt = pg.inner_text('#app')
    check('Accueil : plafond 3 000, utilisé 500, disponible 2 500', all(x in txt.replace(' ', ' ').replace('\xa0', ' ') for x in ['3 000,00', '500,00', '2 500,00']) and '5 500' not in txt.replace(' ', ' ').replace('\xa0', ' '), txt)
    pg.click('[data-a=nav][data-v=set]')
    pg.click('details[data-fold=comptes] > summary')
    ligne = pg.inner_text('[data-a=editacc][data-id=a2]').replace(' ', ' ').replace('\xa0', ' ')
    check('Réglages : la ligne de la carte indique dû 500 et disponible 2 500', 'dû 500,00' in ligne and 'disponible 2 500,00' in ligne, ligne)
    pg.click('[data-a=editacc][data-id=a2]')
    check('la fiche explique le solde d’une carte de crédit (montant disponible)', 'ce qu\'il te reste à utiliser' in pg.inner_text('.sheet'))
    pg.click('[data-a=closem]')
    pg.click('[data-a=newacc]')
    check('nouveau compte : « Compter dans le reste à vivre » coché au départ', pg.is_checked('#ac_cash'))
    pg.select_option('#ac_type', 'credit')
    check('choisir « Carte de crédit » décoche « Compter dans le reste à vivre »', not pg.is_checked('#ac_cash'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_calcul(browser)
        test_mouvements(browser)
        test_totaux(browser)
        test_affichage(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
