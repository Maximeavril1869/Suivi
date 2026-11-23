"""Tests : module « Bulletin de paye » (suivi de l'évolution de chaque ligne), Chromium via Playwright.

Vérifie : données (migration, restauration), carte d'entrée sur Récurrent, modèle de lignes (création, changement de montant daté),
fiches mensuelles à valider (pré-remplies, ignorées, validées en bloc, corrigées, supprimées), lignes ponctuelles (primes),
tableau et courbe, absence de tout effet sur les comptes / soldes / lignes, synchronisation chiffrée du champ.
Aucune donnée réelle : libellés et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_paie.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device  # noqa: E402


def norm(t):
    return t.replace('\u202f', ' ').replace('\xa0', ' ')


def mois(pg, k=0):
    return pg.evaluate("(k) => addMonths(monthOf(today()), k)", k)


def depart(pg, paie=None):
    pg.evaluate("([k, p]) => { const s = defaultState(); if (p) s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, paie])
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    pg.reload()


def pick(pg, ident, ym):
    y, m = ym.split('-')
    pg.select_option('#%s_m' % ident, str(int(m)))
    pg.select_option('#%s_y' % ident, y)


def ouvre_paie(pg):
    pg.click('[data-a=nav][data-v=rec]')
    pg.click('[data-a=openpaie]')
    # les menus sont repliés de base : on les déplie pour que les tests voient leur contenu (test_replis_defaut vérifie l'état de départ)
    pg.evaluate("() => { ['paie-evo', 'paie-crb', 'paie-fiches', 'paie-mod', 'pt-gain', 'pt-ret'].forEach((k) => { FOLD[k] = true; }); render(); }")


def etat_paie(pg):
    return pg.evaluate("() => JSON.parse(JSON.stringify(S.paie))")


def ajoute_ligne(pg, label, kind, montant, debut):
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.fill('#pl_lab', label)
    pg.select_option('#pl_kind', kind)
    pg.fill('#pl_amt', montant)
    pick(pg, 'pl_start', debut)
    pg.click('[data-a=savepaline]')


VIDE = {'lines': [], 'slips': {}, 'skips': [], 'pt': {'amount': 0, 'hist': []}, 'acf': {'amount': 0, 'hist': []}}


def test_donnees(browser):
    print('Données : migration et restauration')
    pg = device(browser, FauxSupabase())
    pg.evaluate("([k]) => localStorage.setItem(k, JSON.stringify({ v: 2, accounts: [{ id: 'a1', name: 'C', type: 'courant', opening: 0, cash: true }], shown: ['a1'], tx: [], rec: [], plans: [], rules: [], budgets: {}, payDates: {}, csvMaps: {}, skips: [] }))", [T.KEY])
    pg.reload()
    check('anciennes données : S.paie créé vide', etat_paie(pg) == VIDE, etat_paie(pg))
    pg.evaluate("([k]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = 'n importe quoi'; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY])
    pg.reload()
    check('champ paie illisible : remplacé par une structure vide', etat_paie(pg) == VIDE, etat_paie(pg))
    pg.evaluate("([k]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = { lines: 3, slips: [], skips: 'x' }; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY])
    pg.reload()
    check('sous-champs invalides : remplacés', etat_paie(pg) == VIDE, etat_paie(pg))
    p = {'lines': [{'id': 'l1', 'label': 'Brut', 'kind': 'gain', 'amount': 100, 'start': '2026-01', 'end': ''}], 'slips': {'2026-01': {'rows': [{'k': 'l1', 'label': 'Brut', 'kind': 'gain', 'amount': 100}]}}, 'skips': []}
    ATT = {**p, 'pt': {'amount': 0, 'hist': []}, 'acf': {'amount': 0, 'hist': []}, 'lines': [{**p['lines'][0], 'mode': 'fixed'}]}
    pg.evaluate("([k, p]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, p])
    pg.reload()
    check('données valides conservées au rechargement (mode fixe et valeur du point ajoutés)', etat_paie(pg) == ATT)
    exp = pg.evaluate("() => JSON.parse(JSON.stringify(S))")
    pg.evaluate("(o) => { S = migrate(o); }", {k: v for k, v in exp.items() if k != 'paie'})
    check('restauration d\'une sauvegarde d\'avant le module : pas de plantage, paie vide', etat_paie(pg) == VIDE)
    pg.evaluate("(o) => { S = migrate(o); }", exp)
    check('restauration d\'une sauvegarde avec paie : conservée', etat_paie(pg) == ATT)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_parcours(browser):
    print('Modèle, fiches à valider, tableau et courbe')
    pg = device(browser, FauxSupabase())
    msgs = []
    ign = [False]   # réponse à « Ignorer aussi ce mois ? »
    rep_parcours = lambda d: (msgs.append(d.message), d.accept() if (ign[0] or not d.message.startswith('Ignorer aussi')) else d.dismiss())
    pg.on('dialog', rep_parcours)
    depart(pg)
    pg.evaluate("() => { S.accounts[0].anchor = { date: '2020-01-01', amount: 1000 }; reanchor(); save(); }")
    avant = pg.evaluate("() => ({ bal: balanceAt(today(), true), tx: S.tx.length, acc: JSON.stringify(S.accounts), rec: S.rec.length, due: dueRange('2000-01-01', '2100-01-01').length })")
    pg.click('[data-a=nav][data-v=rec]')
    t = norm(pg.inner_text('[data-a=openpaie]'))
    check('carte d\'entrée sur Récurrent', 'Bulletin de paye' in t and 'Suis l\'évolution' in t, t)
    pg.click('[data-a=openpaie]')
    check('la vue Bulletin de paye s\'ouvre', pg.evaluate("() => view") == 'paie' and 'Bulletin de paye' in pg.inner_text('#app'))
    check('onglet Récurrent resté actif', pg.evaluate("() => document.querySelector('nav button.on').dataset.v") == 'rec')
    check('menus repliés de base : tableau, courbe, fiches et modèle', pg.evaluate("() => ['paie-evo', 'paie-crb', 'paie-fiches', 'paie-mod'].map((k) => document.querySelector('details[data-fold=' + k + ']').open)") == [False, False, False, False])
    pg.evaluate("() => { ['paie-evo', 'paie-crb', 'paie-fiches', 'paie-mod', 'pt-gain', 'pt-ret'].forEach((k) => { FOLD[k] = true; }); render(); }")
    check('sans ligne : pas de carte « À valider », consigne dans le modèle', 'À valider' not in pg.inner_text('#app') and 'Ajoute les lignes de ton bulletin' in norm(pg.inner_text('#app')))
    check('sans fiche : tableau vide', 'Aucune fiche validée' in pg.inner_text('#app'))

    m0, m2 = mois(pg, 0), mois(pg, -2)
    ajoute_ligne(pg, 'Traitement brut', 'gain', '2500,55', m2)
    ajoute_ligne(pg, 'Retenue retraite', 'ret', '345,67', m2)
    ajoute_ligne(pg, 'Net à payer', 'tot', '2100,10', m2)
    e = etat_paie(pg)
    check('3 lignes créées, montants et types corrects', [(l['label'], l['kind'], l['amount']) for l in e['lines']] == [('Traitement brut', 'gain', 2500.55), ('Retenue retraite', 'ret', 345.67), ('Net à payer', 'tot', 2100.1)], e['lines'])
    check('liste du modèle affichée avec les montants', all(x in norm(pg.inner_text('#app')) for x in ['Traitement brut', '2 500,55', 'Retenue retraite', '345,67']))
    check('3 mois à valider (de il y a 2 mois à ce mois)', pg.evaluate("() => paDue()") == [m2, mois(pg, -1), m0], pg.evaluate("() => paDue()"))
    check('aucun mois futur à valider', mois(pg, 1) not in pg.evaluate("() => paDue()"))
    check('bouton « Tout valider (3 mois) »', '(3 mois)' in pg.inner_text('[data-a=paiall]'))

    pg.click('[data-a=paiopen][data-m="%s"]' % m2)
    ids = pg.evaluate("() => S.paie.lines.map((l) => l.id)")
    check('fiche pré-remplie avec les montants du modèle', pg.input_value('#modal .pa-a[data-k="%s"]' % ids[0]) == '2500,55' and pg.input_value('#modal .pa-a[data-k="%s"]' % ids[1]) == '345,67')
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], 'abc')
    pg.click('[data-a=saveslip]')
    check('montant invalide refusé, fiche non créée', msgs and 'invalide' in msgs[-1] and m2 not in etat_paie(pg)['slips'], msgs)
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], '2 500,55')
    pg.click('[data-a=saveslip]')
    e = etat_paie(pg)
    check('fiche validée : 3 lignes enregistrées', [r['amount'] for r in e['slips'][m2]['rows']] == [2500.55, 345.67, 2100.1], e['slips'])
    check('mois validé retiré de la liste à valider', pg.evaluate("() => paDue()") == [mois(pg, -1), m0])

    pg.click('[data-a=paiskip][data-m="%s"]' % mois(pg, -1))
    check('mois ignoré : plus à valider, gardé dans skips', pg.evaluate("() => paDue()") == [m0] and mois(pg, -1) in etat_paie(pg)['skips'])
    pg.click('[data-a=paiopen][data-m="%s"]' % m0)
    pg.click('[data-a=saveslip]')
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    check('fiche du mois courant validée', m0 in etat_paie(pg)['slips'])
    # un mois ignoré peut être renseigné ensuite : on l'ouvre directement, il sort des « ignorés »
    pg.evaluate("(m) => openSlip(m)", mois(pg, -1))
    pg.click('[data-a=saveslip]')
    e = etat_paie(pg)
    check('mois ignoré puis validé : sort de skips', mois(pg, -1) in e['slips'] and mois(pg, -1) not in e['skips'], e['skips'])
    check('plus rien à valider', pg.evaluate("() => paDue()") == [] and 'Rien à valider' in pg.inner_text('#app'))

    t = norm(pg.inner_text('table.pa')).upper()
    check('tableau : 3 mois, gains puis retenues puis totaux', t.index('GAIN') < t.index('RETENUE') < t.index('TOTAL / INFORMATION') and t.count('2 500,55') >= 3, t)
    pg.evaluate("() => { S.paie.slips['%s'].rows[0].amount = 2510.55; render(); }" % m0)
    check('montant différent de la fiche précédente en gras (classe chg)', pg.evaluate("() => document.querySelectorAll('table.pa td.chg').length") == 1)

    # courbe
    pg.evaluate("() => { FOLD['paie-crb'] = true; paSel = ''; render(); }")
    check('courbe : une ligne « Net à payer » proposée par défaut (type total)', pg.evaluate("() => document.getElementById('pa_sel').value") == ids[2])
    pg.select_option('#pa_sel', ids[0])
    check('choix de la ligne tracée', pg.evaluate("() => paSel") == ids[0] and pg.evaluate("() => document.querySelectorAll('svg circle[data-a=paipt]').length") == 3)
    check('dernier point sélectionné par défaut : montant affiché', '2 510,55' in norm(pg.inner_text('#app')))
    pg.evaluate("() => document.querySelector('circle[data-a=paipt][data-i=\"0\"]').dispatchEvent(new MouseEvent('click', { bubbles: true }))")
    check('toucher un point affiche son mois et sa valeur', '2 500,55' in norm(pg.inner_text('#app')) and pg.evaluate("() => paPt") == 0)

    # changement de grade / d'échelon : montant daté
    pg.click('[data-a=paiedit][data-id="%s"]' % ids[0])
    check('fiche de la ligne : bloc « nouveau montant » masqué au départ', pg.evaluate("() => $('pl_fromw').style.display") == 'none')
    pg.fill('#pl_amt', '2600,00')
    check('montant changé : bloc « à partir du mois » affiché', pg.evaluate("() => $('pl_fromw').style.display") == 'block')
    pick(pg, 'pl_from', m0)
    pg.fill('#pl_note', 'Passage à l\'échelon 5')
    pg.click('[data-a=savepaline]')
    ligne = etat_paie(pg)['lines'][0]
    check('historique daté enregistré avec son motif', [(h['from'], h['amount'], h.get('note')) for h in ligne['hist']] == [('0000-00', 2500.55, None), (m0, 2600.0, "Passage à l'échelon 5")], ligne['hist'])
    check('montant du modèle : ancien avant, nouveau à partir du mois choisi', pg.evaluate("(a) => [paAmt(S.paie.lines[0], a[0]), paAmt(S.paie.lines[0], a[1]), paAmt(S.paie.lines[0], a[2])]", [mois(pg, -1), m0, mois(pg, 3)]) == [2500.55, 2600.0, 2600.0])
    check('fiches validées d\'avant le mois choisi inchangées, celle du mois choisi au nouveau montant', [etat_paie(pg)['slips'][m]['rows'][0]['amount'] for m in (m2, mois(pg, -1), m0)] == [2500.55, 2500.55, 2600.0])
    check('le prochain mois sera pré-rempli au nouveau montant', pg.evaluate("(m) => paRowsFromModel(m)[0].amount", mois(pg, 1)) == 2600.0)
    check('le motif s\'affiche dans l\'historique de la ligne', "Passage à l'échelon 5" in norm(pg.evaluate("() => { FOLD['paie-hist'] = true; paSel = S.paie.lines[0].id; render(); return document.getElementById('app').innerText; }")))
    pg.click('[data-a=paiedit][data-id="%s"]' % ids[0])
    pg.fill('#pl_amt', '2700,00')
    pg.click('[data-a=savepaline]')
    check('changement de montant sans mois choisi : mois par défaut = ce mois, une 3e entrée', len(etat_paie(pg)['lines'][0]['hist']) == 2, etat_paie(pg)['lines'][0]['hist'])
    # (le mois par défaut du sélecteur est le mois courant : l'entrée du mois est remplacée, pas dupliquée)

    # prime ponctuelle
    pg.evaluate("(m) => openSlip(m)", m0)
    pg.click('[data-a=paaddx]')
    check('ligne ponctuelle ajoutée dans la fenêtre', pg.evaluate("() => document.querySelectorAll('#modal .pa-x').length") == 1)
    pg.fill('#modal .pa-xa', '300')
    pg.click('[data-a=saveslip]')
    check('prime sans libellé refusée', 'Libellé manquant' in msgs[-1], msgs[-1])
    pg.fill('#modal .pa-xl', 'Prime exceptionnelle')
    pg.click('[data-a=saveslip]')
    r = [x for x in etat_paie(pg)['slips'][m0]['rows'] if x['k'].startswith('x:')]
    check('prime enregistrée (clé issue du libellé)', len(r) == 1 and r[0]['amount'] == 300 and r[0]['kind'] == 'gain', r)
    pg.evaluate("(m) => openSlip(m)", mois(pg, -1))
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-xl', 'prime exceptionnelle')
    pg.fill('#modal .pa-xa', '150,5')
    pg.click('[data-a=saveslip]')
    serie = pg.evaluate("() => paSeries().filter((s) => s.k.startsWith('x:')).map((s) => [s.label, Object.keys(s.vals).length])")
    check('même libellé (casse près) sur deux mois : une seule série', len(serie) == 1 and serie[0][1] == 2, serie)
    check('réouverture d\'une fiche : la prime revient comme ligne ponctuelle', pg.evaluate("(m) => { openSlip(m); return document.querySelectorAll('#modal .pa-x').length; }", m0) == 1 and pg.input_value('#modal .pa-xl') == 'Prime exceptionnelle')
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-x:nth-of-type(2) .pa-xl', 'PRIME EXCEPTIONNELLE')
    pg.fill('#modal .pa-x:nth-of-type(2) .pa-xa', '10')
    pg.click('[data-a=saveslip]')
    check('deux lignes ponctuelles au même libellé dans une fiche : refusé', 'même libellé' in msgs[-1], msgs[-1])
    pg.click('[data-a=closem]')

    # suppression rapide d'une ligne ponctuelle : bouton ✕, sans vider le libellé
    pg.evaluate("(m) => openSlip(m)", m0)
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-x:nth-of-type(2) .pa-xl', 'Autre prime')
    pg.fill('#modal .pa-x:nth-of-type(2) .pa-xa', '40')
    check('✕ présent sur chaque ligne ponctuelle', pg.locator('#modal .pa-x [data-a=paxdel]').count() == 2)
    pg.click('#modal .pa-x:nth-of-type(1) [data-a=paxdel]')
    check('✕ : la ligne disparaît de la fenêtre, l\'autre reste', pg.locator('#modal .pa-x').count() == 1 and pg.input_value('#modal .pa-xl') == 'Autre prime')
    pg.click('[data-a=saveslip]')
    r = [x['label'] for x in etat_paie(pg)['slips'][m0]['rows'] if x['k'].startswith('x:')]
    check('enregistrement : la ligne supprimée n\'est plus dans la fiche, l\'autre est gardée', r == ['Autre prime'], r)
    pg.evaluate("(m) => openSlip(m)", m0)
    pg.click('[data-a=paxdel]')
    pg.click('[data-a=closem]')
    check('✕ puis fermeture sans enregistrer : rien n\'est modifié', [x['label'] for x in etat_paie(pg)['slips'][m0]['rows'] if x['k'].startswith('x:')] == ['Autre prime'])
    pg.evaluate("(m) => openSlip(m)", m0)
    pg.click('[data-a=paxdel]')
    pg.click('[data-a=saveslip]')
    check('dernière ligne ponctuelle supprimée : la fiche est enregistrée sans elle', not [x for x in etat_paie(pg)['slips'][m0]['rows'] if x['k'].startswith('x:')], etat_paie(pg)['slips'][m0]['rows'])

    # supprimer une fiche et valider en bloc
    pg.evaluate("(m) => openSlip(m)", m2)
    pg.click('[data-a=delslip]')
    check('fiche supprimée, « Annuler » à la question « Ignorer aussi » : le mois revient à valider', m2 not in etat_paie(pg)['slips'] and pg.evaluate("() => paDue()") == [m2] and m2 not in etat_paie(pg)['skips'] and any(x.startswith('Ignorer aussi ce mois') for x in msgs), msgs)
    ign[0] = True
    pg.evaluate("(m) => { S.paie.slips[m] = { rows: [{ k: S.paie.lines[0].id, label: 'x', kind: 'gain', amount: 1 }] }; render(); openSlip(m); }", m2)
    pg.click('[data-a=delslip]')
    check('fiche supprimée, « OK » à la question « Ignorer aussi » : mois ignoré, plus à valider', m2 not in etat_paie(pg)['slips'] and m2 in etat_paie(pg)['skips'] and m2 not in pg.evaluate("() => paDue()"), etat_paie(pg)['skips'])
    pg.evaluate("() => { S.paie.slips = {}; S.paie.skips = []; render(); }")
    msgs.clear()
    pg.click('[data-a=paiall]')
    check('« Tout valider » : 3 fiches créées aux montants du modèle, confirmation demandée', len(etat_paie(pg)['slips']) == 3 and msgs and 'Valider 3 mois' in msgs[0], msgs)
    check('plus rien à valider après « Tout valider »', pg.evaluate("() => paDue()") == [])

    # ligne supprimée : fiches conservées (réponse « Annuler » à la question « Retirer aussi des fiches validées ? »)
    pg.remove_listener('dialog', rep_parcours)
    ign[0] = False
    rep_suite = lambda d: (msgs.append(d.message), d.dismiss() if d.message.startswith(('Retirer aussi', 'Ignorer aussi')) else d.accept())
    pg.on('dialog', rep_suite)
    pg.click('[data-a=paiedit][data-id="%s"]' % ids[1])
    pg.click('[data-a=delpaline]')
    e = etat_paie(pg)
    check('ligne supprimée du modèle, fiches validées conservées', len(e['lines']) == 2 and all(any(r['k'] == ids[1] for r in s['rows']) for s in e['slips'].values()))
    check('ligne supprimée : toujours visible dans le tableau', 'Retenue retraite' in norm(pg.inner_text('table.pa')))
    pg.evaluate("(m) => openSlip(m)", m0)
    check('fiche rouverte : la ligne supprimée revient en ponctuelle avec sa clé d\'origine', pg.evaluate("() => document.querySelectorAll('#modal .pa-x[data-k]').length") >= 1)
    pg.click('[data-a=saveslip]')
    check('enregistrer sans toucher garde la même série (clé d\'origine)', all(any(r['k'] == ids[1] for r in s['rows']) for s in etat_paie(pg)['slips'].values()))

    # fin de ligne
    pg.evaluate("() => { S.paie.lines[0].end = '%s'; save(); }" % mois(pg, -1))
    check('ligne terminée : plus de mois à valider pour elle', pg.evaluate("(m) => paRowsFromModel(m).every((r) => r.k !== S.paie.lines[0].id)", m0))
    # fenêtre du tableau
    pg.evaluate("() => { paWin = 0; render(); }")
    pg.click('[data-a=pawin][data-d="1"]') if pg.evaluate("() => paSlipMonths().length") > 3 else None
    check('fenêtre du tableau : trois mois au plus', pg.evaluate("() => document.querySelectorAll('table.pa thead th.n').length") <= 3)

    # aucun effet sur le reste
    apres = pg.evaluate("() => ({ bal: balanceAt(today(), true), tx: S.tx.length, acc: JSON.stringify(S.accounts), rec: S.rec.length, due: dueRange('2000-01-01', '2100-01-01').length })")
    check('aucun effet sur les comptes, soldes, lignes, récurrences ni échéances', apres == avant, (avant, apres))
    check('le budget du jour et le patrimoine ne lisent pas le module', pg.evaluate("() => !budgetInfo.toString().includes('paie') && !patrimoine.toString().includes('paie') && !balanceAt.toString().includes('paie')"))
    pg.click('[data-a=paieback]')
    check('retour : la vue Récurrent revient', pg.evaluate("() => view") == 'rec' and 'À valider' in pg.inner_text('#app'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_propagation(browser):
    print('Corriger un mois : le changement vaut pour les mois suivants (comme les récurrences)')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    mm = {k: mois(pg, k) for k in range(-5, 2)}
    ajoute_ligne(pg, 'Brut', 'gain', '1000', mm[-5])
    ajoute_ligne(pg, 'Net', 'tot', '800', mm[-5])
    pg.click('[data-a=paiall]')
    ids = pg.evaluate("() => S.paie.lines.map((l) => l.id)")

    def montants(k, i=0):
        return [etat_paie(pg)['slips'][mm[j]]['rows'][i]['amount'] for j in range(-5, 1)] if k is None else None

    def brut():
        return [etat_paie(pg)['slips'][mm[j]]['rows'][0]['amount'] for j in range(-5, 1)]

    def net():
        return [etat_paie(pg)['slips'][mm[j]]['rows'][1]['amount'] for j in range(-5, 1)]

    check('6 fiches validées à 1000 (rattrapage)', brut() == [1000] * 6, brut())
    # mois 3 : 1000 -> 1500
    pg.evaluate("(m) => openSlip(m)", mm[-2])
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], '1500')
    pg.click('[data-a=saveslip]')
    t = norm(pg.inner_text('#modal'))
    check('montant changé : la question « mois suivants » est posée', 'Appliquer aux mois suivants' in t and 'Brut' in t and '1 000,00 € → 1 500,00 €' in t, t)
    check('la question annonce le nombre de fiches suivantes touchées (2)', '2 fiches déjà validées après ce mois' in t, t)
    check('rien n\'est enregistré tant qu\'on n\'a pas répondu', brut() == [1000] * 6)
    pg.click('[data-a=paipback]')
    check('« Retour » rouvre la fiche avec la valeur saisie', pg.input_value('#modal .pa-a[data-k="%s"]' % ids[0]) == '1500')
    pg.click('[data-a=saveslip]')
    pg.fill('#pp_note', 'Passage à l\'échelon 5')
    pg.click('[data-a=paipropag]')
    check('« À partir de ce mois » : ce mois et les suivants à 1500, les précédents inchangés', brut() == [1000, 1000, 1000, 1500, 1500, 1500], brut())
    check('l\'autre ligne n\'est pas touchée', net() == [800] * 6, net())
    h = etat_paie(pg)['lines'][0]['hist']
    check('modèle mis à jour : historique daté avec motif', [(e['from'], e['amount'], e.get('note')) for e in h] == [('0000-00', 1000, None), (mm[-2], 1500, "Passage à l'échelon 5")], h)
    check('les mois à venir sont pré-remplis à 1500', pg.evaluate("(m) => paRowsFromModel(m)[0].amount", mm[1]) == 1500)
    check('fenêtre refermée', pg.evaluate("() => !document.getElementById('modal').classList.contains('open')"))

    # variation ponctuelle : ce mois seulement
    pg.evaluate("(m) => openSlip(m)", mm[-1])
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], '1200')
    pg.click('[data-a=saveslip]')
    pg.check('#modal input[name=pp_0][value=one]')
    pg.click('[data-a=paipropag]')
    check('« Ce mois seulement » : seule cette fiche change, modèle inchangé', brut() == [1000, 1000, 1000, 1500, 1200, 1500] and len(etat_paie(pg)['lines'][0]['hist']) == 2, brut())
    # rouvrir la fiche ponctuelle sans la toucher : aucune question
    pg.evaluate("(m) => openSlip(m)", mm[-1])
    pg.click('[data-a=saveslip]')
    check('fiche différente du modèle rouverte puis enregistrée sans changement : aucune question', 'Appliquer aux mois suivants' not in pg.inner_text('body') and brut()[4] == 1200)
    # corriger une fiche ponctuelle dont la ligne diffère déjà : la question compare à la valeur de la fiche
    pg.evaluate("(m) => openSlip(m)", mm[-1])
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], '1250')
    pg.click('[data-a=saveslip]')
    check('la question compare à la valeur de la fiche (1 200 → 1 250)', '1 200,00 € → 1 250,00 €' in norm(pg.inner_text('#modal')))
    pg.click('[data-a=paipback]')
    pg.click('[data-a=closem]')
    # prime : jamais de question
    pg.evaluate("(m) => openSlip(m)", mm[0])
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-xl', 'Prime test')
    pg.fill('#modal .pa-xa', '200')
    pg.click('[data-a=saveslip]')
    check('ligne ponctuelle : jamais de question, pas de propagation', 'Appliquer aux mois suivants' not in pg.inner_text('body') and any(r['k'].startswith('x:') for r in etat_paie(pg)['slips'][mm[0]]['rows']))
    check('une prime ne change pas le modèle', len(etat_paie(pg)['lines']) == 2)
    # fiche nouvelle : la correction vaut pour la suite
    pg.evaluate("(m) => { delete S.paie.slips[m]; render(); }", mm[0])
    pg.click('[data-a=paiopen][data-m="%s"]' % mm[0])
    pg.fill('#modal .pa-a[data-k="%s"]' % ids[0], '1600')
    pg.click('[data-a=saveslip]')
    t = norm(pg.inner_text('#modal'))
    check('fiche nouvelle : question posée, sans mention de fiches suivantes (aucune)', 'Appliquer aux mois suivants' in t and 'fiche' not in t.split('Brut', 1)[1].split('Motif')[0], t)
    pg.click('[data-a=paipropag]')
    check('fiche nouvelle enregistrée, mois suivants pré-remplis à 1600', etat_paie(pg)['slips'][mm[0]]['rows'][0]['amount'] == 1600 and pg.evaluate("(m) => paRowsFromModel(m)[0].amount", mm[1]) == 1600)
    # même règle depuis la fenêtre de la ligne du modèle
    msgs.clear()
    pg.click('[data-a=paiedit][data-id="%s"]' % ids[0])
    pg.fill('#pl_amt', '2000')
    pick(pg, 'pl_from', mm[-2])
    pg.click('[data-a=savepaline]')
    check('fenêtre de la ligne : confirmation avec le nombre de fiches touchées (3)', msgs and msgs[0].startswith('3 fiches déjà validées') and 'seront modifiées' in msgs[0], msgs)
    check('fiches du mois choisi et suivantes au nouveau montant, précédentes inchangées', [etat_paie(pg)['slips'][mm[j]]['rows'][0]['amount'] for j in range(-5, 1)] == [1000, 1000, 1000, 2000, 2000, 2000], brut())
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_selection_suppression(browser):
    print('Sélectionner des fiches pour les supprimer')
    pg = device(browser, FauxSupabase())
    msgs = []
    refus = [False]
    ignore = [False]   # réponse à la question « Ignorer aussi ces mois ? »

    def rep(d):
        msgs.append(d.message)
        ok = ignore[0] if d.message.startswith('Ignorer aussi') else not refus[0]
        d.accept() if ok else d.dismiss()
    pg.on('dialog', rep)
    depart(pg)
    ouvre_paie(pg)
    mm = {k: mois(pg, k) for k in range(-4, 2)}
    ajoute_ligne(pg, 'Brut', 'gain', '1000', mm[-4])
    pg.click('[data-a=paiall]')
    check('5 fiches validées pour le test', len(etat_paie(pg)['slips']) == 5)
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    check('bouton « Sélectionner » dans les fiches validées', pg.locator('[data-a=paisel]').count() == 1)
    pg.click('[data-a=paisel]')
    check('mode sélection : cases vides, « Supprimer (0) » désactivé', pg.inner_text('[data-a=paidel]').strip() == 'Supprimer (0)' and pg.evaluate("() => document.querySelector('[data-a=paidel]').disabled") is True)
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-3])
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-1])
    check('deux fiches cochées : compteur à 2 et cases ☑', pg.inner_text('[data-a=paidel]').strip() == 'Supprimer (2)' and pg.inner_text('[data-a=paitog][data-m="%s"]' % mm[-3]).count('☑') == 1)
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-1])
    check('toucher une fiche cochée la décoche', pg.inner_text('[data-a=paidel]').strip() == 'Supprimer (1)')
    pg.click('[data-a=paiselall]')
    check('« Tout sélectionner » : les 5 fiches', pg.inner_text('[data-a=paidel]').strip() == 'Supprimer (5)')
    pg.click('[data-a=paiselall]')
    check('« Tout désélectionner » : plus aucune', pg.inner_text('[data-a=paidel]').strip() == 'Supprimer (0)')
    check('en mode sélection, toucher une fiche ne l\'ouvre pas', not pg.evaluate("() => document.getElementById('modal').classList.contains('open')"))
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-3])
    pg.click('[data-a=paitog][data-m="%s"]' % mm[0])
    refus[0] = True
    pg.click('[data-a=paidel]')
    check('confirmation demandée (2 fiches) ; refusée : rien n\'est supprimé', msgs and msgs[-1].startswith('Supprimer 2 fiches') and len(etat_paie(pg)['slips']) == 5, msgs)
    refus[0] = False
    pg.click('[data-a=paidel]')
    e = etat_paie(pg)
    check('confirmée : les 2 fiches cochées sont supprimées, les autres gardées', sorted(e['slips']) == [mm[-4], mm[-2], mm[-1]], sorted(e['slips']))
    check('sortie du mode sélection après suppression', pg.locator('[data-a=paisel]').count() == 1 and pg.locator('[data-a=paidel]').count() == 0)
    check('les mois supprimés reviennent dans « À valider »', pg.evaluate("() => paDue()") == [mm[-3], mm[0]], pg.evaluate("() => paDue()"))
    check('le modèle est intact', len(e['lines']) == 1 and e['lines'][0]['amount'] == 1000)
    check('question « Ignorer aussi ces 2 mois » posée, refusée : aucun mois ignoré', any(x.startswith('Ignorer aussi ces 2 mois') for x in msgs) and e['skips'] == [], msgs)
    # suppression en masse avec « supprimer et ignorer »
    ignore[0] = True
    pg.click('[data-a=paisel]')
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-4])
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-2])
    pg.click('[data-a=paidel]')
    e = etat_paie(pg)
    check('« supprimer et ignorer » : les 2 mois sont ignorés, non remis à valider', sorted(e['skips']) == [mm[-4], mm[-2]] and mm[-4] not in e['slips'] and mm[-2] not in e['slips'] and mm[-4] not in pg.evaluate("() => paDue()") and mm[-2] not in pg.evaluate("() => paDue()"), (e['skips'], pg.evaluate("() => paDue()")))
    check('les mois ignorés apparaissent dans « Mois ignorés »', pg.locator('[data-a=paiunskip]').count() == 2)
    ignore[0] = False
    pg.evaluate("(m) => { S.paie.skips = []; S.paie.slips[m] = { rows: [{ k: S.paie.lines[0].id, label: 'Brut', kind: 'gain', amount: 1000 }] }; render(); }", mm[-2])
    # annuler la sélection, puis quitter la page en cours de sélection
    pg.click('[data-a=paisel]')
    pg.click('[data-a=paitog][data-m="%s"]' % mm[-2])
    pg.click('[data-a=paiselend]')
    check('« Annuler » : rien n\'est supprimé, fiches ouvrables de nouveau', pg.locator('[data-a=paisel]').count() == 1 and mm[-2] in etat_paie(pg)['slips'])
    pg.click('[data-a=paisel]')
    pg.click('[data-a=paieback]')
    ouvre_paie(pg)
    check('quitter la page en pleine sélection : la sélection est abandonnée', pg.evaluate("() => paSelM") is None)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_tableau_repli(browser):
    print('Tableau d\'évolution : gains et retenues repliés de base, totaux toujours visibles')
    pg = device(browser, FauxSupabase())
    depart(pg)
    ouvre_paie(pg)
    ms = [mois(pg, k) for k in range(-2, 1)]
    pg.evaluate("""(ms) => {
      const mk = (id, label, kind, amount) => ({ id, label, kind, amount, start: ms[0], end: '', mode: 'fixed' });
      S.paie.lines = [mk('g', 'Traitement', 'gain', 1000), mk('p', 'Prime', 'gain', 100), mk('r', 'Retraite', 'ret', 100), mk('n', 'Net imprimé', 'tot', 900)];
      S.paie.slips = {};
      ms.forEach((m) => { S.paie.slips[m] = { rows: [{ k: 'g', label: 'Traitement', kind: 'gain', amount: 1000 }, { k: 'p', label: 'Prime', kind: 'gain', amount: 50 }, { k: 'r', label: 'Retraite', kind: 'ret', amount: 120 }, { k: 'n', label: 'Net imprimé', kind: 'tot', amount: 800 }] }; });
      FOLD['paie-evo'] = true; delete FOLD['pt-gain']; delete FOLD['pt-ret']; paWin = 0; render();
    }""", ms)
    libs = lambda: pg.evaluate("() => [...document.querySelectorAll('table.pa td.l')].map((e) => e.textContent)")
    cell_tot = lambda lib: pg.evaluate("(l) => { const tr = [...document.querySelectorAll('table.pa tbody tr')].find((x) => x.querySelector('td.l') && x.querySelector('td.l').textContent === l); return tr ? [...tr.querySelectorAll('td.n, td.tc')].map((e) => e.textContent) : null; }", lib)
    check('de base : lignes de gains et de retenues masquées, totaux et ligne « total / information » visibles', libs() == ['Total des gains', 'Total des retenues', 'Net calculé', 'Net imprimé'], libs())
    check('de base : « Traitement » et « Retraite » absents', 'Traitement' not in pg.inner_text('table.pa') and 'Retraite' not in pg.inner_text('table.pa'))
    check('totaux inchangés une fois repliés (gains 3 × 1 050 = 3 150,00 ; retenues 3 × 120 = 360,00)', cell_tot('Total des gains')[-1].replace('\u202f', ' ') == '3 150,00' and cell_tot('Total des retenues')[-1] == '360,00', (cell_tot('Total des gains'), cell_tot('Total des retenues')))
    pg.click('tr.pa-fh[data-k=gain]')
    check('gains dépliés : lignes visibles, retenues toujours repliées', 'Traitement' in pg.inner_text('table.pa') and 'Prime' in pg.inner_text('table.pa') and 'Retraite' not in pg.inner_text('table.pa'))
    pg.click('tr.pa-fh[data-k=ret]')
    check('retenues dépliées aussi', 'Retraite' in pg.inner_text('table.pa'))
    check('état mémorisé sur l\'appareil (hors données synchronisées)', pg.evaluate("() => JSON.parse(localStorage.getItem('compte-replis'))") .get('pt-gain') is True and 'pt-gain' not in json.dumps(etat_paie(pg)))
    pg.click('tr.pa-fh[data-k=gain]')
    check('gains repliés de nouveau', 'Traitement' not in pg.inner_text('table.pa') and 'Retraite' in pg.inner_text('table.pa'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_ligne_dans_fiches_existantes(browser):
    print('Nouvelle ligne du modèle : proposée aux fiches déjà validées')
    pg = device(browser, FauxSupabase())
    msgs = []
    refus = [False]
    pg.on('dialog', lambda d: (msgs.append(d.message), d.dismiss() if refus[0] else d.accept()))
    depart(pg)
    ouvre_paie(pg)
    mm = {k: mois(pg, k) for k in range(-3, 2)}
    ajoute_ligne(pg, 'Brut', 'gain', '1000', mm[-3])
    pg.click('[data-a=paiall]')
    check('4 fiches validées avec une seule ligne', len(etat_paie(pg)['slips']) == 4 and all(len(s['rows']) == 1 for s in etat_paie(pg)['slips'].values()))
    msgs.clear()
    ajoute_ligne(pg, 'Indemnité', 'gain', '120,50', mm[-1])
    check('question posée : 2 fiches (de il y a 1 mois à ce mois)', msgs and msgs[0].startswith('Ajouter « Indemnité » aux 2 fiches déjà validées'), msgs)
    sl = etat_paie(pg)['slips']
    check('ligne ajoutée aux fiches couvertes (début = mois choisi), avec le montant du modèle', [any(r['k'] == etat_paie(pg)['lines'][1]['id'] and r['amount'] == 120.5 for r in sl[mm[j]]['rows']) for j in (-3, -2, -1, 0)] == [False, False, True, True], [len(sl[mm[j]]['rows']) for j in (-3, -2, -1, 0)])
    check('la ligne apparaît dans le tableau avec « — » avant son début', '120,50' in norm(pg.inner_text('table.pa')) and '—' in pg.inner_text('table.pa'))
    # début avancé : les mois nouvellement couverts sont proposés
    msgs.clear()
    pg.click('[data-a=paiedit][data-id="%s"]' % etat_paie(pg)['lines'][1]['id'])
    pick(pg, 'pl_start', mm[-3])
    pg.click('[data-a=savepaline]')
    check('début avancé de 2 mois : question pour les 2 mois nouvellement couverts seulement', msgs and msgs[0].startswith('Ajouter « Indemnité » aux 2 fiches'), msgs)
    sl = etat_paie(pg)['slips']
    check('les 4 fiches ont maintenant la ligne', all(any(r['label'] == 'Indemnité' for r in sl[mm[j]]['rows']) for j in (-3, -2, -1, 0)))
    # modification sans changement de période : aucune question
    msgs.clear()
    pg.click('[data-a=paiedit][data-id="%s"]' % etat_paie(pg)['lines'][1]['id'])
    pg.fill('#pl_lab', 'Indemnité de résidence')
    pg.click('[data-a=savepaline]')
    check('renommer la ligne : aucune question', msgs == [], msgs)
    # fiche rouverte à blanc volontairement : pas rajoutée
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.label === 'Brut'); save(); }", mm[-2])
    pg.click('[data-a=paiedit][data-id="%s"]' % etat_paie(pg)['lines'][1]['id'])
    pg.fill('#pl_lab', 'Indemnité')
    pg.click('[data-a=savepaline]')
    check('mois laissé vide volontairement : pas ré-ajouté à chaque modification', msgs == [] and not any(r['label'].startswith('Indemnité') for r in etat_paie(pg)['slips'][mm[-2]]['rows']), msgs)
    # refus : la ligne est créée, les fiches restent intactes
    refus[0] = True
    ajoute_ligne(pg, 'Prime de test', 'gain', '50', mm[-3])
    check('question refusée : la ligne est créée, aucune fiche modifiée', len(etat_paie(pg)['lines']) == 3 and all(not any(r['label'] == 'Prime de test' for r in s['rows']) for s in etat_paie(pg)['slips'].values()))
    refus[0] = False
    # ligne qui ne couvre aucun mois déjà validé : aucune question
    msgs.clear()
    ajoute_ligne(pg, 'Ligne future', 'gain', '10', mm[1])
    check('ligne démarrant le mois prochain : aucune question', msgs == [], msgs)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_net_calcule(browser):
    print('Net calculé (gains − retenues) sur chaque fiche ; aucune ligne « net à payer » n\'est lue')
    pg = device(browser, FauxSupabase())
    depart(pg)
    m = mois(pg, 0)
    pg.evaluate("([k, p]) => { const s = defaultState(); s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, {'lines': [], 'skips': [], 'slips': {m: {'rows': [
        {'k': 'a', 'label': 'Traitement', 'kind': 'gain', 'amount': 2500}, {'k': 'b', 'label': 'Indemnité', 'kind': 'gain', 'amount': 100.5},
        {'k': 'c', 'label': 'Retraite', 'kind': 'ret', 'amount': 345.67}, {'k': 'd', 'label': 'Brut', 'kind': 'tot', 'amount': 2600.5},
        {'k': 'e', 'label': 'Net à payer', 'kind': 'tot', 'amount': 1999.99}]}}}])
    pg.reload()
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    sel = '[data-a=paislip][data-m="%s"]' % m
    t = norm(pg.inner_text(sel))
    check('la fiche affiche son net calculé (2500 + 100,50 − 345,67 = 2 254,83)', '2 254,83 €' in t and 'Net à payer' in t, t)
    check('la ligne « Net à payer » saisie n\'est pas lue à la place du net calculé', '1 999,99' not in t, t)
    check('plus de message d\'aide sur une ligne « Net à payer »', 'nomme une ligne' not in pg.inner_text('#app'))
    check('les lignes « total / information » ne comptent pas dans le calcul', pg.evaluate("(m) => paNet(S.paie.slips[m].rows)", m) == 2254.83)
    check('le net calculé ne dépend pas du nom des lignes', not pg.evaluate("() => paNet.toString().includes('NET') || typeof paNetRow !== 'undefined'"))
    pg.evaluate("(m) => openSlip(m)", m)
    tt = norm(pg.inner_text('#pa_tot'))
    check('fiche ouverte : total des gains 2 600,50, total des retenues 345,67, net calculé 2 254,83', 'Total des gains' in tt and '2 600,50 €' in tt and 'Total des retenues' in tt and '345,67 €' in tt and 'Net calculé' in tt and '2 254,83 €' in tt, tt)
    pg.click('[data-a=closem]')
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.k !== 'e'); render(); }", m)
    check('sans ligne « net à payer » : le net calculé est identique', '2 254,83 €' in norm(pg.inner_text(sel)))
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.kind !== 'gain'); render(); }", m)
    t = norm(pg.inner_text(sel))
    check('sans aucune ligne de gain : tiret, jamais un montant négatif inventé', '—' in t and 'Net à payer' in t and '345' not in t, t)
    pg.evaluate("(m) => { S.paie.slips[m].rows = [{ k: 'a', label: 'Traitement', kind: 'gain', amount: 1000 }, { k: 'c', label: 'Retraite', kind: 'ret', amount: 1500 }]; render(); }", m)
    t = norm(pg.inner_text(sel))
    check('retenues supérieures aux gains : net calculé négatif affiché tel quel', '-500,00 €' in t or '−500,00 €' in t, t)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_totaux_fiche(browser):
    print('Brut, net avant impôt (sans prélèvement à la source), net à payer, retenues en % du brut')
    pg = device(browser, FauxSupabase())
    depart(pg)
    m = mois(pg, 0)
    rows = [{'k': 'a', 'label': 'Traitement', 'kind': 'gain', 'amount': 2000}, {'k': 'b', 'label': 'Primes', 'kind': 'gain', 'amount': 500},
            {'k': 'c', 'label': 'Retraite', 'kind': 'ret', 'amount': 300}, {'k': 'p', 'label': 'Prélèvement à la source', 'kind': 'ret', 'amount': 200},
            {'k': 'd', 'label': 'Net imprimé', 'kind': 'tot', 'amount': 1}]
    pg.evaluate("([k, p]) => { const s = defaultState(); s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, {'lines': [], 'skips': [], 'slips': {m: {'rows': rows}}}])
    pg.reload()
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    sel = '[data-a=paislip][data-m="%s"]' % m
    t = norm(pg.inner_text(sel))
    check('brut = tous les gains (2 500,00 €)', 'Brut' in t and '2 500,00 €' in t, t)
    check('net à payer = gains − toutes les retenues (2 000,00 €)', 'Net à payer' in t and '2 000,00 €' in t, t)
    check('net avant impôt = net à payer + prélèvement à la source (2 200,00 €)', 'Net avant impôt' in t and '2 200,00 €' in t, t)
    check('retenues en % du brut ((300 + 200) ÷ 2500 = 20,0 %)', '20,0 %' in t, t)
    check('brut, net avant impôt et net à payer sur la même ligne (3 cases), ratio en haut à droite', pg.locator(sel + ' .pa-sum > div').count() == 3 and 'Retenues' not in norm(pg.inner_text(sel + ' .pa-sum')) and 'Net à payer' in norm(pg.inner_text(sel + ' .pa-sum')) and '20,0 %' in norm(pg.inner_text(sel + ' > .a')), t)
    check('lignes total / information ignorées', '1,00' not in t, t)
    pg.evaluate("(m) => { S.paie.slips[m].rows[3].label = 'PRELEVEMENT  a la source (mensuel)'; render(); }", m)
    check('libellé repéré sans tenir compte des accents ni de la casse', '2 200,00 €' in norm(pg.inner_text(sel)))
    pg.evaluate("(m) => { S.paie.slips[m].rows[3].label = 'Impôt'; render(); }", m)
    t = norm(pg.inner_text(sel))
    check('sans ligne « Prélèvement à la source » : net avant impôt affiché, égal au net à payer (2 000,00 € deux fois)', t.count('2 000,00 €') == 2 and '2 200,00 €' not in t and '—' not in t and pg.evaluate("(m) => paSums(S.paie.slips[m].rows).hasPas", m) is False, t)
    pg.evaluate("(m) => { S.paie.slips[m].rows[3].kind = 'gain'; S.paie.slips[m].rows[3].label = 'Prélèvement à la source'; render(); }", m)
    check('une ligne PAS qui n\'est pas une retenue n\'est pas prise pour le PAS', pg.evaluate("(m) => paSums(S.paie.slips[m].rows).hasPas", m) is False)
    pg.evaluate("(m) => { S.paie.slips[m].rows = [{ k: 'a', label: 'X', kind: 'ret', amount: 5 }]; render(); }", m)
    check('sans gain : pas de totaux, pas de division par zéro', '—' in norm(pg.inner_text(sel)) and 'NaN' not in pg.inner_text('#app') and 'Infinity' not in pg.inner_text('#app'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_ordre_modele(browser):
    print('Ordre des lignes du modèle (monter / descendre)')
    pg = device(browser, FauxSupabase())
    depart(pg)
    m = mois(pg, 0)
    L = lambda i, n, k: {'id': i, 'label': n, 'kind': k, 'amount': 10, 'start': m, 'end': '', 'mode': 'fixed'}
    depart(pg, {'lines': [L('a', 'Alpha', 'gain'), L('r', 'Retenue1', 'ret'), L('b', 'Bravo', 'gain'), L('c', 'Charlie', 'gain')], 'slips': {m: {'rows': [
        {'k': i, 'label': n, 'kind': k, 'amount': 10} for i, n, k in [('a', 'Alpha', 'gain'), ('r', 'Retenue1', 'ret'), ('b', 'Bravo', 'gain'), ('c', 'Charlie', 'gain')]]}}, 'skips': []})
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-mod'] = true; FOLD['paie-evo'] = true; FOLD['pt-gain'] = true; FOLD['pt-ret'] = true; render(); }")
    ordre = lambda: pg.evaluate("() => [...document.querySelectorAll('[data-a=paiedit] .l')].map((e) => e.textContent)")
    check('affichage : gains puis retenues, ordre du modèle', ordre() == ['Alpha', 'Bravo', 'Charlie', 'Retenue1'], ordre())
    check('première ligne de chaque type : « monter » inactif, dernière : « descendre » inactif', pg.evaluate("() => [...document.querySelectorAll('[data-a=pamove]')].filter((b) => b.disabled).map((b) => b.closest('.row').querySelector('.l').textContent + b.dataset.d)") == ['Alpha-1', 'Charlie1', 'Retenue1-1', 'Retenue11'])
    pg.click('[data-a=pamove][data-id=c][data-d="-1"]')
    check('Charlie monté d\'un cran (passe devant Bravo)', ordre() == ['Alpha', 'Charlie', 'Bravo', 'Retenue1'], ordre())
    check('ordre enregistré dans le modèle (sans toucher aux montants ni aux fiches)', pg.evaluate("() => S.paie.lines.map((l) => l.id).join('')") .replace('r', '') == 'acb' and pg.evaluate("() => S.paie.lines.every((l) => l.amount === 10) && Object.keys(S.paie.slips).length") == 1)
    pg.click('[data-a=pamove][data-id=a][data-d="1"]')
    pg.click('[data-a=pamove][data-id=a][data-d="1"]')
    check('Alpha descendu jusqu\'en bas des gains', ordre() == ['Charlie', 'Bravo', 'Alpha', 'Retenue1'], ordre())
    pg.reload()
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-mod'] = true; FOLD['paie-evo'] = true; FOLD['pt-gain'] = true; FOLD['pt-ret'] = true; render(); }")
    check('ordre conservé au rechargement', ordre() == ['Charlie', 'Bravo', 'Alpha', 'Retenue1'], ordre())
    tab = pg.evaluate("() => [...document.querySelectorAll('table.pa td.l')].map((e) => e.textContent)")
    check('tableau d\'évolution dans le même ordre (avec les lignes de total)', tab == ['Charlie', 'Bravo', 'Alpha', 'Total des gains', 'Retenue1', 'Total des retenues', 'Net calculé'], tab)
    pg.evaluate("(m) => openSlip(m)", m)
    fiche = pg.evaluate("() => [...document.querySelectorAll('#modal .pa-a')].map((e) => e.closest('label').textContent.split(' ·')[0].trim())")
    check('fiche : même ordre', fiche == ['Charlie', 'Bravo', 'Alpha', 'Retenue1'], fiche)
    pg.click('[data-a=closem]')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_validation_ligne(browser):
    print('Formulaire d\'une ligne : contrôles')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.click('[data-a=savepaline]')
    check('libellé manquant refusé', 'Libellé manquant' in msgs[-1], msgs)
    pg.fill('#pl_lab', 'Brut')
    pg.click('[data-a=savepaline]')
    check('montant manquant refusé', 'Montant invalide' in msgs[-1], msgs)
    pg.fill('#pl_amt', '100')
    pick(pg, 'pl_start', mois(pg, -1))
    pick(pg, 'pl_end', mois(pg, -3))
    pg.click('[data-a=savepaline]')
    check('fin avant le début refusée', 'ne peut pas précéder' in msgs[-1], msgs)
    check('aucune ligne créée par les refus', etat_paie(pg)['lines'] == [])
    pg.select_option('#pl_end_m', '')
    pg.select_option('#pl_end_y', '')
    pg.fill('#pl_amt', '-100')
    pg.click('[data-a=savepaline]')
    check('montant négatif saisi : enregistré en valeur absolue (le type porte le sens)', etat_paie(pg)['lines'][0]['amount'] == 100)
    check('dernière fiche facultative : vide = pas de fin', etat_paie(pg)['lines'][0]['end'] == '')
    check('fenêtre refermée après enregistrement', pg.evaluate("() => !document.getElementById('modal').classList.contains('open')"))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_mois_ignores(browser):
    print('Mois ignorés : remise à valider')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.accept())
    m0, m1, m2 = mois(pg, -2), mois(pg, -1), mois(pg, 0)
    depart(pg, {'lines': [{'id': 'l1', 'label': 'Brut', 'kind': 'gain', 'amount': 100, 'start': m0, 'end': '', 'mode': 'fixed'}], 'slips': {}, 'skips': [m0, m1]})
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    check('mois ignorés listés, seul le mois courant à valider', pg.evaluate("() => paDue()") == [m2] and 'Mois ignorés' in pg.inner_text('#app') and len(pg.query_selector_all('[data-a=paiunskip]')) == 2)
    check('menu « Mois ignorés (2) » replié de base : titre visible, mois masqués', 'Mois ignorés (2)' in pg.inner_text('#app') and not pg.is_visible('[data-a=paiunskip][data-m="%s"]' % m0))
    pg.click('details[data-fold="paie-skips"] > summary')
    pg.wait_for_timeout(150)
    check('menu ouvert : mois visibles', pg.is_visible('[data-a=paiunskip][data-m="%s"]' % m0))
    pg.click('details[data-fold="paie-skips"] > summary')
    pg.wait_for_timeout(150)
    check('menu refermé : les mois ignorés sont masqués, le titre reste', not pg.is_visible('[data-a=paiunskip][data-m="%s"]' % m0) and 'Mois ignorés (2)' in pg.inner_text('#app'))
    pg.evaluate("() => render()")
    check('refermé : reste fermé après un nouvel affichage (état gardé sur l\'appareil)', not pg.is_visible('[data-a=paiunskip][data-m="%s"]' % m0) and pg.evaluate("() => FOLD['paie-skips']") is False)
    pg.click('details[data-fold="paie-skips"] > summary')
    pg.wait_for_timeout(150)
    check('menu rouvert : mois visibles', pg.is_visible('[data-a=paiunskip][data-m="%s"]' % m0))
    pg.click('[data-a=paiunskip][data-m="%s"]' % m0)
    check('un mois remis à valider : revient dans « À valider »', pg.evaluate("() => paDue()") == [m0, m2] and etat_paie(pg)['skips'] == [m1])
    pg.click('[data-a=paiunskip][data-m="%s"]' % m1)
    check('dernier mois remis : section « Mois ignorés » disparue', pg.evaluate("() => paDue().length") == 3 and 'Mois ignorés' not in pg.inner_text('#app'))
    pg.evaluate("(m) => { S.paie.skips = [m, addMonths(m, 1)]; render(); }", m0)
    pg.click('[data-a=paiunskipall]')
    check('« Tout remettre à valider »', etat_paie(pg)['skips'] == [] and pg.evaluate("() => paDue().length") == 3)
    # sélection : tout sélectionner, remettre à valider
    pg.evaluate("([a, b, c]) => { S.paie.skips = [a, b, c]; render(); }", [m0, m1, m2])
    check('trois mois ignorés : bouton « Sélectionner » présent', pg.locator('[data-a=paksel]').count() == 1)
    pg.click('[data-a=paksel]')
    check('mode sélection : cases vides, « Remettre à valider (0) » désactivé, boutons par mois masqués', pg.inner_text('[data-a=pakres]').strip() == 'Remettre à valider (0)' and pg.evaluate("() => document.querySelector('[data-a=pakres]').disabled") is True and pg.locator('[data-a=paiunskip]').count() == 0 and pg.locator('[data-a=paiunskipall]').count() == 0)
    pg.click('[data-a=paktog][data-m="%s"]' % m1)
    check('un mois coché : compteur à 1', pg.inner_text('[data-a=pakres]').strip() == 'Remettre à valider (1)' and pg.inner_text('[data-a=paktog][data-m="%s"]' % m1).count('☑') == 1)
    pg.click('[data-a=pakselall]')
    check('« Tout sélectionner » : les 3 mois', pg.inner_text('[data-a=pakres]').strip() == 'Remettre à valider (3)')
    pg.click('[data-a=pakselall]')
    check('« Tout désélectionner » : aucun', pg.inner_text('[data-a=pakres]').strip() == 'Remettre à valider (0)')
    pg.click('[data-a=paktog][data-m="%s"]' % m0)
    pg.click('[data-a=paktog][data-m="%s"]' % m2)
    pg.click('[data-a=pakres]')
    check('deux mois remis à valider, le troisième reste ignoré, sortie du mode sélection', etat_paie(pg)['skips'] == [m1] and pg.evaluate("() => paDue()") == [m0, m2] and pg.locator('[data-a=pakres]').count() == 0)
    pg.evaluate("([a, b, c]) => { S.paie.skips = [a, b, c]; render(); }", [m0, m1, m2])
    pg.click('[data-a=paksel]')
    pg.click('[data-a=pakselall]')
    pg.click('[data-a=pakres]')
    check('tout sélectionner puis remettre : plus aucun mois ignoré, section disparue', etat_paie(pg)['skips'] == [] and 'Mois ignorés' not in pg.inner_text('#app'))
    pg.evaluate("([a, b, c]) => { S.paie.skips = [a, b, c]; render(); }", [m0, m1, m2])
    pg.click('[data-a=paksel]')
    pg.click('[data-a=pakselend]')
    check('« Annuler » : rien n\'est remis, bouton « Sélectionner » de retour', etat_paie(pg)['skips'] == [m0, m1, m2] and pg.locator('[data-a=paksel]').count() == 1)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)
def test_selection_lignes(browser):
    print('Sélectionner des lignes du modèle pour les supprimer')
    pg = device(browser, FauxSupabase())
    msgs = []
    refus = [False]
    retire = [False]   # réponse à la question « Retirer aussi des fiches validées ? »

    def rep(d):
        msgs.append(d.message)
        ok = retire[0] if d.message.startswith('Retirer aussi') else not refus[0]
        d.accept() if ok else d.dismiss()
    pg.on('dialog', rep)
    depart(pg)
    ouvre_paie(pg)
    d0 = mois(pg, -1)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    check('sans ligne : pas de bouton « Sélectionner »', pg.locator('[data-a=palsel]').count() == 0)
    for lb, k, v in (('Brut', 'gain', '1000'), ('Prime', 'gain', '100'), ('Cotis', 'ret', '50'), ('Autre', 'ret', '5')):
        ajoute_ligne(pg, lb, k, v, d0)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiall]')
    ids = pg.evaluate("() => Object.fromEntries(S.paie.lines.map((l) => [l.label, l.id]))")
    pg.click('[data-a=palsel]')
    check('mode sélection : « Supprimer (0) » désactivé, flèches ▲▼ masquées', pg.inner_text('[data-a=paldel]').strip() == 'Supprimer (0)' and pg.evaluate("() => document.querySelector('[data-a=paldel]').disabled") is True and pg.locator('[data-a=pamove]').count() == 0)
    pg.click('[data-a=paltog][data-id="%s"]' % ids['Prime'])
    pg.click('[data-a=paltog][data-id="%s"]' % ids['Autre'])
    check('deux lignes cochées : compteur à 2, cases ☑, la ligne ne s\'ouvre pas', pg.inner_text('[data-a=paldel]').strip() == 'Supprimer (2)' and pg.inner_text('[data-a=paltog][data-id="%s"]' % ids['Prime']).count('☑') == 1 and not pg.evaluate("() => document.getElementById('modal').classList.contains('open')"))
    pg.click('[data-a=palselall]')
    check('« Tout sélectionner » : 4 lignes', pg.inner_text('[data-a=paldel]').strip() == 'Supprimer (4)')
    pg.click('[data-a=palselall]')
    pg.click('[data-a=paltog][data-id="%s"]' % ids['Prime'])
    pg.click('[data-a=paltog][data-id="%s"]' % ids['Autre'])
    refus[0] = True
    pg.click('[data-a=paldel]')
    check('confirmation demandée (2 lignes) ; refusée : rien n\'est supprimé', msgs and msgs[-1].startswith('Supprimer 2 lignes') and len(etat_paie(pg)['lines']) == 4, msgs)
    refus[0] = False
    pg.click('[data-a=paldel]')
    e = etat_paie(pg)
    check('confirmée : les 2 lignes cochées supprimées, les autres gardées', sorted(l['label'] for l in e['lines']) == ['Brut', 'Cotis'], e['lines'])
    check('fiches validées conservées (4 lignes chacune), sortie du mode sélection', all(len(sl['rows']) == 4 for sl in e['slips'].values()) and pg.locator('[data-a=palsel]').count() == 1 and pg.locator('[data-a=paldel]').count() == 0)
    # annuler, puis quitter la page en pleine sélection
    pg.click('[data-a=palsel]')
    pg.click('[data-a=paltog][data-id="%s"]' % ids['Brut'])
    pg.click('[data-a=palselend]')
    check('« Annuler » : rien n\'est supprimé', len(etat_paie(pg)['lines']) == 2 and pg.locator('[data-a=palsel]').count() == 1)
    pg.click('[data-a=palsel]')
    pg.click('[data-a=paieback]')
    ouvre_paie(pg)
    check('quitter la page en pleine sélection : sélection abandonnée', pg.evaluate("() => paSelL") is None)
    # base : une ligne à taux dont toute la base disparaît bloque la suppression ; sinon la base est nettoyée
    pg.evaluate("""() => {
      const d0 = monthOf(addMonths(monthOf(today()), -1)), mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: d0, end: '', mode: 'fixed' }, extra || {});
      S.paie.lines = [mk('a', 'A', 'gain', 100), mk('b', 'B', 'gain', 200), mk('c', 'C', 'ret', 5, { mode: 'rate', base: ['a', 'b'], coef: 100, cap: { pct: 50, line: 'b' } }), mk('d', 'D', 'ret', 5, { mode: 'rate', base: ['a'], coef: 100 })];
      render();
    }""")
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=palsel]')
    pg.click('[data-a=paltog][data-id="a"]')
    pg.click('[data-a=paldel]')
    check('suppression refusée si une ligne à taux n\'aurait plus de base', 'Impossible' in msgs[-1] and '« D »' in msgs[-1] and len(etat_paie(pg)['lines']) == 4, msgs[-1])
    pg.click('[data-a=paltog][data-id="a"]')
    pg.click('[data-a=paltog][data-id="b"]')
    pg.click('[data-a=paldel]')
    check('suppression d\'une base partagée : base nettoyée, plafond retiré', pg.evaluate("() => S.paie.lines.map((l) => l.label + ':' + (l.base || []).join(',') + ':' + (l.cap ? 1 : 0)).join('|')") == 'A::0|C:a:0|D:a:0', pg.evaluate("() => JSON.stringify(S.paie.lines)"))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_suppression_fiches_validees(browser):
    print('Suppression de lignes du modèle : option « retirer aussi des fiches validées »')
    pg = device(browser, FauxSupabase())
    msgs = []
    retire = [True]

    def rep(d):
        msgs.append(d.message)
        d.accept() if (retire[0] or not d.message.startswith('Retirer aussi')) else d.dismiss()
    pg.on('dialog', rep)
    depart(pg)
    ouvre_paie(pg)
    m = mois(pg, -1)

    def prepare():
        pg.evaluate("""(m) => {
          const mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: m, end: '', mode: 'fixed' }, extra || {});
          S.paie.lines = [mk('t', 'Traitement', 'gain', 2000), mk('a1', 'ACF points', 'gain', 100.93), mk('a2', 'ACF ancien', 'gain', 103.09), mk('c', 'CSG', 'ret', 10, { mode: 'rate', base: ['t', 'a1', 'a2'], coef: 100 })];
          S.paie.slips = {}; S.paie.slips[m] = { rows: paRowsFromModel(m) };
          FOLD['paie-mod'] = true; render();
        }""", m)
    prepare()
    csg = lambda: pg.evaluate("(m) => { const r = S.paie.slips[m].rows.find((x) => x.k === 'c'); return r ? r.amount : null; }", m)
    check('départ : CSG = 10 % de 2204,02 = 220,40', csg() == 220.4, csg())
    # suppression depuis la fenêtre de la ligne, fiches conservées
    retire[0] = False
    pg.click('[data-a=paiedit][data-id="a2"]')
    pg.click('[data-a=delpaline]')
    check('deux questions : suppression puis « Retirer aussi des fiches »', any(x.startswith('Supprimer cette ligne') for x in msgs) and msgs[-1].startswith('Retirer aussi') and '1 fiche déjà validée' in msgs[-1], msgs)
    check('refusé : ligne supprimée du modèle, fiche gardée telle quelle (4 lignes, CSG 220,40)', len(etat_paie(pg)['lines']) == 3 and len(etat_paie(pg)['slips'][m]['rows']) == 4 and csg() == 220.4, etat_paie(pg)['slips'])
    # accepté : la ligne sort de la fiche, la CSG est recalculée
    prepare()
    retire[0] = True
    msgs.clear()
    pg.click('[data-a=paiedit][data-id="a2"]')
    pg.click('[data-a=delpaline]')
    rows = etat_paie(pg)['slips'][m]['rows']
    check('accepté : ligne retirée de la fiche (3 lignes)', len(rows) == 3 and not [r for r in rows if r['k'] == 'a2'], rows)
    check('la CSG de la fiche est recalculée : 10 % de 2100,93 = 210,09', csg() == 210.09, csg())
    # même chose en sélection multiple
    prepare()
    pg.click('[data-a=palsel]')
    pg.click('[data-a=paltog][data-id="a2"]')
    pg.click('[data-a=paldel]')
    check('sélection multiple : question posée et fiche recalculée', any(x.startswith('Retirer aussi') for x in msgs) and csg() == 210.09 and len(etat_paie(pg)['slips'][m]['rows']) == 3, msgs)
    # aucune fiche ne contient la ligne : pas de seconde question
    prepare()
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.k !== 'a2'); render(); }", m)
    msgs.clear()
    pg.click('[data-a=paiedit][data-id="a2"]')
    pg.click('[data-a=delpaline]')
    check('ligne absente des fiches : pas de question sur les fiches', not any(x.startswith('Retirer aussi') for x in msgs), msgs)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_ponctuelles_taux(browser):
    print('Lignes ponctuelles « soumises aux taux »')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    m = mois(pg, -1)
    pg.evaluate("""(m) => {
      const mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: m, end: '', mode: 'fixed' }, extra || {});
      S.paie.lines = [mk('t', 'Traitement', 'gain', 2000), mk('c1', 'CSG', 'ret', 10, { mode: 'rate', base: ['t'], coef: 100, xp: true }), mk('c2', 'CRDS', 'ret', 5, { mode: 'rate', base: ['t'], coef: 100 })];
      S.paie.slips = {}; render();
    }""", m)
    val = lambda k: pg.evaluate("(k) => parseAmount(document.querySelector('#modal .pa-a[data-k=\"' + k + '\"]').value)", k)
    pg.evaluate("(m) => openSlip(m)", m)
    check('départ : CSG 200, CRDS 100', val('c1') == 200 and val('c2') == 100, (val('c1'), val('c2')))
    pg.click('[data-a=paaddx]')
    check('case « Soumise aux taux » sur la ligne ponctuelle, décochée au départ', pg.locator('#modal .pa-xr').count() == 1 and not pg.is_checked('#modal .pa-xr'))
    pg.fill('#modal .pa-xl', 'Prime test')
    pg.fill('#modal .pa-xa', '100')
    check('prime non cochée : bases inchangées', val('c1') == 200 and val('c2') == 100)
    pg.check('#modal .pa-xr')
    check('prime cochée : CSG (ligne qui l\'accepte) passe à 210, CRDS (qui ne l\'accepte pas) reste à 100', val('c1') == 210 and val('c2') == 100, (val('c1'), val('c2')))
    pg.select_option('#modal .pa-xk', 'ret')
    check('même ponctuelle en retenue : retranchée de la base (CSG 190)', val('c1') == 190, val('c1'))
    pg.select_option('#modal .pa-xk', 'gain')
    pg.fill('#modal .pa-xa', '50')
    check('montant modifié : CSG recalculée en direct (205)', val('c1') == 205, val('c1'))
    pg.click('#modal .pa-x [data-a=paxdel]')
    check('ponctuelle supprimée avec ✕ : CSG revient à 200', val('c1') == 200, val('c1'))
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-xl', 'Prime test')
    pg.fill('#modal .pa-xa', '100')
    pg.check('#modal .pa-xr')
    pg.click('[data-a=saveslip]')
    rows = etat_paie(pg)['slips'][m]['rows']
    px = [r for r in rows if r['k'].startswith('x:')]
    check('fiche enregistrée : ponctuelle marquée « rated », CSG 210', len(px) == 1 and px[0].get('rated') is True and [r['amount'] for r in rows if r['k'] == 'c1'] == [210], rows)
    pg.evaluate("(m) => openSlip(m)", m)
    check('fiche rouverte : la case reste cochée', pg.is_checked('#modal .pa-xr'))
    pg.evaluate("() => { S.paie.lines.find((l) => l.id === 'c2').xp = true; }")
    pg.click('[data-a=parecalc]')
    check('ligne qui accepte désormais les ponctuelles : CRDS = 5 % de 2100 = 105 après « Recalculer »', val('c2') == 105, val('c2'))
    pg.click('[data-a=closem]')
    # fiche validée recalculée côté code (changement de valeur du point, de base…) : la ponctuelle cochée reste prise en compte
    pg.evaluate("(m) => paRecalcMonth(m)", m)
    check('recalcul d\'une fiche validée : la ponctuelle cochée est incluse (CSG 210, CRDS 105)', pg.evaluate("(m) => S.paie.slips[m].rows.filter((r) => r.k === 'c1' || r.k === 'c2').map((r) => r.amount).join(',')", m) == '210,105', etat_paie(pg)['slips'][m]['rows'])
    # fenêtre d'une ligne à taux : case « inclure », cochée par défaut pour une nouvelle ligne, décochée pour une ligne existante
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.select_option('#pl_mode', 'rate')
    check('nouvelle ligne à taux : « Inclure les lignes ponctuelles » cochée par défaut', pg.is_checked('#pl_xp'))
    pg.click('[data-a=closem]')
    pg.evaluate("() => { delete S.paie.lines.find((l) => l.id === 'c2').xp; render(); }")
    pg.click('[data-a=paiedit][data-id="c2"]')
    check('ligne à taux existante sans le réglage : case décochée (aucun changement de ses montants)', not pg.is_checked('#pl_xp'))
    pg.check('#pl_xp')
    msgs.clear()
    pg.click('[data-a=savepaline]')
    check('cocher la case est un changement de structure : proposition de recalculer les fiches', any('Recalculer cette ligne' in x for x in msgs), msgs)
    check('réglage enregistré et fiche recalculée (CRDS 105)', pg.evaluate("() => S.paie.lines.find((l) => l.id === 'c2').xp") is True and pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 'c2').amount", m) == 105)
    check('résumé du modèle : « + ponctuelles soumises »', 'ponctuelles soumises' in pg.inner_text('#app'))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_recalcul_toutes_fiches(browser):
    print('Recalculer toutes les fiches validées')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    m0, m1 = mois(pg, -1), mois(pg, 0)
    pg.evaluate("""([m0, m1]) => {
      const mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: m0, end: '', mode: 'fixed' }, extra || {});
      S.paie.lines = [mk('t', 'Traitement', 'gain', 2000), mk('p', 'Prime', 'gain', 100), mk('c', 'CSG non déductible', 'ret', 2.4, { mode: 'rate', base: ['t', 'p'], coef: 98.25 })];
      const row = (k, label, kind, amount) => ({ k, label, kind, amount });
      S.paie.slips = {};
      [m0, m1].forEach((m) => { S.paie.slips[m] = { rows: [row('t', 'Traitement', 'gain', 2000), row('p', 'Prime', 'gain', 100), row('c', 'CSG non déductible', 'ret', 137.28)] }; });
      FOLD['paie-mod'] = true; render();
    }""", [m0, m1])
    check('bouton « Recalculer toutes les fiches validées » présent', pg.locator('[data-a=parecalcall]').count() == 1)
    pg.click('[data-a=parecalcall]')
    csg = pg.evaluate("() => Object.values(S.paie.slips).map((s) => s.rows.find((r) => r.k === 'c').amount)")
    check('CSG de toutes les fiches recalculée : 2,4 % de 98,25 % × 2100 = 49,52', csg == [49.52, 49.52], csg)
    check('lignes fixes inchangées', pg.evaluate("() => Object.values(S.paie.slips).every((s) => s.rows.find((r) => r.k === 't').amount === 2000 && s.rows.find((r) => r.k === 'p').amount === 100)"))
    check('confirmation puis compte rendu : 2 montants modifiés', any(x.startswith('Recalculer les lignes calculées des 2 fiches') for x in msgs) and msgs[-1] == '2 montants modifiés.', msgs)
    msgs.clear()
    pg.click('[data-a=parecalcall]')
    check('second passage : aucun montant modifié', msgs[-1].startswith('Aucun montant modifié'), msgs)
    pg.evaluate("() => { S.paie.slips = {}; render(); }")
    check('sans fiche validée : pas de bouton', pg.locator('[data-a=parecalcall]').count() == 0)
    # historique daté d'une ligne à taux : un ancien taux fausse les anciens mois, même après recalcul
    pg.evaluate("""([m0, m1]) => {
      const c = S.paie.lines.find((l) => l.id === 'c');
      c.hist = [{ from: '0000-00', amount: 6.9 }, { from: m1, amount: 2.4 }];
      const row = (k, label, kind, amount) => ({ k, label, kind, amount });
      S.paie.slips = {}; S.paie.slips[m0] = { rows: [row('t', 'Traitement', 'gain', 2000), row('p', 'Prime', 'gain', 100), row('c', 'CSG non déductible', 'ret', 1)] };
      render();
    }""", [m0, m1])
    pg.click('[data-a=parecalcall]')
    check('ancien taux dans l\'historique : le recalcul garde la valeur fausse (6,9 % → 142,36)', pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 'c').amount", m0) == 142.36, pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 'c').amount", m0))
    pg.click('[data-a=paiedit][data-id="c"]')
    check('historique des valeurs replié de base', pg.evaluate("() => document.querySelector('#modal details[data-fold=paie-lh]').open") is False)
    pg.click('#modal details[data-fold=paie-lh] > summary')
    check('fenêtre de la ligne : historique visible avec 2 entrées', pg.locator('#modal [data-a=pahistdel]').count() == 2 and 'Au départ' in pg.inner_text('#modal'))
    pg.click('#modal [data-a=pahistdel][data-i="0"]')
    check('entrée de départ supprimée : fiche recalculée au taux de 2,4 % (49,52), historique à 1 entrée', pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 'c').amount", m0) == 49.52 and pg.locator('#modal [data-a=pahistdel]').count() == 1, pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 'c').amount", m0))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_bulletin_reel(browser):
    print('Bulletin réel : rappel de CSG (ponctuelle soumise) et transfert primes/points négatif')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.accept())
    depart(pg)
    ouvre_paie(pg)
    m = mois(pg, -1)
    pg.evaluate("""(m) => {
      const mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: m, end: '', mode: 'fixed' }, extra || {});
      const base = ['t', 'im', 'pr', 'ia', 'acf', 'ics'];
      S.paie.lines = [mk('t', 'Traitement brut', 'gain', 1537.01), mk('im', 'Indemnité mensuelle', 'gain', 106.76), mk('pr', 'Prime de rendement', 'gain', 150.78), mk('ia', 'Indemnité administration', 'gain', 128.03), mk('acf', 'ACF technicité', 'gain', 100.93), mk('ics', 'Indemnité compensatrice CSG', 'gain', 15.38),
        mk('tr', 'Transfert prime/point', 'ret', 13.92), mk('pc', 'Retenue PC', 'ret', 162.31), mk('imt', 'Retenue PC IMT', 'ret', 21.35),
        mk('nd', 'CSG non déductible', 'ret', 2.4, { mode: 'rate', base: base.concat('tr'), coef: 98.25, xp: true }),
        mk('de', 'CSG déductible', 'ret', 6.8, { mode: 'rate', base: base.concat('tr'), coef: 98.25, xp: true }),
        mk('cr', 'CRDS', 'ret', 0.5, { mode: 'rate', base: base.concat('tr'), coef: 98.25, xp: true }),
        mk('ra', 'RAFP', 'ret', 5, { mode: 'rate', base: base, cap: { pct: 20, line: 't' } })];
      S.paie.slips = {}; render(); openSlip(m);
    }""", m)
    val = lambda k: pg.evaluate("(k) => parseAmount(document.querySelector('#modal .pa-a[data-k=\"' + k + '\"]').value)", k)
    check('mois courant (transfert 13,92, sans rappel) : CSG déd. 135,29, non déd. 47,75, CRDS 9,95', (val('de'), val('nd'), val('cr')) == (135.29, 47.75, 9.95), (val('de'), val('nd'), val('cr')))
    pg.fill('#modal .pa-a[data-k="tr"]', '-9,28')
    pg.click('[data-a=paaddx]')
    pg.fill('#modal .pa-xl', 'Rappel indemnité compensatrice CSG')
    pg.fill('#modal .pa-xa', '25,62')
    pg.check('#modal .pa-xr')
    check('bulletin : CSG déductible 138,55, non déductible 48,90, CRDS 10,19, RAFP 15,37', (val('de'), val('nd'), val('cr'), val('ra')) == (138.55, 48.9, 10.19, 15.37), (val('de'), val('nd'), val('cr'), val('ra')))
    pg.click('[data-a=saveslip]')
    check('transfert différent du modèle : question « mois suivants » posée (seul le transfert, pas les lignes calculées)', 'Transfert prime/point' in pg.inner_text('#modal') and 'CSG' not in pg.inner_text('#modal'), pg.inner_text('#modal')[:200])
    pg.check('#modal input[name=pp_0][value=one]')
    pg.click('[data-a=paipropag]')
    rows = {r['k']: r['amount'] for r in etat_paie(pg)['slips'][m]['rows']}
    check('fiche enregistrée : transfert −9,28 conservé avec son signe, CSG déd. 138,55', rows.get('tr') == -9.28 and rows.get('de') == 138.55, rows)
    pg.evaluate("(m) => paRecalcMonth(m)", m)
    check('recalcul de la fiche validée : mêmes montants (signe et ponctuelle conservés)', pg.evaluate("(m) => S.paie.slips[m].rows.filter((r) => ['de', 'nd', 'cr'].includes(r.k)).map((r) => r.amount).sort().join(',')", m) == '10.19,138.55,48.9')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_proratisation(browser):
    print('Proratisation : période payée du … au … (base 30 jours)')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    m = mois(pg, -1)
    pg.evaluate("""(m) => {
      const mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: m, end: '', mode: 'fixed' }, extra || {});
      S.paie.pt = { amount: 5623.23, hist: [] };
      S.paie.lines = [mk('t', 'Traitement brut', 'gain', 328, { mode: 'points' }), mk('p', 'Prime', 'gain', 106.76), mk('r', 'Retenue fixe', 'ret', 21.35), mk('c', 'CSG déductible', 'ret', 6.8, { mode: 'rate', base: ['t', 'p'], coef: 98.25 })];
      S.paie.slips = {}; render(); openSlip(m);
    }""", m)
    val = lambda k: pg.evaluate("(k) => parseAmount(document.querySelector('#modal .pa-a[data-k=\"' + k + '\"]').value)", k)
    check('mois complet au départ : 1537,01 / 106,76 / 21,35 / CSG 100,24', (val('t'), val('p'), val('r')) == (1537.01, 106.76, 21.35) and 'Mois complet' in pg.inner_text('#pa_q'), (val('t'), val('p'), val('r')))
    pg.fill('#pa_d', '11')
    check('du 11 au dernier jour : 20 jours sur 30, traitement 1024,67 (proratisé avant de tronquer)', val('t') == 1024.67 and '20 jours sur 30' in pg.inner_text('#pa_q'), (val('t'), pg.inner_text('#pa_q')))
    check('lignes fixes proratisées (prime 71,17, retenue 14,23)', (val('p'), val('r')) == (71.17, 14.23), (val('p'), val('r')))
    check('ligne à taux : suit la base proratisée (CSG déd. 73,21)', val('c') == 73.21, val('c'))
    tt = norm(pg.inner_text('#pa_tot'))
    check('totaux en direct dans la fiche : gains 1 095,84, retenues 87,44, net 1 008,40', '1 095,84 €' in tt and '87,44 €' in tt and '1 008,40 €' in tt, tt)
    pg.fill('#pa_f', '31') if pg.evaluate("(m) => paDim(m)", m) == 31 else pg.fill('#pa_f', str(pg.evaluate("(m) => paDim(m)", m)))
    check('« au » = dernier jour du mois (28, 30 ou 31) : toujours 20 jours', val('t') == 1024.67, val('t'))
    pg.fill('#pa_f', '31')
    pg.fill('#pa_d', '10')
    pg.fill('#pa_f', '30')
    pg.fill('#pa_d', '10')
    check('du 10 au 30 : 21 jours, traitement 1075,91, prime 74,73', (val('t'), val('p')) == (1075.91, 74.73), (val('t'), val('p')))
    pg.fill('#pa_d', '20')
    pg.fill('#pa_f', '5')
    check('période invalide (début après fin) : message, enregistrement refusé', 'invalide' in pg.inner_text('#pa_q'))
    pg.click('[data-a=saveslip]')
    check('enregistrement refusé avec une alerte', any('Période payée invalide' in x for x in msgs) and m not in etat_paie(pg)['slips'], msgs)
    pg.fill('#pa_d', '11')
    pg.fill('#pa_f', '')
    pg.fill('#modal .pa-a[data-k="r"]', '15')
    pg.fill('#pa_d', '11')
    check('montant fixe saisi à la main : conservé', val('r') == 15)
    pg.click('[data-a=saveslip]')
    s = etat_paie(pg)['slips'][m]
    rows = {x['k']: x['amount'] for x in s['rows']}
    check('fiche enregistrée avec sa période (jour 11) et ses montants proratisés', s.get('pr', {}).get('d') == 11 and rows['t'] == 1024.67 and rows['p'] == 71.17 and rows['c'] == 73.21, s)
    check('mois proratisé : aucune question de propagation, le modèle reste intact', not any('mois suivants' in x for x in msgs) and pg.evaluate("() => S.paie.lines.find((l) => l.id === 'p').amount") == 106.76 and 'Appliquer aux mois suivants' not in pg.inner_text('body'))
    # la valeur du point change : recalcul de la fiche validée, quotité conservée
    pg.evaluate("(m) => { S.paie.pt = { amount: 5700, hist: [] }; paRecalcMonth(m); }", m)
    v = pg.evaluate("(m) => S.paie.slips[m].rows.find((r) => r.k === 't').amount", m)
    check('recalcul d\'une fiche proratisée : quotité 20/30 conservée (5700 → 1038,66)', v == 1038.66, v)
    pg.evaluate("() => { S.paie.pt = { amount: 5623.23, hist: [] }; }")
    # retour à un mois complet
    pg.evaluate("(m) => openSlip(m)", m)
    check('fiche rouverte : jour de début 11 affiché, 20 jours sur 30', pg.input_value('#pa_d') == '11' and '20 jours sur 30' in pg.inner_text('#pa_q'))
    pg.fill('#pa_d', '')
    check('retour au mois complet : traitement 1537,01, prime 106,76, retenue saisie à la main (15) conservée', (val('t'), val('p'), val('r')) == (1537.01, 106.76, 15.0), (val('t'), val('p'), val('r')))
    pg.click('[data-a=saveslip]')
    check('mois complet enregistré : plus de période dans la fiche', 'pr' not in etat_paie(pg)['slips'][m], etat_paie(pg)['slips'][m])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_tableau_totaux(browser):
    print('Tableau d\'évolution : totaux des gains et des retenues, total de la période affichée')
    pg = device(browser, FauxSupabase())
    depart(pg)
    ouvre_paie(pg)
    ms = [mois(pg, k) for k in range(-4, 1)]
    pg.evaluate("""(ms) => {
      const mk = (id, label, kind, amount) => ({ id, label, kind, amount, start: ms[0], end: '', mode: 'fixed' });
      S.paie.lines = [mk('g', 'Traitement', 'gain', 1000), mk('p', 'Prime', 'gain', 100), mk('r', 'Retraite', 'ret', 100), mk('n', 'Net imprimé', 'tot', 900)];
      S.paie.slips = {};
      ms.forEach((m, i) => { S.paie.slips[m] = { rows: [{ k: 'g', label: 'Traitement', kind: 'gain', amount: 1000 + 100 * i }, { k: 'p', label: 'Prime', kind: 'gain', amount: 50 }, { k: 'r', label: 'Retraite', kind: 'ret', amount: 100 + 10 * i }, { k: 'n', label: 'Net imprimé', kind: 'tot', amount: 800 }] }; });
      FOLD['paie-evo'] = true; FOLD['pt-gain'] = true; FOLD['pt-ret'] = true; paWin = 0; render();
    }""", ms)
    cell = lambda lib: pg.evaluate("(l) => { const tr = [...document.querySelectorAll('table.pa tbody tr')].find((x) => x.querySelector('td.l') && x.querySelector('td.l').textContent === l); return tr ? [...tr.querySelectorAll('td.n, td.tc')].map((e) => e.textContent.replace(/\\s/g, ' ').trim()) : null; }", lib)
    check('en-tête : trois mois puis colonne « Total »', pg.evaluate("() => [...document.querySelectorAll('table.pa thead th')].map((e) => e.textContent.trim()).length") == 5 and pg.evaluate("() => document.querySelector('table.pa thead th.tc').textContent") == 'Total')
    # mois affichés : les trois derniers (indices 2, 3, 4)
    check('total des gains : trois mois visibles, total sur les 5 mois (1050 + 1150 + 1250 + 1350 + 1450 = 6 250,00)', cell('Total des gains') == ['1 250,00', '1 350,00', '1 450,00', '6 250,00'], cell('Total des gains'))
    check('total des retenues : 5 mois → 600,00', cell('Total des retenues') == ['120,00', '130,00', '140,00', '600,00'], cell('Total des retenues'))
    check('net calculé : 5 mois → 5 650,00', cell('Net calculé') == ['1 130,00', '1 220,00', '1 310,00', '5 650,00'], cell('Net calculé'))
    check('total par ligne sur la période : traitement 6 000 + prime 250', cell('Traitement')[-1] == '6 000,00' and cell('Prime')[-1] == '250,00', (cell('Traitement'), cell('Prime')))
    check('ligne « total / information » : somme aussi (5 × 800)', cell('Net imprimé')[-1] == '4 000,00', cell('Net imprimé'))
    check('total des gains juste après la dernière ligne de gain, avant les retenues', pg.evaluate("() => [...document.querySelectorAll('table.pa td.l')].map((e) => e.textContent)") == ['Traitement', 'Prime', 'Total des gains', 'Retraite', 'Total des retenues', 'Net calculé', 'Net imprimé'])
    check('période affichée rappelée sous le tableau', 'somme de toute la période choisie' in pg.inner_text('#app'))
    pg.click('[data-a=pawin][data-d="1"]')
    check('mois plus anciens (indices 1, 2, 3) : colonnes décalées, total de la période inchangé', cell('Total des gains') == ['1 150,00', '1 250,00', '1 350,00', '6 250,00'], cell('Total des gains'))
    pg.evaluate("(ms) => { delete S.paie.slips[ms[2]].rows[1]; S.paie.slips[ms[2]].rows = S.paie.slips[ms[2]].rows.filter(Boolean); paWin = 0; render(); }", ms)
    check('ligne absente d\'un mois : « — » dans la case, total sur les mois présents', cell('Prime') == ['—', '50,00', '50,00', '200,00'], cell('Prime'))
    pg.evaluate("(ms) => { S.paie.slips[ms[2]].rows.splice(1, 0, { k: 'p', label: 'Prime', kind: 'gain', amount: 50 }); paWin = 0; render(); }", ms)
    # --- choix de la période : du mois X au mois Y
    check('sélecteurs « Du » et « Au » présents, réglés sur toute la période', pg.input_value('#pa_from') == ms[0] and pg.input_value('#pa_to') == ms[4] and pg.is_disabled('[data-a=paperall]'))
    pg.select_option('#pa_from', ms[1])
    pg.select_option('#pa_to', ms[3])
    check('période ms[1] → ms[3] : 3 colonnes, total = 1150 + 1250 + 1350 = 3 750,00', cell('Total des gains') == ['1 150,00', '1 250,00', '1 350,00', '3 750,00'], cell('Total des gains'))
    check('retenues et net sur la période : 110 + 120 + 130 = 360,00 / 3 390,00', cell('Total des retenues')[-1] == '360,00' and cell('Net calculé')[-1] == '3 390,00', (cell('Total des retenues'), cell('Net calculé')))
    check('en-tête : 3 mois de la période, pas de flèche utile (rien de plus ancien)', pg.evaluate("() => document.querySelector('[data-a=pawin][data-d=\"1\"]').disabled") is True and pg.evaluate("() => document.querySelector('[data-a=pawin][data-d=\"-1\"]').disabled") is True)
    check('bouton « Toute la période » actif', not pg.is_disabled('[data-a=paperall]'))
    pg.select_option('#pa_to', ms[2])
    check('Au = ms[2] : 2 mois, total 1150 + 1250 = 2 400,00', cell('Total des gains') == ['1 150,00', '1 250,00', '2 400,00'], cell('Total des gains'))
    pg.select_option('#pa_from', ms[3])
    check('Du après Au : Au suit (période d\'un seul mois ms[3])', pg.input_value('#pa_to') == ms[3] and cell('Total des gains') == ['1 350,00', '1 350,00'], (pg.input_value('#pa_to'), cell('Total des gains')))
    pg.evaluate("() => { FOLD['paie-crb'] = true; render(); }")
    check('courbe limitée à la période : un seul point', pg.evaluate("() => document.querySelectorAll('[data-a=paipt]').length") == 1)
    pg.select_option('#pa_from', ms[0])
    pg.select_option('#pa_to', ms[4])
    check('retour à toute la période : courbe à 5 points', pg.evaluate("() => document.querySelectorAll('[data-a=paipt]').length") == 5)
    pg.select_option('#pa_from', ms[2])
    pg.click('[data-a=paperall]')
    check('« Toute la période » rétablit tous les mois', pg.input_value('#pa_from') == ms[0] and pg.input_value('#pa_to') == ms[4] and cell('Total des gains')[-1] == '6 250,00')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_point_acf(browser):
    print('Valeur du point ACF : saisie, ligne « points ACF », valeur datée')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    d0, d1 = mois(pg, -2), mois(pg, -1)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.fill('#pl_lab', 'ACF technicité')
    pg.select_option('#pl_mode', 'acf')
    pg.fill('#pl_amt', '22')
    pick(pg, 'pl_start', d0)
    pg.click('[data-a=savepaline]')
    check('points ACF sans valeur du point ACF : refusé', 'point ACF' in msgs[-1] and etat_paie(pg)['lines'] == [], msgs)
    pg.click('[data-a=closem]')
    check('ligne « Valeur du point ACF » dans le modèle (à saisir)', 'Valeur du point ACF' in pg.inner_text('#app') and 'à saisir' in pg.inner_text('[data-a=paacf]'))
    pg.click('[data-a=paacf]')
    pg.fill('#pt_amt', '55,05')
    pg.click('[data-a=savepapt]')
    e = etat_paie(pg)
    check('valeur ACF enregistrée sans toucher au point d\'indice', e['acf'] == {'amount': 55.05, 'hist': []} and e['pt'] == {'amount': 0, 'hist': []}, e)
    ligne_calc(pg, 'ACF technicité', 'gain', 'acf', '22', d0)
    check('ligne ACF : 22 points × 55,05 ÷ 12 = 100,93 (arrondi normal)', calc(pg, d0)['ACF technicité'] == 100.93, calc(pg, d0))
    check('descriptif « 22 points ACF »', '22 points ACF' in pg.inner_text('#app'))
    pg.click('[data-a=paiall]')
    check('fiches validées avec 100,93', ligne_de(pg, d0, 'ACF technicité') == 100.93 and ligne_de(pg, d1, 'ACF technicité') == 100.93)
    pg.click('[data-a=paacf]')
    pg.fill('#pt_amt', '56')
    pick(pg, 'pt_from', d1)
    pg.click('[data-a=savepapt]')
    check('valeur ACF datée : mois d\'avant inchangé, suivants recalculés (22 × 56 ÷ 12 = 102,67 arrondi)', ligne_de(pg, d0, 'ACF technicité') == 100.93 and ligne_de(pg, d1, 'ACF technicité') == 102.67, [ligne_de(pg, d0, 'ACF technicité'), ligne_de(pg, d1, 'ACF technicité')])
    pg.evaluate("() => { S = migrate(JSON.parse(JSON.stringify(Object.assign({}, S, { paie: { lines: [], slips: {}, skips: [] } })))); }")
    check('migration : valeur ACF absente → 0, historique vide', pg.evaluate("() => JSON.stringify(S.paie.acf)") == '{"amount":0,"hist":[]}')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_ordre_base(browser):
    print('Choix de la base : gains d\'abord, puis retenues, dans l\'ordre du modèle')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.accept())
    depart(pg)
    ouvre_paie(pg)
    d0 = mois(pg, -1)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    for lb, k, v in (('Ret1', 'ret', '10'), ('Gain1', 'gain', '100'), ('Info1', 'tot', '5'), ('Gain2', 'gain', '50'), ('Ret2', 'ret', '7')):
        ajoute_ligne(pg, lb, k, v, d0)
        pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    def ordre():
        return pg.evaluate("() => [...document.querySelectorAll('#modal .pl-b')].map((x) => x.closest('label').firstChild.nextSibling.textContent.trim())")
    pg.click('[data-a=paiaddline]')
    pg.select_option('#pl_mode', 'rate')
    check('nouvelle ligne à taux : gains puis retenues puis totaux', ordre() == ['Gain1', 'Gain2', 'Ret1', 'Ret2', 'Info1'], ordre())
    caps = pg.evaluate("() => [...document.querySelectorAll('#pl_capline option')].slice(1).map((o) => o.textContent)")
    check('même ordre pour le plafond', caps == ['Gain1', 'Gain2', 'Ret1', 'Ret2', 'Info1'], caps)
    pg.click('[data-a=closem]')
    ajoute_ligne(pg, 'Gain0', 'gain', '1', d0)
    ajoute_ligne(pg, 'Ret0', 'ret', '1', d0)
    pg.click('[data-a=paiaddline]')
    check('lignes créées depuis : intégrées à leur place (gain parmi les gains, retenue parmi les retenues)', ordre() == ['Gain1', 'Gain2', 'Gain0', 'Ret1', 'Ret2', 'Ret0', 'Info1'], ordre())
    pg.click('[data-a=closem]')
    pg.click('[data-a=paiedit]')
    check('modification d\'une ligne : la ligne elle-même est exclue de la liste', len(ordre()) == 6, ordre())
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def ligne_calc(pg, label, kind, mode, val, debut, bases=(), coef=None, cap=None):
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.fill('#pl_lab', label)
    pg.select_option('#pl_kind', kind)
    pg.select_option('#pl_mode', mode)
    pg.fill('#pl_amt', val)
    for b in bases:
        pg.locator('#modal label.pbx', has_text=b).locator('input').check()
    if coef:
        pg.fill('#pl_coef', coef)
    if cap:
        pg.fill('#pl_cappct', cap[0])
        pg.select_option('#pl_capline', label=cap[1])
    pick(pg, 'pl_start', debut)
    pg.click('[data-a=savepaline]')


def calc(pg, m):
    return pg.evaluate("(m) => { const c = paCompute(m), o = {}; S.paie.lines.forEach((l) => { o[l.label] = c[l.id]; }); return o; }", m)


def ligne_de(pg, m, label):
    return pg.evaluate("([m, lb]) => { const l = S.paie.lines.find((x) => x.label === lb), r = S.paie.slips[m].rows.find((x) => x.k === l.id); return r ? r.amount : null; }", [m, label])


def test_calculees(browser):
    print('Lignes calculées : points, taux, base cochée, plafond')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    ouvre_paie(pg)
    d0 = mois(pg, -2)
    pg.evaluate("() => { FOLD['paie-mod'] = true; render(); }")
    pg.click('[data-a=paiaddline]')
    pg.fill('#pl_lab', 'Traitement brut')
    pg.select_option('#pl_mode', 'points')
    pg.fill('#pl_amt', '3000')
    pick(pg, 'pl_start', d0)
    pg.click('[data-a=savepaline]')
    check('points sans valeur du point : refusé', 'valeur du point' in msgs[-1] and etat_paie(pg)['lines'] == [], msgs)
    pg.click('[data-a=closem]')
    pg.click('[data-a=papoint]')
    pg.fill('#pt_amt', '590')
    pg.click('[data-a=savepapt]')
    check('valeur du point enregistrée (première saisie, sans historique)', etat_paie(pg)['pt'] == {'amount': 590, 'hist': []}, etat_paie(pg)['pt'])
    ligne_calc(pg, 'Traitement brut', 'gain', 'points', '3000', d0)
    ligne_calc(pg, 'Indemnité', 'gain', 'fixed', '200', d0)
    ligne_calc(pg, 'Primes', 'gain', 'fixed', '150', d0)
    ligne_calc(pg, 'CSG', 'ret', 'rate', '2,4', d0, ['Traitement brut', 'Indemnité', 'Primes'], coef='98,25')
    ligne_calc(pg, 'RAFP', 'ret', 'rate', '5', d0, ['Primes'], cap=('20', 'Traitement brut'))
    c = calc(pg, d0)
    check('points : 3000 × 590 ÷ 100 ÷ 12 = 1475,00', c['Traitement brut'] == 1475, c)
    check('taux sur base cochée × coefficient : 2,4 % de 98,25 % × 1825 = 43,03', c['CSG'] == 43.03, c)
    check('plafond non atteint : 5 % de 150 = 7,50', c['RAFP'] == 7.5, c)
    check('modèle : montants calculés affichés et descriptif de la base', '1 475,00' in norm(pg.inner_text('#app')) and '2,4 % de Traitement brut + Indemnité + Primes' in norm(pg.inner_text('#app')))
    # refus : base vide, cycle
    pg.click('[data-a=paiaddline]')
    pg.fill('#pl_lab', 'Vide')
    pg.select_option('#pl_mode', 'rate')
    pg.fill('#pl_amt', '1')
    pg.click('[data-a=savepaline]')
    check('taux sans base cochée : refusé', 'au moins une ligne' in msgs[-1], msgs[-1])
    pg.click('[data-a=closem]')
    pg.evaluate("() => openPaLine(S.paie.lines.find((l) => l.label === 'Primes').id)")
    pg.select_option('#pl_mode', 'rate')
    pg.fill('#pl_amt', '10')
    pg.locator('#modal label.pbx', has_text='CSG').locator('input').check()
    pg.click('[data-a=savepaline]')
    check('référence circulaire refusée', 'dépendre' in msgs[-1], msgs[-1])
    check('ligne inchangée après le refus', [l['mode'] for l in etat_paie(pg)['lines'] if l['label'] == 'Primes'] == ['fixed'])
    pg.click('[data-a=closem]')
    # fiches : tout valider
    msgs.clear()
    pg.click('[data-a=paiall]')
    sl = etat_paie(pg)['slips']
    check('« Tout valider » : 3 fiches avec les lignes calculées', len(sl) == 3 and ligne_de(pg, d0, 'CSG') == 43.03 and ligne_de(pg, d0, 'Traitement brut') == 1475)
    # fiche : recalcul en direct
    d1, d2 = mois(pg, -1), mois(pg, 0)
    pg.evaluate("(m) => openSlip(m)", d0)
    val = lambda k: pg.evaluate("(k) => document.querySelector('#modal .pa-a[data-k=\"' + S.paie.lines.find((l) => l.label === k).id + '\"]').value", k)
    check('fiche existante : champs calculés non recalculés d\'office (traités comme saisis)', val('CSG') == '43,03')
    pg.click('[data-a=parecalc]')
    pg.fill('#modal .pa-a[data-k="%s"]' % pg.evaluate("() => S.paie.lines.find((l) => l.label === 'Primes').id"), '400')
    check('fiche : base modifiée, CSG recalculée en direct (48,93)', val('CSG') == '48,93', val('CSG'))
    check('fiche : plafond atteint, RAFP = 5 % de 20 % × 1475 = 14,75', val('RAFP') == '14,75', val('RAFP'))
    pg.fill('#modal .pa-a[data-k="%s"]' % pg.evaluate("() => S.paie.lines.find((l) => l.label === 'RAFP').id"), '9')
    pg.fill('#modal .pa-a[data-k="%s"]' % pg.evaluate("() => S.paie.lines.find((l) => l.label === 'Primes').id"), '300')
    check('correction manuelle d\'une ligne calculée conservée', val('RAFP') == '9', val('RAFP'))
    check('les autres lignes calculées suivent (CSG 300 : 1975 × 98,25 % × 2,4 % = 46,57)', val('CSG') == '46,57', val('CSG'))
    pg.click('[data-a=parecalc]')
    check('« Recalculer » : RAFP revient au calcul (7,50 au plafond de 295 → min(300;295) = 295 × 5 % = 14,75)', val('RAFP') == '14,75', val('RAFP'))
    msgs.clear()
    pg.click('[data-a=saveslip]')
    check('primes changées : question de propagation (ligne fixe seulement)', pg.evaluate("() => document.getElementById('modal').innerText").count('Primes') >= 1 and 'CSG' not in pg.inner_text('#modal'))
    pg.click('[data-a=paipropag]')
    check('fiche enregistrée avec les valeurs calculées', ligne_de(pg, d0, 'Primes') == 300 and ligne_de(pg, d0, 'CSG') == 46.57 and ligne_de(pg, d0, 'RAFP') == 14.75, [ligne_de(pg, d0, 'Primes'), ligne_de(pg, d0, 'CSG'), ligne_de(pg, d0, 'RAFP')])
    check('mois suivants : prime à 300 et lignes calculées recalculées', ligne_de(pg, d1, 'Primes') == 300 and ligne_de(pg, d1, 'CSG') == 46.57 and ligne_de(pg, d2, 'RAFP') == 14.75)
    # valeur du point datée
    pg.click('[data-a=papoint]')
    pg.fill('#pt_amt', '600')
    pick(pg, 'pt_from', d1)
    pg.click('[data-a=savepapt]')
    check('valeur du point datée : mois d\'avant inchangé', ligne_de(pg, d0, 'Traitement brut') == 1475)
    check('valeur du point datée : mois suivants recalculés (3000 × 600 ÷ 100 ÷ 12 = 1500)', ligne_de(pg, d1, 'Traitement brut') == 1500 and ligne_de(pg, d2, 'Traitement brut') == 1500)
    check('CSG suit le nouveau traitement (2000 × 98,25 % × 2,4 % = 47,16)', ligne_de(pg, d1, 'CSG') == 47.16, ligne_de(pg, d1, 'CSG'))
    check('historique du point : entrée datée', etat_paie(pg)['pt']['hist'][-1]['from'] == d1 and etat_paie(pg)['pt']['amount'] == 600)
    # échelon : nombre de points qui change à partir de d2
    pg.evaluate("() => openPaLine(S.paie.lines.find((l) => l.label === 'Traitement brut').id)")
    pg.fill('#pl_amt', '3100')
    pick(pg, 'pl_from', d2)
    pg.click('[data-a=savepaline]')
    check('échelon : points changés à partir du mois choisi (3100 × 600 ÷ 100 ÷ 12 = 1550), mois d\'avant inchangés', ligne_de(pg, d2, 'Traitement brut') == 1550 and ligne_de(pg, d1, 'Traitement brut') == 1500)
    check('CSG du mois recalculée (2050 × 98,25 % × 2,4 % = 48,34)', ligne_de(pg, d2, 'CSG') == 48.34, ligne_de(pg, d2, 'CSG'))
    # changement de base : recalcul proposé, accepté
    msgs.clear()
    pg.evaluate("() => openPaLine(S.paie.lines.find((l) => l.label === 'CSG').id)")
    pg.locator('#modal label.pbx', has_text='Indemnité').locator('input').uncheck()
    pg.click('[data-a=savepaline]')
    check('base modifiée : recalcul des fiches proposé', msgs and 'Recalculer cette ligne dans les 3 fiches' in msgs[0], msgs)
    check('CSG recalculée sans l\'indemnité (1475 + 300 = 1775 × 98,25 % × 2,4 % = 41,85)', ligne_de(pg, d0, 'CSG') == 41.85, ligne_de(pg, d0, 'CSG'))
    # nouvelle ligne calculée dans des fiches existantes
    ligne_calc(pg, 'Retenue test', 'ret', 'rate', '10', d0, ['Traitement brut'])
    check('nouvelle ligne calculée ajoutée aux fiches existantes avec son montant calculé', ligne_de(pg, d0, 'Retenue test') == 147.5 and ligne_de(pg, d2, 'Retenue test') == 155, [ligne_de(pg, d0, 'Retenue test'), ligne_de(pg, d2, 'Retenue test')])
    # changement de mode
    msgs.clear()
    pg.evaluate("() => openPaLine(S.paie.lines.find((l) => l.label === 'Retenue test').id)")
    pg.select_option('#pl_mode', 'fixed')
    pg.fill('#pl_amt', '12')
    pg.click('[data-a=savepaline]')
    l = [x for x in etat_paie(pg)['lines'] if x['label'] == 'Retenue test'][0]
    check('changement de mode : avertissement, base/taux effacés, historique remis à zéro', msgs and 'efface l\'historique' in msgs[0] and l['mode'] == 'fixed' and 'base' not in l and 'hist' not in l, (msgs, l))
    # aucun arrondi intermédiaire : 500 points × 5 623,23 ÷ 100 ÷ 12 = 2343,0125 → 2343,01 (arrondir d'abord le mois d'un point donnerait 2343,00)
    pg.evaluate("() => { S.paie.pt = { amount: 5623.23, hist: [] }; S.paie.lines.find((l) => l.label === 'Traitement brut').amount = 500; delete S.paie.lines.find((l) => l.label === 'Traitement brut').hist; }")
    check('valeur du point base indice 100, un seul arrondi à la fin (2343,01)', calc(pg, d0)['Traitement brut'] == 2343.01, calc(pg, d0))
    # points : troncature au centime, vérifiée sur trois bulletins réels (valeur du point, points, traitement brut imprimé)
    for vp, pts, attendu, arrondi in ((5623.23, 328, 1537.01, 1537.02), (5907.34, 435, 2141.41, 2141.41), (5820.04, 355, 1721.76, 1721.76)):
        r = pg.evaluate("([vp, pts]) => { S.paie.pt = { amount: vp, hist: [] }; const l = S.paie.lines.find((x) => x.label === 'Traitement brut'); l.amount = pts; delete l.hist; return paCompute(monthOf(today()))[l.id]; }", [vp, pts])
        check('points tronqués au centime : %s × %d = %s (un arrondi donnerait %s)' % (vp, pts, attendu, arrondi), r == attendu, r)
    # points ACF : valeur annuelle par point (sans ÷ 100), arrondi normal, vérifié sur les bulletins (22 pts → 100,925 payé 100,93 ; 80 pts → 367,00 ; 40 → 183,50 ; 20 → 91,75)
    for pts, attendu in ((22, 100.93), (80, 367.0), (40, 183.5), (20, 91.75)):
        r = pg.evaluate("([pts]) => { S.paie.acf = { amount: 55.05, hist: [] }; const l = S.paie.lines.find((x) => x.label === 'Traitement brut'); l.mode = 'acf'; l.amount = pts; delete l.hist; return paCompute(monthOf(today()))[l.id]; }", [pts])
        check('points ACF : %d × 55,05 ÷ 12 = %s' % (pts, attendu), r == attendu, r)
    pg.evaluate("() => { const l = S.paie.lines.find((x) => x.label === 'Traitement brut'); l.mode = 'points'; l.amount = 328; S.paie.pt = { amount: 5623.23, hist: [] }; }")
    # base : une retenue cochée est retranchée (transfert primes/points), un gain est ajouté
    pg.evaluate("""() => {
      const d0 = monthOf(today()), mk = (id, label, kind, amount, extra) => Object.assign({ id, label, kind, amount, start: d0, end: '', mode: 'fixed' }, extra || {});
      S.paie.lines = [mk('t', 'Traitement', 'gain', 1000), mk('p', 'Prime', 'gain', 200), mk('x', 'Transfert', 'ret', 10), mk('c', 'CSG base', 'ret', 6.8, { mode: 'rate', base: ['t', 'p', 'x'], coef: 98.25 })];
    }""")
    r = pg.evaluate("() => paCompute(monthOf(today())).c")
    check('base : gains ajoutés, retenue cochée retranchée (1000 + 200 − 10 = 1190 × 98,25 % × 6,8 % = 79,50)', r == 79.5, r)
    # migration
    pg.evaluate("() => { S.paie.lines.push({id: 'z', label: 'Z', kind: 'gain', amount: 1, start: '2026-01', end: '', mode: 'bizarre', base: [1]}); S = migrate(JSON.parse(JSON.stringify(S))); }")
    z = [x for x in etat_paie(pg)['lines'] if x['id'] == 'z'][0]
    check('migration : mode inconnu → fixe, champs de taux retirés', z['mode'] == 'fixed' and 'base' not in z)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_sync(browser):
    print('Synchronisation : le module voyage avec le reste des données (chiffré)')
    T.PUMP[0] = None   # la page « pompe » du faux serveur doit appartenir à ce navigateur
    if True:
        fake = FauxSupabase()
        a = T.test_creation_phrase_et_envoi(browser, fake)
        b = T.test_second_appareil(browser, fake)
        T.edit(a, "S.paie = { lines: [{ id: 'l1', label: 'Brut test', kind: 'gain', amount: 1234.5, start: '2026-01', end: '' }], slips: { '2026-01': { rows: [{ k: 'l1', label: 'Brut test', kind: 'gain', amount: 1234.5 }] } }, skips: [] }")
        T.sync(a)
        check('B reçoit le modèle et la fiche de A', T.wait(b, "() => S.paie.lines.length === 1 && S.paie.slips['2026-01'] && S.paie.slips['2026-01'].rows[0].amount === 1234.5", None, 12000), b.evaluate("() => JSON.stringify(S.paie)"))
        brut = json.dumps(fake.rows) if hasattr(fake, 'rows') else json.dumps(fake.posts)
        check('le serveur ne reçoit rien de lisible (ni libellé ni montant)', 'Brut test' not in brut and '1234' not in brut)
        T.edit(b, "S.paie.lines[0].amount = 1300; S.paie.skips.push('2026-02')")
        T.sync(b)
        check('A reçoit la modification faite sur B', T.wait(a, "() => S.paie.lines[0].amount === 1300 && S.paie.skips.includes('2026-02')", None, 12000))
        check('aucune erreur JavaScript', not a.errors and not b.errors, a.errors + b.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        T.PUMP[0] = None
        test_donnees(browser)
        test_parcours(browser)
        test_propagation(browser)
        test_selection_suppression(browser)
        test_selection_lignes(browser)
        test_suppression_fiches_validees(browser)
        test_ponctuelles_taux(browser)
        test_recalcul_toutes_fiches(browser)
        test_bulletin_reel(browser)
        test_proratisation(browser)
        test_tableau_totaux(browser)
        test_tableau_repli(browser)
        test_ligne_dans_fiches_existantes(browser)
        test_net_calcule(browser)
        test_totaux_fiche(browser)
        test_ordre_modele(browser)
        test_validation_ligne(browser)
        test_mois_ignores(browser)
        test_calculees(browser)
        test_point_acf(browser)
        test_ordre_base(browser)
        test_sync(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
