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

## 🔒 Update — Owner-Login jetzt sicher (kein Passwort mehr im Programmcode!)

**Wichtig, falls ihr die App öffentlich verteilen wollt:** Bisher stand das
Owner-Passwort fest im main.py-Code — das hätte bedeutet, dass jeder, der
die App-Datei bekommt, sich selbst als "Felix" oder "Lisa" hätte einloggen
und sich kostenlos Premium für immer freischalten können. Das ist jetzt
behoben: das echte Passwort lebt nur noch **hier auf dem Server**, als
Umgebungsvariable.

### Das musst du einmalig auf Render nachtragen

1. Gehe zu deinem Render-Dashboard → dein Backend-Service (z. B.
   `downloader3-backend`)
2. Links auf **"Environment"** klicken
3. **"+ Add Environment Variable"**:
   - Name: `OWNER_PASSWORD`
   - Value: ein **neues, sicheres Passwort** deiner Wahl (kann, muss aber
     nicht das alte sein — neu ist sogar sicherer, da das alte jetzt in
     diesem Chat-Verlauf steht)
4. Speichern — Render startet den Server automatisch neu

### Was sich für dich als Owner ändert

- Beim **nächsten Login** auf jedem deiner Geräte (PC, Laptop, ...) wirst
  du einmalig gefragt und die App prüft das Passwort **einmalig online**
  gegen den Server
- Danach merkt sich **dieses eine Gerät** den Zugang — du musst dich nicht
  bei jedem Login neu online verifizieren, nur einmalig pro Gerät
- Ohne Internetverbindung geht die allererste Anmeldung auf einem neuen
  Gerät nicht — das ist beabsichtigt (Sicherheit vor Bequemlichkeit)

### Für alle anderen (öffentliche Downloads der App)

Ohne das echte Passwort zu kennen, kann niemand mehr Owner-Zugriff auf
seiner eigenen Kopie der App bekommen — das Premium-/Bezahlsystem bleibt
dadurch für alle Nutzer fair und funktionsfähig.

## 📧 Update — E-Mail-Versand jetzt auch über den Server (kein Passwort in der App)

Genau wie beim Owner-Login: Die App kennt kein E-Mail-Passwort mehr selbst
— sie fragt diesen Server, und der Server verschickt die E-Mail mit
**seinen eigenen** (nur hier hinterlegten) Zugangsdaten.

### Das musst du einmalig auf Render eintragen

Bei **Environment**, zusätzlich zu `OWNER_PASSWORD`:

| Name | Wert |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `lisawer008@gmail.com` |
| `SMTP_PASSWORD` | dein **App-Passwort** (das neue, nachdem du das alte gelöscht hast!) |
| `SMTP_FROM` | `lisawer008@gmail.com` |

Danach funktioniert der E-Mail-Versand auf **jedem** Gerät automatisch,
ganz ohne dass irgendwer (auch nicht dein eigenes Gerät) das Passwort
lokal eintragen muss — die App fragt einfach den Server. Nur falls der
Server mal nicht erreichbar ist, fällt die App auf ein lokal eingetragenes
SMTP zurück (falls vorhanden) oder zeigt den Code direkt in der App an.

### Schutz gegen Missbrauch
- Max. 5 E-Mails pro Adresse pro Stunde (verhindert Spam-Missbrauch)
- E-Mail-Adressen werden grob validiert, bevor überhaupt versucht wird zu senden

## 🌍 Update — Premium-Status ist jetzt an dein Konto gebunden, nicht ans Gerät

**Genau das Problem gelöst:** Kauft jemand z. B. Lifetime-Premium, wechselt
danach den PC oder installiert die App neu, war das Premium bisher weg
(weil es nur lokal auf dem alten Gerät gespeichert war). Jetzt merkt sich
der **Server** zusätzlich, welche E-Mail-Adresse Premium hat — komplett
unabhängig vom Gerät.

### Was neu ist
- Die Checkout-Webseite fragt jetzt zusätzlich nach der E-Mail-Adresse
  (derselben wie in der App) — der Kauf wird direkt daran gebunden
- Bei jedem Login/jeder Registrierung fragt die App automatisch den
  Server: "Hat diese E-Mail schon Premium?" — falls ja, wird es
  automatisch übernommen, auch auf einem brandneuen, leeren Gerät
- Auch Admin-vergebene Geschenk-Codes werden jetzt zusätzlich am Konto
  festgemacht (nicht nur lokal)
- **Nie verkürzen:** Hat jemand z. B. schon Lifetime, und kauft aus
  Versehen nochmal 30 Tage, bleibt Lifetime bestehen — es wird immer der
  großzügigere Stand übernommen

Keine neuen Umgebungsvariablen nötig — das läuft direkt über eine neue
Tabelle in der bestehenden Datenbank. Mit mehreren Tests abgesichert,
inklusive dem genauen Szenario "Lifetime kaufen → PC wechseln →
App neu installieren → Premium ist automatisch wieder da".

## ☁️ Update — Komplette Cloud-Sicherung (Einstellungen, Verlauf, Favoriten, Abos)

Zusätzlich zum Premium-Status kann jetzt der **komplette lokale Zustand**
an ein Konto gebunden gesichert werden — Design, Farben, Schriftart,
Download-Verlauf, Favoriten und Kanal-Abos. Läuft über zwei neue
Endpunkte (`/api/backup-settings`, `/api/restore-settings`), keine neuen
Umgebungsvariablen nötig. Das E-Mail-Passwort/SMTP wird dabei **nie**
mitgesichert — bleibt immer lokal pro Gerät.

Mit vollständigem Test abgesichert: Sicherung auf "PC 1" → komplett
identisch auf "PC 2" wiederhergestellt (Design, Verlauf, Favoriten, Abos),
inklusive Schutz gegen zu große/missbräuchliche Sicherungen (3-MB-Grenze).

## 🎁 Update — Premium an eine beliebige E-Mail verschenken

Neuer Endpunkt `/api/admin-grant-premium` — geschützt durch dasselbe
`OWNER_PASSWORD` wie der Owner-Login. Funktioniert auch für Personen, die
die App noch nie genutzt haben: sobald sie sich mit der beschenkten
E-Mail-Adresse registrieren/anmelden, ist ihr Premium automatisch da
(über den bestehenden Konto-Sync-Mechanismus). Verschickt zusätzlich eine
zweisprachige (DE + EN) Glückwunsch-Mail über die server-eigenen
SMTP-Zugangsdaten.

Mit einem echten End-zu-End-Test bestätigt: Owner verschenkt 90 Tage an
eine wildfremde Person → diese Person hätte, würde sie die App
installieren, ihr Premium sofort automatisch aktiv.

## 🌍 Update — Liste aller weltweiten Nutzer für den Owner

Neuer Endpunkt `/api/admin-list-accounts` (geschützt durch OWNER_PASSWORD)
— zeigt jede E-Mail-Adresse, die jemals mit der App interagiert hat
(Login, Registrierung, Kauf), nicht nur lokal bekannte. Jede App-Instanz
"meldet sich" automatisch beim Server (über den schon bestehenden
Premium-Sync-Check), wodurch sich diese Liste von selbst füllt.

Mit Test abgesichert: 3 simulierte Nutzer weltweit → Owner sieht alle 3,
ohne sie vorher gekannt zu haben; falsches Passwort → Liste bleibt geschützt.

## ⏰ Server dauerhaft "wach" halten (kein Einschlafen mehr)

Der kostenlose Render-Tarif schläft nach 15 Minuten Inaktivität ein und
braucht dann beim nächsten Aufruf bis zu 50 Sekunden zum Aufwachen. Zwei
Möglichkeiten, das zu vermeiden:

### Option 1 — Kostenlos: externer "Wach-Halte"-Dienst
Ein kostenloser Dienst ruft alle 10 Minuten deinen Server auf, damit er nie
lange genug inaktiv ist zum Einschlafen:
1. Geh auf **https://cron-job.org** (oder alternativ uptimerobot.com)
2. Kostenloses Konto erstellen
3. Neuen "Cronjob"/Monitor anlegen:
   - URL: `https://downloader3-backend.onrender.com`
   - Intervall: alle 10 Minuten
4. Speichern — läuft danach automatisch im Hintergrund, kostenlos

### Option 2 — Bezahlt: Render-Tarif hochstufen
Der "Starter"-Tarif (ca. 7 $/Monat) schläft nie ein. Auf Render:
dein Service → "Settings" → "Instance Type" → "Starter" auswählen.

**Empfehlung:** Fang mit Option 1 (kostenlos) an — reicht für die meisten
Fälle völlig aus.

## 🎨 Update — KI-Studio jetzt KOSTENLOS für alle Nutzer (kein eigener API-Schlüssel nötig)

Neue Endpunkte: `/api/ai-text`, `/api/ai-image`, `/api/ai-video`,
`/api/ai-video-status`, `/api/ai-video-download` — verwenden EINEN
gemeinsamen Gemini-API-Schlüssel (als Umgebungsvariable), den ALLE Nutzer
der App automatisch mitbenutzen. Niemand muss mehr selbst einen
API-Schlüssel besorgen.

### ⚠️ Wichtig, bevor du das aktivierst
Da alle Nutzer denselben Schlüssel teilen, **trägst du die Kosten** dafür
(auch wenn Gemini eine kostenlose Stufe hat — bei vielen Nutzern kann das
gemeinsame Kontingent schneller aufgebraucht sein). Eingebauter Schutz:
Rate-Begrenzung pro E-Mail (Text: 30/Std., Bilder: 15/Std., Video: 5/Std.)
— das verhindert groben Missbrauch, ersetzt aber keine echte
Kostenkontrolle bei sehr großem Nutzerkreis.

### Einrichtung
1. Eigenen (kostenlosen) API-Schlüssel holen: **https://aistudio.google.com/apikey**
2. Render → dein Backend-Service → Environment → **`GEMINI_API_KEY`**
   eintragen
3. Speichern — läuft automatisch für alle Nutzer der App, ohne dass sie
   selbst etwas einrichten müssen

### Sicherheits-Hinweis
Der geteilte Schlüssel wird **nie** an die App weitergegeben — auch nicht
beim Video-Download (der Server lädt das fertige Video selbst herunter und
reicht nur die Datei weiter, nicht die Zugangsdaten).

## 📧 E-Mail-Versand reparieren: "Network unreachable" (Render Free)

**Das Problem:** Render blockiert im kostenlosen Tarif ALLE ausgehenden
SMTP-Verbindungen (Ports 25/465/587) — als Spam-Schutz, offiziell
dokumentiert. Deshalb schlägt jeder direkte E-Mail-Versand über
smtp.gmail.com von dort mit "Network unreachable" fehl, bei allen
Nutzern weltweit. Kein Bug in der App — eine Hoster-Sperre.

**Die Lösung (eingebaut):** Der Server verschickt E-Mails jetzt über die
Brevo-HTTPS-API (Port 443, nie blockiert). Kostenlos bis 300 E-Mails
pro Tag, keine eigene Domain nötig. Einrichtung dauert ~5 Minuten:

### Schritt 1 — Brevo-Konto anlegen
1. https://www.brevo.com öffnen → kostenlos registrieren
   (am besten mit derselben Gmail-Adresse, von der die App-Mails
   kommen sollen).
2. Bestätigungs-Mail anklicken, Anmeldung abschließen.

### Schritt 2 — Absender-Adresse verifizieren
1. In Brevo: oben rechts aufs Profil → "Senders & Domains" →
   Reiter "Senders".
2. Deine Absender-Adresse (z. B. deine Gmail) als Sender hinzufügen —
   Brevo schickt eine Bestätigungs-Mail an diese Adresse → Link klicken.

### Schritt 3 — API-Schlüssel erzeugen
1. In Brevo: Profil → "SMTP & API" → Reiter "API Keys" →
   "Generate a new API key" → Namen vergeben (z. B. "downloader3") →
   Schlüssel KOPIEREN (wird nur einmal angezeigt!).

### Schritt 4 — Auf Render eintragen
1. https://dashboard.render.com → deinen Service
   (downloader3-backend) anklicken → links "Environment".
2. Neue Umgebungsvariable: Key = BREVO_API_KEY, Value = der kopierte
   Schlüssel → "Save Changes".
3. Prüfen, dass SMTP_FROM (oder SMTP_USER) auf die in Schritt 2
   verifizierte Absender-Adresse gesetzt ist.
4. Die neue app.py ins Backend-Repo hochladen (falls noch nicht
   geschehen) — Render deployt automatisch neu.

### Schritt 5 — Testen
In der App einen Verifizierungs-Code anfordern (Registrierung) —
die Mail sollte innerhalb von Sekunden ankommen. Falls nicht, zeigt
die App jetzt die ECHTE Fehlermeldung des Servers an (dank des
verbesserten Fehler-Durchreichens in main.py).

**Hinweise:**
- Die alten SMTP-Umgebungsvariablen können bleiben — sie dienen als
  Fallback auf Hostern ohne SMTP-Sperre und SMTP_FROM/SMTP_USER wird
  weiterhin als Absender-Adresse verwendet.
- Optional: BREVO_FROM_NAME setzen (Anzeigename, Standard
  "Downloader<3").
- Brevo Free hängt an jede Mail einen kleinen "Sent with Brevo"-Hinweis
  an — bei einem Gratis-Dienst fair und für Verifizierungs-Codes
  unproblematisch.
