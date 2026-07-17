"""
Downloader<3 — Premium-Checkout Backend
=========================================
Nimmt Zahlungen über PayPal entgegen, erzeugt danach einen einmaligen
Aktivierungscode und speichert ihn in einer kleinen lokalen Datenbank
(SQLite). Die Downloader<3-App fragt diesen Server, wenn jemand einen
Code einlöst.

WICHTIG — das musst du selbst einrichten:
1. Ein PayPal-Entwicklerkonto erstellen: https://developer.paypal.com
2. Dort eine "App" anlegen -> du bekommst CLIENT_ID und CLIENT_SECRET
3. Diese als Umgebungsvariablen setzen (siehe README.md), NIEMALS im Code
   fest eintragen und NIEMALS die .env-Datei mit hochladen/teilen.
4. Diesen Server irgendwo hosten (z. B. render.com, kostenlos) — siehe
   README.md für eine Schritt-für-Schritt-Anleitung.
"""

import os
import re
import json
import base64
import socket
import sqlite3
import secrets
import datetime
import smtplib
from email.mime.text import MIMEText
import urllib.request
import urllib.error
import http.cookiejar
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Konfiguration über Umgebungsvariablen (NIE Zugangsdaten hier eintragen!) ---
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")  # "sandbox" oder "live"
PAYPAL_BASE = ("https://api-m.paypal.com" if PAYPAL_MODE == "live"
              else "https://api-m.sandbox.paypal.com")

# 👑 Owner-Login: das ECHTE Passwort steht NUR hier als Umgebungsvariable,
# niemals im main.py der App (die App wird öffentlich verteilt, dieser
# Server nicht — nur du hast Zugriff auf die Render-Umgebungsvariablen).
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")
OWNER_EMAILS = {"felixwerther1@gmail.com", "lisa.werther@proton.me"}

# 📧 E-Mail-Versand: genau dasselbe Prinzip — die App fragt diesen Server,
# der Server verschickt die E-Mail mit SEINEN eigenen (nur hier
# hinterlegten) SMTP-Zugangsdaten. Kein Passwort im verteilten Code.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587").strip())
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER).strip()
# 🐛 KERN-FIX ("Network unreachable" bei E-Mails): Render BLOCKIERT im
# kostenlosen Tarif ALLE ausgehenden SMTP-Verbindungen (Ports 25/465/587,
# als Spam-Schutz — offiziell dokumentiert). Direkter SMTP-Versand von
# diesem Server kann dort also NIE funktionieren, egal ob IPv4 oder IPv6
# — genau daher kam die Meldung. Lösung: Versand über eine HTTPS-E-Mail-
# API (Port 443 ist nie blockiert). Brevo ist kostenlos (300 Mails/Tag)
# und braucht keine eigene Domain — Einrichtung siehe README in diesem
# Ordner. Ist BREVO_API_KEY gesetzt, läuft ALLER Versand darüber;
# ansonsten wird wie bisher SMTP versucht (funktioniert auf Hostern,
# die SMTP nicht blockieren).
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
BREVO_FROM_NAME = os.environ.get("BREVO_FROM_NAME", "Downloader<3").strip()
_email_attempts = {}  # einfacher Schutz gegen Missbrauch/Spam

# 🎨 KI-Studio: EIN gemeinsamer Gemini-API-Schlüssel für ALLE Nutzer der
# App — steht NUR hier als Umgebungsvariable, nie im verteilten Code.
# WICHTIG: Da alle Nutzer denselben Schlüssel teilen, trägst DU (der
# Owner) die Kosten dafür — die Rate-Begrenzung unten schützt vor Missbrauch,
# ersetzt aber keine Kostenkontrolle bei sehr vielen Nutzern.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_ai_attempts = {}  # Missbrauchsschutz: begrenzt Anfragen pro E-Mail

# 🎧 Musik-Download (Spotify/Apple Music/Amazon Music): Spotify streamt
# DRM-verschlüsselt — wir laden dort NICHTS direkt herunter, sondern
# lesen nur die ÖFFENTLICHEN Metadaten (Songtitel + Künstler) über
# Spotifys offizielle Web-API aus (Client-Credentials-Flow, braucht
# KEIN Nutzer-Login, nur eine kostenlose App-Registrierung). Die App
# sucht den Song danach selbst ganz normal auf YouTube. Kostenlose
# Einrichtung: https://developer.spotify.com/dashboard -> "Create app"
# -> Client ID + Client Secret hier als Umgebungsvariablen eintragen.
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
_spotify_token_cache = {"token": None, "expires": None}
# 🐛 FIX ("Playlist-Download: Couldn't fetch song info: HTTP Error 403:
# Forbidden"): Seit einer Spotify-API-Richtlinienänderung (Ende 2024)
# blockiert der normale App-Zugangs-Token (Client-Credentials-Flow) den
# Zugriff auf den Song-Inhalt von Spotify-EIGENEN, algorithmischen
# Playlists (z. B. "Discover Weekly", "Release Radar", "Today's Top
# Hits" — deren Link-IDs immer mit "37i9dQZF1" beginnen, genau wie die
# gemeldete Playlist) — unabhängig davon, wie die eigene App
# registriert ist, das betrifft ALLE Entwickler gleichermaßen. Normale,
# selbst erstellte Nutzer-Playlists sind davon NICHT betroffen und
# funktionierten schon vorher. Als Ausweg wird jetzt zusätzlich der
# GLEICHE anonyme, kurzlebige Zugangs-Token verwendet, den die echte
# open.spotify.com-Webseite selbst für nicht eingeloggte Besucher nutzt,
# um genau diese Playlists im Browser anzuzeigen — technisch dasselbe,
# öffentlich einsehbare Ergebnis, nur über einen anderen, nicht davon
# betroffenen Zugangsweg. Weiterhin werden dabei ausschließlich
# öffentliche Songtitel/Künstler-Infos gelesen, kein Audio, keine
# geschützten Inhalte, kein DRM-Umgehen.
_spotify_anon_token_cache = {"token": None, "expires": None}
_music_attempts = {}  # Missbrauchsschutz: begrenzt Anfragen pro IP/Stunde

# Verfügbare Pakete: Preis in EUR + wie viele Tage Premium es gibt
# ("forever" = unbegrenzt). Passe Preise/Namen hier nach Belieben an.
PLANS = {
    "30days": {"price": "2.99", "days": 30, "label": "30 Tage Premium"},
    "365days": {"price": "19.99", "days": 365, "label": "1 Jahr Premium"},
    "forever": {"price": "39.99", "days": None, "label": "Premium für immer"},
}

DB_PATH = os.path.join(os.path.dirname(__file__), "codes.db")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS codes (
        code TEXT PRIMARY KEY,
        days INTEGER,
        order_id TEXT,
        plan TEXT,
        created_at TEXT,
        redeemed_at TEXT
    )""")
    # 🌍 Konten: Premium-Status hängt hier an der E-Mail-Adresse, nicht an
    # einem einzelnen Gerät — bleibt so über PC-Wechsel/Neuinstallation
    # hinweg erhalten. premium_until: ISO-Datum, "forever", oder NULL.
    conn.execute("""CREATE TABLE IF NOT EXISTS accounts (
        email TEXT PRIMARY KEY,
        premium_until TEXT,
        updated_at TEXT,
        first_seen TEXT,
        last_seen TEXT
    )""")
    # Migration für bereits bestehende Datenbanken ohne diese Spalten
    # 🤝 role: NULL/"" = normaler Nutzer, "helper" = Helfer-Rang (siehe
    # unten). last_helper_code_at: wann ein Helper zuletzt einen eigenen
    # Gutscheincode erstellt hat — für die 2-Wochen-Abklingzeit, serverseitig
    # geprüft (nicht nur lokal in der App), damit sie weltweit gilt und
    # sich nicht durch Neuinstallation umgehen lässt.
    # 🌍 password_hash: NEU — macht Konten server-seitig
    # authentifizierbar (siehe /api/account-register, /api/account-login
    # weiter unten), damit ein Konto von JEDEM Gerät aus nutzbar ist und
    # nicht mehr verloren geht, nur weil die lokalen App-Daten fehlen
    # (Neuinstallation, App-Update, neues Gerät o. Ä.). Enthält NIE das
    # Klartext-Passwort — nur den bereits in der App gehashten Wert
    # (SHA-256, exakt wie zuvor schon lokal gespeichert).
    # 🤝 Ehrentafel: Helfer können sich im Helfer-Tab der App freiwillig
    # (Opt-in) dafür entscheiden, mit einem selbst gewählten Anzeigenamen
    # (NICHT der echten E-Mail-Adresse) auf der Landingpage genannt zu
    # werden — helper_public_optin "1"/"0", helper_public_name ist frei
    # wählbar und komplett getrennt vom privaten In-App-Namen.
    for col in ("first_seen", "last_seen", "role", "last_helper_code_at",
                "password_hash", "helper_public_name",
                "helper_public_optin"):
        try:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # Spalte existiert schon
    # ☁️ Komplette Sicherung (Einstellungen, Verlauf, Favoriten, Abos) pro
    # E-Mail-Adresse — für "alles synchronisieren" zwischen Geräten.
    conn.execute("""CREATE TABLE IF NOT EXISTS user_backups (
        email TEXT PRIMARY KEY,
        data TEXT,
        updated_at TEXT
    )""")
    return conn


def _touch_account(email):
    """📇 Merkt sich, dass diese E-Mail die App benutzt (auch ohne
    Premium) — damit der Owner eine Liste aller weltweiten Nutzer sehen
    kann, nicht nur die, die er zufällig schon kennt."""
    email = (email or "").strip().lower()
    if not email:
        return
    conn = db()
    now = datetime.datetime.now().isoformat()
    row = conn.execute(
        "SELECT first_seen FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    if row:
        conn.execute("UPDATE accounts SET last_seen = ? WHERE email = ?",
                    (now, email))
    else:
        conn.execute(
            "INSERT INTO accounts (email, premium_until, updated_at, "
            "first_seen, last_seen) VALUES (?, NULL, ?, ?, ?)",
            (email, now, now, now))
    conn.commit()
    conn.close()


def _upsert_premium(email, premium_until):
    """Setzt/verlängert den Premium-Status einer E-Mail-Adresse — nimmt
    dabei immer den GRÜNZÜGIGEREN Stand (nie versehentlich verkürzen)."""
    email = (email or "").strip().lower()
    if not email:
        return
    conn = db()
    row = conn.execute(
        "SELECT premium_until FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    current = row[0] if row else None

    def _later(a, b):
        if a == "forever" or b == "forever":
            return "forever"
        if not a:
            return b
        if not b:
            return a
        return max(a, b)  # ISO-Daten lassen sich als Strings vergleichen

    new_value = _later(current, premium_until)
    conn.execute(
        "INSERT INTO accounts (email, premium_until, updated_at) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(email) DO UPDATE SET premium_until=excluded.premium_until, "
        "updated_at=excluded.updated_at",
        (email, new_value, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()


def _get_role(email):
    """🤝 Liest den aktuellen Rang (z. B. "helper") einer E-Mail-Adresse
    aus der weltweiten Konten-Datenbank — leerer/​None-Wert = normaler
    Nutzer."""
    email = (email or "").strip().lower()
    if not email:
        return None
    conn = db()
    row = conn.execute(
        "SELECT role FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return (row[0] or None) if row else None


def _set_role(email, role):
    """🤝 Setzt/entfernt den Rang einer E-Mail-Adresse weltweit (legt das
    Konto an, falls es noch gar nicht existiert — z. B. wenn der Owner
    jemanden befördert, der die App noch nie geöffnet hat)."""
    email = (email or "").strip().lower()
    if not email:
        return
    conn = db()
    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO accounts (email, premium_until, updated_at, "
        "first_seen, last_seen, role) VALUES (?, NULL, ?, ?, ?, ?) "
        "ON CONFLICT(email) DO UPDATE SET role=excluded.role, "
        "updated_at=excluded.updated_at",
        (email, now, now, now, role))
    conn.commit()
    conn.close()


def paypal_token():
    """Holt ein OAuth2-Zugangstoken von PayPal."""
    req = urllib.request.Request(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        method="POST",
    )
    import base64
    auth = base64.b64encode(
        f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def paypal_request(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{PAYPAL_BASE}{path}", data=data,
                                 method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def make_code() -> str:
    return "DL-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper()


@app.after_request
def add_cors(resp):
    # Erlaubt Anfragen von der Checkout-Webseite (im Browser) und der App.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.route("/api/plans", methods=["GET"])
def get_plans():
    """Zeigt der Webseite, welche Pakete/Preise es gibt."""
    return jsonify(PLANS)


@app.route("/api/create-order", methods=["POST", "OPTIONS"])
def create_order():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    plan_key = data.get("plan")
    plan = PLANS.get(plan_key)
    if not plan:
        return jsonify({"error": "unknown plan"}), 400

    token = paypal_token()
    order = paypal_request("POST", "/v2/checkout/orders", token, {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "EUR", "value": plan["price"]},
            "description": f"Downloader<3 — {plan['label']}",
        }],
    })
    return jsonify({"id": order["id"]})


@app.route("/api/capture-order", methods=["POST", "OPTIONS"])
def capture_order():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    order_id = data.get("orderID")
    plan_key = data.get("plan")
    email = (data.get("email") or "").strip().lower()
    plan = PLANS.get(plan_key)
    if not order_id or not plan:
        return jsonify({"error": "missing orderID/plan"}), 400

    token = paypal_token()
    result = paypal_request(
        "POST", f"/v2/checkout/orders/{order_id}/capture", token, {})

    status = result.get("status")
    if status != "COMPLETED":
        return jsonify({"ok": False, "error": "payment not completed"}), 402

    code = make_code()
    conn = db()
    conn.execute(
        "INSERT INTO codes (code, days, order_id, plan, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, plan["days"], order_id, plan_key,
         datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # 🌍 Premium zusätzlich direkt an die E-Mail-Adresse binden (falls
    # angegeben) — bleibt so über jedes Gerät/jede Neuinstallation hinweg
    # erhalten, unabhängig vom Einlöse-Code.
    if email:
        if plan["days"] is None:
            premium_until = "forever"
        else:
            until_date = (datetime.datetime.now()
                          + datetime.timedelta(days=plan["days"]))
            premium_until = until_date.date().isoformat()
        _upsert_premium(email, premium_until)

    return jsonify({"ok": True, "code": code, "days": plan["days"]})


@app.route("/api/redeem", methods=["GET"])
def redeem():
    """Wird von der Downloader<3-App aufgerufen, wenn jemand einen Code
    einlöst. Ein Code funktioniert nur EINMAL."""
    code = (request.args.get("code") or "").strip().upper()
    email = (request.args.get("email") or "").strip().lower()
    if not code:
        return jsonify({"ok": False, "error": "no code"}), 400

    conn = db()
    row = conn.execute(
        "SELECT days, redeemed_at FROM codes WHERE code = ?", (code,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "invalid code"})
    days, redeemed_at = row
    if redeemed_at:
        conn.close()
        return jsonify({"ok": False, "error": "already redeemed"})

    conn.execute("UPDATE codes SET redeemed_at = ? WHERE code = ?",
                (datetime.datetime.now().isoformat(), code))
    conn.commit()
    conn.close()

    # 🌍 Auch bei Admin-vergebenen Geschenk-Codes: Premium zusätzlich am
    # Konto festmachen (falls eine E-Mail mitgeschickt wurde), damit es
    # überall erhalten bleibt, nicht nur auf diesem einen Gerät.
    if email:
        if days is None:
            premium_until = "forever"
        else:
            until_date = datetime.datetime.now() + datetime.timedelta(days=days)
            premium_until = until_date.date().isoformat()
        _upsert_premium(email, premium_until)

    return jsonify({"ok": True, "days": days})


@app.route("/api/account-status", methods=["GET"])
def account_status():
    """🌍 Prüft den Premium-Status einer E-Mail-Adresse — so kann jedes
    Gerät (auch nach Neuinstallation) automatisch erkennen, dass ein
    Konto bereits Premium hat, ohne den Code erneut einzulösen."""
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"premium_until": None})
    _touch_account(email)  # merkt sich: diese E-Mail nutzt die App
    conn = db()
    row = conn.execute(
        "SELECT premium_until, role, helper_public_name, "
        "helper_public_optin FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return jsonify({"premium_until": row[0] if row else None,
                    "role": (row[1] if row else None) or None,
                    "helper_public_name": (row[2] if row else None) or "",
                    "helper_public_optin": bool(row and row[3] == "1")})


_account_attempts = {}  # Missbrauchsschutz für Login/Registrierung pro E-Mail


def _rate_check(email, max_attempts=10, window=600):
    """Einfacher Schutz gegen Brute-Force auf /account-login und
    /account-register — max. `max_attempts` Versuche pro E-Mail innerhalb
    von `window` Sekunden (In-Memory, wie die anderen Limiter hier)."""
    now = datetime.datetime.now()
    attempts = [t for t in _account_attempts.get(email, [])
               if (now - t).total_seconds() < window]
    limited = len(attempts) >= max_attempts
    attempts.append(now)
    _account_attempts[email] = attempts
    return limited


@app.route("/api/account-register", methods=["POST", "OPTIONS"])
def account_register():
    """🌍 KERN-FIX: registriert eine E-Mail+Passwort-Kombination
    SERVERSEITIG, statt nur lokal auf dem Gerät. Vorher waren Konten rein
    lokal (pro Gerät) gespeichert — nach einer Neuinstallation, einem
    App-Update, das die lokalen Daten zurücksetzte, oder auf einem
    zweiten Gerät "verschwand" das Konto scheinbar, obwohl es in der
    weltweiten Nutzerliste (Owner-Admin) längst auftauchte. Jetzt prüft
    die Registrierung zuerst hier: ist die E-Mail server-seitig schon mit
    einem Passwort belegt, schlägt die Registrierung ab ("exists") —
    andernfalls wird sie hier hinterlegt und ist ab sofort von JEDEM
    Gerät aus nutzbar. Das Passwort selbst verlässt das Gerät nie im
    Klartext, nur der (bereits in der App erzeugte) SHA-256-Hash wird
    hier gespeichert und verglichen."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    pw_hash = (data.get("password_hash") or "").strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid email"}), 400
    if not pw_hash:
        return jsonify({"ok": False, "error": "missing password_hash"}), 400
    if _rate_check(email, max_attempts=10, window=600):
        return jsonify({"ok": False, "error": "too many attempts"}), 429

    conn = db()
    row = conn.execute(
        "SELECT password_hash FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    if row and row[0]:
        conn.close()
        return jsonify({"ok": False, "error": "exists"}), 409

    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO accounts (email, premium_until, updated_at, "
        "first_seen, last_seen, password_hash) "
        "VALUES (?, NULL, ?, ?, ?, ?) "
        "ON CONFLICT(email) DO UPDATE SET "
        "password_hash=excluded.password_hash, "
        "updated_at=excluded.updated_at, last_seen=excluded.last_seen",
        (email, now, now, now, pw_hash))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/account-login", methods=["POST", "OPTIONS"])
def account_login():
    """🌍 Prüft E-Mail+Passwort GEGEN DEN SERVER (statt nur lokal) — so
    kann sich jeder von JEDEM Gerät aus einloggen, auch wenn die lokalen
    App-Daten fehlen (neues Gerät, Neuinstallation, App-Update, o. Ä.).
    Meldet bewusst nur zwei mögliche Fehler zurück ("no_account" /
    "wrong_password"), damit die App darauf reagieren kann — die
    eigentliche Anzeige in der App bleibt trotzdem generisch ("E-Mail
    oder Passwort ist falsch"), um nicht zu verraten, ob eine E-Mail
    überhaupt existiert."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    pw_hash = (data.get("password_hash") or "").strip()
    if not email or not pw_hash:
        return jsonify({"ok": False, "error": "invalid request"}), 400
    if _rate_check(email, max_attempts=15, window=600):
        return jsonify({"ok": False, "error": "too many attempts"}), 429

    conn = db()
    row = conn.execute(
        "SELECT password_hash, premium_until, role FROM accounts "
        "WHERE email = ?", (email,)).fetchone()
    if not row or not row[0]:
        conn.close()
        return jsonify({"ok": False, "error": "no_account"}), 404
    if row[0] != pw_hash:
        conn.close()
        return jsonify({"ok": False, "error": "wrong_password"}), 401
    now = datetime.datetime.now().isoformat()
    conn.execute("UPDATE accounts SET last_seen = ? WHERE email = ?",
                (now, email))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "premium_until": row[1], "role": row[2]})


_owner_attempts = {}  # simple In-Memory-Schutz gegen wiederholtes Ausprobieren


@app.route("/api/verify-owner", methods=["POST", "OPTIONS"])
def verify_owner():
    """👑 Prüft ein Owner-Login. Das echte Passwort steckt nur in der
    Umgebungsvariable OWNER_PASSWORD auf diesem Server — steht NIRGENDS
    im main.py der App, die öffentlich verteilt wird."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # Einfacher Schutz: max. 5 Versuche pro E-Mail alle 10 Minuten
    now = datetime.datetime.now()
    attempts = [t for t in _owner_attempts.get(email, [])
               if (now - t).total_seconds() < 600]
    if len(attempts) >= 5:
        return jsonify({"ok": False, "error": "too many attempts"}), 429
    attempts.append(now)
    _owner_attempts[email] = attempts

    if email not in OWNER_EMAILS:
        return jsonify({"ok": False}), 403
    if not OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "not configured"}), 503
    if password == OWNER_PASSWORD:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401


# 🐛 FIX ("Net unreachable" bei E-Mail-Versand): Hoster wie Render haben
# nach außen oft KEIN funktionierendes IPv6, aber smtp.gmail.com (und
# viele andere SMTP-Server) haben sowohl eine IPv4- als auch eine
# IPv6-Adresse. Pythons Standard-smtplib probiert je nach Auflösung
# manchmal zuerst IPv6 -> die ist von dort aus nicht erreichbar ->
# genau die Meldung "Network is unreachable". Diese zwei Klassen
# zwingen die Verbindung gezielt auf IPv4, der Zertifikats-Check beim
# TLS-Handshake bleibt dabei unverändert korrekt (server_hostname wird
# weiterhin auf den echten Hostnamen gesetzt, nur die IP-Adresse für
# die eigentliche Socket-Verbindung wird auf IPv4 festgelegt).
def _ipv4_connect(host, port, timeout):
    infos = socket.getaddrinfo(host, port, socket.AF_INET,
                               socket.SOCK_STREAM)
    ip = infos[0][4][0]
    return socket.create_connection((ip, port), timeout=timeout)


class _IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _ipv4_connect(host, port, timeout)


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        sock = _ipv4_connect(host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=self._host)


def _email_configured():
    """E-Mail-Versand ist eingerichtet, wenn ENTWEDER der Brevo-Schlüssel
    (+ Absender-Adresse) ODER klassische SMTP-Zugangsdaten da sind."""
    if BREVO_API_KEY and (SMTP_FROM or SMTP_USER):
        return True
    return bool(SMTP_USER and SMTP_PASSWORD)


def _smtp_send_raw(to_addr, subject, body, attachment=None):
    """Klassischer SMTP-Versand (funktioniert NICHT auf Render Free —
    dort sind die SMTP-Ports gesperrt, siehe Kommentar bei BREVO_API_KEY).
    `attachment` (optional): {"name": str, "content_b64": str}."""
    if attachment:
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders
        msg = MIMEMultipart()
        msg.attach(MIMEText(body))
        part = MIMEBase("application", "octet-stream")
        part.set_payload(base64.b64decode(attachment["content_b64"]))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f'attachment; filename="{attachment["name"]}"')
        msg.attach(part)
    else:
        msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    if SMTP_PORT == 465:
        server = _IPv4SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
    else:
        server = _IPv4SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(SMTP_FROM, [to_addr], msg.as_string())
    server.quit()


def _brevo_send(to_addr, subject, body, attachment=None):
    """📧 Versand über die Brevo-HTTPS-API (Port 443 — funktioniert auch
    auf Render Free, wo SMTP-Ports gesperrt sind). Wirft Exception bei
    Fehlern. `attachment` (optional): {"name": str, "content_b64": str}
    -- Brevo nimmt Anhänge direkt als Base64 im JSON-Payload entgegen."""
    import urllib.request
    payload = {
        "sender": {"email": SMTP_FROM or SMTP_USER,
                   "name": BREVO_FROM_NAME},
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": body,
    }
    if attachment:
        payload["attachment"] = [{
            "content": attachment["content_b64"],
            "name": attachment["name"],
        }]
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json",
                 "api-key": BREVO_API_KEY,
                 "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status not in (200, 201, 202):
            raise RuntimeError(f"Brevo HTTP {r.status}")


def _smtp_send(to_addr, subject, body, attachment=None):
    """Zentraler E-Mail-Versand: Brevo-HTTPS-API zuerst (falls Schlüssel
    gesetzt — der Weg, der auf Render Free wirklich funktioniert),
    sonst klassisches SMTP. Name bleibt _smtp_send, damit alle
    bestehenden Aufrufer unverändert funktionieren. `attachment`
    (optional): {"name": str, "content_b64": str}."""
    if BREVO_API_KEY:
        # Wenn ein Brevo-Schlüssel gesetzt ist, NIE auf klassisches SMTP
        # zurückfallen — SMTP ist auf Render Free eh gesperrt und würde
        # nur ewig hängen (-> "timeout" in der App statt einer echten
        # Fehlermeldung). Stattdessen den echten Brevo-Fehler sofort
        # durchreichen, damit man sieht, was wirklich los ist (z.B.
        # "Absender nicht verifiziert").
        try:
            _brevo_send(to_addr, subject, body, attachment)
            return
        except Exception as e:
            raise RuntimeError(f"Brevo-Versand fehlgeschlagen: {e}")
    try:
        _smtp_send_raw(to_addr, subject, body, attachment)
    except OSError as e:
        if "unreachable" in str(e).lower():
            # Der bekannte Render-Fall — dem Owner eine Meldung geben,
            # die direkt sagt, was zu tun ist.
            raise RuntimeError(
                "SMTP ist auf diesem Hoster gesperrt (Render Free "
                "blockiert Ports 25/465/587). Lösung: kostenlosen "
                "BREVO_API_KEY als Umgebungsvariable setzen — Anleitung "
                "in premium-backend/README.md.")
        raise


@app.route("/api/send-code", methods=["POST", "OPTIONS"])
def send_code():
    """📧 Verschickt eine Verifizierungs-E-Mail über die EIGENEN
    SMTP-Zugangsdaten dieses Servers. Die App selbst kennt kein Passwort —
    sie schickt nur E-Mail-Adresse + Code hierher."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    to_addr = (data.get("to") or "").strip()
    code = (data.get("code") or "").strip()
    subject = data.get("subject") or "Your verification code is {code}"
    body = data.get("body") or "Your code: {code}"

    if "@" not in to_addr or "." not in to_addr.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid email"}), 400
    if not code or len(code) > 12:
        return jsonify({"ok": False, "error": "invalid code"}), 400

    # 🐛 FIX ("rate limited" bei normaler Nutzung): Das Limit lag bisher
    # bei nur 5 E-Mails pro Adresse UND STUNDE — das reicht schon bei
    # ganz normalem Testen/mehrfachem Ein-/Ausloggen oder wenn ein Code
    # abläuft und neu angefordert wird locker aus, ohne dass irgendwer
    # etwas missbraucht hat. Jetzt: nur noch ein KURZER Mindestabstand
    # zwischen zwei Anfragen an dieselbe Adresse (verhindert Doppelklick-
    # Spam/Skripte), plus ein deutlich großzügigeres Stunden-Limit als
    # zweite Absicherung — greift bei normaler Nutzung praktisch nie.
    now = datetime.datetime.now()
    attempts = [t for t in _email_attempts.get(to_addr, [])
               if (now - t).total_seconds() < 3600]
    if attempts and (now - attempts[-1]).total_seconds() < 20:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    if len(attempts) >= 30:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    attempts.append(now)
    _email_attempts[to_addr] = attempts

    # Konfiguriert = Brevo-Schlüssel ODER klassische SMTP-Zugangsdaten
    if not _email_configured():
        return jsonify({"ok": False, "error": "email not configured"}), 503

    try:
        subject = subject.replace("{code}", code)
        body = body.replace("{code}", code)
        _smtp_send(to_addr, subject, body)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


_contact_attempts = {}  # Missbrauchsschutz: begrenzt Kontakt-Nachrichten pro Absender


@app.route("/api/contact-owner", methods=["POST", "OPTIONS"])
def contact_owner():
    """✉️ Schickt eine Nachricht aus der App an BEIDE Owner per E-Mail —
    über die SERVER-eigenen Zugangsdaten (Brevo/SMTP), NICHT über
    irgendwelche lokalen Einstellungen auf dem Gerät der schreibenden
    Person (die hat ja normalerweise gar kein eigenes SMTP eingerichtet
    — nur der Owner selbst). Genau DAS war der Grund, warum das
    'Probleme/Feedback'- und das neue Helfer-Kontaktformular vorher nur
    auf dem PC des Owners funktionierten, weltweit aber sonst nirgends
    — jetzt läuft der Versand zentral über diesen Server, für jede
    Person überall."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    sender = (data.get("email") or "").strip().lower()
    message = (data.get("message") or "").strip()
    context = (data.get("context") or "contact").strip()[:40]

    if not message:
        return jsonify({"ok": False, "error": "empty message"}), 400
    if len(message) > 4000:
        return jsonify({"ok": False, "error": "message too long"}), 400

    now = datetime.datetime.now()
    key = sender or "anon"
    attempts = [t for t in _contact_attempts.get(key, [])
               if (now - t).total_seconds() < 3600]
    if attempts and (now - attempts[-1]).total_seconds() < 15:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    if len(attempts) >= 10:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    attempts.append(now)
    _contact_attempts[key] = attempts

    if not _email_configured():
        return jsonify({"ok": False, "error": "email not configured"}), 503

    subject = f"Downloader<3 — {context}: Nachricht von {sender or 'anonym'}"
    body = f"Von: {sender or 'anonym'}\nBereich: {context}\n\n{message}"

    any_ok = False
    last_error = None
    for owner in OWNER_EMAILS:
        try:
            _smtp_send(owner, subject, body)
            any_ok = True
        except Exception as e:
            last_error = str(e)
    if any_ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": last_error or "send failed"}), 500


# 🐛 WICHTIG: E-Mail-Anhänge haben ÜBERALL (Gmail, Outlook, Brevo, jeder
# SMTP-Server) eine harte Größengrenze — meist irgendwo zwischen 10 und
# 25 MB, je nach Anbieter. Das ist kein Limit dieser App, sondern eine
# technische Grenze von E-Mail selbst. Deshalb: kleine Dateien gehen als
# echter Anhang raus (SMALL_ATTACH_LIMIT, bewusst konservativ gewählt,
# damit Base64-Overhead + JSON nirgends anecken), alles Größere schickt
# die App stattdessen als Download-LINK (Datei wird vom Gerät des
# Nutzers direkt zu einem Datei-Hoster hochgeladen, siehe main.py) --
# so "klappt" der Versand am Ende wirklich für jede Dateigröße, nur eben
# nicht immer als klassischer Anhang.
SMALL_ATTACH_LIMIT = 6 * 1024 * 1024  # 6 MB Rohdatei (~8.2 MB Base64)
_file_send_attempts = {}  # Missbrauchsschutz pro Absender


def _file_send_rate_limited(sender):
    now = datetime.datetime.now()
    key = sender or "anon"
    attempts = [t for t in _file_send_attempts.get(key, [])
               if (now - t).total_seconds() < 3600]
    if attempts and (now - attempts[-1]).total_seconds() < 10:
        return True
    if len(attempts) >= 20:
        return True
    attempts.append(now)
    _file_send_attempts[key] = attempts
    return False


@app.route("/api/send-file", methods=["POST", "OPTIONS"])
def send_file():
    """📤 Verschickt eine kleine Datei (<= SMALL_ATTACH_LIMIT) als
    ECHTEN E-Mail-Anhang an eine beliebige Adresse. Für größere Dateien
    nutzt die App stattdessen /api/send-file-link (siehe dort/main.py)."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    sender = (data.get("from_email") or "").strip().lower()
    to_addr = (data.get("to") or "").strip()
    message = (data.get("message") or "").strip()[:2000]
    filename = (data.get("filename") or "datei").strip()[:120]
    content_b64 = data.get("content_b64") or ""

    if "@" not in to_addr or "." not in to_addr.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid recipient"}), 400
    if not content_b64:
        return jsonify({"ok": False, "error": "missing file"}), 400
    # Base64 ist ca. 4/3 der Rohgröße -- grobe Vorab-Prüfung ohne alles
    # zu dekodieren.
    if len(content_b64) > SMALL_ATTACH_LIMIT * 4 // 3 + 1024:
        return jsonify({"ok": False, "error": "file too large"}), 413
    if _file_send_rate_limited(sender):
        return jsonify({"ok": False, "error": "rate limited"}), 429
    if not _email_configured():
        return jsonify({"ok": False, "error": "email not configured"}), 503

    subject = f"📎 {sender or 'Jemand'} hat dir eine Datei über Downloader<3 geschickt"
    body = (
        f"Hey!\n\n{sender or 'Jemand'} hat dir über die Downloader<3-App "
        f"eine Datei geschickt: {filename}\n"
        + (f"\nNachricht:\n{message}\n" if message else "")
        + "\nDie Datei hängt an dieser E-Mail an. 💜"
    )
    try:
        _smtp_send(to_addr, subject, body,
                  attachment={"name": filename, "content_b64": content_b64})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/send-file-link", methods=["POST", "OPTIONS"])
def send_file_link():
    """📤 Für Dateien, die für einen normalen E-Mail-Anhang zu groß sind:
    die App lädt die Datei vorher selbst zu einem Datei-Hoster hoch
    (client-seitig, siehe main.py) und schickt hier nur noch eine
    E-Mail mit dem fertigen Download-Link -- funktioniert dadurch
    unabhängig von der Dateigröße."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    sender = (data.get("from_email") or "").strip().lower()
    to_addr = (data.get("to") or "").strip()
    message = (data.get("message") or "").strip()[:2000]
    filename = (data.get("filename") or "datei").strip()[:120]
    link = (data.get("link") or "").strip()

    if "@" not in to_addr or "." not in to_addr.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid recipient"}), 400
    if not link.startswith("http"):
        return jsonify({"ok": False, "error": "invalid link"}), 400
    if _file_send_rate_limited(sender):
        return jsonify({"ok": False, "error": "rate limited"}), 429
    if not _email_configured():
        return jsonify({"ok": False, "error": "email not configured"}), 503

    subject = f"📎 {sender or 'Jemand'} hat dir eine Datei über Downloader<3 geschickt"
    body = (
        f"Hey!\n\n{sender or 'Jemand'} hat dir über die Downloader<3-App "
        f"eine Datei geschickt: {filename}\n"
        + (f"\nNachricht:\n{message}\n" if message else "")
        + f"\n⬇ Download: {link}\n\n"
        "(Die Datei war zu groß für einen normalen E-Mail-Anhang, "
        "deshalb hier als Link -- er läuft nach einiger Zeit automatisch ab.)"
    )
    try:
        _smtp_send(to_addr, subject, body)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/backup-settings", methods=["POST", "OPTIONS"])
def backup_settings():
    """☁️ Speichert eine komplette Sicherung (Einstellungen, Verlauf,
    Favoriten, Abos) für ein Konto — überschreibt die vorherige
    Sicherung für diese E-Mail-Adresse."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    payload = data.get("data")
    if not email or payload is None:
        return jsonify({"ok": False, "error": "missing email/data"}), 400
    payload_str = json.dumps(payload)
    if len(payload_str) > 3_000_000:  # ca. 3 MB Grenze gegen Missbrauch
        return jsonify({"ok": False, "error": "too large"}), 413
    conn = db()
    conn.execute(
        "INSERT INTO user_backups (email, data, updated_at) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(email) DO UPDATE SET data=excluded.data, "
        "updated_at=excluded.updated_at",
        (email, payload_str, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/restore-settings", methods=["GET"])
def restore_settings():
    """☁️ Holt die gespeicherte Sicherung für ein Konto zurück — z. B. auf
    einem neuen Gerät nach der Anmeldung."""
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "missing email"}), 400
    conn = db()
    row = conn.execute(
        "SELECT data, updated_at FROM user_backups WHERE email = ?",
        (email,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "no backup"}), 404
    return jsonify({"ok": True, "data": json.loads(row[0]),
                    "updated_at": row[1]})


def _gift_email_text(days):
    """Baut eine zweisprachige (DE + EN) Glückwunsch-Mail — funktioniert
    unabhängig davon, welche Sprache die beschenkte Person spricht."""
    if days is None:
        de_line = "du hast gerade Premium FÜR IMMER geschenkt bekommen! 🎉"
        en_line = "you've just been gifted LIFETIME Premium! 🎉"
    else:
        de_line = f"du hast gerade {days} Tage Premium geschenkt bekommen! 🎉"
        en_line = f"you've just been gifted {days} days of Premium! 🎉"
    subject = "🎁 Downloader<3 — Herzlichen Glückwunsch! / Congratulations!"
    body = (
        "🇩🇪 Deutsch\n"
        "Herzlichen Glückwunsch! " + de_line + "\n"
        "Öffne einfach Downloader<3 auf deinem Gerät (mit derselben "
        "E-Mail-Adresse, an die diese Nachricht ging) — dein Premium ist "
        "automatisch aktiv. Viel Spaß dabei!\n\n"
        "— Lisa & Felix\n\n"
        "―――――――――――――――――――――――\n\n"
        "🇬🇧 English\n"
        "Congratulations! " + en_line + "\n"
        "Just open Downloader<3 on your device (using the same email "
        "address this message was sent to) — your Premium is "
        "automatically active. Enjoy!\n\n"
        "— Lisa & Felix"
    )
    return subject, body


def _helper_email_text():
    """Baut eine zweisprachige (DE + EN) Glückwunsch-Mail für neue
    Helfer — genau wie bei _gift_email_text() beim Premium-Verschenken,
    nur mit den Helfer-Vorteilen statt reinem Premium."""
    subject = "🤝 Downloader<3 — Du bist jetzt Helfer! / You're now a Helper!"
    body = (
        "🇩🇪 Deutsch\n"
        "Herzlichen Glückwunsch! Du bist jetzt offiziell Helfer bei "
        "Downloader<3 — vielen Dank für deine Unterstützung! 🎉\n\n"
        "Das bringt dir:\n"
        "★ Unbegrenztes Premium, für immer, komplett kostenlos\n"
        "🎁 Alle 2 Wochen einen eigenen Gutscheincode (bis zu 5 Tage "
        "Premium) erstellen und verschenken\n"
        "🤝 Einen eigenen Helfer-Bereich in der App\n\n"
        "Öffne einfach Downloader<3 auf deinem Gerät (mit derselben "
        "E-Mail-Adresse, an die diese Nachricht ging) — im neuen "
        "'Helfer'-Tab in der Seitenleiste findest du alles.\n\n"
        "— Lisa & Felix\n\n"
        "―――――――――――――――――――――――\n\n"
        "🇬🇧 English\n"
        "Congratulations! You're now officially a Helper at "
        "Downloader<3 — thank you for your support! 🎉\n\n"
        "This gets you:\n"
        "★ Unlimited Premium, forever, completely free\n"
        "🎁 Create and give away your own voucher code every 2 weeks "
        "(up to 5 days of Premium)\n"
        "🤝 Your own Helper area in the app\n\n"
        "Just open Downloader<3 on your device (using the same email "
        "address this message was sent to) — you'll find everything in "
        "the new 'Helper' tab in the sidebar.\n\n"
        "— Lisa & Felix"
    )
    return subject, body


@app.route("/api/admin-grant-premium", methods=["POST", "OPTIONS"])
def admin_grant_premium():
    """🎁 Owner-only: schenkt einer beliebigen E-Mail-Adresse Premium
    (auch wenn die Person die App noch nie genutzt hat) und verschickt
    eine zweisprachige Glückwunsch-Mail. Geschützt durch das
    Owner-Passwort (dieselbe Umgebungsvariable wie beim Owner-Login)."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    email = (data.get("email") or "").strip().lower()
    days = data.get("days")  # int oder None (= für immer)

    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid email"}), 400
    if email in OWNER_EMAILS:
        # Owner haben ohnehin schon immer unbegrenztes Premium — sich
        # selbst oder sich gegenseitig hier zusätzlich "beschenken" ist
        # sinnlos und wird deshalb blockiert.
        return jsonify({"ok": False, "error": "cannot gift owner"}), 400

    if days is None:
        premium_until = "forever"
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid days"}), 400
        until_date = datetime.datetime.now() + datetime.timedelta(days=days)
        premium_until = until_date.date().isoformat()
    _upsert_premium(email, premium_until)

    email_sent = True
    email_error = None
    if _email_configured():
        try:
            subject, body = _gift_email_text(days)
            _smtp_send(email, subject, body)
        except Exception as e:
            email_sent = False
            email_error = str(e)
    else:
        email_sent = False
        email_error = "email not configured"

    return jsonify({"ok": True, "premium_until": premium_until,
                    "email_sent": email_sent, "email_error": email_error})


@app.route("/api/admin-list-accounts", methods=["POST", "OPTIONS"])
def admin_list_accounts():
    """🌍 Owner-only: listet ALLE E-Mail-Adressen weltweit auf, die
    jemals mit der App interagiert haben (Login, Registrierung, Kauf) —
    damit der Owner nicht nur lokal bekannte Leute beschenken kann.
    Geschützt durch dasselbe Owner-Passwort wie der Owner-Login."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = db()
    rows = conn.execute(
        "SELECT email, premium_until, first_seen, last_seen, role "
        "FROM accounts ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    # 🌍 last_seen bleibt bewusst drin, auch wenn null/alt — die Liste zeigt
    # ALLE jemals bekannten Konten, nicht nur gerade aktive/online Nutzer,
    # damit der Owner z. B. zufällig jemandem etwas schenken kann, der die
    # App gerade nicht offen hat.
    accounts = [{"email": r[0], "premium_until": r[1],
                "first_seen": r[2], "last_seen": r[3],
                "role": r[4] or None} for r in rows]
    return jsonify({"ok": True, "accounts": accounts})


@app.route("/api/admin-revoke-premium", methods=["POST", "OPTIONS"])
def admin_revoke_premium():
    """👑 Owner-only: entzieht einer E-Mail-Adresse ihr Premium wieder —
    weltweit (wirkt auf das Server-Konto, nicht nur ein einzelnes Gerät),
    geschützt durchs selbe Owner-Passwort."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    email = (data.get("email") or "").strip().lower()
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not email:
        return jsonify({"ok": False, "error": "missing email"}), 400
    if email in OWNER_EMAILS:
        return jsonify({"ok": False, "error": "cannot modify owner"}), 400

    conn = db()
    conn.execute(
        "UPDATE accounts SET premium_until = NULL, updated_at = ? "
        "WHERE email = ?",
        (datetime.datetime.now().isoformat(), email))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin-delete-account", methods=["POST", "OPTIONS"])
def admin_delete_account():
    """👑 Owner-only: löscht ein Konto (E-Mail, Premium-Status, Rang,
    Cloud-Sicherung) komplett und weltweit vom Server — geschützt durchs
    Owner-Passwort. Owner-Konten selbst können nicht gelöscht werden."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    email = (data.get("email") or "").strip().lower()
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not email:
        return jsonify({"ok": False, "error": "missing email"}), 400
    if email in OWNER_EMAILS:
        return jsonify({"ok": False, "error": "cannot delete owner"}), 400

    conn = db()
    conn.execute("DELETE FROM accounts WHERE email = ?", (email,))
    conn.execute("DELETE FROM user_backups WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin-set-helper", methods=["POST", "OPTIONS"])
def admin_set_helper():
    """🤝 Owner-only: befördert eine E-Mail-Adresse weltweit zum
    Helfer-Rang (oder stuft sie wieder zurück). Helfer bekommen
    automatisch unbegrenztes Premium und dürfen alle 2 Wochen selbst
    einen kleinen Gutscheincode (max. 5 Tage) erstellen — siehe
    /api/helper-create-code."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    email = (data.get("email") or "").strip().lower()
    promote = data.get("promote", True)
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "invalid email"}), 400
    if email in OWNER_EMAILS:
        # Owner sind schon automatisch "über" jedem Rang (unbegrenztes
        # Premium sowieso) — sich selbst/sich gegenseitig zum Helfer
        # machen ist sinnlos und wird deshalb blockiert.
        return jsonify({"ok": False, "error": "cannot set owner role"}), 400

    email_sent = True
    email_error = None
    if promote:
        _set_role(email, "helper")
        _upsert_premium(email, "forever")  # Helfer = unbegrenzt Premium
        # 🎉 Genau wie beim Premium-Verschenken (admin-grant-premium) bekommt
        # die beförderte Person eine zweisprachige Glückwunsch-Mail.
        if _email_configured():
            try:
                subject, body = _helper_email_text()
                _smtp_send(email, subject, body)
            except Exception as e:
                email_sent = False
                email_error = str(e)
        else:
            email_sent = False
            email_error = "email not configured"
    else:
        _set_role(email, None)
    return jsonify({"ok": True, "role": "helper" if promote else None,
                    "email_sent": email_sent, "email_error": email_error})


@app.route("/api/admin-create-code", methods=["POST", "OPTIONS"])
def admin_create_code():
    """👑 Owner-only: erstellt einen Geschenk-Code SERVERSEITIG (statt nur
    lokal in der App), damit er wirklich weltweit bei jeder Person
    funktioniert, egal auf welchem Gerät sie ihn einlöst — genau der Fix
    für den Bug, dass Owner-Codes vorher nur auf dem eigenen Gerät
    gültig waren."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    days = data.get("days")  # int oder None (= für immer)
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if days is not None:
        try:
            days = int(days)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid days"}), 400

    code = make_code()
    conn = db()
    conn.execute(
        "INSERT INTO codes (code, days, order_id, plan, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, days, "admin-gift", "gift",
         datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "code": code, "days": days})


@app.route("/api/helper-create-code", methods=["POST", "OPTIONS"])
def helper_create_code():
    """🤝 Für Helfer: erstellt alle 2 Wochen einen eigenen Gutscheincode
    (max. 5 Tage Premium) — komplett serverseitig geprüft (Rang +
    Abklingzeit), damit sich das nicht durch eine neue Geräte-
    Installation umgehen lässt."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    days = data.get("days", 5)
    if not email:
        return jsonify({"ok": False, "error": "missing email"}), 400
    if _get_role(email) != "helper":
        return jsonify({"ok": False, "error": "not a helper"}), 403
    try:
        days = max(1, min(5, int(days)))
    except (TypeError, ValueError):
        days = 5

    conn = db()
    row = conn.execute(
        "SELECT last_helper_code_at FROM accounts WHERE email = ?",
        (email,)).fetchone()
    last = row[0] if row else None
    now = datetime.datetime.now()
    if last:
        try:
            elapsed = now - datetime.datetime.fromisoformat(last)
        except ValueError:
            elapsed = datetime.timedelta(days=999)
        if elapsed.total_seconds() < 14 * 24 * 3600:
            remaining = 14 * 24 * 3600 - elapsed.total_seconds()
            conn.close()
            return jsonify({
                "ok": False, "error": "cooldown",
                "hours_left": int(remaining // 3600) + 1,
            }), 429

    code = make_code()
    conn.execute(
        "INSERT INTO codes (code, days, order_id, plan, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, days, "helper-gift", "helper-gift", now.isoformat()))
    conn.execute(
        "UPDATE accounts SET last_helper_code_at = ? WHERE email = ?",
        (now.isoformat(), email))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "code": code, "days": days})


@app.route("/api/helper-set-public", methods=["POST", "OPTIONS"])
def helper_set_public():
    """🤝 Ehrentafel: ein Helfer entscheidet hier freiwillig (Opt-in), ob
    und mit welchem selbst gewählten Anzeigenamen er auf der Landingpage
    genannt wird — komplett getrennt vom privaten In-App-Namen, NIE die
    echte E-Mail-Adresse. Nur für Konten mit Rang 'helper'."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    public_name = (data.get("public_name") or "").strip()[:40]
    opt_in = bool(data.get("opt_in"))
    if not email:
        return jsonify({"ok": False, "error": "missing email"}), 400
    if _get_role(email) != "helper":
        return jsonify({"ok": False, "error": "not a helper"}), 403
    if opt_in and not public_name:
        return jsonify({"ok": False, "error": "missing public_name"}), 400

    conn = db()
    conn.execute(
        "UPDATE accounts SET helper_public_name = ?, "
        "helper_public_optin = ? WHERE email = ?",
        (public_name, "1" if opt_in else "0", email))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/helpers-public", methods=["GET"])
def helpers_public():
    """🤝 Öffentlich (keine Anmeldung nötig) — für die Ehrentafel auf der
    Landingpage. Gibt NUR die selbst gewählten Anzeigenamen der Helfer
    zurück, die sich aktiv fürs Zeigen entschieden haben (Opt-in) — NIE
    E-Mail-Adressen oder andere Kontodaten."""
    conn = db()
    rows = conn.execute(
        "SELECT helper_public_name FROM accounts WHERE role = 'helper' "
        "AND helper_public_optin = '1' AND helper_public_name IS NOT NULL "
        "AND helper_public_name != '' ORDER BY first_seen ASC"
    ).fetchall()
    conn.close()
    return jsonify({"helpers": [r[0] for r in rows]})


def _beta_email_text(zip_url, note):
    """🧪 Bilinguale Beta-Test-E-Mail an alle Helfer — der Server kennt
    die bevorzugte Sprache eines Nutzers nicht, deshalb steht hier
    bewusst IMMER Deutsch UND Englisch im selben Text."""
    subject = "🧪 Downloader<3 Beta-Test — sei als Erste(r) dabei! / Be the first to test!"
    extra = f"\n\n📝 {note}\n" if note else ""
    body = (
        "Hey! 🎉\n\n"
        "Du bist Helfer bei Downloader<3 — und weil du das bist, darfst du "
        "die neueste Beta-Version schon jetzt testen, bevor sie für alle "
        "anderen veröffentlicht wird!\n\n"
        f"⬇ Download: {zip_url}"
        f"{extra}\n"
        "Danke, dass du uns hilfst, Downloader<3 noch besser zu machen! 💜\n\n"
        "---\n\n"
        "Hey! 🎉 (English)\n\n"
        "You're a Helper on Downloader<3 — and because of that, you get to "
        "try out the newest beta version before anyone else!\n\n"
        f"⬇ Download: {zip_url}"
        f"{extra}\n"
        "Thanks for helping us make Downloader<3 even better! 💜"
    )
    return subject, body


@app.route("/api/admin-broadcast-beta", methods=["POST", "OPTIONS"])
def admin_broadcast_beta():
    """🧪 Owner-only: schickt eine (bewusst automatisch generierte)
    Beta-Test-Einladung samt Download-Link an ALLE aktuellen Helfer
    weltweit auf einmal — z. B. bevor eine neue Version öffentlich
    veröffentlicht wird. Der eigentliche Build wird bewusst NICHT als
    E-Mail-Anhang verschickt (30+ MB sprengen die meisten Postfach-/
    SMTP-Limits zuverlässig), sondern als Link (z. B. ein GitHub-
    Pre-Release-Asset-Link)."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    owner_password = data.get("owner_password") or ""
    if not OWNER_PASSWORD or owner_password != OWNER_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    zip_url = (data.get("zip_url") or "").strip()
    note = (data.get("note") or "").strip()
    if not zip_url:
        return jsonify({"ok": False, "error": "missing zip_url"}), 400
    if not _email_configured():
        return jsonify({"ok": False, "error": "email not configured"}), 503

    conn = db()
    rows = conn.execute(
        "SELECT email FROM accounts WHERE role = 'helper'").fetchall()
    conn.close()
    emails = [r[0] for r in rows if r[0]]

    subject, body = _beta_email_text(zip_url, note)
    sent = 0
    failed = []
    for addr in emails:
        try:
            _smtp_send(addr, subject, body)
            sent += 1
        except Exception as e:
            failed.append({"email": addr, "error": str(e)})
    return jsonify({"ok": True, "total": len(emails), "sent": sent,
                    "failed": failed})


def _check_ai_rate_limit(identifier, max_per_hour):
    """Einfacher Missbrauchsschutz: begrenzt Anfragen pro E-Mail/Stunde."""
    now = datetime.datetime.now()
    attempts = [t for t in _ai_attempts.get(identifier, [])
               if (now - t).total_seconds() < 3600]
    if len(attempts) >= max_per_hour:
        return False
    attempts.append(now)
    _ai_attempts[identifier] = attempts
    return True


@app.route("/api/ai-text", methods=["POST", "OPTIONS"])
def ai_text():
    """🎨 KI-Studio: Text-Generierung über den GEMEINSAMEN Gemini-Schlüssel
    dieses Servers — die App selbst braucht keinen eigenen Schlüssel."""
    if request.method == "OPTIONS":
        return "", 204
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "not configured"}), 503
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    identifier = (data.get("email") or request.remote_addr or "anon")
    if not prompt:
        return jsonify({"ok": False, "error": "no prompt"}), 400
    if not _check_ai_rate_limit("text:" + identifier, 60):
        return jsonify({"ok": False, "error": "rate limited"}), 429
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/"
              f"models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}")
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}]
        }).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"ok": True, "text": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai-image", methods=["POST", "OPTIONS"])
def ai_image():
    """🎨 KI-Studio: Bild-Generierung über den gemeinsamen Schlüssel."""
    if request.method == "OPTIONS":
        return "", 204
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "not configured"}), 503
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    identifier = (data.get("email") or request.remote_addr or "anon")
    if not prompt:
        return jsonify({"ok": False, "error": "no prompt"}), 400
    if not _check_ai_rate_limit("image:" + identifier, 30):
        return jsonify({"ok": False, "error": "rate limited"}), 429
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/"
              f"models/gemini-2.5-flash-image:generateContent?"
              f"key={GEMINI_API_KEY}")
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            result = json.loads(r.read().decode())
        parts = result["candidates"][0]["content"]["parts"]
        img_b64 = next((p["inlineData"]["data"] for p in parts
                        if "inlineData" in p), None)
        if not img_b64:
            return jsonify({"ok": False, "error": "no image returned"}), 502
        return jsonify({"ok": True, "image_base64": img_b64})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai-video", methods=["POST", "OPTIONS"])
def ai_video():
    """🎨 KI-Studio: Video-Generierung (experimentell, Veo) über den
    gemeinsamen Schlüssel — startet nur den Auftrag, die App fragt den
    Fortschritt separat über /api/ai-video-status ab (dauert Minuten)."""
    if request.method == "OPTIONS":
        return "", 204
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "not configured"}), 503
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    identifier = (data.get("email") or request.remote_addr or "anon")
    if not prompt:
        return jsonify({"ok": False, "error": "no prompt"}), 400
    if not _check_ai_rate_limit("video:" + identifier, 10):
        return jsonify({"ok": False, "error": "rate limited"}), 429
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/"
              f"models/veo-3.1-generate-preview:predictLongRunning"
              f"?key={GEMINI_API_KEY}")
        body = json.dumps({"instances": [{"prompt": prompt}]}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            op = json.loads(r.read().decode())
        if not op.get("name"):
            return jsonify({"ok": False, "error": str(op)}), 502
        return jsonify({"ok": True, "operation": op["name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai-video-status", methods=["GET"])
def ai_video_status():
    """🎨 Fragt den Fortschritt einer laufenden Video-Generierung ab.
    Gibt NIE den geteilten API-Schlüssel an die App weiter — das
    eigentliche Herunterladen läuft über /api/ai-video-download."""
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "not configured"}), 503
    op_name = request.args.get("operation") or ""
    if not op_name:
        return jsonify({"ok": False, "error": "no operation"}), 400
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
              f"{op_name}?key={GEMINI_API_KEY}")
        with urllib.request.urlopen(url, timeout=30) as r:
            result = json.loads(r.read().decode())
        if not result.get("done"):
            return jsonify({"ok": True, "done": False})
        samples = (result.get("response", {})
                  .get("generateVideoResponse", {})
                  .get("generatedSamples", []))
        if not samples:
            return jsonify({"ok": False, "done": True,
                            "error": str(result.get("error", result))})
        return jsonify({"ok": True, "done": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai-video-download", methods=["GET"])
def ai_video_download():
    """🎨 Lädt das fertige Video vom Server herunter und reicht die Datei
    direkt an die App weiter — der geteilte API-Schlüssel bleibt dabei
    ausschließlich auf dem Server, die App sieht ihn nie."""
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "not configured"}), 503
    op_name = request.args.get("operation") or ""
    if not op_name:
        return jsonify({"ok": False, "error": "no operation"}), 400
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
              f"{op_name}?key={GEMINI_API_KEY}")
        with urllib.request.urlopen(url, timeout=30) as r:
            result = json.loads(r.read().decode())
        samples = (result.get("response", {})
                  .get("generateVideoResponse", {})
                  .get("generatedSamples", []))
        if not samples:
            return jsonify({"ok": False, "error": "not ready"}), 404
        video_uri = samples[0]["video"]["uri"]
        dl_url = video_uri if "key=" in video_uri else (
            video_uri + ("&" if "?" in video_uri else "?")
            + f"key={GEMINI_API_KEY}")
        video_req = urllib.request.Request(dl_url)
        with urllib.request.urlopen(video_req, timeout=120) as vr:
            video_bytes = vr.read()
        from flask import Response
        return Response(video_bytes, mimetype="video/mp4")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# 🎧 Musik-Download (Spotify/Apple Music/Amazon Music)
# ---------------------------------------------------------------------------
# WICHTIG: Wir laden hier NIEMALS Audio direkt von diesen Diensten
# herunter — das würde bedeuten, ihren Kopierschutz (DRM) zu umgehen,
# was in den meisten Ländern verboten ist (z. B. DMCA in den USA). Wir
# lesen ausschließlich ÖFFENTLICHE, unverschlüsselte Metadaten
# (Songtitel + Künstler) aus. Die App sucht den Song danach selbst ganz
# normal auf YouTube und lädt IHN — genau wie bei jedem anderen
# YouTube-Download in der App.
def _spotify_access_token():
    """Holt (und cached) einen App-Zugangs-Token über Spotifys
    Client-Credentials-Flow — braucht KEIN Nutzer-Login, nur die eigene
    App-Registrierung. Wirft eine Exception, wenn nicht konfiguriert
    oder Spotify ablehnt."""
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        raise RuntimeError("spotify not configured")
    now = datetime.datetime.now()
    cached = _spotify_token_cache
    if cached["token"] and cached["expires"] and now < cached["expires"]:
        return cached["token"]
    auth = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    body = b"grant_type=client_credentials"
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=body, method="POST",
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read().decode())
    token = result["access_token"]
    expires_in = int(result.get("expires_in", 3600))
    # Etwas früher als offiziell nötig ablaufen lassen (Sicherheitsnetz
    # gegen knapp abgelaufene Tokens bei einer laufenden Anfrage).
    cached["token"] = token
    cached["expires"] = now + datetime.timedelta(seconds=expires_in - 60)
    return token


def _spotify_get(path):
    token = _spotify_access_token()
    req = urllib.request.Request(
        f"https://api.spotify.com/v1{path}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _spotify_anon_token():
    """🎧 Holt (und cached) den anonymen, kurzlebigen Web-Player-Token,
    den open.spotify.com selbst für nicht eingeloggte Besucher benutzt.
    Hat KEINE Einschränkung bei Spotify-eigenen algorithmischen
    Playlists (anders als der normale App-Zugangs-Token oben) — genau
    deshalb hier als Ausweg für genau diesen Fall genutzt.

    🐛 FIX ("HTTP Error 403: URL Blocked"): Der erste, einfache Versuch
    (nur "get_access_token" ohne vorherigen Seitenaufruf/Cookies, ohne
    Referer/Accept-Header, mit productType=embed) wurde von Spotifys
    Bot-Schutz erkannt und direkt blockiert — echte Browser laden IMMER
    zuerst die Seite selbst (wodurch Sitzungs-Cookies gesetzt werden)
    und schicken bei der Token-Anfrage danach passende Referer-/
    Accept-/App-Platform-Header mit. Genau dieses zweistufige,
    browser-typische Verhalten wird jetzt nachgebildet: 1) einmal
    open.spotify.com laden (setzt die nötigen Cookies über einen
    gemeinsamen Cookie-Speicher), 2) danach get_access_token MIT diesen
    Cookies und vollständigen Browser-Headern abfragen."""
    now = datetime.datetime.now()
    cached = _spotify_anon_token_cache
    if cached["token"] and cached["expires"] and now < cached["expires"]:
        return cached["token"]

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))

    # 1) Einmal die echte Seite laden, damit Spotify die üblichen
    #    Sitzungs-Cookies setzt (ohne die wird der Token-Endpunkt als
    #    Bot erkannt und blockiert).
    home_req = urllib.request.Request(
        "https://open.spotify.com/", headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;"
                     "q=0.9,*/*;q=0.8",
        })
    with opener.open(home_req, timeout=15):
        pass

    # 2) Jetzt den Token mit den gesetzten Cookies + vollständigen,
    #    browser-typischen Headern abfragen.
    token_req = urllib.request.Request(
        "https://open.spotify.com/get_access_token"
        "?reason=transport&productType=web-player",
        headers={
            "User-Agent": ua,
            "Accept": "application/json",
            "Referer": "https://open.spotify.com/",
            "App-Platform": "WebPlayer",
        })
    with opener.open(token_req, timeout=15) as r:
        data = json.loads(r.read().decode())
    token = data.get("accessToken")
    if not token:
        raise RuntimeError("spotify anon token unavailable")
    exp_ms = data.get("accessTokenExpirationTimestampMs")
    if exp_ms:
        expires = (datetime.datetime.fromtimestamp(exp_ms / 1000)
                  - datetime.timedelta(seconds=30))
    else:
        expires = now + datetime.timedelta(minutes=30)
    cached["token"] = token
    cached["expires"] = expires
    return token


def _spotify_get_resilient(path):
    """Wie _spotify_get, aber mit automatischem Ausweg auf den anonymen
    Web-Player-Token, wenn der normale App-Token mit 403/404 abgelehnt
    wird (siehe Kommentar bei _spotify_anon_token_cache oben — betrifft
    v. a. Spotify-eigene algorithmische Playlists)."""
    try:
        return _spotify_get(path)
    except urllib.error.HTTPError as he:
        if he.code not in (403, 404):
            raise
        try:
            token = _spotify_anon_token()
            req = urllib.request.Request(
                f"https://api.spotify.com/v1{path}",
                headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception:
            # 🐛 Beide Wege (normaler App-Token UND anonymer
            # Web-Player-Token) sind fehlgeschlagen — ein klarerer,
            # verständlicher Fehler ist hier hilfreicher als die rohe
            # zweite Exception (z. B. ein kryptisches "URL Blocked"),
            # die sonst den eigentlichen Grund (Spotify-eigene,
            # algorithmische Playlist nicht abrufbar) verschleiern
            # würde.
            raise RuntimeError(
                "spotify blocked this playlist/album on every available "
                "access path (this can happen for Spotify's own "
                "algorithmic/editorial playlists) — please try a "
                "different, self-created playlist, or add the songs as "
                "individual track links instead")


def _spotify_track_to_item(t):
    if not t:
        return None
    artists = ", ".join(a.get("name", "") for a in (t.get("artists") or [])
                        if a.get("name"))
    title = t.get("name") or ""
    if not title:
        return None
    return {"title": title, "artist": artists}


_SPOTIFY_ID_RE = re.compile(
    r"open\.spotify\.com/(?:intl-\w+/)?(track|playlist|album)/([A-Za-z0-9]+)")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def _spotify_scrape_embed(kind, sid):
    """🎧 DRITTER, letzter Ausweg (nach normalem App-Token UND anonymem
    Web-Player-Token): liest die öffentliche, für iframe-Einbettungen
    gedachte Embed-Seite (open.spotify.com/embed/...) aus. Diese Seite
    braucht KEINE Anmeldung/keinen Token-Austausch überhaupt — nur ein
    einfacher GET-Request auf eine öffentliche HTML-Seite, wie ihn jede
    Webseite macht, die ein Spotify-Widget einbettet (WhatsApp/Discord-
    Linkvorschauen funktionieren nach demselben Prinzip). Dadurch deutlich
    unwahrscheinlicher vom Bot-Schutz blockiert als die eigentlichen
    Auth-/Token-Endpunkte. Die Song-Liste steckt in einem eingebetteten
    JSON-Datenblock (__NEXT_DATA__) mitten in der HTML-Seite — die genaue
    Datenstruktur ist nicht offiziell dokumentiert und kann sich mit
    Spotify-Updates ändern, deshalb wird hier bewusst nicht auf einen
    einzigen exakten Pfad im JSON vertraut, sondern das GESAMTE JSON
    rekursiv nach Objekten durchsucht, die wie ein Song aussehen (entweder
    im Format der offiziellen API: {"name", "artists": [{"name"}, ...]},
    oder im vereinfachten Embed-Format: {"title", "subtitle"})."""
    req = urllib.request.Request(
        f"https://open.spotify.com/embed/{kind}/{sid}",
        headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;"
                     "q=0.9,*/*;q=0.8",
        })
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read(3_000_000).decode("utf-8", errors="ignore")
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise RuntimeError("embed page: no data block found")
    data = json.loads(m.group(1))

    items = []
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            name = node.get("name")
            artists = node.get("artists")
            if (isinstance(name, str) and name
                    and isinstance(artists, list)):
                artist_names = ", ".join(
                    a.get("name", "") for a in artists
                    if isinstance(a, dict) and a.get("name"))
                if artist_names:
                    key = (name, artist_names)
                    if key not in seen:
                        seen.add(key)
                        items.append({"title": name, "artist": artist_names})
            title = node.get("title")
            subtitle = node.get("subtitle")
            if (isinstance(title, str) and title
                    and isinstance(subtitle, str) and subtitle):
                key = (title, subtitle)
                if key not in seen:
                    seen.add(key)
                    items.append({"title": title, "artist": subtitle})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    if not items:
        raise RuntimeError("embed page: no tracks parsed")
    return items


def _resolve_spotify(url):
    m = _SPOTIFY_ID_RE.search(url)
    if not m:
        raise RuntimeError("invalid spotify url")
    kind, sid = m.group(1), m.group(2)
    try:
        if kind == "track":
            t = _spotify_get_resilient(f"/tracks/{sid}")
            item = _spotify_track_to_item(t)
            if not item:
                raise RuntimeError("track not found")
            return [item]
        if kind == "album":
            data = _spotify_get_resilient(f"/albums/{sid}/tracks?limit=50")
            items = [_spotify_track_to_item(t)
                     for t in data.get("items", [])]
            items = [i for i in items if i]
            if not items:
                raise RuntimeError("no tracks")
            return items
        # playlist — auf 200 Songs gedeckelt (großzügig, verhindert aber
        # eine riesige Anfrage bei Mega-Playlists mit tausenden Songs)
        items = []
        offset = 0
        while offset < 200:
            data = _spotify_get_resilient(
                f"/playlists/{sid}/tracks?limit=50&offset={offset}"
                "&fields=items(track(name,artists(name))),next")
            for entry in data.get("items", []):
                item = _spotify_track_to_item(entry.get("track"))
                if item:
                    items.append(item)
            if not data.get("next"):
                break
            offset += 50
        if not items:
            raise RuntimeError("no tracks")
        return items
    except Exception as original_error:
        # 🐛 FIX ("blocked on every available access path" trotz
        # vorherigem Cookie-/Header-Fix): Weder der normale App-Token
        # noch der anonyme Web-Player-Token (beide über
        # _spotify_get_resilient) kamen durch — als letzten Ausweg jetzt
        # die öffentliche Embed-Seite versuchen (siehe
        # _spotify_scrape_embed oben). Schlägt AUCH das fehl, wird die
        # ursprüngliche Fehlermeldung weitergereicht, nicht die vom
        # Embed-Versuch — die beschreibt den eigentlichen Grund besser.
        try:
            return _spotify_scrape_embed(kind, sid)
        except Exception:
            raise original_error


def _scrape_page_title_artist(url):
    """🌐 Bestes-Bemühen-Auslesen von Songtitel + Künstler aus der
    ÖFFENTLICH sichtbaren Seite (og:title/og:description-Metatags —
    dieselben Infos, die z. B. auch beim Teilen des Links in Whatsapp/
    Discord als Vorschau angezeigt werden). Genutzt für Apple Music und
    Amazon Music, die (anders als Spotify) keine kostenlose öffentliche
    API für Song-Metadaten anbieten."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read(200_000).decode("utf-8", errors="ignore")
    def meta(prop):
        # 🐛 Robuster: HTML-Meta-Tags schreiben "property"/"name" und
        # "content" nicht immer in derselben Reihenfolge — beide
        # Varianten durchprobieren, statt nur eine anzunehmen.
        m = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\']'
            r'[^>]+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+'
                rf'(?:property|name)=["\']{re.escape(prop)}["\']',
                html, re.IGNORECASE)
        return m.group(1).strip() if m else None
    title = meta("og:title")
    desc = meta("og:description") or ""
    if not title:
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = m.group(1).strip() if m else None
    if not title:
        raise RuntimeError("title not found")
    # og:title ist meist NUR der Songtitel, der Künstler steckt oft im
    # og:description ("Song · Künstler · ...", "Künstler · Song") oder im
    # <title> ("Songtitel - song by Künstler | ..."). Mehrere gängige
    # Muster durchprobieren, sonst bleibt der Künstler leer (immer noch
    # besser als komplett zu scheitern — die YouTube-Suche findet den
    # Song meist auch nur mit dem Titel).
    artist = None
    m = re.search(r"song by ([^|·]+)", title + " " + desc, re.IGNORECASE)
    if m:
        artist = m.group(1).strip()
    if not artist and "·" in desc:
        parts = [p.strip() for p in desc.split("·") if p.strip()]
        if len(parts) >= 2:
            artist = parts[1] if parts[0].lower() == title.lower() \
                else parts[0]
    # <title>-Tag enthält oft " - song by X | ..." -> das Suffix abtrennen
    title = re.split(r"\s*[-–]\s*song by\s", title, flags=re.IGNORECASE)[0]
    title = title.split("|")[0].strip()
    return {"title": title, "artist": artist or ""}


@app.route("/api/music-lookup", methods=["POST", "OPTIONS"])
def music_lookup():
    """🎧 Liest Songtitel + Künstler aus einem Spotify-/Apple-Music-/
    Amazon-Music-Link aus (nur öffentliche Metadaten, kein DRM-Umgehen)
    — die App sucht den Song danach selbst auf YouTube."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "no url"}), 400

    # Missbrauchsschutz: max. 30 Anfragen pro IP und Stunde
    identifier = request.remote_addr or "anon"
    now = datetime.datetime.now()
    attempts = [t for t in _music_attempts.get(identifier, [])
               if (now - t).total_seconds() < 3600]
    if len(attempts) >= 30:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    attempts.append(now)
    _music_attempts[identifier] = attempts

    try:
        if "open.spotify.com" in url:
            items = _resolve_spotify(url)
        elif "music.apple.com" in url or "music.amazon." in url:
            items = [_scrape_page_title_artist(url)]
        else:
            return jsonify({"ok": False, "error": "unsupported url"}), 400
        if not items:
            return jsonify({"ok": False, "error": "no tracks found"}), 404
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Downloader<3 backend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
