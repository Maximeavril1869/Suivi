"""Tests : rappel de sauvegarde partagé et bannière « Hors ligne » de Mon Compte (Chromium via Playwright, faux serveur Supabase en mémoire).

Réutilise le faux serveur et les outils de test_sync.py. Aucune donnée réelle : libellés, montants et identifiants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_rappel_et_hors_ligne.py
"""
import json
import pathlib
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, connect, device, edit, go_settings, seed, sync, tx, wait, wait_remote  # noqa: E402


def jours(n):
    return (date.today() + timedelta(days=n)).isoformat()


def bk(pg):
    return pg.evaluate("() => S.bk")


def go_home(pg):
    pg.click('[data-a=nav][data-v=home]')


def banner_rappel(pg):
    go_home(pg)
    return pg.locator('text=Sauvegarde conseillée').count() == 1


def test_rappel_local(browser):
    print('Rappel de sauvegarde : état local')
    fake = FauxSupabase()
    pg = device(browser, fake)
    pg.on('dialog', lambda d: d.accept())
    # anciennes données (sans « bk »), jamais exportées : le compte commence aujourd'hui
    pg.evaluate("(k) => { const s = defaultState(); delete s.bk; s.tx = [%s]; localStorage.setItem(k, JSON.stringify(s)); }" % json.dumps(tx('t1', '2026-11-05', 'Loyer test', -500)), T.KEY)
    pg.reload()
    check('anciennes données jamais exportées : le compte commence aujourd’hui', bk(pg)['since'] == jours(0) and bk(pg)['every'] == 7, bk(pg))
    check('pas de rappel le premier jour', not banner_rappel(pg))
    pg.evaluate("() => { S.bk.since = '%s'; save(true); render(); }" % jours(-8))
    check('modifications non sauvegardées depuis 8 jours : le rappel s’affiche', banner_rappel(pg))
    check('le rappel indique la durée', pg.locator('text=depuis 8 jours').count() == 1)
    pg.click('[data-a=bk-later]')
    check('« Plus tard » masque le rappel', pg.locator('text=Sauvegarde conseillée').count() == 0)
    check('… jusqu’à demain', bk(pg)['snooze'] == jours(1), bk(pg))
    pg.evaluate("() => { S.bk.snooze = '%s'; save(true); render(); }" % jours(-1))
    check('report échu : le rappel revient', banner_rappel(pg))
    # réglage du délai
    go_settings(pg)
    check('Réglages : le délai se règle (jamais, 3, 7, 14, 30 jours)', pg.locator('#bk_every option').count() == 5)
    pg.select_option('#bk_every', '30')
    check('délai 30 jours : plus de rappel à 8 jours', bk(pg)['every'] == 30 and not banner_rappel(pg))
    go_settings(pg)
    pg.select_option('#bk_every', '0')
    check('« Jamais » : aucun rappel même après 8 jours', bk(pg)['every'] == 0 and not banner_rappel(pg))
    go_settings(pg)
    pg.select_option('#bk_every', '7')
    check('retour à 7 jours : le rappel revient', banner_rappel(pg))
    # cocher un compte n'est pas une modification de données
    pg.evaluate("() => { S.bk.since = null; save(true); }")
    pg.evaluate("() => act('togacc', {id: S.accounts[0].id})")
    pg.evaluate("() => act('togacc', {id: S.accounts[0].id})")
    check('cocher / décocher un compte ne compte pas comme une modification', bk(pg)['since'] is None, bk(pg))
    edit(pg, "S.tx[0].label = 'Loyer modifié'")
    check('une vraie modification date le rappel d’aujourd’hui', bk(pg)['since'] == jours(0), bk(pg))
    # export
    pg.evaluate("() => { S.bk.since = '%s'; save(true); render(); }" % jours(-9))
    check('rappel visible avant l’export', banner_rappel(pg))
    with pg.expect_download():
        pg.click('[data-a=export]')
    pg.wait_for_timeout(200)
    b = bk(pg)
    check('après l’export : modifications à zéro, rappel masqué', b['since'] is None and b['snooze'] is None and pg.evaluate("() => S.lastExport") == jours(0), b)
    check('le rappel a disparu', not banner_rappel(pg))
    # restauration d'un fichier
    data = json.dumps({'v': 2, 'accounts': [{'id': 'a1', 'name': 'Compte test', 'type': 'courant', 'opening': 0, 'cash': True}], 'shown': ['a1'],
                       'tx': [tx('t9', '2026-11-06', 'Restauré test', -9)], 'rec': [], 'plans': [], 'rules': [], 'budgets': {}, 'csvMaps': {}, 'skips': [],
                       'lastExport': None, 'bk': {'since': jours(-20), 'snooze': None, 'every': 14}})
    f = pathlib.Path(tempfile.mkdtemp()) / 'sauvegarde-test.json'
    f.write_text(data, encoding='utf-8')
    go_settings(pg)
    pg.set_input_files('#jsonfile', str(f))
    check('restauration : les lignes du fichier sont là', wait(pg, "() => S.tx.length === 1 && S.tx[0].label === 'Restauré test'"))
    check('restauration : l’appareil est identique au fichier, aucun rappel en attente', bk(pg)['since'] is None and bk(pg)['every'] == 14, bk(pg))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_rappel_partage(browser):
    print('Rappel de sauvegarde : partagé entre deux appareils')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Loyer test', -500)])
    connect(a, create=True)
    wait_remote(lambda: 'meta' in fake.rows)
    b = device(browser, fake)
    connect(b)
    wait(b, "() => S.tx.length === 1")
    a.evaluate("() => { S.bk.since = '%s'; save(true); }" % jours(-10))
    sync(a)
    b.wait_for_timeout(400)
    sync(b)
    check('B reçoit la date de première modification de A', wait(b, "(d) => S.bk.since === d", jours(-10)), bk(b))
    check('B affiche le rappel', banner_rappel(b))
    with a.expect_download():
        a.click('[data-a=nav][data-v=set]') if False else a.evaluate("() => exportJSON()")
    sync(a)
    b.wait_for_timeout(400)
    sync(b)
    check('après l’export sur A, le rappel disparaît sur B', wait(b, "() => S.bk.since === null"), bk(b))
    check('B n’affiche plus le rappel', not banner_rappel(b))
    check('B connaît la date de la dernière sauvegarde', b.evaluate("() => S.lastExport") == jours(0))
    b.evaluate("() => { S.bk.every = 14; save(true); }")
    sync(b)
    a.wait_for_timeout(400)
    sync(a)
    check('le délai choisi sur B s’applique aussi sur A', wait(a, "() => S.bk.every === 14"), bk(a))
    check('aucune erreur JavaScript', not a.errors and not b.errors, a.errors + b.errors)


def barre(pg):
    return pg.evaluate("""() => { const e = document.getElementById('offbar'), n = document.querySelector('nav');
        const r = e.getBoundingClientRect(), nr = n.getBoundingClientRect();
        return { hidden: e.hidden, shown: r.height > 0, bottom: r.bottom, navTop: nr.top, h: r.height, pe: getComputedStyle(e).pointerEvents, text: e.textContent }; }""")


def test_hors_ligne(browser):
    print('Bannière « Hors ligne » (compte connecté)')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Avant coupure', -5)])
    connect(a, create=True)
    wait_remote(lambda: 'tx:2026-11' in fake.rows)
    wait(a, "() => syncState.status === 'ok'")
    check('en ligne : pas de bannière', barre(a)['shown'] is False, barre(a))
    # coupure réelle du navigateur (événement « offline »)
    a.context.set_offline(True)
    check('réseau coupé : la bannière apparaît tout de suite', wait(a, "() => !document.getElementById('offbar').hidden", None, 3000))
    s = barre(a)
    check('elle dit « Hors ligne »', s['text'].startswith('Hors ligne'), s)
    check('elle est juste au-dessus des onglets', abs(s['bottom'] - s['navTop']) <= 1.5 and s['h'] >= 20, s)
    check('elle n’intercepte aucun toucher (pointer-events: none)', s['pe'] == 'none', s)
    for v in ['home', 'tx', 'rec', 'imp', 'set']:
        a.click('[data-a=nav][data-v=%s]' % v)
        check('écran « %s » : bannière visible, navigation possible' % v, barre(a)['shown'] is True)
    # l'app reste utilisable : ajout d'une ligne pendant la coupure
    edit(a, "S.tx.push(%s)" % json.dumps(tx('t2', '2026-11-07', 'Ajout hors ligne', -7)))
    check('hors ligne : on peut modifier, la donnée est gardée', T.stored_labels(a) == ['Avant coupure', 'Ajout hors ligne'][::-1] or sorted(T.stored_labels(a)) == ['Ajout hors ligne', 'Avant coupure'], T.stored_labels(a))
    # retour du réseau
    n = len(fake.posts)
    a.context.set_offline(False)
    sync(a)
    check('réseau revenu : la bannière disparaît après la synchronisation', wait(a, "() => document.getElementById('offbar').hidden", None, 9000), barre(a))
    check('la modification faite hors ligne est partie', wait_remote(lambda: len(fake.posts) > n), fake.posts)
    # navigateur « en ligne » mais le serveur ne répond pas (Wi-Fi sans internet) : détecté par l'échec de la synchro
    fake.offline = True
    edit(a, "S.tx[0].label = 'Pendant panne serveur'")
    sync(a)
    check('Wi-Fi sans internet : bannière après l’échec de la synchro', wait(a, "() => !document.getElementById('offbar').hidden", None, 6000))
    fake.offline = False
    sync(a)
    check('… et elle disparaît au retour', wait(a, "() => document.getElementById('offbar').hidden", None, 9000))
    # une erreur serveur n'est pas « hors ligne »
    check('aucune erreur JavaScript', not a.errors, a.errors)


def test_hors_ligne_sans_compte(browser):
    print('Bannière « Hors ligne » : rien à signaler sans compte connecté')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Local seulement', -5)])
    a.context.set_offline(True)
    a.wait_for_timeout(500)
    check('sans compte : pas de bannière (l’app est locale)', barre(a)['shown'] is False, barre(a))
    check('aucune erreur JavaScript', not a.errors, a.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_rappel_local(browser)
        test_rappel_partage(browser)
        test_hors_ligne(browser)
        test_hors_ligne_sans_compte(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
