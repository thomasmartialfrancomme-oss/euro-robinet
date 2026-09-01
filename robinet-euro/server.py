#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robinet € — Site de micro-gains (démo)
Backend autonome : Python stdlib + SQLite. Aucune dépendance externe.
"""
import http.server
import json
import sqlite3
import os
import hashlib
import secrets
import time
import random
import math
import re
import urllib.parse
import urllib.request
import urllib.error
import threading
import atexit
import signal
import base64

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
PORT = int(os.environ.get("PORT", 8000))

def _pick_db_path():
    env = os.environ.get("DB_PATH")
    if env:
        return env
    if os.path.isdir("/data"):
        return "/data/data.db"
    return os.path.join(BASE, "data.db")

DB_PATH = _pick_db_path()
GITHUB_BACKUP_REPO = os.environ.get("GITHUB_BACKUP_REPO", "thomasmartialfrancomme-oss/euro-robinet-data")
GITHUB_BACKUP_FILE = os.environ.get("GITHUB_BACKUP_FILE", "data.db")

# ------- Paramètres -------
MIN_WITHDRAW_CENTS = 600          # 6,00 €
DAILY_CAP_CENTS = 100             # plafond de gain / jour (1,00 € au lieu de 5,00 €)
VIDEO_COOLDOWN_SEC = 45           # délai entre 2 vidéos
BONUS_CENTS = 2                   # bonus quotidien (0,02 €)
WHEEL_SPINS_PER_DAY = 5
FAUCET_COOLDOWN_SEC = 90          # recharge du robinet (1 min 30)
FAUCET_MIN_CENTS = 1              # gain minimum (0,01 €)
FAUCET_MAX_CENTS = 2              # gain maximum (0,02 €)
GAME_MAX_REWARD_CENTS = 5         # gain max par partie (0,05 €)
GAME_DAILY_CAP_CENTS = 50         # plafond par jeu et par jour (0,50 €)
GAMES = ("clicker", "memory")
COINFLIP_STAKE_CENTS = 5          # mise du jeu Pile ou Face (0,05 €)
ALLOWED_STAKES = (2, 5, 10)       # 0,02 / 0,05 / 0,10 €
STAKE_ROUND_CAP = 40              # parties à mise / jeu / jour
FUN_KINDS = ("scratch", "chest", "balloon", "quiz")
FUN_PER_KIND = 8                  # 8 pubs fun / type / jour
FUN_COOLDOWN_SEC = 20
CRASH_K = 0.055
CRASH_MAX = 2.80
CRASH_ROUND_CAP = 25
CRASH_DAILY_PROFIT_CAP = 25   # max +0,25 € net / jour sur Express
CRASH_PAYOUT_CAP_MULT = 2.20  # jamais plus de 2,20x

def now_ms():
    return int(time.time() * 1000)

def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

# ---------------- PERSISTENCE (Render free efface le disque) ----------------
_backup_lock = threading.Lock()
_backup_sha = None

def _gh_token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

def _gh_request(method, url, payload=None):
    token = _gh_token()
    if not token:
        return None, None
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "robinet-euro-backup")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        log(f"Backup GitHub erreur réseau : {e}")
        return None, None

def _checkpoint_db():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass

def restore_db():
    """Récupère la base sauvegardée avant init (sinon tout est à zéro après un sleep Render)."""
    global _backup_sha
    if not _gh_token():
        log("Pas de GITHUB_TOKEN : pas de restauration (la base sera vide si le disque a été effacé).")
        return
    url = f"https://api.github.com/repos/{GITHUB_BACKUP_REPO}/contents/{GITHUB_BACKUP_FILE}"
    status, body = _gh_request("GET", url + "?ref=main")
    if status == 404:
        log("Aucune sauvegarde GitHub pour l'instant.")
        return
    if status != 200 or not body or not body.get("content"):
        log(f"Restauration GitHub impossible (HTTP {status}).")
        return
    _backup_sha = body.get("sha")
    raw = base64.b64decode(body["content"].encode("ascii"))
    if len(raw) < 100:
        log("Sauvegarde GitHub trop petite, ignorée.")
        return
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    tmp = DB_PATH + ".restore"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, DB_PATH)
    log(f"Base restaurée depuis GitHub ({len(raw)} octets).")

def backup_db(force=False):
    """Envoie data.db sur un repo GitHub privé."""
    global _backup_sha
    token = _gh_token()
    if not token:
        return
    if not os.path.isfile(DB_PATH):
        return
    if not _backup_lock.acquire(blocking=force):
        return
    try:
        _checkpoint_db()
        with open(DB_PATH, "rb") as f:
            raw = f.read()
        if len(raw) < 100:
            return
        content = base64.b64encode(raw).decode("ascii")
        url = f"https://api.github.com/repos/{GITHUB_BACKUP_REPO}/contents/{GITHUB_BACKUP_FILE}"
        payload = {
            "message": "backup data.db " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "content": content,
            "branch": "main",
        }
        if _backup_sha:
            payload["sha"] = _backup_sha
        status, body = _gh_request("PUT", url, payload)
        if status in (200, 201) and body and body.get("content"):
            _backup_sha = body["content"].get("sha")
            log(f"Base sauvegardée ({len(raw)} octets).")
        elif status == 409:
            # sha périmé : relire puis réessayer une fois
            st2, b2 = _gh_request("GET", url)
            if st2 == 200 and b2:
                _backup_sha = b2.get("sha")
                payload["sha"] = _backup_sha
                status, body = _gh_request("PUT", url, payload)
                if status in (200, 201) and body and body.get("content"):
                    _backup_sha = body["content"].get("sha")
                    log(f"Base sauvegardée ({len(raw)} octets).")
        else:
            log(f"Sauvegarde GitHub HTTP {status} {str(body)[:180] if body else ''}")
    except Exception as e:
        log(f"Sauvegarde échouée : {e}")
    finally:
        _backup_lock.release()

def _backup_loop():
    while True:
        time.sleep(45)
        try:
            backup_db(False)
        except Exception:
            pass

def start_persistence():
    restore_db()
    threading.Timer(8.0, lambda: backup_db(False)).start()
    t = threading.Thread(target=_backup_loop, daemon=True)
    t.start()
    atexit.register(lambda: backup_db(True))
    def _sig(signum, frame):
        log("Arrêt : sauvegarde de la base…")
        backup_db(True)
        raise SystemExit(0)
    try:
        signal.signal(signal.SIGTERM, _sig)
    except Exception:
        pass

def hash_pw(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt + ":" + h

def check_pw(password, stored):
    salt, h = stored.split(":", 1)
    return hash_pw(password, salt) == stored

# ---------------- INIT DB ----------------
def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        password TEXT NOT NULL,
        balance_cents INTEGER NOT NULL DEFAULT 0,
        total_earned_cents INTEGER NOT NULL DEFAULT 0,
        is_admin INTEGER NOT NULL DEFAULT 0,
        banned INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        type TEXT NOT NULL,               -- video | ptc | survey | cpa
        reward_cents INTEGER NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        description TEXT DEFAULT '',
        color TEXT DEFAULT '#6366f1',
        link TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS video_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        offer_id INTEGER NOT NULL,
        completed_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ptc_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        offer_id INTEGER NOT NULL,
        clicked_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS survey_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        survey_id INTEGER NOT NULL,
        answered_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS bonuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        claimed_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS wheel_spins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        spun_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS faucet_claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        claimed_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS game_plays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game TEXT NOT NULL,
        played_at INTEGER NOT NULL,
        reward_cents INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,              -- earn | withdraw
        amount_cents INTEGER NOT NULL,
        label TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL,
        method TEXT NOT NULL,
        details TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',   -- pending | paid | rejected
        created_at INTEGER NOT NULL
    );
    """)
    conn.commit()

    # ---- migration : ajout colonne link si absente ----
    try:
        conn.execute("ALTER TABLE offers ADD COLUMN link TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crash_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        stake_cents INTEGER NOT NULL,
        crash_at REAL NOT NULL,
        start_ms INTEGER NOT NULL,
        status TEXT NOT NULL,
        cashed_mult REAL,
        payout_cents INTEGER NOT NULL DEFAULT 0
    )
    """)
    conn.commit()

    # ---- seed admin ----
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users(username,email,password,balance_cents,is_admin,created_at) VALUES(?,?,?,?,?,?)",
                  ("admin", "admin@robinet-euro.fr", hash_pw("Robinet974"), 0, 1, now_ms()))
        conn.commit()

    # ---- seed offers ----
    c.execute("SELECT COUNT(*) FROM offers")
    if c.fetchone()[0] == 0:
        offers = [
            ("Publicité vidéo — Boisson énergisante", "video", 2, 20, "Regarde la pub jusqu'au bout pour gagner 0,02 €.", "#f59e0b"),
            ("Publicité vidéo — Appli de shopping", "video", 3, 25, "Regarde la pub jusqu'au bout pour gagner 0,03 €.", "#6366f1"),
            ("Publicité vidéo — Jeu mobile gratuit", "video", 2, 15, "Regarde la pub jusqu'au bout pour gagner 0,02 €.", "#10b981"),
            ("Publicité vidéo — Service de streaming", "video", 4, 30, "Regarde la pub jusqu'au bout pour gagner 0,04 €.", "#ec4899"),
            ("Clic sponsorisé — Boutique partenaire A", "ptc", 1, 15, "Visite la page partenaire pendant 15 s pour gagner 0,01 €.", "#8b5cf6"),
            ("Clic sponsorisé — Boutique partenaire B", "ptc", 1, 15, "Visite la page partenaire pendant 15 s pour gagner 0,01 €.", "#f97316"),
            ("Clic sponsorisé — Site d'actualités", "ptc", 1, 10, "Visite la page partenaire pendant 10 s pour gagner 0,01 €.", "#14b8a6"),
            ("Sondage rapide — Tes habitudes de consommation", "survey", 3, 0, "Réponds à 3 questions pour gagner 0,03 €.", "#3b82f6"),
            ("Sondage — La musique que tu écoutes", "survey", 3, 0, "Réponds à 3 questions pour gagner 0,03 €.", "#a855f7"),
            ("Offre partenaire — Installe l'appli de cashback", "cpa", 150, 0, "Installe l'appli partenaire et ouvre-la pour gagner 1,50 €.", "#0ea5e9"),
            ("Offre partenaire — Inscris-toi au site de sondages", "cpa", 100, 0, "Crée un compte sur le site partenaire pour gagner 1,00 €.", "#0ea5e9"),
            ("Offre partenaire — Essaie le service de streaming", "cpa", 200, 0, "Essaie le service partenaire (gratuit) pour gagner 2,00 €.", "#0ea5e9"),
        ]
        for o in offers:
            c.execute("INSERT INTO offers(title,type,reward_cents,duration_seconds,description,color) VALUES(?,?,?,?,?,?)", o)
        conn.commit()

    conn.close()

# ---------------- HELPERS ----------------
def cents_to_str(c):
    return f"{c/100:.2f}".replace(".", ",")

def fmt_wait(sec):
    sec = int(sec)
    if sec >= 60:
        m, s = divmod(sec, 60)
        return f"{m} min {s:02d} s"
    return f"{sec} s"

def get_user_by_token(conn, token):
    if not token:
        return None
    r = conn.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (token,)).fetchone()
    return r

def require_auth(conn, token):
    u = get_user_by_token(conn, token)
    if not u:
        return None
    return u

def add_transaction(conn, user_id, kind, amount, label):
    conn.execute("INSERT INTO transactions(user_id,kind,amount_cents,label,created_at) VALUES(?,?,?,?,?)",
                 (user_id, kind, amount, label, now_ms()))

def earned_today(conn, user_id):
    day_start = int(time.time()) - (int(time.time()) % 86400)
    # approximation : on considère "aujourd'hui" via timestamp en ms
    t = now_ms()
    start = t - (t % (86400 * 1000))
    r = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE user_id=? AND kind='earn' AND created_at>=?",
                     (user_id, start)).fetchone()[0]
    return r

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def crash_mult_from_elapsed(elapsed_sec):
    return math.exp(CRASH_K * max(0.0, float(elapsed_sec)))

def crash_net_today(conn, uid):
    day_start = now_ms() - (now_ms() % (86400 * 1000))
    return conn.execute(
        "SELECT COALESCE(SUM(reward_cents),0) FROM game_plays WHERE user_id=? AND game='crash' AND played_at>=?",
        (uid, day_start)).fetchone()[0]

def gen_crash_at(hot=False):
    # hot = déjà trop gagné aujourd'hui → crash très tôt
    instant = 0.32 if hot else 0.14
    if random.random() < instant:
        return 1.00
    u = random.random() ** 0.62
    span = 0.50 if hot else 1.70
    m = 1.00 + u * span
    return round(min(max(m, 1.00), CRASH_MAX), 2)

def credit_house(conn, cents, label):
    if cents <= 0:
        return
    adm = conn.execute("SELECT id FROM users WHERE is_admin=1 ORDER BY id ASC LIMIT 1").fetchone()
    if not adm:
        return
    conn.execute(
        "UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
        (cents, cents, adm["id"]))
    add_transaction(conn, adm["id"], "earn", cents, label)

def settle_crash_if_needed(conn, row):
    """Si le crash est dépassé, marque perdu et verse la mise à l'admin."""
    if not row or row["status"] != "playing":
        return row
    elapsed = (now_ms() - row["start_ms"]) / 1000.0
    m = crash_mult_from_elapsed(elapsed)
    if m >= row["crash_at"]:
        conn.execute("UPDATE crash_rounds SET status='lost', cashed_mult=? WHERE id=?",
                     (row["crash_at"], row["id"]))
        credit_house(conn, row["stake_cents"], "Express : mise perdue d'un joueur")
        conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                     (row["user_id"], "crash", now_ms(), -row["stake_cents"]))
        conn.commit()
        row = conn.execute("SELECT * FROM crash_rounds WHERE id=?", (row["id"],)).fetchone()
    return row

# ---------------- HANDLERS ----------------
def handle_api(conn, path, method, body, token):
    parts = path.strip("/").split("/")
    # parts ex: ['api','login']
    if len(parts) < 2:
        return 404, {"error": "Not found"}

    endpoint = parts[1]

    # ---- AUTH ----
    if endpoint == "register" and method == "POST":
        username = (body.get("username") or "").strip()
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            return 400, {"error": "Nom d'utilisateur et mot de passe requis."}
        if len(username) < 3:
            return 400, {"error": "Le nom d'utilisateur doit faire au moins 3 caractères."}
        if len(password) < 4:
            return 400, {"error": "Le mot de passe doit faire au moins 4 caractères."}
        if not re.match(r"^[A-Za-z0-9_.-]+$", username):
            return 400, {"error": "Nom d'utilisateur invalide (lettres, chiffres, _ . -)."}
        try:
            cur = conn.execute("INSERT INTO users(username,email,password,created_at) VALUES(?,?,?,?)",
                               (username, email, hash_pw(password), now_ms()))
            conn.commit()
            uid = cur.lastrowid
            # bonus de bienvenue
            conn.execute("UPDATE users SET balance_cents=balance_cents+5, total_earned_cents=total_earned_cents+5 WHERE id=?", (uid,))
            add_transaction(conn, uid, "earn", 5, "Bonus de bienvenue")
            conn.commit()
            tok = secrets.token_hex(24)
            conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (tok, uid, now_ms()))
            conn.commit()
            return 200, {"token": tok, "message": "Compte créé ! +0,05 € offert."}
        except sqlite3.IntegrityError:
            return 400, {"error": "Ce nom d'utilisateur est déjà pris."}

    if endpoint == "login" and method == "POST":
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not u or not check_pw(password, u["password"]):
            return 401, {"error": "Identifiants incorrects."}
        if u["banned"]:
            return 403, {"error": "Compte suspendu. Contacte le support."}
        tok = secrets.token_hex(24)
        conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (tok, u["id"], now_ms()))
        conn.commit()
        return 200, {"token": tok}

    if endpoint == "logout" and method == "POST":
        if token:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
        return 200, {"ok": True}

    # ---- USER ----
    if endpoint == "me" and method == "GET":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        return 200, user_payload(conn, u)

    if endpoint == "leaderboard" and method == "GET":
        rows = conn.execute(
            "SELECT username, total_earned_cents FROM users WHERE banned=0 ORDER BY total_earned_cents DESC LIMIT 20").fetchall()
        return 200, {"leaderboard": [{"username": r["username"], "earned": r["total_earned_cents"]} for r in rows]}

    # ---- OFFERS ----
    if endpoint == "offers" and method == "GET":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        offers = conn.execute("SELECT * FROM offers WHERE active=1").fetchall()
        return 200, {"offers": [offer_payload(conn, u, o) for o in offers]}

    if endpoint == "dashboard" and method == "GET":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        return 200, dashboard_payload(conn, u)

    # ---- EARNING ACTIONS ----
    if endpoint == "finish_view" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        offer_id = body.get("offer_id")
        o = conn.execute("SELECT * FROM offers WHERE id=? AND type='video' AND active=1", (offer_id,)).fetchone()
        if not o:
            return 404, {"error": "Offre introuvable."}
        # déjà regardée ? une seule fois par vidéo
        already = conn.execute("SELECT 1 FROM video_views WHERE user_id=? AND offer_id=?", (u["id"], o["id"])).fetchone()
        if already:
            return 429, {"error": "Tu as déjà regardé cette vidéo."}
        # cooldown
        last = conn.execute("SELECT completed_at FROM video_views WHERE user_id=? ORDER BY completed_at DESC LIMIT 1",
                            (u["id"],)).fetchone()
        if last and (now_ms() - last["completed_at"]) < VIDEO_COOLDOWN_SEC * 1000:
            wait = VIDEO_COOLDOWN_SEC - (now_ms() - last["completed_at"]) // 1000
            return 429, {"error": f"Attends encore {int(wait)} s avant une nouvelle vidéo."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €). Reviens demain !"}
        reward = o["reward_cents"]
        conn.execute("INSERT INTO video_views(user_id,offer_id,completed_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], o["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, f"Vidéo : {o['title']}")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "click_ptc" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        offer_id = body.get("offer_id")
        o = conn.execute("SELECT * FROM offers WHERE id=? AND type='ptc' AND active=1", (offer_id,)).fetchone()
        if not o:
            return 404, {"error": "Offre introuvable."}
        day_ms = 24 * 3600 * 1000
        last = conn.execute("SELECT clicked_at FROM ptc_clicks WHERE user_id=? AND offer_id=? ORDER BY clicked_at DESC LIMIT 1",
                            (u["id"], o["id"])).fetchone()
        if last and (now_ms() - last["clicked_at"]) < day_ms:
            return 429, {"error": "Tu as déjà fait ce clic aujourd'hui."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €)."}
        reward = o["reward_cents"]
        conn.execute("INSERT INTO ptc_clicks(user_id,offer_id,clicked_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], o["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, f"Clic : {o['title']}")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "survey_submit" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        survey_id = body.get("survey_id")
        o = conn.execute("SELECT * FROM offers WHERE id=? AND type='survey' AND active=1", (survey_id,)).fetchone()
        if not o:
            return 404, {"error": "Sondage introuvable."}
        last = conn.execute("SELECT answered_at FROM survey_answers WHERE user_id=? AND survey_id=?",
                            (u["id"], o["id"])).fetchone()
        if last:
            return 429, {"error": "Tu as déjà répondu à ce sondage."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €)."}
        reward = o["reward_cents"]
        conn.execute("INSERT INTO survey_answers(user_id,survey_id,answered_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], o["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, f"Sondage : {o['title']}")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "claim_bonus" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        day_ms = 24 * 3600 * 1000
        last = conn.execute("SELECT claimed_at FROM bonuses WHERE user_id=? ORDER BY claimed_at DESC LIMIT 1",
                            (u["id"],)).fetchone()
        if last and (now_ms() - last["claimed_at"]) < day_ms:
            return 429, {"error": "Bonus déjà réclamé aujourd'hui."}
        reward = BONUS_CENTS
        conn.execute("INSERT INTO bonuses(user_id,claimed_at,reward_cents) VALUES(?,?,?)", (u["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, "Bonus quotidien")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "spin_wheel" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        day_start = now_ms() - (now_ms() % (86400 * 1000))
        spins = conn.execute("SELECT COUNT(*) FROM wheel_spins WHERE user_id=? AND spun_at>=?",
                             (u["id"], day_start)).fetchone()[0]
        if spins >= WHEEL_SPINS_PER_DAY:
            return 429, {"error": f"Plus que {WHEEL_SPINS_PER_DAY} tours par jour."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €)."}
        rewards = [0, 1, 2, 1, 3, 5, 1, 2, 1, 2, 1, 3]  # en cents (max 0,05 €)
        reward = random.choice(rewards)
        conn.execute("INSERT INTO wheel_spins(user_id,spun_at,reward_cents) VALUES(?,?,?)", (u["id"], now_ms(), reward))
        if reward > 0:
            conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                         (reward, reward, u["id"]))
            add_transaction(conn, u["id"], "earn", reward, "Roue de la fortune")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "claim_faucet" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        last = conn.execute("SELECT claimed_at FROM faucet_claims WHERE user_id=? ORDER BY claimed_at DESC LIMIT 1",
                            (u["id"],)).fetchone()
        if last and (now_ms() - last["claimed_at"]) < FAUCET_COOLDOWN_SEC * 1000:
            wait = FAUCET_COOLDOWN_SEC - (now_ms() - last["claimed_at"]) // 1000
            return 429, {"error": f"Le robinet se recharge. Réessaie dans {fmt_wait(wait)}."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €). Reviens demain !"}
        reward = random.randint(FAUCET_MIN_CENTS, FAUCET_MAX_CENTS)
        conn.execute("INSERT INTO faucet_claims(user_id,claimed_at,reward_cents) VALUES(?,?,?)",
                     (u["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, "Robinet €")
        conn.commit()

        return 200, {"reward": reward, "balance": balance(conn, u["id"]), "cooldown": FAUCET_COOLDOWN_SEC}

    if endpoint == "claim_fun" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        kind = body.get("kind")
        if kind not in FUN_KINDS:
            return 400, {"error": "Jeu fun inconnu."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint. Reviens demain !"}
        day_start = now_ms() - (now_ms() % (86400 * 1000))
        n = conn.execute(
            "SELECT COUNT(*) FROM game_plays WHERE user_id=? AND game=? AND played_at>=?",
            (u["id"], "fun-" + kind, day_start)).fetchone()[0]
        if n >= FUN_PER_KIND:
            return 429, {"error": "Tu as déjà trop joué à ça aujourd'hui. Reviens demain !"}
        last = conn.execute(
            "SELECT played_at FROM game_plays WHERE user_id=? AND game LIKE 'fun-%' ORDER BY played_at DESC LIMIT 1",
            (u["id"],)).fetchone()
        if last and (now_ms() - last["played_at"]) < FUN_COOLDOWN_SEC * 1000:
            wait = FUN_COOLDOWN_SEC - (now_ms() - last["played_at"]) // 1000
            return 429, {"error": f"Encore un peu… réessaie dans {wait} s."}
        reward = 2 if random.random() < 0.12 else 1
        names = {"scratch": "Carte à gratter", "chest": "Coffre mystère", "balloon": "Bulles d'or", "quiz": "Quiz fun"}
        label = names.get(kind, "Fun")
        conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], "fun-" + kind, now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, label)
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"]), "left": FUN_PER_KIND - n - 1}

    if endpoint == "play_game" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        game = body.get("game")
        score = int(body.get("score") or 0)
        if game not in GAMES:
            return 404, {"error": "Jeu inconnu."}
        score = max(0, min(score, GAME_MAX_REWARD_CENTS))
        day_start = now_ms() - (now_ms() % (86400 * 1000))
        earned_game = conn.execute("SELECT COALESCE(SUM(reward_cents),0) FROM game_plays WHERE user_id=? AND game=? AND played_at>=?",
                                   (u["id"], game, day_start)).fetchone()[0]
        remaining = GAME_DAILY_CAP_CENTS - earned_game
        if remaining <= 0:
            return 429, {"error": f"Plafond du jeu atteint pour aujourd'hui. Reviens demain !"}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €)."}
        reward = min(score, remaining)
        conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], game, now_ms(), reward))
        if reward > 0:
            conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                         (reward, reward, u["id"]))
            add_transaction(conn, u["id"], "earn", reward, f"Jeu : {game}")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    if endpoint == "play_coinflip" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        choice = body.get("choice")
        if choice not in ("pile", "face"):
            return 400, {"error": "Choisis Pile ou Face."}
        stake = COINFLIP_STAKE_CENTS
        if u["balance_cents"] < stake:
            return 400, {"error": "Solde insuffisant : il faut 0,05 € pour jouer."}
        actual = random.choice(["pile", "face"])
        won = (choice == actual)
        if won:
            conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                         (stake, stake, u["id"]))
            add_transaction(conn, u["id"], "earn", stake, "Pile ou Face (gagné)")
        else:
            conn.execute("UPDATE users SET balance_cents=balance_cents-? WHERE id=?", (stake, u["id"]))
            add_transaction(conn, u["id"], "earn", -stake, "Pile ou Face (perdu)")

        conn.commit()
        return 200, {"won": won, "actual": actual, "stake": stake, "balance": balance(conn, u["id"])}


    if endpoint == "crash_start" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        try:
            stake = int(body.get("stake_cents") or 0)
        except (TypeError, ValueError):
            stake = 0
        if stake not in ALLOWED_STAKES:
            return 400, {"error": "Mise invalide (0,02 / 0,05 / 0,10 €)."}
        if u["balance_cents"] < stake:
            return 400, {"error": f"Solde insuffisant : il faut {cents_to_str(stake)} €."}
        day_start = now_ms() - (now_ms() % (86400 * 1000))
        nplays = conn.execute(
            "SELECT COUNT(*) FROM game_plays WHERE user_id=? AND game=? AND played_at>=?",
            (u["id"], "crash", day_start)).fetchone()[0]
        if nplays >= CRASH_ROUND_CAP:
            return 429, {"error": "Limite Express atteinte pour aujourd'hui."}
        # clôturer une partie restante
        leftover = conn.execute(
            "SELECT * FROM crash_rounds WHERE user_id=? AND status='playing' ORDER BY id DESC LIMIT 1",
            (u["id"],)).fetchone()
        if leftover:
            settle_crash_if_needed(conn, leftover)
            leftover = conn.execute("SELECT * FROM crash_rounds WHERE id=?", (leftover["id"],)).fetchone()
            if leftover and leftover["status"] == "playing":
                conn.execute("UPDATE crash_rounds SET status='lost', cashed_mult=? WHERE id=?",
                             (leftover["crash_at"], leftover["id"]))
                credit_house(conn, leftover["stake_cents"], "Express : mise perdue d'un joueur")
                conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                             (u["id"], "crash", now_ms(), -leftover["stake_cents"]))
        hot = crash_net_today(conn, u["id"]) >= CRASH_DAILY_PROFIT_CAP
        crash_at = gen_crash_at(hot=hot)
        conn.execute("UPDATE users SET balance_cents=balance_cents-? WHERE id=?", (stake, u["id"]))
        add_transaction(conn, u["id"], "earn", -stake, "Express (mise)")
        cur = conn.execute(
            "INSERT INTO crash_rounds(user_id,stake_cents,crash_at,start_ms,status) VALUES(?,?,?,?, 'playing')",
            (u["id"], stake, crash_at, now_ms()))
        conn.commit()
        return 200, {"id": cur.lastrowid, "stake": stake, "k": CRASH_K, "max": CRASH_MAX,
                     "balance": balance(conn, u["id"])}

    if endpoint == "crash_status" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        rid = int(body.get("id") or 0)
        row = conn.execute("SELECT * FROM crash_rounds WHERE id=? AND user_id=?", (rid, u["id"])).fetchone()
        if not row:
            return 404, {"error": "Partie introuvable."}
        row = settle_crash_if_needed(conn, row)
        elapsed = (now_ms() - row["start_ms"]) / 1000.0
        shown = min(crash_mult_from_elapsed(elapsed), CRASH_MAX)
        if row["status"] == "lost":
            return 200, {"status": "lost", "crash_at": row["crash_at"], "stake": row["stake_cents"],
                         "balance": balance(conn, u["id"])}
        if row["status"] == "won":
            return 200, {"status": "won", "at": row["cashed_mult"], "payout": row["payout_cents"],
                         "stake": row["stake_cents"], "balance": balance(conn, u["id"])}
        return 200, {"status": "playing", "multiplier": round(shown, 2), "stake": row["stake_cents"]}

    if endpoint == "crash_cashout" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        rid = int(body.get("id") or 0)
        row = conn.execute("SELECT * FROM crash_rounds WHERE id=? AND user_id=?", (rid, u["id"])).fetchone()
        if not row:
            return 404, {"error": "Partie introuvable."}
        row = settle_crash_if_needed(conn, row)
        if row["status"] == "lost":
            return 200, {"status": "lost", "crash_at": row["crash_at"], "stake": row["stake_cents"],
                         "balance": balance(conn, u["id"])}
        if row["status"] != "playing":
            return 400, {"error": "Cette partie est déjà terminée."}
        elapsed = (now_ms() - row["start_ms"]) / 1000.0
        at = round(min(crash_mult_from_elapsed(elapsed), CRASH_MAX), 2)
        if at >= row["crash_at"]:
            conn.execute("UPDATE crash_rounds SET status='lost', cashed_mult=? WHERE id=?",
                         (row["crash_at"], row["id"]))
            credit_house(conn, row["stake_cents"], "Express : mise perdue d'un joueur")
            conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                         (u["id"], "crash", now_ms(), -row["stake_cents"]))
            conn.commit()
            return 200, {"status": "lost", "crash_at": row["crash_at"], "stake": row["stake_cents"],
                         "balance": balance(conn, u["id"])}
        at_pay = min(at, CRASH_PAYOUT_CAP_MULT)
        payout = int(round(row["stake_cents"] * at_pay))
        net = crash_net_today(conn, u["id"])
        profit = payout - row["stake_cents"]
        if net + profit > CRASH_DAILY_PROFIT_CAP:
            payout = row["stake_cents"] + max(0, CRASH_DAILY_PROFIT_CAP - net)
            at_pay = round(payout / max(1, row["stake_cents"]), 2)
        if payout < 1:
            payout = row["stake_cents"]
        conn.execute("UPDATE crash_rounds SET status='won', cashed_mult=?, payout_cents=? WHERE id=?",
                     (at_pay, payout, row["id"]))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (payout, max(0, payout - row["stake_cents"]), u["id"]))
        add_transaction(conn, u["id"], "earn", payout, f"Express retiré à {at_pay:.2f}x")
        conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], "crash", now_ms(), payout - row["stake_cents"]))
        conn.commit()
        return 200, {"status": "won", "at": at_pay, "payout": payout, "stake": row["stake_cents"],
                     "balance": balance(conn, u["id"])}

    if endpoint == "play_stake" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        game = body.get("game")
        choice = body.get("choice")
        try:
            stake = int(body.get("stake_cents") or 0)
        except (TypeError, ValueError):
            stake = 0
        if stake not in ALLOWED_STAKES:
            return 400, {"error": "Mise invalide (0,02 / 0,05 / 0,10 €)."}
        if u["balance_cents"] < stake:
            return 400, {"error": f"Solde insuffisant : il faut {cents_to_str(stake)} €."}
        day_start = now_ms() - (now_ms() % (86400 * 1000))
        nplays = conn.execute(
            "SELECT COUNT(*) FROM game_plays WHERE user_id=? AND game=? AND played_at>=?",
            (u["id"], game, day_start)).fetchone()[0]
        if nplays >= STAKE_ROUND_CAP:
            return 429, {"error": "Limite de parties atteinte pour ce jeu aujourd'hui."}

        net = 0
        won = False
        draw = False
        actual = None
        extra = {}
        label = "Jeu à mise"

        if game == "dice":
            if choice not in ("even", "odd"):
                return 400, {"error": "Choisis pair ou impair."}
            actual = random.randint(1, 6)
            is_even = actual % 2 == 0
            won = (choice == "even" and is_even) or (choice == "odd" and not is_even)
            net = stake if won else -stake
            label = "Dé (gagné)" if won else "Dé (perdu)"
        elif game == "rps":
            opts = ("pierre", "feuille", "ciseaux")
            if choice not in opts:
                return 400, {"error": "Choisis pierre, feuille ou ciseaux."}
            actual = random.choice(opts)
            beats = {"pierre": "ciseaux", "feuille": "pierre", "ciseaux": "feuille"}
            if choice == actual:
                draw = True
                net = 0
                label = "Chifoumi (égalité)"
            else:
                won = beats[choice] == actual
                net = stake if won else -stake
                label = "Chifoumi (gagné)" if won else "Chifoumi (perdu)"
        elif game == "slots":
            symbols = ["🍒", "🍋", "🍇", "🔔", "⭐", "7️⃣"]
            reels = [random.choice(symbols) for _ in range(3)]
            extra["reels"] = reels
            extra["kind"] = "lose"
            if reels[0] == reels[1] == reels[2]:
                won = True
                if reels[0] == "7️⃣":
                    net = 5 * stake
                    extra["kind"] = "jackpot"
                    label = "Machine à sous (jackpot)"
                else:
                    net = 3 * stake
                    extra["kind"] = "triple"
                    label = "Machine à sous (triple)"
            elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
                won = True
                net = stake
                extra["kind"] = "double"
                label = "Machine à sous (paire)"
            else:
                net = -stake
                label = "Machine à sous (perdu)"
            actual = "".join(reels)
        elif game == "color":
            if choice not in ("rouge", "noir"):
                return 400, {"error": "Choisis rouge ou noir."}
            actual = random.choice(["rouge", "noir"])
            won = choice == actual
            net = stake if won else -stake
            label = "Rouge/Noir (gagné)" if won else "Rouge/Noir (perdu)"
        else:
            return 404, {"error": "Jeu inconnu."}

        if net > 0:
            conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                         (net, net, u["id"]))
        elif net < 0:
            conn.execute("UPDATE users SET balance_cents=balance_cents-? WHERE id=?", (-net, u["id"]))
        add_transaction(conn, u["id"], "earn", net, label)
        conn.execute("INSERT INTO game_plays(user_id,game,played_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], game, now_ms(), net))
        conn.commit()
        payload = {"won": won, "draw": draw, "actual": actual, "stake": stake, "payout": net,
                   "balance": balance(conn, u["id"])}
        payload.update(extra)
        return 200, payload

    if endpoint == "complete_cpa" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        offer_id = body.get("offer_id")
        o = conn.execute("SELECT * FROM offers WHERE id=? AND type='cpa' AND active=1", (offer_id,)).fetchone()
        if not o:
            return 404, {"error": "Offre introuvable."}
        last = conn.execute("SELECT clicked_at FROM ptc_clicks WHERE user_id=? AND offer_id=?",
                            (u["id"], o["id"])).fetchone()
        if last:
            return 429, {"error": "Tu as déjà fait cette offre."}
        if earned_today(conn, u["id"]) >= DAILY_CAP_CENTS:
            return 429, {"error": "Plafond journalier atteint (5,00 €)."}
        reward = o["reward_cents"]
        conn.execute("INSERT INTO ptc_clicks(user_id,offer_id,clicked_at,reward_cents) VALUES(?,?,?,?)",
                     (u["id"], o["id"], now_ms(), reward))
        conn.execute("UPDATE users SET balance_cents=balance_cents+?, total_earned_cents=total_earned_cents+? WHERE id=?",
                     (reward, reward, u["id"]))
        add_transaction(conn, u["id"], "earn", reward, f"Partenaire : {o['title']}")
        conn.commit()
        return 200, {"reward": reward, "balance": balance(conn, u["id"])}

    # ---- WITHDRAWALS ----
    if endpoint == "withdrawals" and method == "GET":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        rows = conn.execute("SELECT * FROM withdrawals WHERE user_id=? ORDER BY created_at DESC", (u["id"],)).fetchall()
        return 200, {"withdrawals": [dict(r) for r in rows]}

    if endpoint == "withdraw" and method == "POST":
        u = require_auth(conn, token)
        if not u:
            return 401, {"error": "Non connecté."}
        method = body.get("method")
        details = (body.get("details") or "").strip()
        amount = int(body.get("amount_cents") or 0)
        if amount < MIN_WITHDRAW_CENTS:
            return 400, {"error": f"Le retrait minimum est de 6,00 € (tu as demandé {cents_to_str(amount)} €)."}
        if amount > u["balance_cents"]:
            return 400, {"error": "Solde insuffisant."}
        if method not in ("paypal", "virement", "crypto"):
            return 400, {"error": "Méthode de paiement invalide."}
        if not details:
            return 400, {"error": "Merci d'indiquer tes coordonnées de paiement."}
        conn.execute("UPDATE users SET balance_cents=balance_cents-? WHERE id=?", (amount, u["id"]))
        conn.execute("INSERT INTO withdrawals(user_id,amount_cents,method,details,status,created_at) VALUES(?,?,?,?,?,?)",
                     (u["id"], amount, method, details, "pending", now_ms()))
        add_transaction(conn, u["id"], "withdraw", -amount, f"Retrait ({method})")
        conn.commit()
        return 200, {"balance": balance(conn, u["id"]), "message": "Demande de retrait envoyée !"}

    # ---- ADMIN ----
    if endpoint.startswith("admin"):
        u = require_auth(conn, token)
        if not u or not u["is_admin"]:
            return 403, {"error": "Accès refusé."}
        return handle_admin(conn, parts, method, body)

    return 404, {"error": "Not found"}

def handle_admin(conn, parts, method, body):
    if len(parts) < 3:
        return 404, {"error": "Not found"}
    sub = parts[2]

    if sub == "overview" and method == "GET":
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'").fetchone()[0]
        total_paid = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM withdrawals WHERE status='paid'").fetchone()[0]
        total_earned = conn.execute("SELECT COALESCE(SUM(total_earned_cents),0) FROM users").fetchone()[0]
        return 200, {"users": users, "pending_withdrawals": pending,
                     "total_paid": total_paid, "total_earned": total_earned}

    if sub == "users" and method == "GET":
        rows = conn.execute("SELECT id,username,email,balance_cents,total_earned_cents,banned,created_at FROM users ORDER BY created_at DESC").fetchall()
        return 200, {"users": [dict(r) for r in rows]}

    if sub == "withdrawals" and method == "GET":
        rows = conn.execute(
            "SELECT w.*, u.username FROM withdrawals w JOIN users u ON u.id=w.user_id ORDER BY w.created_at DESC").fetchall()
        return 200, {"withdrawals": [dict(r) for r in rows]}

    if sub == "withdrawal_status" and method == "POST":
        wid = body.get("id")
        status = body.get("status")
        if status not in ("paid", "rejected"):
            return 400, {"error": "Statut invalide."}
        w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
        if not w:
            return 404, {"error": "Retrait introuvable."}
        if w["status"] == "pending" and status == "rejected":
            # rembourse
            conn.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=?", (w["amount_cents"], w["user_id"]))
            add_transaction(conn, w["user_id"], "earn", w["amount_cents"], "Retrait refusé (remboursement)")
        conn.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
        conn.commit()
        return 200, {"ok": True}

    if sub == "user_toggle_ban" and method == "POST":
        uid = body.get("id")
        u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            return 404, {"error": "Utilisateur introuvable."}
        conn.execute("UPDATE users SET banned=? WHERE id=?", (0 if u["banned"] else 1, uid))
        conn.commit()
        return 200, {"banned": 0 if u["banned"] else 1}

    if sub == "user_adjust" and method == "POST":
        uid = body.get("id")
        delta = int(body.get("delta") or 0)
        conn.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=?", (delta, uid))
        if delta > 0:
            conn.execute("UPDATE users SET total_earned_cents=total_earned_cents+? WHERE id=?", (delta, uid))
        conn.commit()
        return 200, {"ok": True}

    if sub == "offer_create" and method == "POST":
        title = body.get("title")
        type_ = body.get("type")
        reward = int(body.get("reward_cents") or 0)
        dur = int(body.get("duration_seconds") or 0)
        if type_ not in ("video", "ptc", "survey"):
            return 400, {"error": "Type invalide."}
        conn.execute("INSERT INTO offers(title,type,reward_cents,duration_seconds,description,color) VALUES(?,?,?,?,?,?)",
                     (title, type_, reward, dur, body.get("description", ""), body.get("color", "#6366f1")))
        conn.commit()
        return 200, {"ok": True}

    if sub == "offer_toggle" and method == "POST":
        oid = body.get("id")
        o = conn.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        if not o:
            return 404, {"error": "Offre introuvable."}
        conn.execute("UPDATE offers SET active=? WHERE id=?", (0 if o["active"] else 1, oid))
        conn.commit()
        return 200, {"active": 0 if o["active"] else 1}

    if sub == "offer_set_link" and method == "POST":
        oid = body.get("id")
        link = (body.get("link") or "").strip()
        o = conn.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        if not o:
            return 404, {"error": "Offre introuvable."}
        conn.execute("UPDATE offers SET link=? WHERE id=?", (link, oid))
        conn.commit()
        return 200, {"ok": True, "link": link}

    return 404, {"error": "Not found"}

# ---------------- PAYLOADS ----------------
def balance(conn, uid):
    return conn.execute("SELECT balance_cents FROM users WHERE id=?", (uid,)).fetchone()[0]

def user_payload(conn, u):
    return {
        "id": u["id"], "username": u["username"], "email": u["email"],
        "balance": u["balance_cents"], "total_earned": u["total_earned_cents"],
        "is_admin": bool(u["is_admin"]), "banned": bool(u["banned"]),
        "min_withdraw": MIN_WITHDRAW_CENTS,
        "earned_today": earned_today(conn, u["id"]),
        "daily_cap": DAILY_CAP_CENTS,
    }

def offer_payload(conn, u, o):
    p = dict(o)
    if o["type"] == "ptc":
        last = conn.execute("SELECT clicked_at FROM ptc_clicks WHERE user_id=? AND offer_id=? ORDER BY clicked_at DESC LIMIT 1",
                            (u["id"], o["id"])).fetchone()
        p["done"] = bool(last and (now_ms() - last["clicked_at"]) < 24 * 3600 * 1000)
    elif o["type"] == "video":
        last = conn.execute("SELECT 1 FROM video_views WHERE user_id=? AND offer_id=?", (u["id"], o["id"])).fetchone()
        p["done"] = bool(last)
    elif o["type"] == "cpa":
        last = conn.execute("SELECT 1 FROM ptc_clicks WHERE user_id=? AND offer_id=?", (u["id"], o["id"])).fetchone()
        p["done"] = bool(last)
    elif o["type"] == "survey":
        last = conn.execute("SELECT 1 FROM survey_answers WHERE user_id=? AND survey_id=?", (u["id"], o["id"])).fetchone()
        p["done"] = bool(last)
    else:
        p["done"] = False
    return p

def dashboard_payload(conn, u):
    offers = conn.execute("SELECT * FROM offers WHERE active=1").fetchall()
    recent = conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 15", (u["id"],)).fetchall()
    lb = conn.execute("SELECT username, total_earned_cents FROM users WHERE banned=0 ORDER BY total_earned_cents DESC LIMIT 10").fetchall()
    last_faucet = conn.execute("SELECT claimed_at FROM faucet_claims WHERE user_id=? ORDER BY claimed_at DESC LIMIT 1",
                               (u["id"],)).fetchone()
    return {
        "user": user_payload(conn, u),
        "offers": [offer_payload(conn, u, o) for o in offers],
        "recent": [dict(r) for r in recent],
        "leaderboard": [{"username": r["username"], "earned": r["total_earned_cents"]} for r in lb],
        "faucet": {
            "cooldown": FAUCET_COOLDOWN_SEC,
            "min": FAUCET_MIN_CENTS,
            "max": FAUCET_MAX_CENTS,
            "last_claim": last_faucet["claimed_at"] if last_faucet else 0,
        },
    }

# ---------------- HTTP SERVER ----------------
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            conn = db()
            try:
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                code, obj = handle_api(conn, path, "GET", {}, token)
            except Exception as e:
                log(f"ERR GET {path}: {e}")
                code, obj = 500, {"error": "Erreur interne."}
            finally:
                conn.close()
            self._send(code, obj)
            return
        self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}
        if path.startswith("/api/"):
            conn = db()
            try:
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                code, obj = handle_api(conn, path, "POST", body, token)
            except Exception as e:
                log(f"ERR POST {path}: {e}")
                code, obj = 500, {"error": "Erreur interne."}
            finally:
                conn.close()
            self._send(code, obj)
            return
        self._send(404, {"error": "Not found"})

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        # sécurité : pas de path traversal
        fpath = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fpath.startswith(STATIC):
            self._send(404, {"error": "Not found"})
            return
        if not os.path.isfile(fpath):
            self._send(404, {"error": "Not found"})
            return
        ext = os.path.splitext(fpath)[1]
        ctype = {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
                 "js": "application/javascript; charset=utf-8", "svg": "image/svg+xml",
                 "png": "image/png", "jpg": "image/jpeg", "ico": "image/x-icon",
                 "txt": "text/plain; charset=utf-8"}.get(ext.lstrip("."), "application/octet-stream")
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    log(f"Fichier base : {DB_PATH}")
    start_persistence()
    init_db()
    log(f"Démarrage sur 0.0.0.0:{PORT}")
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        backup_db(True)
