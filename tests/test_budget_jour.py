"""Tests : budget du jour (façon Money Coach) et jours de paie, Chromium via Playwright.

Réutilise les outils de test_sync.py. Aucune donnée réelle : comptes, montants et libellés inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_budget_jour.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402


def etat(pg, tx=None, rec=None, solde=3000, cartes=False):
    comptes = [{'id': 'a1', 'name': 'Compte test', 'type': 'courant', 'opening': 0, 'cash': True, 'anchor': {'date': '2020-01-01', 'amount': solde}}]
    if cartes:
        comptes.append({'id': 'a2', 'name': 'Carte test', 'type': 'credit', 'opening': 0, 'cash': False, 'limit': 3000, 'anchor': {'date': '2020-01-01', 'amount': 2500}})
    s = {'v': 2, 'accounts': comptes, 'shown': [c['id'] for c in comptes], 'tx': tx or [], 'rec': rec or [], 'plans': [], 'rules': [],
         'budgets': {}, 'payDates': {}, 'csvMaps': {}, 'skips': []}
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.reload()


def ligne(id_, date, amount, **extra):
    t = {'id': id_, 'date': date, 'label': 'Achat test', 'amount': amount, 'cat': 'Divers', 'sub': 'Non classé', 'acc': 'a1', 'payee': ''}
    t.update(extra)
    return t


CHARGE = {'id': 'r1', 'label': 'Charge test', 'amount': -300, 'acc': 'a1', 'loan': '', 'cat': 'Logement', 'sub': 'Charges', 'freq': 'monthly', 'day': 20, 'every': 1, 'start': '2020-01-01', 'end': '', 'match': ''}
SALAIRE = {'id': 'r2', 'label': 'Salaire test', 'amount': 2000, 'acc': 'a1', 'loan': '', 'cat': 'Revenus', 'sub': 'Salaire', 'freq': 'monthly', 'day': 26, 'every': 1, 'start': '2020-01-01', 'end': '', 'match': ''}


def bi(pg, now):
    return pg.evaluate("(d) => budgetInfo(d)", now)


def proche(a, b):
    return abs(a - b) < 0.005


def test_regle_de_paie(browser):
    print('Jours de paie : règle, jours fériés, décembre, modification')
    pg = device(browser, FauxSupabase())
    r = lambda ym: pg.evaluate("(m) => payRule(m)", ym)  # noqa: E731
    check('novembre 2026 : dernier jour ouvré lundi 30, paie jeudi 26', r('2026-11') == '2026-11-26', r('2026-11'))
    check('octobre 2026 (31 = samedi) : paie mercredi 28', r('2026-10') == '2026-10-28', r('2026-10'))
    check('décembre 2026 : la règle normale donnerait le 29, la paie est le 22', r('2026-12') == '2026-12-22', r('2026-12'))
    check('janvier 2027 (31 = dimanche) : paie mercredi 27', r('2027-01') == '2027-01-27', r('2027-01'))
    for d, attendu in [('2026-04-06', False), ('2026-05-14', False), ('2026-05-25', False), ('2026-05-01', False), ('2026-05-08', False), ('2026-07-14', False),
                       ('2026-11-01', False), ('2026-11-11', False), ('2026-12-25', False), ('2026-01-01', False), ('2026-11-02', True), ('2026-11-07', False), ('2026-11-27', True)]:
        ok = pg.evaluate("(d) => isWorkday(d)", d) == attendu
        check('%s : %s' % (d, 'ouvré' if attendu else 'non ouvré (férié ou week-end)'), ok)
    check('Pâques 2026 = 5 avril', pg.evaluate("() => easter(2026)") == '2026-04-05')
    pg.evaluate("() => { S.payDates = { '2026-11': '2026-11-27' }; }")
    check('une date modifiée l’emporte sur la règle', pg.evaluate("() => payDate('2026-11')") == '2026-11-27')
    check('les autres mois gardent la règle', pg.evaluate("() => payDate('2026-10')") == '2026-10-28')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_periodes(browser):
    print('Périodes de budget : de paie à la veille de la paie suivante')
    pg = device(browser, FauxSupabase())
    c = lambda d: pg.evaluate("(d) => payCycle(d)", d)  # noqa: E731
    check('18 nov 2026 : du 28 oct au 25 nov', c('2026-11-18') == {'from': '2026-10-28', 'to': '2026-11-25'}, c('2026-11-18'))
    check('le jour de paie (26 nov) commence une période : du 26 nov au 21 déc', c('2026-11-26') == {'from': '2026-11-26', 'to': '2026-12-21'}, c('2026-11-26'))
    check('veille de paie (25 nov) : dernier jour de la période précédente', c('2026-11-25')['to'] == '2026-11-25')
    check('22 déc 2026 : jusqu’au 26 janvier 2027', c('2026-12-22') == {'from': '2026-12-22', 'to': '2027-01-26'}, c('2026-12-22'))
    pg.evaluate("() => { S.payDates = { '2026-11': '2026-11-27' }; }")
    check('paie de novembre déplacée au 27 : la période d’octobre va jusqu’au 26', c('2026-11-26') == {'from': '2026-10-28', 'to': '2026-11-26'}, c('2026-11-26'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_calcul(browser):
    print('Budget du jour : calcul et recalage')
    pg = device(browser, FauxSupabase())
    etat(pg, rec=[CHARGE, SALAIRE])
    b = bi(pg, '2026-11-18')   # mercredi ; période du 28 oct au 25 nov ; reste 8 jours (18 → 25)
    check('budget de la période = reste à vivre 3000 − échéance à venir 300 = 2700', proche(b['B'], 2700), b)
    check('la paie du 26 (hors période) n’est pas comptée', proche(b['upSum'], -300), b)
    check('8 jours restants, aujourd’hui compris', b['days'] == 8, b)
    check('par jour : 2700 ÷ 8 = 337,50', proche(b['perDay'], 337.5), b)
    check('aujourd’hui : 337,50 (rien dépensé)', proche(b['today'], 337.5), b)
    check('cette semaine (mer → dim = 5 jours) : 1 687,50', b['wDays'] == 5 and proche(b['week'], 1687.5), b)
    etat(pg, tx=[ligne('t1', '2026-11-18', -37.5)], rec=[CHARGE, SALAIRE])
    b = bi(pg, '2026-11-18')
    check('une dépense de 37,50 aujourd’hui : le montant par jour ne bouge pas', proche(b['perDay'], 337.5), b)
    check('… le reste d’aujourd’hui baisse à 300', proche(b['today'], 300), b)
    check('… la semaine baisse de 37,50 : 1 650', proche(b['week'], 1650), b)
    check('… le budget de la période baisse à 2 662,50', proche(b['B'], 2662.5), b)
    b = bi(pg, '2026-11-19')
    check('le lendemain, le budget se répartit sur 7 jours : (3000 − 37,50 − 300) ÷ 7', proche(b['perDay'], (3000 - 37.5 - 300) / 7), b)
    check('… et il n’y a plus de dépense « du jour »', proche(b['conso'], 0) and proche(b['today'], b['perDay']), b)
    etat(pg, tx=[ligne('t1', '2026-11-18', -37.5, xfer='x'), ligne('t2', '2026-11-18', -20, recKey='r9|2026-11-18')], rec=[CHARGE, SALAIRE])
    check('virements et lignes de récurrences ne comptent pas comme consommation', proche(bi(pg, '2026-11-18')['conso'], 0), bi(pg, '2026-11-18'))
    etat(pg, tx=[ligne('t1', '2026-11-18', 50)], rec=[CHARGE, SALAIRE])
    check('une recette du jour n’est pas une consommation', proche(bi(pg, '2026-11-18')['conso'], 0))
    etat(pg, rec=[CHARGE, SALAIRE], cartes=True)
    check('une carte de crédit hors reste à vivre ne change pas le budget', proche(bi(pg, '2026-11-18')['B'], 2700), bi(pg, '2026-11-18'))
    etat(pg, rec=[CHARGE], solde=100)
    b = bi(pg, '2026-11-18')
    check('budget négatif : reste négatif, par jour négatif', b['B'] < 0 and b['perDay'] < 0, b)
    etat(pg, rec=[CHARGE, SALAIRE])
    b = bi(pg, '2026-11-25')
    check('dernier jour de la période : 1 jour restant, tout le budget est pour aujourd’hui', b['days'] == 1 and proche(b['today'], b['B']), b)
    b = bi(pg, '2026-11-22')
    check('dimanche : la semaine = le jour', b['wDays'] == 1 and proche(b['week'], b['today']), b)
    pg.evaluate("() => { S.accounts[0].cash = false; }")
    check('aucun compte « reste à vivre » : pas de budget', pg.evaluate("() => budgetInfo('2026-11-18')") is None)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_interface(browser):
    print('Budget du jour : Accueil, Réglages, synchronisation')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.accept())
    etat(pg, tx=[ligne('t1', '2020-02-01', -5)], rec=[CHARGE, SALAIRE])
    pg.click('[data-a=nav][data-v=home]')
    txt = pg.inner_text('#app')
    check('Accueil : carte « Budget du jour » avec ses trois chiffres', 'Budget du jour' in txt and "Aujourd'hui" in txt and 'Cette semaine' in txt and "Jusqu'au" in txt, txt[:400])
    check('Accueil : période et reste à vivre expliqués', 'Période du' in txt and 'Reste à vivre' in txt and 'échéances à venir' in txt)
    etat(pg)
    pg.click('[data-a=nav][data-v=home]')
    check('sans aucune ligne, la carte n’est pas affichée', 'Budget du jour' not in pg.inner_text('#app'))
    etat(pg, tx=[ligne('t1', '2020-02-01', -5)])
    pg.click('[data-a=nav][data-v=set]')
    check('Réglages : carte « Jours de paie » repliée par défaut', pg.evaluate("() => document.querySelector('details[data-fold=paie]').open") is False)
    pg.click('details[data-fold=paie] > summary')
    n = pg.evaluate("() => document.querySelectorAll('[data-a=editpay]').length")
    check('14 mois listés (le mois précédent et les 12 suivants, avec le mois courant)', n == 14, n)
    m = pg.evaluate("() => monthOf(today())")
    regle = pg.evaluate("(m) => payRule(m)", m)
    pg.click('[data-a=editpay][data-m="%s"]' % m)
    check('la fiche d’un mois propose la date de la règle', pg.input_value('#pay_d') == regle, pg.input_value('#pay_d'))
    pg.fill('#pay_d', m + '-15')
    pg.click('[data-a=savepay]')
    check('changer la date l’enregistre', pg.evaluate("(m) => S.payDates[m]", m) == m + '-15')
    check('la liste indique « modifié » avec la règle d’origine', 'modifié' in pg.inner_text('[data-a=editpay][data-m="%s"]' % m))
    pg.click('[data-a=editpay][data-m="%s"]' % m)
    pg.click('[data-a=resetpay]')
    check('« Rétablir la règle » supprime la modification', pg.evaluate("(m) => m in S.payDates", m) is False)
    pg.click('[data-a=editpay][data-m="%s"]' % m)
    pg.fill('#pay_d', regle)
    pg.click('[data-a=savepay]')
    check('saisir la date de la règle ne crée pas de modification', pg.evaluate("(m) => m in S.payDates", m) is False)
    check('les dates de paie sont synchronisées entre appareils', pg.evaluate("() => SYNC_META_FIELDS.includes('payDates')") is True)
    check('anciennes données sans dates de paie : champ créé', pg.evaluate("() => { const o = migrate({ accounts: [{ id: 'a1', name: 'x', type: 'courant', cash: true }] }); return typeof o.payDates === 'object' && !Array.isArray(o.payDates); }") is True)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_regle_de_paie(browser)
        test_periodes(browser)
        test_calcul(browser)
        test_interface(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
