"""Tests : autorisation de découvert, plafonds de carte et disponible réel (compte courant), Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : comptes, montants et libellés inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_decouvert_plafonds.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402

NOW = '2026-11-19'   # jeudi ; période de paie du 28 oct au 25 nov
RETRAIT = "Retrait d'espèces"


def ligne(id_, date, amount, acc='a1', **extra):
    t = {'id': id_, 'date': date, 'label': 'Achat test', 'amount': amount, 'cat': 'Divers', 'sub': 'Non classé', 'acc': acc, 'payee': ''}
    t.update(extra)
    return t


def etat(pg, solde=200, od=500, pl=800, wl=200, tx=None, rec=None, differe=False):
    a1 = {'id': 'a1', 'name': 'Compte test', 'type': 'courant', 'opening': 0, 'cash': True, 'anchor': {'date': '2020-01-01', 'amount': solde}}
    if od:
        a1['od'] = od
    if pl:
        a1.update(payLim=pl, payDays=30)
    if wl:
        a1.update(wdLim=wl, wdDays=7)
    comptes = [a1]
    if differe:
        comptes.append({'id': 'a3', 'name': 'Carte différée test', 'type': 'differe', 'opening': 0, 'cash': True, 'debitAcc': 'a1', 'debitDay': 5})
    s = {'v': 2, 'accounts': comptes, 'shown': [c['id'] for c in comptes], 'tx': tx or [], 'rec': rec or [], 'plans': [], 'rules': [],
         'budgets': {}, 'payDates': {}, 'csvMaps': {}, 'skips': []}
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()


def info(pg, now=NOW):
    return pg.evaluate("(d) => cardInfo(accById('a1'), d)", now)


def eq(a, b):
    return abs(a - b) < 0.005


CHARGE = {'id': 'r1', 'label': 'Charge test', 'amount': -300, 'acc': 'a1', 'loan': '', 'cat': 'Logement', 'sub': 'Charges', 'freq': 'monthly', 'day': 20, 'every': 1, 'start': '2020-01-01', 'end': '', 'match': ''}


def test_disponible(browser):
    print('Disponible réel : solde + découvert, limité par le plafond de carte')
    pg = device(browser, FauxSupabase())
    etat(pg)
    c = info(pg)
    check('solde 200 + découvert 500 = 700 de marge', eq(c['margin'], 700) and c['over'] == 0, c)
    check('rien dépensé : disponible par carte = 700 (le plafond 800 ne limite pas)', eq(c['availCard'], 700), c)
    check('disponible en retrait = plafond de retrait 200 (limite la marge 700)', eq(c['availCash'], 200), c)
    etat(pg, tx=[ligne('t1', '2026-11-10', -600)])
    c = info(pg)
    check('600 payés : solde −400, marge 100, plafond restant 200 → disponible 100', eq(c['bal'], -400) and eq(c['availCard'], 100) and eq(c['pay']['left'], 200), c)
    etat(pg, od=500, pl=150, tx=[ligne('t1', '2026-11-10', -600)])
    c = info(pg)
    check('plafond de paiement épuisé (600 > 150) : disponible par carte = 0 malgré la marge', eq(c['pay']['left'], 0) and eq(c['availCard'], 0) and c['margin'] > 0, c)
    etat(pg, solde=-100, tx=[ligne('t1', '2026-11-10', -500)])
    c = info(pg)
    check('solde −600 pour 500 autorisés : dépassement de 100, disponible 0', eq(c['over'], 100) and eq(c['availCard'], 0) and eq(c['availCash'], 0), c)
    etat(pg, od=0, pl=0, wl=0, solde=300)
    c = info(pg)
    check('sans découvert ni plafond : disponible = solde', eq(c['availCard'], 300) and c['pay'] is None and c['wd'] is None, c)
    etat(pg, od=0, pl=0, wl=0, solde=-50)
    check('sans découvert, solde négatif : dépassement dès le premier euro', eq(info(pg)['over'], 50) and eq(info(pg)['availCard'], 0))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_fenetres(browser):
    print('Plafonds : fenêtres glissantes, retraits, lignes exclues, cartes différées')
    pg = device(browser, FauxSupabase())
    etat(pg, solde=2000, tx=[ligne('t1', '2026-10-20', -100), ligne('t2', '2026-10-21', -30)])
    c = info(pg)
    check('30 jours glissants : le 20 oct (il y a 30 jours) est exclu, le 21 oct est inclus', eq(c['pay']['spent'], 30), c['pay'])
    etat(pg, solde=2000, tx=[ligne('t1', '2026-11-15', -80, sub=RETRAIT), ligne('t2', '2026-11-12', -50, sub=RETRAIT), ligne('t3', '2026-11-15', -40)])
    c = info(pg)
    check('retrait : 7 jours glissants, le 12 nov est exclu, le 15 nov est compté (80)', eq(c['wd']['spent'], 80) and eq(c['wd']['left'], 120), c['wd'])
    check('un retrait ne compte pas dans le plafond de paiement, un paiement ne compte pas dans le retrait', eq(c['pay']['spent'], 40), c['pay'])
    etat(pg, solde=2000, tx=[ligne('t1', '2026-11-15', -70, xfer='x'), ligne('t2', '2026-11-15', -60, recKey='r9|2026-11-15'), ligne('t3', '2026-11-15', 25)])
    check('virements, lignes de récurrences et recettes ne comptent pas', eq(info(pg)['pay']['spent'], 0), info(pg)['pay'])
    etat(pg, solde=2000, differe=True, tx=[ligne('t1', '2026-11-15', -45, acc='a3'), ligne('t2', '2026-11-16', -5)])
    check('les paiements d’une carte à débit différé rattachée comptent dans le plafond', eq(info(pg)['pay']['spent'], 50), info(pg)['pay'])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_prevision(browser):
    print('Prévision : solde le plus bas avant la paie')
    pg = device(browser, FauxSupabase())
    etat(pg, solde=100, od=500, rec=[CHARGE])
    c = info(pg)
    check('100 − 300 (échéance du 20 nov) = −200 le 20/11', eq(c['min'], -200) and c['minDate'] == '2026-11-20', c)
    check('−200 reste dans 500 autorisés : pas de dépassement prévu', c['projOver'] is False, c)
    etat(pg, solde=100, od=150, rec=[CHARGE])
    check('−200 pour 150 autorisés : dépassement prévu', info(pg)['projOver'] is True, info(pg))
    etat(pg, solde=100, od=0, pl=0, wl=0, rec=[CHARGE])
    check('sans découvert : tout solde prévu négatif est un dépassement', info(pg)['projOver'] is True)
    etat(pg, solde=100, od=500, rec=[CHARGE])
    c = info(pg, '2026-11-22')
    check('après l’échéance du 20 (non validée) : elle compte à la date du jour', eq(c['min'], -200) and c['minDate'] == '2026-11-22', c)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_budget_inchange(browser):
    print('Le découvert n’entre pas dans le budget du jour')
    pg = device(browser, FauxSupabase())
    etat(pg, solde=1000, od=0, pl=0, wl=0, rec=[CHARGE])
    sans = pg.evaluate("(d) => budgetInfo(d)", NOW)
    etat(pg, solde=1000, od=800, rec=[CHARGE])
    avec = pg.evaluate("(d) => budgetInfo(d)", NOW)
    check('budget et reste à vivre identiques avec ou sans autorisation de découvert', eq(sans['B'], avec['B']) and eq(sans['rav'], avec['rav']) and eq(sans['perDay'], avec['perDay']), [sans, avec])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def norm(t):
    return t.replace(' ', ' ').replace('\xa0', ' ')


def test_interface(browser):
    print('Interface : Accueil, fiche du compte, liste des comptes')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    etat(pg, solde=200, tx=[ligne('t1', '2020-02-01', -5)])
    pg.click('[data-a=nav][data-v=home]')
    txt = norm(pg.inner_text('#app'))
    check('Accueil : carte du compte avec état, découvert, plafonds et disponibles', all(x in txt for x in ['Compte test', 'Découvert autorisé', 'Paiement (30 j)', 'Retrait (7 j)', 'sur un plafond de', 'Disponible par carte', 'Disponible en retrait']), txt[:600])
    etat(pg, solde=-100, tx=[ligne('t1', '2026-11-10', -500)])
    pg.click('[data-a=nav][data-v=home]')
    txt = norm(pg.inner_text('#app'))
    check('Accueil : « Découvert dépassé » + carte d’alerte quand la limite est franchie', 'Découvert dépassé' in txt and pg.evaluate("() => !!document.querySelector('.card.warn')"), txt[:500])
    etat(pg, od=0, pl=0, wl=0)
    pg.click('[data-a=nav][data-v=home]')
    check('compte sans découvert ni plafond : pas de carte', 'Plafond de paiement' not in pg.inner_text('#app') and 'Découvert autorisé' not in pg.inner_text('#app'))
    etat(pg, tx=[ligne('t1', '2020-02-01', -5)])
    pg.click('[data-a=nav][data-v=set]')
    pg.click('details[data-fold=comptes] > summary')
    check('liste des comptes : « découvert autorisé 500,00 € »', 'découvert autorisé 500,00 €' in norm(pg.inner_text('[data-a=editacc][data-id=a1]')), norm(pg.inner_text('[data-a=editacc][data-id=a1]')))
    pg.click('[data-a=editacc][data-id=a1]')
    check('fiche : les cinq champs sont visibles pour un compte courant', all(pg.is_visible(i) for i in ['#ac_od', '#ac_pl', '#ac_pld', '#ac_wl', '#ac_wld']))
    check('fiche : valeurs enregistrées affichées', pg.input_value('#ac_od') == '500' and pg.input_value('#ac_pl') == '800' and pg.input_value('#ac_pld') == '30' and pg.input_value('#ac_wl') == '200' and pg.input_value('#ac_wld') == '7')
    pg.fill('#ac_od', '750,50')
    pg.fill('#ac_pl', '1500')
    pg.fill('#ac_pld', '28')
    pg.fill('#ac_wl', '')
    pg.click('[data-a=saveacc]')
    a = pg.evaluate("() => accById('a1')")
    check('enregistrement : découvert 750,50 ; plafond paiement 1500 sur 28 jours', a['od'] == 750.5 and a['payLim'] == 1500 and a['payDays'] == 28, a)
    check('champ de retrait vidé : plafond de retrait supprimé', 'wdLim' not in a and 'wdDays' not in a, a)
    pg.click('[data-a=editacc][data-id=a1]')
    pg.fill('#ac_od', 'abc')
    pg.click('[data-a=saveacc]')
    check('montant invalide : refusé avec un message, rien n’est modifié', any('invalide' in m for m in msgs) and pg.evaluate("() => accById('a1').od") == 750.5 and pg.is_visible('#ac_od'), msgs)
    pg.fill('#ac_od', '750,50')
    pg.fill('#ac_pld', '999')
    pg.click('[data-a=saveacc]')
    check('nombre de jours hors 1-365 : refusé', any('365' in m for m in msgs) and pg.evaluate("() => accById('a1').payDays") == 28, msgs)
    pg.fill('#ac_pld', '28')
    pg.select_option('#ac_type', 'livret')
    check('choisir un autre type masque les champs de découvert et de plafond', not pg.is_visible('#ac_od'))
    pg.click('[data-a=saveacc]')
    a = pg.evaluate("() => accById('a1')")
    check('un compte qui n’est plus courant perd ses champs de découvert et de plafond', not any(k in a for k in ['od', 'payLim', 'payDays', 'wdLim', 'wdDays']), a)
    check('sous-catégorie « Retrait d’espèces » disponible dans Divers', pg.evaluate("(s) => CATS['Divers'].includes(s)", RETRAIT))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_disponible(browser)
        test_fenetres(browser)
        test_prevision(browser)
        test_budget_inchange(browser)
        test_interface(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
