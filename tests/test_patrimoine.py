"""Tests : patrimoine net, types « Épargne bloquée » et « Bien », Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : comptes et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_patrimoine.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402


def norm(t):
    return t.replace(' ', ' ').replace('\xa0', ' ')


def etat(pg):
    def c(i, nom, type_, solde, **kw):
        d = {'id': i, 'name': nom, 'type': type_, 'opening': 0, 'cash': type_ == 'courant', 'anchor': {'date': '2020-01-01', 'amount': solde}}
        d.update(kw)
        return d
    comptes = [
        c('a1', 'Compte test', 'courant', 1000, group='Banque Alpha'),
        c('a2', 'Livret test', 'livret', 500, group='Banque Alpha'),
        c('a3', 'Parts test', 'bloque', 2000, group='Banque Alpha', cash=True),   # cash=True à tort : doit être ignoré
        c('a4', 'Maison test', 'bien', 200000, cash=True),
        c('a5', 'Prêt test', 'emprunt', -150000),
        c('a6', 'Carte crédit test', 'credit', 2500, limit=3000),
        c('a7', 'CB différé test', 'differe', -300, debitAcc='a1', debitDay=5),
    ]
    s = {'v': 2, 'accounts': comptes, 'shown': [x['id'] for x in comptes], 'tx': [], 'rec': [], 'plans': [], 'rules': [], 'budgets': {}, 'payDates': {}, 'csvMaps': {}, 'skips': []}
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    pg.reload()
    pg.click('[data-a=nav][data-v=home]')


def titre(pg):
    return norm(pg.inner_text('details[data-fold=patri] > summary'))


def test_carte(browser):
    print('Accueil : carte Patrimoine')
    pg = device(browser, FauxSupabase())
    etat(pg)
    check('carte repliée au démarrage', pg.evaluate("() => document.querySelector('details[data-fold=patri]').open") is False)
    check('total net sur la ligne repliée (52 700,00)', '52 700,00' in titre(pg), titre(pg))
    pg.click('details[data-fold=patri] > summary')
    d = norm(pg.inner_text('details[data-fold=patri]'))
    for x in ['Liquidités', '1 000,00', 'Épargne (livrets)', '500,00', 'Épargne bloquée', '2 000,00', 'Biens', '200 000,00', 'Total possédé', '203 500,00', 'Emprunts', '-150 000,00', 'Cartes de crédit (dû)', '-500,00', 'Achats différés en attente', '-300,00', 'Total dû', '-150 800,00', 'Patrimoine net', '52 700,00']:
        check('détail : ' + x, x in d, d)
    check('épargne bloquée et bien retirés des comptes cochés au rechargement', pg.evaluate("() => S.shown.includes('a3') || S.shown.includes('a4')") is False)
    check('compte courant : cash conservé, bloqué/bien jamais dans le reste à vivre', pg.evaluate("() => scopeAccs(true).map(a => a.id)") == ['a1'])
    check('solde des comptes cochés sans bloqué ni bien (1000+500-500-300-150000 = -149 300)', pg.evaluate("() => balanceAt(today(), false)") == -149300)
    check('reste à vivre inchangé (compte courant seul)', pg.evaluate("() => balanceAt(today(), true)") == 1000)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_formulaire(browser):
    print('Formulaire : créer un Bien et mettre à jour sa valeur')
    pg = device(browser, FauxSupabase())
    etat(pg)
    pg.evaluate("() => openAcc()")
    check('type Bien proposé', pg.evaluate("() => [...document.querySelectorAll('#ac_type option')].some(o => o.value === 'bien')"))
    check('type Épargne bloquée proposé', pg.evaluate("() => [...document.querySelectorAll('#ac_type option')].some(o => o.value === 'bloque')"))
    pg.select_option('#ac_type', 'bien')
    check('case « Compter dans le reste à vivre » masquée pour un bien', not pg.is_visible('#ac_cash'))
    check('libellé « Valeur à cette date »', 'Valeur à cette date' in pg.inner_text('.ac_l2'))
    pg.fill('#ac_name', 'Voiture test')
    pg.fill('#ac_bal', '10000')
    pg.click('[data-a=saveacc]')
    check('bien créé, hors comptes cochés et hors reste à vivre', pg.evaluate("() => { const a = S.accounts.find(x => x.name === 'Voiture test'); return a && a.cash === false && !S.shown.includes(a.id); }"))
    check('patrimoine net augmenté de 10 000 (62 700,00)', '62 700,00' in titre(pg), titre(pg))
    pg.evaluate("() => openAcc(S.accounts.find(x => x.name === 'Voiture test').id)")
    pg.fill('#ac_bal', '9000')
    pg.click('[data-a=saveacc]')
    check('valeur modifiée : patrimoine 61 700,00', '61 700,00' in titre(pg), titre(pg))
    pg.evaluate("() => openAcc(S.accounts.find(x => x.name === 'Livret test').id)")
    pg.select_option('#ac_type', 'bloque')
    pg.click('[data-a=saveacc]')
    check('livret passé en épargne bloquée : plus de case cochée, hors totaux liquides', pg.evaluate("() => { const a = S.accounts.find(x => x.name === 'Livret test'); return a.type === 'bloque' && !a.cash && !S.shown.includes(a.id); }"))
    check('patrimoine inchangé par ce changement de type', '61 700,00' in titre(pg), titre(pg))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_carte(browser)
        test_formulaire(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
