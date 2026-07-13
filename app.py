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
import json
import sqlite3
import secrets
import datetime
import smtplib
from email.mime.text import MIMEText
import urllib.request
import urllib.error
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
_email_attempts = {}  # einfacher Schutz gegen Missbrauch/Spam

# 🎨 KI-Studio: EIN gemeinsamer Gemini-API-Schlüssel für ALLE Nutzer der
# App — steht NUR hier als Umgebungsvariable, nie im verteilten Code.
# WICHTIG: Da alle Nutzer denselben Schlüssel teilen, trägst DU (der
# Owner) die Kosten dafür — die Rate-Begrenzung unten schützt vor Missbrauch,
# ersetzt aber keine Kostenkontrolle bei sehr vielen Nutzern.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_ai_attempts = {}  # Missbrauchsschutz: begrenzt Anfragen pro E-Mail

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
    for col in ("first_seen", "last_seen"):
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
        "SELECT premium_until FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return jsonify({"premium_until": row[0] if row else None})


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


def _smtp_send(to_addr, subject, body):
    """Verschickt eine einzelne E-Mail über die Server-eigenen SMTP-
    Zugangsdaten. Wirft eine Exception bei Fehlern (vom Aufrufer abfangen)."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    if SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.starttls()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(SMTP_FROM, [to_addr], msg.as_string())
    server.quit()


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

    # Missbrauchsschutz: max. 5 E-Mails pro Adresse pro Stunde
    now = datetime.datetime.now()
    attempts = [t for t in _email_attempts.get(to_addr, [])
               if (now - t).total_seconds() < 3600]
    if len(attempts) >= 5:
        return jsonify({"ok": False, "error": "rate limited"}), 429
    attempts.append(now)
    _email_attempts[to_addr] = attempts

    if not SMTP_USER or not SMTP_PASSWORD:
        return jsonify({"ok": False, "error": "smtp not configured"}), 503

    try:
        subject = subject.replace("{code}", code)
        body = body.replace("{code}", code)
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
    if SMTP_USER and SMTP_PASSWORD:
        try:
            subject, body = _gift_email_text(days)
            _smtp_send(email, subject, body)
        except Exception as e:
            email_sent = False
            email_error = str(e)
    else:
        email_sent = False
        email_error = "smtp not configured"

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
        "SELECT email, premium_until, first_seen, last_seen "
        "FROM accounts ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    accounts = [{"email": r[0], "premium_until": r[1],
                "first_seen": r[2], "last_seen": r[3]} for r in rows]
    return jsonify({"ok": True, "accounts": accounts})


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


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Downloader<3 backend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
