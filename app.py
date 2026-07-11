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
    return conn


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

    return jsonify({"ok": True, "code": code, "days": plan["days"]})


@app.route("/api/redeem", methods=["GET"])
def redeem():
    """Wird von der Downloader<3-App aufgerufen, wenn jemand einen Code
    einlöst. Ein Code funktioniert nur EINMAL."""
    code = (request.args.get("code") or "").strip().upper()
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
    return jsonify({"ok": True, "days": days})


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


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Downloader<3 backend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
