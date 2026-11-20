"""Tests : aucune vue ni fenêtre ne dépasse la largeur de l'écran (iPhone 16e = 390 px, plus petits écrans), Chromium via Playwright.

Pour chaque largeur, chaque vue (Accueil, Lignes, Récurrent, Import, Réglages avec toutes les cartes dépliées)
et chaque fenêtre (ligne, virement, compte de chaque type, plan, récurrence, règle, paie, modification groupée,
aperçu de règle) est chargée avec des données volontairement longues. On vérifie que :
 - la page n'a pas de défilement horizontal ;
 - aucun élément visible ne dépasse le bord droit ou gauche de l'écran ;
 - aucun élément d'une fenêtre ne dépasse celle-ci ;
 - le contenu ne dépasse pas non plus son conteneur direct (carte, fenêtre).
Aucune donnée réelle : noms et montants inventés.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_debordements.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

import test_sync as T  # noqa: E402
from test_sync import FauxSupabase, check  # noqa: E402

LARGEURS = [390, 375, 360, 320]

# Repère les éléments qui dépassent : par rapport à l'écran, puis par rapport à la fenêtre (.sheet) ou à la carte qui les contient.
JS_AUDIT = r"""
() => {
  const W = document.documentElement.clientWidth;
  const out = [];
  const desc = (e) => {
    let s = e.tagName.toLowerCase();
    if (e.id) s += '#' + e.id;
    const c = (e.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.');
    if (c) s += '.' + c;
    const a = e.getAttribute('data-a');
    if (a) s += '[data-a=' + a + ']';
    const t = (e.innerText || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return s + (t ? ' « ' + t + ' »' : '');
  };
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    const cs = getComputedStyle(e);
    return cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  if (document.documentElement.scrollWidth > W + 1) out.push('page : défilement horizontal ' + document.documentElement.scrollWidth + ' > ' + W);
  const root = document.querySelector('#modal.open') || document.body;
  const scope = document.querySelector('#modal.open') ? [...root.querySelectorAll('*')] : [...document.querySelectorAll('#app *, nav *, #offbar')];
  for (const e of scope) {
    if (!visible(e)) continue;
    if (e.closest('option, datalist, svg *, script, style')) continue;
    const r = e.getBoundingClientRect();
    // un élément dans un conteneur défilant volontairement n'est pas jugé sur l'écran, mais le conteneur l'est
    const sc = e.parentElement && e.parentElement.closest('[style*="overflow-x:auto"], [style*="overflow:auto"], .scroll');
    if (!sc && (r.right > W + 1 || r.left < -1)) out.push('hors écran : ' + desc(e) + ' [' + Math.round(r.left) + '→' + Math.round(r.right) + ' / ' + W + ']');
    const p = e.parentElement;
    if (p && p !== document.body && visible(p)) {
      const pr = p.getBoundingClientRect();
      const cs = getComputedStyle(p);
      const clip = cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.overflowX === 'auto' || cs.overflowX === 'scroll';
      if (cs.position !== 'fixed' && (r.right > pr.right + 1.5 || r.left < pr.left - 1.5) && getComputedStyle(e).position !== 'fixed' && getComputedStyle(e).position !== 'absolute') {
        out.push((clip ? 'coupé par son conteneur : ' : 'dépasse son conteneur : ') + desc(e) + ' dans ' + desc(p) + ' [' + Math.round(r.left) + '→' + Math.round(r.right) + ' / conteneur ' + Math.round(pr.left) + '→' + Math.round(pr.right) + ']');
      }
    }
  }
  // un conteneur dont le contenu est plus large que lui (défilement caché)
  for (const e of scope) {
    if (!visible(e)) continue;
    const cs = getComputedStyle(e);
    if ((cs.overflowX === 'hidden' || cs.overflowX === 'clip') && cs.textOverflow !== 'ellipsis' && !/^(INPUT|SELECT|TEXTAREA)$/.test(e.tagName) && e.scrollWidth > e.clientWidth + 1) out.push('contenu coupé : ' + desc(e) + ' scrollWidth ' + e.scrollWidth + ' > ' + e.clientWidth);
  }
  return [...new Set(out)].slice(0, 12);
}
"""


def paie(x=1):
    """Bulletin de paye : lignes aux libellés très longs, montants à six chiffres (x=50), quatre fiches validées."""
    noms = [('Traitement indiciaire brut de la fonction publique d’État', 'gain', 2500.55), ('Indemnité de résidence et supplément familial de traitement', 'gain', 123.45),
            ('Cotisation retraite additionnelle de la fonction publique', 'ret', 345.67), ('Net à payer avant impôt sur le revenu', 'tot', 2100.1)]
    lignes = [{'id': 'l%d' % i, 'label': n, 'kind': k, 'amount': round(a * x, 2), 'start': '2026-07', 'end': ''} for i, (n, k, a) in enumerate(noms)]
    fiches = {}
    for j, m in enumerate(['2026-07', '2026-08', '2026-09', '2026-10']):
        fiches[m] = {'rows': [{'k': l['id'], 'label': l['label'], 'kind': l['kind'], 'amount': round(l['amount'] + j * 10 * x, 2)} for l in lignes]
                     + ([{'k': 'x:prime', 'label': 'Prime exceptionnelle de fin d’année très longue', 'kind': 'gain', 'amount': 1234.56 * x}] if j == 3 else [])}
    lignes[2].update({'mode': 'rate', 'amount': 5, 'base': ['l0', 'l1'], 'coef': 98.25, 'cap': {'pct': 20, 'line': 'l0'}})
    return {'lines': lignes, 'slips': fiches, 'skips': [], 'pt': {'amount': 590 * x, 'hist': []}}


def etat(pg, x=1):
    long_nom = 'Compte courant joint avec un nom volontairement très long pour tester'

    def c(i, nom, type_, solde, **kw):
        d = {'id': i, 'name': nom, 'type': type_, 'opening': 0, 'cash': type_ == 'courant', 'anchor': {'date': '2020-01-01', 'amount': solde * x}}
        d.update(kw)
        return d
    comptes = [
        c('a1', long_nom, 'courant', -2495.18, group='Caisse d’épargne Bourgogne Franche-Comté Auvergne', od=2000, payLim=1500, payDays=30, wdLim=300, wdDays=7),
        c('a2', 'Livret A', 'livret', 12345.67, group='Caisse d’épargne Bourgogne Franche-Comté Auvergne'),
        c('a3', 'Parts sociales de la banque coopérative', 'bloque', 2000, group='Caisse d’épargne Bourgogne Franche-Comté Auvergne'),
        c('a4', 'Maison de bourg de cent vingt mètres carrés', 'bien', 250000),
        c('a5', 'Prêt immobilier de la résidence principale', 'emprunt', -152345.67),
        c('a6', 'Carte de crédit magasin partenaire', 'credit', 2500, limit=3000),
        c('a7', 'Carte bancaire à débit différé', 'differe', -847.23, debitAcc='a1', debitDay=5),
    ]
    tx = []
    for i in range(12):
        tx.append({'id': 't%d' % i, 'date': '2026-11-%02d' % (i + 1), 'label': 'PRELEVEMENT SEPA TRES LONG LIBELLE DE LA BANQUE NUMERO %d REFERENCE ABCDEFGHIJKLMNOP' % i,
                   'amount': (-12345.67 if i == 0 else -(12.5 * (i + 1))) * x, 'cat': 'Logement', 'sub': 'Loyer / crédit', 'acc': 'a1', 'payee': 'FOURNISSEUR AVEC UN NOM TRES TRES LONG'})
    rec = [{'id': 'r1', 'label': 'Abonnement avec un libellé extrêmement long pour la récurrence', 'amount': -39.99, 'acc': 'a1', 'loan': '', 'cat': 'Logement', 'sub': 'Loyer / crédit',
            'freq': 'monthly', 'day': 5, 'every': 1, 'start': '2026-01-05', 'end': '', 'match': 'ABONNEMENT'}]
    plans = [{'id': 'p1', 'label': 'Achat en quatre fois sans frais d’un appareil très cher', 'payee': 'MAGASIN', 'acc': 'a1', 'cat': 'Logement', 'sub': 'Loyer / crédit', 'match': 'MAGASIN',
              'items': [{'date': '2026-11-20', 'amount': -250}, {'date': '2026-12-20', 'amount': -250}, {'date': '2027-01-20', 'amount': -250}]}]
    rules = [{'kw': 'MOT-CLE TRES LONG POUR UNE REGLE DE CLASSEMENT AUTOMATIQUE', 'cat': 'Animaux', 'sub': 'Alimentation', 'payee': 'TIERS AVEC UN NOM TRES LONG'}]
    s = {'v': 2, 'accounts': comptes, 'shown': ['a1', 'a2', 'a5', 'a6', 'a7'], 'tx': tx, 'rec': rec, 'plans': plans, 'rules': rules,
         'budgets': {'Logement': 500}, 'payDates': {}, 'csvMaps': {}, 'skips': [], 'paie': paie(x)}
    pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [T.KEY, s])
    pg.evaluate("() => localStorage.removeItem('compte-replis')")
    pg.reload()


def nav(pg, v):
    # clic par le DOM : si la page déborde, la barre du bas peut être hors de portée d'un vrai toucher, ce que l'audit signale par ailleurs
    pg.evaluate("(v) => document.querySelector('[data-a=nav][data-v=' + v + ']').click()", v)


def audit(pg, nom, largeur):
    probs = pg.evaluate(JS_AUDIT)
    check('%d px — %s' % (largeur, nom), not probs, '\n        ' + '\n        '.join(probs))


def ferme(pg):
    pg.evaluate("() => closeModal()")


def bannieres(pg, largeur):
    # rappel de sauvegarde (carte en haut de chaque vue) et bannière « Hors ligne » (fixe, au-dessus des onglets)
    pg.evaluate("() => { S.bk = { since: '2026-01-01', snooze: null, every: 7 }; S.lastExport = '2026-01-02'; document.getElementById('offbar').hidden = false; render(); }")
    nav(pg, 'home')
    texte_ok = pg.evaluate("() => { const b = document.getElementById('offbar'); return b.scrollWidth <= b.clientWidth + 1; }")
    check('%d px — bannière Hors ligne : texte entier visible, sans être tronqué' % largeur, texte_ok)
    audit(pg, 'Accueil avec rappel de sauvegarde et bannière Hors ligne', largeur)
    for v in ['tx', 'rec', 'set']:
        nav(pg, v)
        audit(pg, 'vue %s avec bannières' % v, largeur)
    pg.evaluate("() => { document.getElementById('offbar').hidden = true; S.bk = { since: null, snooze: null, every: 7 }; render(); }")


def vues(pg, largeur):
    for v, nom in [('home', 'Accueil'), ('tx', 'Lignes'), ('rec', 'Récurrent'), ('imp', 'Import (vide)'), ('set', 'Réglages (cartes dépliées)')]:
        nav(pg, v)
        if v == 'home':
            pg.evaluate("() => { ['patri', 'hacc', 'budget', 'cartes'].forEach((k) => { FOLD[k] = true; }); render(); }")
        if v == 'set':
            pg.evaluate("() => { Object.keys(FOLD).concat(['comptes', 'budgets', 'paie', 'regles', 'sync', 'sauvegarde', 'danger', 'hacc', 'patri']).forEach((k) => { FOLD[k] = true; }); render(); document.querySelectorAll('details').forEach((d) => { d.open = true; }); }")
        if v == 'home':
            pg.evaluate("() => document.querySelectorAll('details').forEach((d) => { d.open = true; })")
        audit(pg, 'vue ' + nom, largeur)
    # vue Bulletin de paye (tableau, courbe, fiches, modèle dépliés), à valider (novembre non validé)
    nav(pg, 'rec')
    audit(pg, 'vue Récurrent avec la carte Bulletin de paye', largeur)
    pg.evaluate("() => { view = 'paie'; Object.assign(FOLD, {'paie-evo': true, 'paie-crb': true, 'paie-fiches': true, 'paie-mod': true, 'paie-hist': true}); render(); document.querySelectorAll('details').forEach((d) => { d.open = true; }); }")
    audit(pg, 'vue Bulletin de paye (tout déplié)', largeur)
    pg.evaluate("() => { paWin = 1; render(); document.querySelectorAll('details').forEach((d) => { d.open = true; }); }")
    audit(pg, 'vue Bulletin de paye (fenêtre décalée)', largeur)
    pg.evaluate("() => { paSelM = new Set(['2026-08', '2026-10']); render(); document.querySelectorAll('details').forEach((d) => { d.open = true; }); }")
    audit(pg, 'vue Bulletin de paye (sélection des fiches)', largeur)
    pg.evaluate("() => { paSelM = null; }")
    pg.evaluate("() => { paWin = 0; paSel = 'x:prime'; render(); document.querySelectorAll('details').forEach((d) => { d.open = true; }); }")
    audit(pg, 'vue Bulletin de paye (courbe d\'une seule fiche)', largeur)
    pg.evaluate("() => { paSel = ''; view = 'rec'; render(); }")
    # vue Lignes en mode sélection
    nav(pg, 'tx')
    pg.evaluate("() => { sel = new Set(['t1', 't2']); render(); }")
    audit(pg, 'vue Lignes en sélection', largeur)
    pg.evaluate("() => { sel = null; render(); }")
    # import CSV avec un fichier chargé
    nav(pg, 'imp')
    csv = 'Date;Libellé très long de la colonne;Tiers;Montant\n01/11/2026;PAIEMENT CB TRES LONG LIBELLE BANCAIRE REFERENCE 123456789;MAGASIN LONG;-12,50\n02/11/2026;VIREMENT;EMPLOYEUR;1500,00\n03/11/2026;AUTRE;X;-3,00\n'
    pg.set_input_files('input[type=file]', files=[{'name': 'releve.csv', 'mimeType': 'text/csv', 'buffer': csv.encode('utf-8')}])
    pg.wait_for_timeout(300)
    audit(pg, 'vue Import (fichier chargé)', largeur)
    pg.evaluate("() => { imp = null; render(); }")


def fenetres(pg, largeur):
    nav(pg, 'home')
    pg.on('dialog', lambda d: d.dismiss())
    cas = [
        ('ligne (nouvelle)', "() => openTx()"),
        ('ligne (existante)', "() => openTx('t0')"),
        ('virement', "() => openXfer()"),
        ('plan (nouveau)', "() => openPlan()"),
        ('plan (existant)', "() => openPlan('p1')"),
        ('récurrence (nouvelle)', "() => openRec()"),
        ('récurrence (existante)', "() => openRec('r1')"),
        ('règle (nouvelle)', "() => openRule()"),
        ('règle (existante)', "() => openRule(S.rules[0].kw)"),
        ('paie', "() => openPay(today().slice(0, 7))"),
        ('compte (nouveau)', "() => openAcc()"),
        ('bulletin : fiche à valider', "() => openSlip('2026-11')"),
        ('bulletin : fiche validée', "() => openSlip('2026-10')"),
        ('bulletin : question « mois suivants »', "() => { openSlip('2026-10'); txCtx.pstash = { ym: '2026-10', rows: [], changed: [{ k: 'l0', label: S.paie.lines[0].label, old: 2500.55 * 50, amt: 2600.55 * 50, later: 2 }, { k: 'l1', label: S.paie.lines[1].label, old: 123.45, amt: 130, later: 1 }] }; openPropag(); }"),
        ('bulletin : ligne (nouvelle)', "() => openPaLine()"),
        ('bulletin : ligne à taux (base cochée, plafond)', "() => openPaLine('l2')"),
        ('bulletin : ligne à taux, nouvelle', "() => { openPaLine(); $('pl_mode').value = 'rate'; paModeUI(); }"),
        ('bulletin : ligne en points', "() => { openPaLine(); $('pl_mode').value = 'points'; paModeUI(); }"),
        ('bulletin : valeur du point (existante)', "() => openPaPt()"),
        ('bulletin : ligne (existante)', "() => { openPaLine('l0'); $('pl_fromw').style.display = 'block'; }"),
        ('modification groupée', "() => { sel = new Set(['t1', 't2']); openBulk(); }"),
        ('aperçu de règle', "() => openRulePreview(S.rules[0], S.tx.slice(0, 6))"),
    ]
    for nom, js in cas:
        try:
            pg.evaluate(js)
        except Exception as e:  # noqa: BLE001
            check('%d px — fenêtre %s : ouverture' % (largeur, nom), False, e)
            ferme(pg)
            continue
        audit(pg, 'fenêtre ' + nom, largeur)
        ferme(pg)
    # fenêtre compte : un par type, en changeant le type dans la fenêtre nouvelle
    for tid, nom in [('a1', 'compte courant'), ('a2', 'livret'), ('a3', 'épargne bloquée'), ('a4', 'bien'), ('a5', 'emprunt'), ('a6', 'carte de crédit'), ('a7', 'carte à débit différé')]:
        pg.evaluate("(i) => openAcc(i)", tid)
        audit(pg, 'fenêtre ' + nom, largeur)
        ferme(pg)
    pg.evaluate("() => { sel = null; }")


def test_largeur(browser, largeur, x=1):
    print('Largeur %d px%s' % (largeur, '' if x == 1 else ' (montants ×%d)' % x))
    ctx = browser.new_context(viewport={'width': largeur, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    fake = FauxSupabase()
    ctx.route(T.HOST + '/**', fake.handle)
    pg = ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)))
    pg.goto(T.URL)
    if T.PUMP[0] is None:
        T.PUMP[0] = pg
    etat(pg, x)
    vues(pg, largeur)
    bannieres(pg, largeur)
    fenetres(pg, largeur)
    check('%d px — aucune erreur JavaScript' % largeur, not pg.errors, pg.errors)
    ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w in LARGEURS:
            test_largeur(browser, w)
        for w in (390, 320):
            test_largeur(browser, w, 50)   # montants à six chiffres : les chiffres doivent passer à la ligne, pas sortir de l'écran
        browser.close()
    failed = [n for n, ok in T.RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(T.RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
