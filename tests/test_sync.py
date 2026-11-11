"""Tests : synchronisation chiffrée de Mon Compte, en navigateur automatisé (Chromium via Playwright).

Le service Supabase est simulé (aucun réseau réel, aucun vrai compte) : un faux serveur en mémoire répond aux appels de connexion, de lecture et
d'écriture. Deux « appareils » (deux contextes de navigateur, donc deux stockages séparés) le partagent. Le faux serveur ne fait AUCUN déchiffrement :
on vérifie qu'il ne reçoit jamais rien de lisible.
Lancer depuis la racine du dépôt :  PYTHONDONTWRITEBYTECODE=1 python3 tests/test_sync.py
Aucune donnée réelle : libellés, montants et identifiants inventés.
"""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / 'index.html').as_uri()
HOST = 'https://zoyrclsppuhgnyzgodjv.supabase.co'
EMAIL, PASSWORD, PHRASE = 'test@example.com', 'mot-de-passe-du-compte', 'phrase secrete de test longue'
CORS = {'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, apikey, content-type, prefer',
        'access-control-allow-methods': 'GET, POST, OPTIONS'}
RESULTS = []
PUMP = [None]
KEY = 'compte-salaire-v1'


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('  OK   ' if cond else '  ECHEC ') + name + ('' if cond else '  -> ' + str(detail)))


class FauxSupabase:
    def __init__(self):
        self.rows = {}
        self.calls = []
        self.offline = False
        self.valid = set()
        self.refresh_ok = set()
        self.n = 0
        self.posts = []

    def maj(self):
        self.n += 1
        return (datetime.now(timezone.utc) + timedelta(microseconds=self.n)).strftime('%Y-%m-%dT%H:%M:%S.%f') + '+00:00'

    def tokens(self):
        self.n += 1
        at, rt = 'AT%d' % self.n, 'RT%d' % self.n
        self.valid.add(at)
        self.refresh_ok.add(rt)
        return {'access_token': at, 'refresh_token': rt, 'expires_in': 3600, 'user': {'id': 'user-test-1', 'email': EMAIL}}

    def reply(self, route, status, body=None):
        route.fulfill(status=status, headers=CORS, content_type='application/json', body=json.dumps(body) if body is not None else '')

    def handle(self, route):
        req = route.request
        u = urlparse(req.url)
        q = parse_qs(u.query)
        if req.method == 'OPTIONS':
            route.fulfill(status=204, headers=CORS)
            return
        if self.offline:
            route.abort()
            return
        self.calls.append((req.method, u.path))
        if u.path == '/auth/v1/token':
            body = json.loads(req.post_data or '{}')
            if q.get('grant_type') == ['password']:
                if body.get('email') == EMAIL and body.get('password') == PASSWORD:
                    self.reply(route, 200, self.tokens())
                else:
                    self.reply(route, 400, {'error_description': 'Invalid login credentials'})
            elif body.get('refresh_token') in self.refresh_ok:
                self.refresh_ok.discard(body['refresh_token'])
                self.reply(route, 200, self.tokens())
            else:
                self.reply(route, 400, {'error_description': 'Invalid Refresh Token'})
            return
        if u.path == '/auth/v1/logout':
            self.reply(route, 204)
            return
        if u.path == '/rest/v1/donnees':
            auth = req.headers.get('authorization', '')
            if not auth.startswith('Bearer ') or auth[7:] not in self.valid:
                self.reply(route, 401, {'message': 'JWT expired'})
                return
            if req.method == 'GET':
                out = list(self.rows.values())
                if 'maj' in q:
                    since = datetime.fromisoformat(q['maj'][0][3:].replace('Z', '+00:00'))
                    out = [r for r in out if datetime.fromisoformat(r['maj']) > since]
                if 'cle' in q:
                    out = [r for r in out if r['cle'] == q['cle'][0][3:]]
                out.sort(key=lambda r: r['maj'])
                self.reply(route, 200, out)
                return
            if req.method == 'POST':
                items = json.loads(req.post_data)
                self.posts.append([it['cle'] for it in items])
                ignore = 'ignore-duplicates' in req.headers.get('prefer', '')
                for it in items:
                    if ignore and it['cle'] in self.rows:
                        continue
                    self.rows[it['cle']] = {'cle': it['cle'], 'valeur': it['valeur'], 'maj': self.maj()}
                self.reply(route, 201)
                return
        self.reply(route, 404, {'message': 'inconnu'})

    def text(self):
        # Texte du serveur + contenu décodé (base64) de chaque valeur : un simple base64 de texte clair ne doit pas passer pour du chiffrement.
        import base64
        out = [json.dumps(self.rows)]
        for r in self.rows.values():
            c = (r['valeur'] or {}).get('c')
            if c:
                out.append(base64.b64decode(c).decode('latin-1'))
        return '\n'.join(out)


def device(browser, fake):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844})
    ctx.route(HOST + '/**', fake.handle)
    pg = ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)))
    pg.goto(URL)
    if PUMP[0] is None:
        PUMP[0] = pg
    return pg


def tx(id_, date, label, amount, acc='a1'):
    return {'id': id_, 'date': date, 'label': label, 'amount': amount, 'cat': 'Logement', 'sub': 'Loyer / crédit', 'acc': acc, 'payee': ''}


def seed(pg, txs):
    pg.evaluate("(t) => { const s = defaultState(); s.tx = t; localStorage.setItem('%s', JSON.stringify(s)); }" % KEY, txs)
    pg.reload()


def go_settings(pg):
    pg.click('[data-a=nav][data-v=set]')


def labels(pg):
    return pg.evaluate("() => S.tx.map((t) => t.label).sort()")


def stored_labels(pg):
    return sorted(t['label'] for t in json.loads(pg.evaluate("(k) => localStorage.getItem(k)", KEY) or '{"tx":[]}')['tx'])


def wait(pg, js, arg=None, timeout=9000):
    try:
        pg.wait_for_function(js, arg=arg, timeout=timeout)
        return True
    except Exception:
        return False


def wait_remote(cond, tries=60):
    # Le faux serveur ne répond que pendant que Playwright traite des événements : on attend par la page, jamais par time.sleep.
    for _ in range(tries):
        if cond():
            return True
        PUMP[0].wait_for_timeout(150)
    return cond()


def sync(pg):
    pg.evaluate("() => syncNow()")
    pg.wait_for_timeout(150)
    pg.evaluate("() => syncNow()")


def connect(pg, phrase=PHRASE, create=False):
    go_settings(pg)
    pg.fill('#sync-email', EMAIL)
    pg.fill('#sync-pass', PASSWORD)
    pg.click('[data-a=sync-login]')
    wait(pg, "() => !!document.querySelector('#sync-phrase')")
    pg.fill('#sync-phrase', phrase)
    if create:
        pg.fill('#sync-phrase2', phrase)
    pg.click('[data-a=sync-phrase]')


def edit(pg, js, arg=None):
    pg.evaluate("(a) => { %s; save(); }" % js, arg)


def test_sans_compte(browser):
    print('Sans compte')
    fake = FauxSupabase()
    pg = device(browser, fake)
    seed(pg, [tx('t1', '2026-11-05', 'Loyer test', -500)])
    go_settings(pg)
    check('la carte Synchronisation existe (e-mail, mot de passe, bouton)', pg.locator('#sync-email').count() == 1 and pg.locator('#sync-pass').count() == 1 and pg.locator('[data-a=sync-login]').count() == 1)
    check('le mot de passe est masqué', pg.get_attribute('#sync-pass', 'type') == 'password')
    pg.wait_for_timeout(400)
    check('aucun appel réseau tant qu’on n’est pas connecté', fake.calls == [], fake.calls)
    pg.fill('#sync-email', EMAIL)
    pg.fill('#sync-pass', 'mauvais')
    pg.click('[data-a=sync-login]')
    check('mauvais mot de passe : message clair', wait(pg, "() => document.querySelector('#sync-msg') && document.querySelector('#sync-msg').textContent.includes('incorrect')"))
    check('aucune session enregistrée', pg.evaluate("() => localStorage.getItem('compte-sync-session')") is None)
    check('l’app fonctionne toujours (les données sont là)', labels(pg) == ['Loyer test'])
    check('aucune erreur JavaScript', not pg.errors, pg.errors)


def test_creation_phrase_et_envoi(browser, fake):
    print('Appareil A : connexion, création de la phrase secrète, premier envoi')
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-10-03', 'Loyer test octobre', -500), tx('t2', '2026-11-05', 'Loyer test novembre', -510)])
    go_settings(a)
    a.fill('#sync-email', EMAIL)
    a.fill('#sync-pass', PASSWORD)
    a.click('[data-a=sync-login]')
    check('connecté : l’écran demande de créer la phrase (deux champs)', wait(a, "() => !!document.querySelector('#sync-phrase2')"))
    check('aucune donnée envoyée avant la phrase secrète', not [p for p in fake.posts if 'meta' in p or any(c.startswith('tx:') for c in p)], fake.posts)
    a.fill('#sync-phrase', 'courte')
    a.fill('#sync-phrase2', 'courte')
    a.click('[data-a=sync-phrase]')
    check('phrase trop courte refusée', wait(a, "() => document.querySelector('#sync-msg').textContent.includes('au moins')"))
    a.fill('#sync-phrase', PHRASE)
    a.fill('#sync-phrase2', PHRASE + 'x')
    a.click('[data-a=sync-phrase]')
    check('deux phrases différentes refusées', wait(a, "() => document.querySelector('#sync-msg').textContent.includes('identiques')"))
    a.fill('#sync-phrase2', PHRASE)
    a.click('[data-a=sync-phrase]')
    check('phrase acceptée : envoi des comptes et des deux mois', wait_remote(lambda: {'meta', 'tx:2026-10', 'tx:2026-11', 'sel', 'verif'} <= set(fake.rows)), list(fake.rows))
    check('l’état affiché est « Synchronisé »', wait(a, "() => document.querySelector('#sync-status') && document.querySelector('#sync-status').textContent.startsWith('Synchronisé')"))
    blob = fake.text()
    check('le serveur ne reçoit rien de lisible (libellés, nom de compte, montants)', 'Loyer' not in blob and 'Compte salaire' not in blob and 'octobre' not in blob and '510' not in blob.replace('=', ''), blob[:200])
    dump = a.evaluate("() => JSON.stringify(Object.assign({}, localStorage))")
    check('ni le mot de passe ni la phrase ne sont stockés', PASSWORD not in dump and PHRASE not in dump)
    check('la clé dérivée est gardée pour ne plus redemander la phrase', 'compte-sync-cle' in dump)
    check('aucune erreur JavaScript', not a.errors, a.errors)
    return a


def test_second_appareil(browser, fake):
    print('Appareil B : phrase fausse, puis bonne')
    b = device(browser, fake)
    go_settings(b)
    b.fill('#sync-email', EMAIL)
    b.fill('#sync-pass', PASSWORD)
    b.click('[data-a=sync-login]')
    check('B : l’écran demande la phrase (un seul champ, pas de création)', wait(b, "() => !!document.querySelector('#sync-phrase') && !document.querySelector('#sync-phrase2')"))
    b.fill('#sync-phrase', 'une autre phrase que celle de A')
    b.click('[data-a=sync-phrase]')
    check('mauvaise phrase : refusée', wait(b, "() => document.querySelector('#sync-msg').textContent.includes('incorrecte')"))
    check('rien n’a été écrit sur B', labels(b) == [] and b.evaluate("() => localStorage.getItem('compte-sync-cle')") is None)
    b.fill('#sync-phrase', PHRASE)
    b.click('[data-a=sync-phrase]')
    check('bonne phrase : B reçoit les lignes', wait(b, "() => S.tx.length === 2") and labels(b) == ['Loyer test novembre', 'Loyer test octobre'], labels(b))
    check('B reçoit aussi les comptes', b.evaluate("() => S.accounts.length >= 1 && S.accounts[0].name") == 'Compte salaire')
    check('aucune erreur JavaScript', not b.errors, b.errors)
    return b


def test_modification_en_direct(a, b, fake):
    print('Une modification sur A arrive sur B toute seule ; seul le mois modifié est envoyé')
    n = len(fake.posts)
    edit(a, "S.tx.push(%s)" % json.dumps(tx('t3', '2026-11-20', 'Courses test', -60)))
    check('A envoie sans clic sur « Synchroniser »', wait_remote(lambda: len(fake.posts) > n), fake.posts)
    check('seul le mois de novembre est envoyé (pas octobre)', all('tx:2026-10' not in p for p in fake.posts[n:]) and any('tx:2026-11' in p for p in fake.posts[n:]), fake.posts[n:])
    check('B reçoit la nouvelle ligne en moins de ~12 s, sans rien faire', wait(b, "() => S.tx.some((t) => t.label === 'Courses test')", None, 12000))
    check('aucune erreur JavaScript', not a.errors and not b.errors, a.errors + b.errors)


def test_suppression(a, b):
    print('Un mois vidé sur A disparaît de B')
    edit(a, "S.tx = S.tx.filter((t) => !t.date.startsWith('2026-10'))")
    sync(a)
    wait_remote(lambda: True)
    sync(b)
    check('B n’a plus la ligne d’octobre', wait(b, "() => !S.tx.some((t) => t.label === 'Loyer test octobre')"), labels(b))
    check('B a gardé novembre', 'Loyer test novembre' in labels(b))


def test_champs_locaux(a, b):
    print('Champs propres à l’appareil : lignes cochées et dernière sauvegarde')
    edit(a, "S.lastExport = '2026-11-01'; S.shown = []")
    sync(a)
    b.wait_for_timeout(500)
    sync(b)
    b.wait_for_timeout(500)
    check('la dernière sauvegarde de A n’arrive pas sur B', b.evaluate("() => S.lastExport") in (None, ''), b.evaluate("() => S.lastExport"))
    check('les comptes cochés de A n’arrivent pas sur B', b.evaluate("() => S.shown.length") >= 1)


def test_integrite(browser):
    print('Intégrité : le serveur ne peut pas échanger deux lignes')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-10-03', 'Octobre test', -1), tx('t2', '2026-11-05', 'Novembre test', -2)])
    connect(a, create=True)
    wait_remote(lambda: {'tx:2026-10', 'tx:2026-11'} <= set(fake.rows))
    b = device(browser, fake)
    connect(b)
    wait(b, "() => S.tx.length === 2")
    o, nv = fake.rows['tx:2026-10']['valeur'], fake.rows['tx:2026-11']['valeur']
    fake.rows['tx:2026-10']['valeur'], fake.rows['tx:2026-11']['valeur'] = nv, o
    fake.rows['tx:2026-10']['maj'] = fake.maj()
    fake.rows['tx:2026-11']['maj'] = fake.maj()
    sync(b)
    check('B refuse les lignes échangées et affiche une erreur', wait(b, "() => document.querySelector('#sync-status') && document.querySelector('#sync-status').textContent.includes('déchiffrement')"))
    check('les données de B ne sont pas abîmées', labels(b) == ['Novembre test', 'Octobre test'], labels(b))
    check('aucune erreur JavaScript', not a.errors and not b.errors, a.errors + b.errors)


def test_premiere_synchro(browser):
    print('Première synchro d’un appareil qui a déjà des lignes : le serveur l’emporte, copie gardée')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Version serveur', -5)])
    connect(a, create=True)
    wait_remote(lambda: 'tx:2026-11' in fake.rows)
    c = device(browser, fake)
    seed(c, [tx('t9', '2026-11-06', 'Version locale de C', -9)])
    connect(c)
    check('C adopte la version du serveur', wait(c, "() => S.tx.length === 1 && S.tx[0].label === 'Version serveur'"), labels(c))
    lost = json.loads(c.evaluate("() => localStorage.getItem('compte-sync-conflits')") or '[]')
    check('la version locale écrasée est gardée', len(lost) == 1 and lost[0]['perdant'] == 'local' and lost[0]['cle'] == 'tx:2026-11', lost)
    check('le serveur n’a pas été écrasé', len([p for p in fake.posts if 'tx:2026-11' in p]) == 1, fake.posts)
    print('Modification faite juste après la première connexion : conservée')
    edit(a, "S.tx[0].label = 'Modifié sur A'")
    sync(a)
    wait_remote(lambda: len([p for p in fake.posts if 'tx:2026-11' in p]) >= 2)
    sync(c)
    check('C reçoit la modification de A', wait(c, "() => S.tx[0].label === 'Modifié sur A'"), labels(c))
    check('aucune erreur JavaScript', not a.errors and not c.errors, a.errors + c.errors)


def test_hors_ligne_et_jeton(browser):
    print('Hors ligne puis retour du réseau ; jeton expiré')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Avant coupure', -5)])
    connect(a, create=True)
    wait_remote(lambda: 'tx:2026-11' in fake.rows)
    fake.offline = True
    edit(a, "S.tx[0].label = 'Pendant coupure'")
    sync(a)
    check('l’état affiche « Hors ligne »', wait(a, "() => document.querySelector('#sync-status') && document.querySelector('#sync-status').textContent.includes('Hors ligne')"))
    check('la donnée locale est intacte', stored_labels(a) == ['Pendant coupure'])
    fake.offline = False
    n = len(fake.posts)
    sync(a)
    check('au retour du réseau, la modification part', wait_remote(lambda: len(fake.posts) > n), fake.posts)
    fake.valid.clear()
    edit(a, "S.tx[0].label = 'Après renouvellement'")
    n = len(fake.posts)
    before = len([c for c in fake.calls if c[1] == '/auth/v1/token'])
    sync(a)
    check('jeton expiré : renouvelé sans intervention, la modification part', wait_remote(lambda: len(fake.posts) > n), fake.posts)
    check('un seul renouvellement', len([c for c in fake.calls if c[1] == '/auth/v1/token']) - before == 1)
    print('Session perdue : retour à la connexion, données gardées')
    fake.valid.clear()
    fake.refresh_ok.clear()
    edit(a, "S.tx[0].label = 'Session perdue'")
    sync(a)
    check('le formulaire de connexion revient avec un message', wait(a, "() => document.querySelector('#sync-email') && document.querySelector('#sync-box').textContent.includes('expiré')"))
    check('les données locales restent', stored_labels(a) == ['Session perdue'])
    check('la clé de chiffrement est effacée avec la session', a.evaluate("() => localStorage.getItem('compte-sync-cle')") is None)
    check('aucune erreur JavaScript', not a.errors, a.errors)


def test_deconnexion(browser):
    print('Déconnexion')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Reste ici', -5)])
    connect(a, create=True)
    wait_remote(lambda: 'tx:2026-11' in fake.rows)
    a.click('[data-a=sync-logout]')
    check('le formulaire de connexion revient', wait(a, "() => !!document.querySelector('#sync-email')"))
    check('session, clé et état de synchro effacés', a.evaluate("() => ['compte-sync-session', 'compte-sync-cle', 'compte-sync-meta'].every((k) => localStorage.getItem(k) === null)"))
    check('les données restent sur l’appareil et sur le serveur', stored_labels(a) == ['Reste ici'] and 'tx:2026-11' in fake.rows)
    n = len(fake.calls)
    a.wait_for_timeout(6500)
    check('plus aucun appel de données après la déconnexion', len([c for c in fake.calls[n:] if c[1].startswith('/rest')]) == 0, fake.calls[n:])
    check('aucune erreur JavaScript', not a.errors, a.errors)


def test_saisie_en_cours(browser):
    print('Fenêtre de saisie ouverte : rien n’est appliqué avant la fermeture')
    fake = FauxSupabase()
    a = device(browser, fake)
    seed(a, [tx('t1', '2026-11-05', 'Ligne A', -5)])
    connect(a, create=True)
    wait_remote(lambda: 'tx:2026-11' in fake.rows)
    b = device(browser, fake)
    connect(b)
    wait(b, "() => S.tx.length === 1")
    b.evaluate("() => openModal('<p id=\"ouverte\">saisie en cours</p>')")
    edit(a, "S.tx.push(%s)" % json.dumps(tx('t2', '2026-11-07', 'Ligne ajoutée sur A', -7)))
    wait_remote(lambda: len([p for p in fake.posts if 'tx:2026-11' in p]) >= 2)
    sync(b)
    b.wait_for_timeout(600)
    check('pendant la saisie, B n’applique rien', labels(b) == ['Ligne A'], labels(b))
    check('la fenêtre de B est toujours ouverte', b.locator('#ouverte').count() == 1)
    b.evaluate("() => closeModal()")
    sync(b)
    check('après fermeture, B reçoit la ligne', wait(b, "() => S.tx.length === 2"), labels(b))
    check('aucune erreur JavaScript', not a.errors and not b.errors, a.errors + b.errors)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        test_sans_compte(browser)
        fake = FauxSupabase()
        a = test_creation_phrase_et_envoi(browser, fake)
        b = test_second_appareil(browser, fake)
        test_modification_en_direct(a, b, fake)
        test_suppression(a, b)
        test_champs_locaux(a, b)
        test_integrite(browser)
        test_premiere_synchro(browser)
        test_hors_ligne_et_jeton(browser)
        test_deconnexion(browser)
        test_saisie_en_cours(browser)
        browser.close()
    failed = [n for n, ok in RESULTS if not ok]
    print('\n%d vérifications, %d échec(s)' % (len(RESULTS), len(failed)))
    for n in failed:
        print('  ECHEC : ' + n)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
