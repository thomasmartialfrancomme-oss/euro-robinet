#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robinet € — Site de micro-gains
Backend : PostgreSQL (via DATABASE_URL) ou repli SQLite local (dev/test).
"""
import http.server
import json
import os
import hashlib
import secrets
import time
import random
import re
import urllib.parse

try:
    import sqlite3
except ImportError:
    sqlite3 = None

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

BASE = os.path.dirname(os.path.abspath(__file__))
# DATABASE_URL : chaîne de connexion PostgreSQL (ex: Supabase). Si elle est
# définie, les données sont stockées dans une vraie base persistante qui
# survit aux redéploiements. Sinon, repli sur SQLite local (dev/test).
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = os.path.join(BASE, "data.db")
STATIC = os.path.join(BASE, "static")
PORT = int(os.environ.get("PORT", 8000))

# Types d'exceptions "contrainte unique" selon le moteur utilisé.
UNIQUE_ERRORS = ()
if sqlite3 is not None:
    UNIQUE_ERRORS = UNIQUE_ERRORS + (sqlite3.IntegrityError,)
if HAS_PG:
    UNIQUE_ERRORS = UNIQUE_ERRORS + (psycopg2.IntegrityError,)

# État de la base (pour diagnostic + repli sécurisé)
_PG_FALLBACK = False
_PG_ERROR = ""

# ------- Paramètres -------
MIN_WITHDRAW_CENTS = 200          # 2,00 €
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

def now_ms():
    return int(time.time() * 1000)


class Row(dict):
    """Ligne de résultat compatible dict ET index (row[0], row['col'])."""
    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self.values())[k]
        return dict.__getitem__(self, k)


def _q(sql):
    # Convertit les marqueurs ? (SQLite) en %s (PostgreSQL).
    return sql.replace("?", "%s")


def _pg_dsn():
    dsn = DATABASE_URL
    if "sslmode=" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = dsn + sep + "sslmode=require"
    return dsn


class PGCursor:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def fetchone(self):
        r = self._cur.fetchone()
        return None if r is None else Row(r)

    def fetchall(self):
        return [Row(r) for r in self._cur.fetchall()]


class PGConn:
    def __init__(self):
        self._conn = psycopg2.connect(_pg_dsn())

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(_q(sql), params)
        return PGCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


class SQLiteConn:
    def __init__(self):
        self._conn = sqlite3.connect(DB_PATH)
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        self._conn.close()


def db():
    global _PG_FALLBACK, _PG_ERROR
    if DATABASE_URL and HAS_PG and not _PG_FALLBACK:
        try:
            return PGConn()
        except Exception as e:
            _PG_FALLBACK = True
            _PG_ERROR = str(e)[:300]
            log(f"PostgreSQL indisponible, repli SQLite: {_PG_ERROR}")
    return SQLiteConn()

def hash_pw(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt + ":" + h

def check_pw(password, stored):
    salt, h = stored.split(":", 1)
    return hash_pw(password, salt) == stored

# ---------------- INIT DB ----------------
# Schéma PostgreSQL (timestamps en BIGINT pour les millisecondes).
SCHEMA_PG = [
    "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT, password TEXT NOT NULL, balance_cents INTEGER NOT NULL DEFAULT 0, total_earned_cents INTEGER NOT NULL DEFAULT 0, is_admin INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0, created_at BIGINT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS offers (id SERIAL PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL, reward_cents INTEGER NOT NULL, duration_seconds INTEGER DEFAULT 0, description TEXT DEFAULT '', color TEXT DEFAULT '#6366f1', link TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1)",
    "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at BIGINT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS video_views (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, completed_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS ptc_clicks (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, clicked_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS survey_answers (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, survey_id INTEGER NOT NULL, answered_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS bonuses (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, claimed_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS wheel_spins (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, spun_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS faucet_claims (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, claimed_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS game_plays (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, game TEXT NOT NULL, played_at BIGINT NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS transactions (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, label TEXT NOT NULL, created_at BIGINT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS withdrawals (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL, method TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at BIGINT NOT NULL)",
]

SCHEMA_SQLITE = [
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT, password TEXT NOT NULL, balance_cents INTEGER NOT NULL DEFAULT 0, total_earned_cents INTEGER NOT NULL DEFAULT 0, is_admin INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS offers (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, type TEXT NOT NULL, reward_cents INTEGER NOT NULL, duration_seconds INTEGER DEFAULT 0, description TEXT DEFAULT '', color TEXT DEFAULT '#6366f1', link TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1)",
    "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS video_views (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, completed_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS ptc_clicks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, clicked_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS survey_answers (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, survey_id INTEGER NOT NULL, answered_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS bonuses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, claimed_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS wheel_spins (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, spun_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS faucet_claims (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, claimed_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS game_plays (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, game TEXT NOT NULL, played_at INTEGER NOT NULL, reward_cents INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, label TEXT NOT NULL, created_at INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL, method TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL)",
]


def init_db():
    conn = db()
    if isinstance(conn, PGConn):
        schema = SCHEMA_PG
    else:
        schema = SCHEMA_SQLITE
    for stmt in schema:
        conn.execute(stmt)
    conn.commit()

    # migration ancienne base SQLite : ajout colonne link si absente
    if not isinstance(conn, PGConn):
        try:
            conn.execute("ALTER TABLE offers ADD COLUMN link TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

    # ---- seed admin ----
    if conn.execute("SELECT COUNT(*) FROM users WHERE username='admin'").fetchone()[0] == 0:
        conn.execute("INSERT INTO users(username,email,password,balance_cents,is_admin,created_at) VALUES(?,?,?,?,?,?)",
                     ("admin", "admin@robinet-euro.fr", hash_pw("Robinet974"), 0, 1, now_ms()))
        conn.commit()

    # ---- seed offers ----
    if conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 0:
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
            conn.execute("INSERT INTO offers(title,type,reward_cents,duration_seconds,description,color) VALUES(?,?,?,?,?,?)", o)
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

# ---------------- HANDLERS ----------------
def handle_api(conn, path, method, body, token):
    parts = path.strip("/").split("/")
    # parts ex: ['api','login']
    if len(parts) < 2:
        return 404, {"error": "Not found"}

    endpoint = parts[1]

    if endpoint == "health" and method == "GET":
        using_pg = bool(DATABASE_URL and HAS_PG and not _PG_FALLBACK)
        return 200, {"db": "postgresql" if using_pg else "sqlite",
                     "error": _PG_ERROR if _PG_FALLBACK else ""}

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
            cur = conn.execute("INSERT INTO users(username,email,password,created_at) VALUES(?,?,?,?) RETURNING id",
                               (username, email, hash_pw(password), now_ms()))
            uid = cur.fetchone()[0]
            conn.commit()
            # bonus de bienvenue
            conn.execute("UPDATE users SET balance_cents=balance_cents+5, total_earned_cents=total_earned_cents+5 WHERE id=?", (uid,))
            add_transaction(conn, uid, "earn", 5, "Bonus de bienvenue")
            conn.commit()
            tok = secrets.token_hex(24)
            conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (tok, uid, now_ms()))
            conn.commit()
            return 200, {"token": tok, "message": "Compte créé ! +0,05 € offert."}
        except UNIQUE_ERRORS:
            conn.rollback()
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
            return 400, {"error": f"Le retrait minimum est de 2,00 € (tu as demandé {cents_to_str(amount)} €)."}
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
                 "png": "image/png", "jpg": "image/jpeg", "ico": "image/x-icon"}.get(ext.lstrip("."), "application/octet-stream")
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    init_db()
    log(f"Démarrage sur 0.0.0.0:{PORT}")
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
