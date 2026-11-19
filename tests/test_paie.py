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


def test_donnees(browser):
    print('Données : migration et restauration')
    pg = device(browser, FauxSupabase())
    pg.evaluate("([k]) => localStorage.setItem(k, JSON.stringify({ v: 2, accounts: [{ id: 'a1', name: 'C', type: 'courant', opening: 0, cash: true }], shown: ['a1'], tx: [], rec: [], plans: [], rules: [], budgets: {}, payDates: {}, csvMaps: {}, skips: [] }))", [T.KEY])
    pg.reload()
    check('anciennes données : S.paie créé vide', etat_paie(pg) == {'lines': [], 'slips': {}, 'skips': []}, etat_paie(pg))
    pg.evaluate("([k]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = 'n importe quoi'; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY])
    pg.reload()
    check('champ paie illisible : remplacé par une structure vide', etat_paie(pg) == {'lines': [], 'slips': {}, 'skips': []}, etat_paie(pg))
    pg.evaluate("([k]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = { lines: 3, slips: [], skips: 'x' }; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY])
    pg.reload()
    check('sous-champs invalides : remplacés', etat_paie(pg) == {'lines': [], 'slips': {}, 'skips': []}, etat_paie(pg))
    p = {'lines': [{'id': 'l1', 'label': 'Brut', 'kind': 'gain', 'amount': 100, 'start': '2026-01', 'end': ''}], 'slips': {'2026-01': {'rows': [{'k': 'l1', 'label': 'Brut', 'kind': 'gain', 'amount': 100}]}}, 'skips': []}
    pg.evaluate("([k, p]) => { const s = JSON.parse(localStorage.getItem(k)); s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, p])
    pg.reload()
    check('données valides conservées au rechargement', etat_paie(pg) == p)
    exp = pg.evaluate("() => JSON.parse(JSON.stringify(S))")
    pg.evaluate("(o) => { S = migrate(o); }", {k: v for k, v in exp.items() if k != 'paie'})
    check('restauration d\'une sauvegarde d\'avant le module : pas de plantage, paie vide', etat_paie(pg) == {'lines': [], 'slips': {}, 'skips': []})
    pg.evaluate("(o) => { S = migrate(o); }", exp)
    check('restauration d\'une sauvegarde avec paie : conservée', etat_paie(pg) == p)
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_parcours(browser):
    print('Modèle, fiches à valider, tableau et courbe')
    pg = device(browser, FauxSupabase())
    msgs = []
    pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
    depart(pg)
    pg.evaluate("() => { S.accounts[0].anchor = { date: '2020-01-01', amount: 1000 }; reanchor(); save(); }")
    avant = pg.evaluate("() => ({ bal: balanceAt(today(), true), tx: S.tx.length, acc: JSON.stringify(S.accounts), rec: S.rec.length, due: dueRange('2000-01-01', '2100-01-01').length })")
    pg.click('[data-a=nav][data-v=rec]')
    t = norm(pg.inner_text('[data-a=openpaie]'))
    check('carte d\'entrée sur Récurrent', 'Bulletin de paye' in t and 'Suis l\'évolution' in t, t)
    pg.click('[data-a=openpaie]')
    check('la vue Bulletin de paye s\'ouvre', pg.evaluate("() => view") == 'paie' and 'Bulletin de paye' in pg.inner_text('#app'))
    check('onglet Récurrent resté actif', pg.evaluate("() => document.querySelector('nav button.on').dataset.v") == 'rec')
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
    check('tableau : 3 mois, gains puis retenues puis totaux', t.index('GAIN') < t.index('RETENUE') < t.index('TOTAL') and t.count('2 500,55') == 3, t)
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

    # supprimer une fiche et valider en bloc
    pg.evaluate("(m) => openSlip(m)", m2)
    pg.click('[data-a=delslip]')
    check('fiche supprimée (confirmation acceptée)', m2 not in etat_paie(pg)['slips'] and pg.evaluate("() => paDue()") == [m2])
    pg.evaluate("() => { S.paie.slips = {}; S.paie.skips = []; render(); }")
    msgs.clear()
    pg.click('[data-a=paiall]')
    check('« Tout valider » : 3 fiches créées aux montants du modèle, confirmation demandée', len(etat_paie(pg)['slips']) == 3 and msgs and 'Valider 3 mois' in msgs[0], msgs)
    check('plus rien à valider après « Tout valider »', pg.evaluate("() => paDue()") == [])

    # ligne supprimée : fiches conservées
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
    check('fenêtre de la ligne : confirmation avec le nombre de fiches touchées (3)', msgs and msgs[0].startswith('3 fiches déjà validées') and 'passeront' in msgs[0], msgs)
    check('fiches du mois choisi et suivantes au nouveau montant, précédentes inchangées', [etat_paie(pg)['slips'][mm[j]]['rows'][0]['amount'] for j in range(-5, 1)] == [1000, 1000, 1000, 2000, 2000, 2000], brut())
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_selection_suppression(browser):
    print('Sélectionner des fiches pour les supprimer')
    pg = device(browser, FauxSupabase())
    msgs = []
    refus = [False]
    pg.on('dialog', lambda d: (msgs.append(d.message), d.dismiss() if refus[0] else d.accept()))
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


def test_net_a_payer(browser):
    print('Net à payer affiché sur chaque fiche')
    pg = device(browser, FauxSupabase())
    depart(pg)
    mm = {k: mois(pg, k) for k in range(-1, 1)}

    def fiche(brut, imposable, net, libelle_net='Net à payer'):
        return {'rows': [{'k': 'a', 'label': 'Brut', 'kind': 'tot', 'amount': brut}, {'k': 'b', 'label': 'Net imposable', 'kind': 'tot', 'amount': imposable},
                         {'k': 'c', 'label': libelle_net, 'kind': 'tot', 'amount': net}]}
    paie = {'lines': [], 'slips': {mm[-1]: fiche(2500, 2100, 1987.65), mm[0]: fiche(2510, 2110, 1999.99)}, 'skips': []}
    pg.evaluate("([k, p]) => { const s = defaultState(); s.paie = p; localStorage.setItem(k, JSON.stringify(s)); }", [T.KEY, paie])
    pg.reload()
    ouvre_paie(pg)
    pg.evaluate("() => { FOLD['paie-fiches'] = true; render(); }")
    t = norm(pg.inner_text('[data-a=paislip][data-m="%s"]' % mm[0]))
    check('la fiche affiche son net à payer (pas le brut ni le net imposable)', '1 999,99 €' in t and 'Net à payer' in t and '2 510' not in t and '2 110' not in t, t)
    t = norm(pg.inner_text('[data-a=paislip][data-m="%s"]' % mm[-1]))
    check('chaque fiche a son propre net', '1 987,65 €' in t, t)
    check('aucun message d\'aide quand le net existe', 'nomme une ligne' not in pg.inner_text('#app'))
    pg.evaluate("(m) => openSlip(m)", mm[0])
    check('fiche ouverte : net à payer enregistré rappelé en haut', 'Net à payer enregistré : 1 999,99 €' in norm(pg.inner_text('#modal')))
    pg.click('[data-a=closem]')
    # variantes de libellé et de casse, plusieurs lignes « net à payer » : la dernière
    pg.evaluate("(m) => { S.paie.slips[m] = { rows: [{ k: 'a', label: 'NET A PAYER AVANT IMPOT', kind: 'tot', amount: 2000 }, { k: 'b', label: 'Net à payer après impôt', kind: 'tot', amount: 1900 }] }; render(); }", mm[0])
    check('plusieurs « net à payer » : la dernière ligne l\'emporte', '1 900,00 €' in norm(pg.inner_text('[data-a=paislip][data-m="%s"]' % mm[0])))
    pg.evaluate("(m) => { S.paie.slips[m] = { rows: [{ k: 'a', label: 'Brut', kind: 'tot', amount: 2500 }, { k: 'b', label: 'net', kind: 'tot', amount: 1800 }] }; render(); }", mm[0])
    check('à défaut, une ligne de type total nommée « net »', '1 800,00 €' in norm(pg.inner_text('[data-a=paislip][data-m="%s"]' % mm[0])))
    pg.evaluate("(m) => { S.paie.slips[m] = { rows: [{ k: 'a', label: 'Brut', kind: 'tot', amount: 2500 }, { k: 'b', label: 'Retraite', kind: 'ret', amount: 300 }] }; render(); }", mm[0])
    t = norm(pg.inner_text('[data-a=paislip][data-m="%s"]' % mm[0]))
    check('sans ligne « net à payer » : tiret (jamais le brut à la place), pas de montant inventé', '—' in t and '2 500' not in t, t)
    check('fiche sans net, mais une autre en a : pas de message d\'aide', 'nomme une ligne' not in pg.inner_text('#app'))
    pg.evaluate("(m) => { S.paie.slips[m] = { rows: [{ k: 'a', label: 'Brut', kind: 'tot', amount: 2500 }] }; S.paie.slips['%s'] = { rows: [{ k: 'a', label: 'Brut', kind: 'tot', amount: 2400 }] }; render(); }" % mm[-1], mm[0])
    check('aucune fiche avec net : message d\'aide pour nommer la ligne', 'Pour voir le net à payer ici, nomme une ligne « Net à payer »' in norm(pg.inner_text('#app')))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_net_calcule(browser):
    print('Net calculé (gains − retenues) sur chaque fiche')
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
    check('net à payer saisi en gras, net calculé dessous (2500 + 100,50 − 345,67 = 2 254,83)', '1 999,99 €' in t and 'calculé : 2 254,83 €' in t, t)
    check('les lignes « total / information » ne comptent pas dans le net calculé', pg.evaluate("(r) => paNet(r)", pg.evaluate("(m) => S.paie.slips[m].rows", m)) == 2254.83)
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.k !== 'e'); render(); }", m)
    t = norm(pg.inner_text(sel))
    check('sans ligne « net à payer » : tiret, mais le net calculé est là', '—' in t and 'calculé : 2 254,83 €' in t, t)
    pg.evaluate("(m) => { S.paie.slips[m].rows = S.paie.slips[m].rows.filter((r) => r.kind !== 'gain'); render(); }", m)
    t = norm(pg.inner_text(sel))
    check('sans aucune ligne de gain : pas de net calculé (jamais un montant négatif inventé)', 'calculé' not in t, t)
    pg.evaluate("(m) => { S.paie.slips[m].rows = [{ k: 'a', label: 'Traitement', kind: 'gain', amount: 1000 }, { k: 'c', label: 'Retraite', kind: 'ret', amount: 1500 }]; render(); }", m)
    check('retenues supérieures aux gains : net calculé négatif affiché tel quel', 'calculé : -500,00 €' in norm(pg.inner_text(sel)) or 'calculé : −500,00 €' in norm(pg.inner_text(sel)))
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
        test_ligne_dans_fiches_existantes(browser)
        test_net_calcule(browser)
        test_net_a_payer(browser)
        test_validation_ligne(browser)
        test_sync(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
