"""Tests : catégorie Animaux, tiers en majuscules, libellé facultatif, règles de classement gérées dans Réglages (Chromium via Playwright).

Réutilise les outils de test_sync.py. Aucune donnée réelle : libellés, montants et identifiants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_regles_et_tiers.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check, device, go_settings, tx  # noqa: E402


def ligne(id_, date, label, amount, cat='Divers', sub='Non classé', payee=''):
    t = tx(id_, date, label, amount)
    t.update({'cat': cat, 'sub': sub, 'payee': payee})
    return t


def etat(pg):
    return pg.evaluate("() => JSON.parse(JSON.stringify(S))")


def test_categorie_et_migration(browser):
    print('Catégorie Animaux et tiers existants en majuscules')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.accept())
    pg.evaluate("(k) => { const s = defaultState(); s.tx = %s; s.rules = [{kw:'LECLERC PET',cat:'Divers',sub:'Cadeaux',payee:'Leclerc  pet'}]; localStorage.setItem(k, JSON.stringify(s)); }" % json.dumps([
        ligne('t1', '2026-11-05', 'Courses', -20, payee='Leclerc'),
        ligne('t2', '2026-11-06', 'Courses', -30, payee='LECLERC '),
        ligne('t3', '2026-11-07', 'Boulangerie', -2, payee='la  Mie'),
    ]), T.KEY)
    pg.reload()
    s = etat(pg)
    check('la catégorie Animaux existe avec ses 5 sous-catégories', pg.evaluate("() => CATS['Animaux'] && CATS['Animaux'].length") == 5)
    check('les tiers existants passent en majuscules (doublons fusionnés)', sorted({t['payee'] for t in s['tx']}) == ['LA MIE', 'LECLERC'], s['tx'])
    check('le tiers d’une règle passe aussi en majuscules', s['rules'][0]['payee'] == 'LECLERC PET', s['rules'])
    stocke = json.loads(pg.evaluate("(k) => localStorage.getItem(k)", T.KEY))
    check('la migration est enregistrée au démarrage', sorted({t['payee'] for t in stocke['tx']}) == ['LA MIE', 'LECLERC'])
    check('Animaux est proposée dans le formulaire d’une ligne', 'Animaux' in pg.evaluate("() => { openTx(null); return $('f_cat').innerText; }"))
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_saisie_manuelle(browser):
    print('Saisie : libellé facultatif, tiers en majuscules')
    pg = device(browser, FauxSupabase())
    pg.on('dialog', lambda d: d.dismiss())   # on refuse la création automatique de règle
    pg.evaluate("() => openTx(null)")
    pg.fill('#f_amt', '12,50')
    pg.fill('#f_pay', 'le clerc  ')
    pg.select_option('#f_cat', 'Animaux')
    pg.select_option('#f_sub', 'Alimentation')
    check('le libellé est facultatif et indiqué comme tel', 'facultatif' in pg.inner_text('.sheet'))
    pg.click('[data-a=savetx]')
    t = etat(pg)['tx'][-1]
    check('tiers enregistré en majuscules', t['payee'] == 'LE CLERC', t)
    check('libellé vide : le tiers sert de libellé', t['label'] == 'LE CLERC', t)
    check('catégorie Animaux › Alimentation', (t['cat'], t['sub']) == ('Animaux', 'Alimentation'), t)
    pg.click('[data-a=nav][data-v=tx]')
    check('la liste n’affiche pas le tiers deux fois', pg.inner_text('#list').count('LE CLERC') == 1, pg.inner_text('#list'))
    pg.click('[data-a=edittx]')
    check('à la modification, le libellé identique au tiers n’est pas répété', pg.input_value('#f_lab') == '')
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_regles(browser):
    print('Règles de classement dans Réglages')
    pg = device(browser, FauxSupabase())
    alertes = []
    pg.on('dialog', lambda d: (alertes.append(d.message), d.accept()))
    pg.evaluate("(k) => { const s = defaultState(); s.tx = %s; localStorage.setItem(k, JSON.stringify(s)); }" % json.dumps([
        ligne('t1', '2026-11-05', 'CARTE LECLERC PET 1234', -20),
        ligne('t2', '2026-11-06', 'CARTE LECLERC PET 5678', -30, 'Santé', 'Pharmacie / médecin'),
        ligne('t3', '2026-11-07', 'CARTE LECLERC PET 9999', -10, 'Animaux', 'Alimentation'),
        ligne('t4', '2026-11-08', 'CARTE BOULANGER', -2),
    ]), T.KEY)
    pg.reload()
    go_settings(pg)
    pg.click('[data-a=newrule]')
    pg.fill('#ru_kw', 'leclerc pét')
    pg.select_option('#ru_cat', 'Animaux')
    pg.select_option('#ru_sub', 'Alimentation')
    pg.fill('#ru_pay', 'leclerc')
    pg.click('[data-a=saverule]')
    r = etat(pg)['rules']
    check('règle ajoutée, mot-clé normalisé', len(r) == 1 and r[0]['kw'] == 'LECLERC PET', r)
    check('tiers de la règle en majuscules', r[0]['payee'] == 'LECLERC', r)
    check('aperçu : 2 lignes concernées (la 3e est déjà classée)', pg.locator('.ru_chk').count() == 2, pg.locator('.ru_chk').count())
    check('rien n’est reclassé avant validation', etat(pg)['tx'][0]['cat'] == 'Divers')
    pg.locator('.ru_chk').nth(0).uncheck()   # tri par date décroissante : la première est t2 (la plus récente)
    pg.click('[data-a=ruleapply]')
    s = {t['id']: t for t in etat(pg)['tx']}
    check('ligne cochée reclassée', (s['t1']['cat'], s['t1']['sub']) == ('Animaux', 'Alimentation'), s['t1'])
    check('ligne décochée laissée telle quelle', s['t2']['cat'] == 'Santé', s['t2'])
    check('le tiers de la règle est renseigné sur la ligne reclassée', s['t1']['payee'] == 'LECLERC', s['t1'])
    check('une ligne sans rapport n’est pas touchée', s['t4']['cat'] == 'Divers')

    # doublon refusé, modification, ordre
    pg.click('[data-a=newrule]')
    pg.fill('#ru_kw', 'leclerc pet')
    pg.click('[data-a=saverule]')
    check('un mot-clé déjà utilisé est refusé', any('existe déjà' in a for a in alertes), alertes)
    pg.click('[data-a=closem]')
    pg.click('[data-a=newrule]')
    pg.fill('#ru_kw', 'leclerc')
    pg.select_option('#ru_cat', 'Alimentation')
    pg.select_option('#ru_sub', 'Courses')
    pg.click('[data-a=saverule]')
    pg.click('[data-a=rulenoapply]')
    kws = [x['kw'] for x in etat(pg)['rules']]
    check('« Ne rien reclasser » enregistre la règle sans toucher aux lignes', kws == ['LECLERC PET', 'LECLERC'] and etat(pg)['tx'][1]['cat'] == 'Santé', kws)
    pg.evaluate("() => { S.tx.push({id:'n1',date:'2026-11-09',label:'CARTE LECLERC PET 1',amount:-5,cat:'Divers',sub:'Non classé',acc:'a1',payee:''}); }")
    check('règle précise en premier : elle l’emporte', pg.evaluate("() => autoCat('CARTE LECLERC PET 1',-5,'').cat") == 'Animaux')
    pg.click('[data-a=ruledown][data-kw="LECLERC PET"]')
    kws = [x['kw'] for x in etat(pg)['rules']]
    check('▼ descend la règle', kws == ['LECLERC', 'LECLERC PET'], kws)
    check('règle générale en premier : elle l’emporte (l’ordre compte)', pg.evaluate("() => autoCat('CARTE LECLERC PET 1',-5,'').cat") == 'Alimentation')
    pg.click('[data-a=ruleup][data-kw="LECLERC PET"]')
    check('▲ remonte la règle', [x['kw'] for x in etat(pg)['rules']] == ['LECLERC PET', 'LECLERC'])
    pg.click('[data-a=editrule][data-kw="LECLERC"]')
    pg.fill('#ru_kw', 'leclerc drive')
    pg.click('[data-a=saverule]')   # aucune ligne concernée : pas d'aperçu, simple message
    check('modifier une règle change son mot-clé sans doublon', [x['kw'] for x in etat(pg)['rules']] == ['LECLERC PET', 'LECLERC DRIVE'], etat(pg)['rules'])
    pg.click('[data-a=editrule][data-kw="LECLERC DRIVE"]')
    pg.click('[data-a=delrule]')
    check('supprimer une règle', [x['kw'] for x in etat(pg)['rules']] == ['LECLERC PET'])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_categorie_et_migration(browser)
        test_saisie_manuelle(browser)
        test_regles(browser)
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
