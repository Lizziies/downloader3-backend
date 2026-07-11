# 💜 Downloader<3 — Premium-Checkout mit PayPal einrichten

Diese Anleitung bringt dich von "Ich hab zwei Ordner mit Code" zu "Leute
können auf meiner Webseite mit PayPal bezahlen und bekommen automatisch
einen Aktivierungscode für die App".

## Was du bekommst
- `premium-backend/` — ein kleiner Server (Python/Flask), der Zahlungen mit
  PayPal abwickelt und danach automatisch einen Code erzeugt
- `checkout-website/` — die Kaufseite selbst (eine HTML-Datei), die deine
  Kunden im Browser sehen
- Die App selbst wurde bereits angepasst: im Admin-Panel gibst du die
  beiden Adressen ein, danach funktioniert "Code einlösen" automatisch
  auch mit echten, gekauften Codes

## Was DU selbst erledigen musst (das kann ich dir nicht abnehmen)
1. Ein PayPal-Business- oder Entwicklerkonto
2. Den Server irgendwo hosten (eine öffentliche Internet-Adresse)
3. Die Webseite irgendwo hosten
4. Die drei Adressen (PayPal-Zugangsdaten, Server-URL, Webseiten-URL)
   überall eintragen

Das ist kein Zauberwerk, dauert aber ca. 30–60 Minuten beim ersten Mal.
Hier die Schritte:

---

## Schritt 1 — PayPal-Entwicklerkonto einrichten

1. Gehe auf **https://developer.paypal.com** und logge dich mit deinem
   normalen PayPal-Konto ein (oder erstelle eins).
2. Oben auf **"Apps & Credentials"** klicken.
3. Zuerst zum Testen: Stelle sicher, dass **"Sandbox"** ausgewählt ist
   (nicht "Live") — damit kannst du mit Fake-Geld testen, bevor echtes
   Geld fließt.
4. Klicke auf **"Create App"**, gib ihr einen Namen (z. B. "Downloader3"),
   erstellen.
5. Du bekommst eine **Client ID** und ein **Secret** angezeigt — beide
   kopieren und sicher aufbewahren (z. B. in einem Passwort-Manager).
   **Niemals in Code hochladen oder öffentlich teilen!**
6. Wenn alles läuft und du auf echtes Geld umstellen willst: oben auf
   "Live" wechseln, dort nochmal eine App erstellen (eigene Live-Zugangsdaten).

## Schritt 2 — Server hosten (Backend)

Der Server braucht eine öffentliche Internet-Adresse. Kostenlose Option
zum Ausprobieren: **Render.com**

1. Gehe auf **https://render.com**, erstelle ein kostenloses Konto.
2. Lade den Ordner `premium-backend/` in ein GitHub-Repository hoch
   (falls du kein GitHub hast: kostenloses Konto auf github.com erstellen,
   neues Repository erstellen, die Dateien per "Upload files" hochladen).
3. Auf Render: **"New" → "Web Service"** → dein GitHub-Repository auswählen.
4. Einstellungen:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Unter **"Environment"** folgende Umgebungsvariablen eintragen (NICHT im
   Code, sondern hier im Render-Dashboard):
   - `PAYPAL_CLIENT_ID` = deine Client ID aus Schritt 1
   - `PAYPAL_CLIENT_SECRET` = dein Secret aus Schritt 1
   - `PAYPAL_MODE` = `sandbox` (zum Testen) oder später `live`
6. "Create Web Service" — nach ein paar Minuten bekommst du eine URL wie
   `https://downloader3-backend.onrender.com`. **Das ist deine
   Backend-Server-URL.**

*(Alternativen zu Render: Railway.app, PythonAnywhere, oder ein eigener
VPS — das Prinzip ist überall ähnlich: Python-Umgebung + die
Umgebungsvariablen setzen + `gunicorn app:app` starten.)*

## Schritt 3 — Checkout-Webseite hosten

Die Datei `checkout-website/index.html` ist eine einzelne, fertige
HTML-Seite. Du musst nur zwei Dinge darin eintragen (ganz unten im
`<script>`-Bereich):

```javascript
const BACKEND_URL = "https://downloader3-backend.onrender.com";  // deine Server-URL aus Schritt 2
const PAYPAL_CLIENT_ID = "deine-client-id-aus-schritt-1";
```

Danach die Datei irgendwo hosten, z. B.:
- **GitHub Pages** (kostenlos): Repository erstellen, `index.html`
  hochladen, unter "Settings → Pages" aktivieren
- **Netlify** (kostenlos): Konto erstellen, Ordner per Drag & Drop hochladen
- Oder auf deiner eigenen Domain, falls vorhanden

Du bekommst eine URL wie `https://deinname.github.io/downloader3-checkout`
— **das ist deine Checkout-Webseiten-URL.**

## Schritt 4 — In der App eintragen

1. App öffnen, als Owner einloggen (Felix oder Lisa)
2. **👑 Admin** → runterscrollen zu **"🌐 Premium-Webseite (PayPal-Kauf)"**
3. **Backend-Server-URL:** die Adresse aus Schritt 2 eintragen
4. **Checkout-Webseiten-URL:** die Adresse aus Schritt 3 eintragen
5. Beides speichern

Ab jetzt:
- Auf der Premium-Seite der App erscheint ein Button **"🌐 Premium auf der
  Webseite kaufen (PayPal)"**, der die Webseite im Browser öffnet
- Kunden zahlen dort mit PayPal, bekommen automatisch einen Code angezeigt
- Diesen Code geben sie in der App unter "Code einlösen" ein — die App
  fragt jetzt automatisch sowohl die lokalen (Admin-vergebenen) Codes als
  auch den Backend-Server ab

## Schritt 5 — Testen, bevor es live geht!

Solange `PAYPAL_MODE=sandbox` gesetzt ist, kannst du mit PayPals
Test-Konten (unter developer.paypal.com → Sandbox → Accounts) bezahlen,
ohne echtes Geld auszugeben. Erst wenn alles funktioniert:
- Neue PayPal-App im "Live"-Modus erstellen (Schritt 1)
- Neue Client-ID/Secret in den Render-Umgebungsvariablen eintragen
- `PAYPAL_MODE` auf `live` setzen
- `PAYPAL_CLIENT_ID` in der `index.html` auf die Live-Client-ID ändern

## Preise ändern

In `premium-backend/app.py` ganz oben:
```python
PLANS = {
    "30days": {"price": "2.99", "days": 30, "label": "30 Tage Premium"},
    "365days": {"price": "19.99", "days": 365, "label": "1 Jahr Premium"},
    "forever": {"price": "39.99", "days": None, "label": "Premium für immer"},
}
```
Preise/Namen einfach anpassen und neu hochladen (Render deployt automatisch
neu, wenn du bei GitHub etwas änderst).

## Ich habe alles getestet, was ich ohne echtes PayPal-Konto testen konnte
- ✅ Der komplette Kauf-Ablauf (Bestellung → Zahlung → Code erzeugen →
  Code einlösen → Code kann nicht doppelt eingelöst werden) — mit
  simulierter PayPal-Antwort durchgetestet
- ✅ Die echte Verbindung zwischen App und Server über HTTP (ein echter
  lokaler Server wurde gestartet und die App-Logik hat erfolgreich einen
  Code darüber eingelöst)
- ❌ Die *echte* PayPal-Zahlungsabwicklung selbst konnte ich nicht testen,
  da ich keinen Internetzugang/PayPal-Konto in meiner Umgebung habe — das
  musst du beim ersten echten Kauf (am besten im Sandbox-Modus) selbst
  prüfen.

## Sicherheitshinweise
- Client Secret **niemals** in Code, GitHub oder der Webseite — nur als
  Umgebungsvariable auf dem Server.
- Die Checkout-Seite braucht nur die Client **ID** (öffentlich, das ist
  normal und sicher), niemals das Secret.
- `PAYPAL_MODE=live` erst umstellen, wenn Sandbox-Tests erfolgreich waren.
