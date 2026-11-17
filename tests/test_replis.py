"""Tests : menus repliables de Réglages (cartes et groupes d'organismes), Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : noms de comptes et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_replis.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402

CARTES = ['comptes', 'budgets', 'regles', 'sync', 'sauvegarde', 'danger']


def etat_replis(pg):
    """{clé: ouvert ?} d'après le DOM."""
    return pg.evaluate("() => Object.fromEntries([...document.querySelectorAll('details[data-fold]')].map((d) => [d.dataset.fold, d.open]))")


def comptes_demo(pg, groupes=True):
    s = {
        'v': 2,
        'accounts': [
            {'id': 'a1', 'name': 'Compte test A', 'type': 'courant', 'opening': 0, 'cash': True, **({'group': 'Banque Alpha'} if groupes else {})},
            {'id': 'a2', 'name': 'Livret test', 'type': 'livret', 'opening': 0, 'cash': False, **({'group': 'Banque Alpha'} if groupes else {})},
            {'id': 'a3', 'name': 'Compte test B', 'type': 'courant', 'opening': 0, 'cash': True, **({'group': 'Banque Beta'} if groupes else {})},
        ],
        'shown': ['a1', 'a2', 'a3'], 'tx': [], 'rec': [], 'plans': [], 'rules': [], 'budgets': {}, 'csvMaps': {}, 'skips': [],
    }
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()


def test_cartes(browser):
    print('Réglages : cartes repliables')
    pg = device(browser, FauxSupabase())
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    comptes_demo(pg, groupes=False)
    pg.click('[data-a=nav][data-v=set]')
    e = etat_replis(pg)
    check('les six cartes sont repliables', sorted(e) == sorted(CARTES), e)
    check('par défaut : Comptes ouverte, les autres repliées', e['comptes'] and not any(e[k] for k in CARTES if k != 'comptes'), e)
    check('une carte repliée masque son contenu', not pg.is_visible('[data-a=newrule]'))
    pg.click('details[data-fold=regles] > summary')
    check('toucher le titre déplie la carte', pg.is_visible('[data-a=newrule]'))
    pg.click('details[data-fold=comptes] > summary')
    check('toucher le titre replie la carte', not pg.is_visible('[data-a=newacc]'))
    pg.wait_for_timeout(100)
    pg.evaluate("() => render()")   # reconstruction complète de l'écran (comme le fait l'app après une action)
    e = etat_replis(pg)
    check('l’état survit à un nouveau rendu', e['regles'] and not e['comptes'], e)
    pg.click('[data-a=nav][data-v=home]')
    pg.click('[data-a=nav][data-v=set]')
    e = etat_replis(pg)
    check('l’état survit à un changement d’onglet', e['regles'] and not e['comptes'], e)
    pg.reload()
    pg.click('[data-a=nav][data-v=set]')
    e = etat_replis(pg)
    check('l’état survit à un rechargement de l’app', e['regles'] and not e['comptes'], e)
    check('l’état est propre à l’appareil : absent des données synchronisées', 'compte-replis' not in json.dumps(pg.evaluate("() => S")) and 'regles' not in pg.evaluate("() => Object.keys(S)"))
    pg.evaluate("() => { localStorage.setItem('compte-replis', '{ pas du json'); }")
    pg.reload()
    pg.click('[data-a=nav][data-v=set]')
    check('un état illisible retombe sur les valeurs par défaut', etat_replis(pg)['comptes'])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_organismes(browser):
    print('Réglages : groupes d’organismes repliables')
    pg = device(browser, FauxSupabase())
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    comptes_demo(pg)
    pg.click('[data-a=nav][data-v=set]')
    e = etat_replis(pg)
    check('un groupe par organisme', 'g:Banque Alpha' in e and 'g:Banque Beta' in e, e)
    check('groupes ouverts par défaut', e['g:Banque Alpha'] and e['g:Banque Beta'])
    check('le solde du groupe reste visible dans le titre', '0,00' in pg.inner_text('details[data-fold="g:Banque Alpha"] > summary'), pg.inner_text('details[data-fold="g:Banque Alpha"] > summary'))
    pg.click('details[data-fold="g:Banque Alpha"] > summary')
    check('replier un organisme masque ses comptes', not pg.is_visible('text=Livret test') and not pg.is_visible('text=Compte test A'))
    check('les autres organismes restent visibles', pg.is_visible('text=Compte test B'))
    pg.wait_for_timeout(100)
    pg.evaluate("() => render()")
    check('l’état d’un organisme survit à un nouveau rendu', not etat_replis(pg)['g:Banque Alpha'] and etat_replis(pg)['g:Banque Beta'])
    pg.click('details[data-fold="g:Banque Alpha"] > summary')
    pg.click('text=Compte test A')
    check('un compte d’un groupe se modifie toujours (la fiche s’ouvre)', pg.is_visible('#ac_name'))
    pg.fill('#ac_name', 'Compte test A2')
    pg.click('[data-a=saveacc]')
    check('après enregistrement, le groupe est toujours ouvert et à jour', pg.is_visible('text=Compte test A2') and etat_replis(pg)['g:Banque Alpha'])
    pg.click('details[data-fold=comptes] > summary')
    check('replier la carte Comptes masque aussi les groupes', not pg.is_visible('text=Compte test B'))
    pg.click('details[data-fold=comptes] > summary')
    check('rouvrir la carte retrouve chaque groupe dans son état', etat_replis(pg)['g:Banque Alpha'] and pg.is_visible('text=Compte test B'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_sans_organisme(browser):
    print('Réglages : comptes sans organisme')
    pg = device(browser, FauxSupabase())
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    comptes_demo(pg, groupes=False)
    pg.click('[data-a=nav][data-v=set]')
    check('sans organisme, aucun groupe n’est affiché (comme avant)', not [k for k in etat_replis(pg) if k.startswith('g:')], etat_replis(pg))
    check('les comptes sont listés directement', pg.is_visible('text=Compte test A'))
    # un seul organisme nommé : le groupe apparaît, avec son nom
    s = json.loads(pg.evaluate("(k) => localStorage.getItem(k)", T.KEY))
    for a in s['accounts']:
        a['group'] = 'Banque Unique'
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()
    pg.click('[data-a=nav][data-v=set]')
    check('un seul organisme nommé : groupe repliable affiché', 'g:Banque Unique' in etat_replis(pg), etat_replis(pg))
    # mélange : comptes avec et sans organisme
    s['accounts'][0].pop('group')
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()
    pg.click('[data-a=nav][data-v=set]')
    check('les comptes sans organisme forment un groupe « Sans organisme »', 'Sans organisme' in pg.inner_text('details[data-fold="g:"] > summary'), etat_replis(pg))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_synchro_ne_replie_pas(browser):
    print('Réglages : la synchronisation ne dérange pas les menus')
    pg = device(browser, FauxSupabase())
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    comptes_demo(pg)
    pg.click('[data-a=nav][data-v=set]')
    pg.click('details[data-fold=sync] > summary')
    pg.click('details[data-fold="g:Banque Beta"] > summary')
    pg.wait_for_timeout(200)
    avant = etat_replis(pg)
    pg.evaluate("() => { try { syncRenderBox(); } catch (e) {} }")
    pg.wait_for_timeout(300)
    check('le menu de synchronisation reste ouvert', pg.is_visible('#sync-box') and etat_replis(pg) == avant, etat_replis(pg))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_cartes(browser)
        test_organismes(browser)
        test_sans_organisme(browser)
        test_synchro_ne_replie_pas(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
