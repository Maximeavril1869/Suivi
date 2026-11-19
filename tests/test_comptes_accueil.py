"""Tests : choix des comptes dans une carte repliable groupée par organisme (Accueil, Lignes, Récurrent), Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : comptes et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_comptes_accueil.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402


def norm(t):
    return t.replace('\u202f', ' ').replace('\xa0', ' ')


def etat(pg, groupes=True, nb=3):
    def compte(i, nom, type_, solde, g):
        c = {'id': 'a%d' % i, 'name': nom, 'type': type_, 'opening': 0, 'cash': type_ == 'courant', 'anchor': {'date': '2020-01-01', 'amount': solde}}
        if groupes and g:
            c['group'] = g
        return c
    comptes = [compte(1, 'Compte test A', 'courant', 1000, 'Banque Alpha'), compte(2, 'Livret test', 'livret', 500, 'Banque Alpha'), compte(3, 'Compte test B', 'courant', 200, 'Banque Beta')][:nb]
    s = {'v': 2, 'accounts': comptes, 'shown': [c['id'] for c in comptes], 'tx': [], 'rec': [], 'plans': [], 'rules': [], 'budgets': {}, 'payDates': {}, 'csvMaps': {}, 'skips': []}
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    pg.reload()


def titre(pg):
    return norm(pg.inner_text('details[data-fold=hacc] > summary'))


def test_carte(browser):
    print('Accueil : carte « Comptes » repliable')
    pg = device(browser, FauxSupabase())
    etat(pg)
    pg.click('[data-a=nav][data-v=home]')
    check('plus de rangée de puces sur l’Accueil', pg.evaluate("() => document.querySelectorAll('#app .chip').length") == 0)
    check('carte repliée au démarrage', pg.evaluate("() => document.querySelector('details[data-fold=hacc]').open") is False)
    check('titre replié : nombre de comptes et solde total', 'Comptes : 3 sur 3' in titre(pg) and '1 700,00' in titre(pg), titre(pg))
    check('comptes masqués tant que la carte est repliée', not pg.is_visible('text=Livret test'))
    pg.click('details[data-fold=hacc] > summary')
    check('dépliée : un groupe par organisme, ouverts par défaut', pg.evaluate("() => [...document.querySelectorAll('details[data-fold^=\"h:\"]')].map((d) => d.open)") == [True, True])
    check('dépliée : tous les comptes avec leur case et leur solde', all(x in norm(pg.inner_text('details[data-fold=hacc]')) for x in ['☑ Compte test A', '☑ Livret test', '☑ Compte test B', '1 000,00', '500,00', '200,00', 'Banque Alpha', 'Banque Beta']))
    pg.click('[data-a=togacc][data-id=a2]')
    check('décocher un compte : titre mis à jour (2 sur 3, solde 1 200,00)', 'Comptes : 2 sur 3' in titre(pg) and '1 200,00' in titre(pg), titre(pg))
    check('la carte reste dépliée après un clic sur un compte', pg.evaluate("() => document.querySelector('details[data-fold=hacc]').open") is True)
    check('la case du compte décoché est vide', '☐ Livret test' in norm(pg.inner_text('details[data-fold=hacc]')))
    pg.click('[data-a=allacc][data-v="0"]')
    check('Tout décocher : 0 sur 3', 'Comptes : 0 sur 3' in titre(pg) and pg.evaluate("() => S.shown.length") == 0, titre(pg))
    pg.click('[data-a=allacc][data-v="1"]')
    check('Tout cocher : 3 sur 3', 'Comptes : 3 sur 3' in titre(pg) and pg.evaluate("() => S.shown.length") == 3, titre(pg))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_groupes_et_pages(browser):
    print('Groupes repliables ; même carte sur Lignes et Récurrent ; état conservé')
    pg = device(browser, FauxSupabase())
    etat(pg)
    pg.click('[data-a=nav][data-v=home]')
    pg.click('details[data-fold=hacc] > summary')
    pg.click('details[data-fold="h:Banque Alpha"] > summary')
    check('replier un organisme masque ses comptes', not pg.is_visible('text=Livret test') and pg.is_visible('text=Compte test B'))
    pg.click('[data-a=togacc][data-id=a3]')
    check('l’état des groupes survit à un clic sur un compte', pg.evaluate("() => document.querySelector('details[data-fold=\"h:Banque Alpha\"]').open") is False)
    pg.click('[data-a=togacc][data-id=a3]')
    for v in ['tx', 'rec']:
        pg.click('[data-a=nav][data-v=%s]' % v)
        check('page %s : même carte repliable, au même état (dépliée), 3 comptes' % v, pg.evaluate("() => [document.querySelector('details[data-fold=hacc]').open, document.querySelectorAll('details[data-fold=hacc] [data-a=togacc]').length]") == [True, 3])
        check('page %s : le groupe replié sur l’Accueil l’est aussi ici' % v, pg.evaluate("() => document.querySelector('details[data-fold=\"h:Banque Alpha\"]').open") is False)
    pg.click('[data-a=nav][data-v=tx]')
    pg.click('[data-a=togacc][data-id=a3]')
    check('Lignes : cocher / décocher fonctionne et met à jour le titre', 'Comptes : 2 sur 3' in titre(pg), titre(pg))
    pg.click('[data-a=togacc][data-id=a3]')
    pg.click('[data-a=nav][data-v=rec]')
    pg.click('[data-a=togacc][data-id=a3]')
    check('Récurrent : cocher / décocher fonctionne et met à jour le titre', 'Comptes : 2 sur 3' in titre(pg), titre(pg))
    pg.click('[data-a=togacc][data-id=a3]')
    pg.click('[data-a=nav][data-v=home]')
    pg.click('details[data-fold="h:Banque Alpha"] > summary')
    pg.click('[data-a=togacc][data-id=a1]')
    pg.click('details[data-fold="h:Banque Alpha"] > summary')
    pg.click('[data-a=nav][data-v=tx]')
    check('le choix des comptes de l’Accueil s’applique aux autres pages (2 sur 3)', 'Comptes : 2 sur 3' in titre(pg), titre(pg))
    pg.click('[data-a=nav][data-v=home]')
    pg.reload()
    pg.click('[data-a=nav][data-v=home]')
    check('après rechargement : carte dépliée comme laissée, groupe replié', pg.evaluate("() => [document.querySelector('details[data-fold=hacc]').open, document.querySelector('details[data-fold=\"h:Banque Alpha\"]').open]") == [True, False])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_sans_groupe(browser):
    print('Accueil : sans organisme, un seul compte')
    pg = device(browser, FauxSupabase())
    etat(pg, groupes=False)
    pg.click('[data-a=nav][data-v=home]')
    pg.click('details[data-fold=hacc] > summary')
    check('sans organisme : liste plate, pas de groupe', pg.evaluate("() => document.querySelectorAll('details[data-fold^=\"h:\"]').length") == 0)
    check('sans organisme : les trois comptes sont listés', pg.evaluate("() => document.querySelectorAll('details[data-fold=hacc] [data-a=togacc]').length") == 3)
    etat(pg, nb=1)
    pg.click('[data-a=nav][data-v=home]')
    check('un seul compte : pas de carte de choix', pg.evaluate("() => document.querySelectorAll('details[data-fold=hacc]').length") == 0)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_carte(browser)
        test_groupes_et_pages(browser)
        test_sans_groupe(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
