#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Downloader<3 — moderner YouTube/Media Downloader
Sprachen: Deutsch / Englisch
Free:    nur MP4 von YouTube, Name 1x gratis änderbar
Premium: MP3, WAV, M4A + direkte Datei-Downloads (PNG, JPG, ...) + Glitzer-Namen
Owner:   felixwerther1@gmail.com & lisa.werther@proton.me
         → automatisch Premium für immer + Admin-Panel + Geschenk-Codes
made by Lisa, Felix
"""

import os
import re
import sys
import json
import shutil
import hashlib
import random
import secrets
import threading
import datetime
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import smtplib
from email.mime.text import MIMEText

# Versteckt auf Windows die schwarzen CMD-Fenster, die ffmpeg/yt-dlp
# beim Herunterladen öffnen würden. (Als Klasse, weil yt-dlp von
# subprocess.Popen erben muss!)
if sys.platform == "win32":
    class _HiddenPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            si = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = si
            kwargs["creationflags"] = (kwargs.get("creationflags", 0)
                                       | 0x08000000)  # CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = _HiddenPopen

import tkinter as tk
import io
import customtkinter as ctk
try:
    from PIL import Image
except ImportError:
    Image = None
from tkinter import messagebox, filedialog, colorchooser

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None

# ----------------------------------------------------------------------------
# Konstanten
# ----------------------------------------------------------------------------
OWNER_EMAILS = {"felixwerther1@gmail.com", "lisa.werther@proton.me"}
# Kein OWNER_PASSWORD mehr hier — das echte Passwort lebt nur noch als
# Umgebungsvariable auf dem Backend-Server, niemals im verteilten Code.
OWNER_NAMES = {"felixwerther1@gmail.com": "Felix",
               "lisa.werther@proton.me": "Lisa"}
APP_NAME = "Downloader<3"
APP_VERSION = "1.1.0"
CHANGELOG = {
    "1.1.0": {
        "de": ["🖼️ Wallpaper-Download (Premium) — passt Bilder automatisch an iOS/Android/PC an",
              "🌍 Untertitel-Übersetzung für 14+ Sprachen, jetzt auch direkt auf der Download-Seite",
              "🔤 Eigene Schriftart & -größe in den Einstellungen",
              "🐢 Sparmodus für ältere/schwächere Computer",
              "⭐ Favoriten für häufig genutzte Links",
              "💾 Komplette Einstellungen sichern & wiederherstellen",
              "🎵🎬 Schnellwahl-Buttons für Musik/Video-Format",
              "🔔 Ton bei fertigem Download (abschaltbar)",
              "Diverse Bugfixes: Vorschau-Bild, Textfarben bei hellen Akzentfarben, fehlende Scrollbalken"],
        "en": ["🖼️ Wallpaper download (Premium) — auto-fits images for iOS/Android/PC",
              "🌍 Subtitle translation for 14+ languages, now also right on the download page",
              "🔤 Custom font & size in Settings",
              "🐢 Performance mode for older/weaker computers",
              "⭐ Favorites for frequently used links",
              "💾 Full settings backup & restore",
              "🎵🎬 Quick preset buttons for Music/Video format",
              "🔔 Sound when download finishes (can be disabled)",
              "Various bugfixes: preview thumbnail, text colors on light accent colors, missing scrollbars"],
    },
}
MADE_BY = "Created by developers Lisa & Felix"
APP_DIR = os.path.join(os.path.expanduser("~"), ".downloader3")
DATA_FILE = os.path.join(APP_DIR, "data.json")
EMAILS_FILE = os.path.join(APP_DIR, "emails.txt")
FFMPEG_DIR = os.path.join(APP_DIR, "ffmpeg")
FFMPEG_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/latest/"
              "download/ffmpeg-master-latest-win64-gpl.zip")

# Fertige SMTP-Voreinstellungen für gängige E-Mail-Anbieter — füllt Server/
# Port/SSL automatisch aus, Benutzername/Passwort/Absender bleiben frei.
SMTP_PRESETS = {
    "Gmail": {"host": "smtp.gmail.com", "port": 587, "use_ssl": False},
    "Outlook / Hotmail": {"host": "smtp.office365.com", "port": 587,
                          "use_ssl": False},
    "GMX": {"host": "mail.gmx.net", "port": 587, "use_ssl": False},
    "Web.de": {"host": "smtp.web.de", "port": 587, "use_ssl": False},
    "Yahoo Mail": {"host": "smtp.mail.yahoo.com", "port": 587,
                   "use_ssl": False},
    "iCloud Mail": {"host": "smtp.mail.me.com", "port": 587,
                    "use_ssl": False},
    "ProtonMail (Bridge)": {"host": "127.0.0.1", "port": 1025,
                            "use_ssl": False},
}

NAME_STYLES = ["none", "glitter", "rainbow", "hearts", "fire", "pulse"]

FREE_FORMATS = ["mp4"]
PREMIUM_FORMATS = ["mp4", "mp3", "wav", "m4a", "webm"]

RES_LIST = ["480p", "720p", "1080p", "1440p", "4K"]
RES_FREE_SET = {"480p", "720p"}
RES_HEIGHT = {"480p": 480, "720p": 720, "1080p": 1080,
              "1440p": 1440, "4K": 2160}
# Zusätzlich zur reinen Pixelangabe die gängige Kurzform anzeigen —
# kommt beim Nutzer klarer rüber als nackte Zahlen.
RES_DISPLAY = {
    "480p": "480p",
    "720p": "720p · HD",
    "1080p": "1080p · 1K",
    "1440p": "1440p · 2K",
    "4K": "4K · Ultra HD",
}
RES_DISPLAY_REV = {v: k for k, v in RES_DISPLAY.items()}

PLATFORM_FORMATS = {
    "youtube": {"free": ["mp4"],
                "premium": ["mp3", "wav", "webm", "mkv", "mov", "3gp",
                            "m4a", "aac", "flac", "ogg", "png", "jpg"]},
    "tiktok": {"free": ["mp4"],
               "premium": ["mp3", "wav", "mov", "webm", "gif",
                           "jpg", "png"]},
    "instagram": {"free": ["mp4"],
                  "premium": ["mp3", "gif", "wav", "webm", "m4a",
                              "mov", "jpg", "png"]},
    "facebook": {"free": ["mp4"],
                 "premium": ["mp3", "gif", "wav", "m4a", "jpg",
                             "png", "webp"]},
    "browser": {"free": ["mp4"],
                "premium": ["mp3", "wav", "webm", "mkv", "mov",
                            "jpg", "png", "pdf"]},
}
AUDIO_FMTS = {"mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"}
IMAGE_FMTS = {"jpg", "png", "webp", "gifimg"}
VIDEO_FMTS = {"mp4", "webm", "mkv", "mov", "3gp", "gif"}

# Kategorie + Symbol pro Format — damit im Format-Menü nicht nur "wav" oder
# "mkv" steht, sondern klar wird, WAS das eigentlich ist (Ton/Video/Bild/Doc).
FORMAT_INFO = {
    "mp4": ("🎥", "Video"), "webm": ("🎥", "Video"), "mkv": ("🎥", "Video"),
    "mov": ("🎥", "Video"), "3gp": ("🎥", "Video"),
    "gif": ("🎬", "Animation"),
    "mp3": ("🎵", "Nur Ton"), "wav": ("🎵", "Nur Ton"),
    "m4a": ("🎵", "Nur Ton"), "aac": ("🎵", "Nur Ton"),
    "flac": ("🎵", "Nur Ton"), "ogg": ("🎵", "Nur Ton"),
    "jpg": ("🖼", "Bild"), "png": ("🖼", "Bild"), "webp": ("🖼", "Bild"),
    "pdf": ("📄", "Dokument"),
}
FORMAT_INFO_EN = {
    "mp4": ("🎥", "Video"), "webm": ("🎥", "Video"), "mkv": ("🎥", "Video"),
    "mov": ("🎥", "Video"), "3gp": ("🎥", "Video"),
    "gif": ("🎬", "Animation"),
    "mp3": ("🎵", "Audio only"), "wav": ("🎵", "Audio only"),
    "m4a": ("🎵", "Audio only"), "aac": ("🎵", "Audio only"),
    "flac": ("🎵", "Audio only"), "ogg": ("🎵", "Audio only"),
    "jpg": ("🖼", "Image"), "png": ("🖼", "Image"), "webp": ("🖼", "Image"),
    "pdf": ("📄", "Document"),
}

ACCENTS = {
    "Violet":  {"main": "#8B5CF6", "hover": "#7C3AED"},
    "Cyan":    {"main": "#06B6D4", "hover": "#0891B2"},
    "Emerald": {"main": "#10B981", "hover": "#059669"},
    "Rose":    {"main": "#F43F5E", "hover": "#E11D48"},
    "Amber":   {"main": "#F59E0B", "hover": "#D97706"},
}

CORNER_STYLES = {"eckig": 0, "rund": 12, "oval": 25}

YOUTUBE_RE = re.compile(
    r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE
)

PLATFORM_URL_RE = {
    "youtube": YOUTUBE_RE,
    "tiktok": re.compile(r"^(https?://)?(www\.|vm\.|vt\.|m\.)?tiktok\.com/",
                         re.IGNORECASE),
    "instagram": re.compile(r"^(https?://)?(www\.)?instagram\.com/",
                            re.IGNORECASE),
    "facebook": re.compile(
        r"^(https?://)?((www|m|web)\.)?(facebook\.com|fb\.watch)/",
        re.IGNORECASE),
}

# 🖼️ Wallpaper-Download (Premium): Auflösungen pro Gerät.
# PC/Windows wird gestreckt (füllt den Monitor exakt aus), Handys werden
# stattdessen mittig zugeschnitten (verzerrt sonst Gesichter/Motive zu stark).
WALLPAPER_RESOLUTIONS = {
    "ios": [("iPhone (1170×2532)", 1170, 2532),
            ("iPhone Plus (1284×2778)", 1284, 2778),
            ("iPad (2048×2732)", 2048, 2732)],
    "android": [("Full HD+ (1080×2400)", 1080, 2400),
               ("QHD+ (1440×3200)", 1440, 3200),
               ("Tablet (1200×1920)", 1200, 1920)],
    "windows": [("Full HD (1920×1080)", 1920, 1080),
               ("2K (2560×1440)", 2560, 1440),
               ("4K (3840×2160)", 3840, 2160)],
}

# ----------------------------------------------------------------------------
# Übersetzungen
# ----------------------------------------------------------------------------
T = {
    "de": {
        "choose_language": "Welche Sprache bevorzugst du?",
        "german": "Deutsch",
        "english": "English",
        "continue": "Weiter",
        "welcome": "Willkommen bei Downloader<3",
        "create_account": "Konto erstellen",
        "login": "Anmelden",
        "email": "E-Mail",
        "password": "Passwort",
        "register": "Registrieren",
        "have_account": "Schon ein Konto? Anmelden",
        "no_account": "Noch kein Konto? Registrieren",
        "invalid_email": "Bitte gib eine gültige E-Mail-Adresse ein.",
        "pw_too_short": "Das Passwort muss mindestens 4 Zeichen haben.",
        "user_exists": "Diese E-Mail ist bereits registriert.",
        "wrong_login": "E-Mail oder Passwort ist falsch.",
        "download": "Download",
        "settings": "Einstellungen",
        "premium": "Premium",
        "admin": "Admin",
        "logout": "Abmelden",
        "paste_link": "Link hier einfügen (YouTube, TikTok, Instagram, Facebook)...",
        "paste_link_premium": "Link hier einfügen (YouTube, Bilder, direkte Dateien)...",
        "format": "Format",
        "start_download": "Herunterladen",
        "downloading": "Wird heruntergeladen...",
        "done": "Fertig!",
        "dl_complete": "Download abgeschlossen",
        "dl_complete_msg": "Deine Datei wurde erfolgreich heruntergeladen:",
        "dl_failed": "Download fehlgeschlagen",
        "only_youtube_free": "Mit der Gratis-Version kannst du nur YouTube-Links herunterladen. Hol dir Premium für andere Links!",
        "format_locked": "Dieses Format ist nur mit Premium verfügbar. Gratis: nur MP4.",
        "no_ytdlp": "yt-dlp ist nicht installiert. Bitte führe aus:  pip install yt-dlp",
        "language": "Sprache",
        "notifications": "Benachrichtigungen",
        "notifications_desc": "Benachrichtigung anzeigen, wenn ein Download fertig ist",
        "accent_color": "Design-Farbe",
        "corner_style": "Aussehen (Form)",
        "appearance": "Modus",
        "dark": "Dunkel",
        "light": "Hell",
        "download_folder": "Download-Ordner",
        "choose_folder": "Ordner wählen",
        "square": "Eckig",
        "round": "Rund",
        "oval": "Oval",
        "premium_title": "Downloader<3 Premium",
        "premium_active": "Premium ist aktiv",
        "premium_until": "Premium aktiv bis:",
        "premium_forever": "Premium aktiv: unbegrenzt",
        "premium_pitch": "Mit Premium bekommst du:",
        "perk_1": "• Alle Formate: MP3, WAV, M4A, WEBM & MP4",
        "perk_2": "• Downloads von anderen Links (Bilder: PNG, JPG, direkte Dateien)",
        "perk_3": "• Unterstützt die Entwicklung von Downloader<3",
        "buy_premium": "Premium kaufen – 30 Tage (Beta)",
        "buy_demo_note": "Hinweis: Premium befindet sich noch in der Beta-Phase.",
        "purchased": "Premium wurde für 30 Tage aktiviert. Viel Spaß!",
        "owner_badge": "OWNER — Premium für immer",
        "admin_title": "Admin-Panel (nur Owner)",
        "admin_desc": "Vergib Premium an registrierte Nutzer und lege die Laufzeit fest.",
        "user_email": "E-Mail des Nutzers",
        "duration_days": "Laufzeit (Tage)",
        "forever": "Unbegrenzt",
        "grant": "Premium vergeben",
        "revoke": "Premium entziehen",
        "user_not_found": "Kein Nutzer mit dieser E-Mail gefunden.",
        "granted": "Premium vergeben an",
        "revoked": "Premium entzogen von",
        "registered_users": "Registrierte Nutzer",
        "status_free": "Gratis",
        "status_premium": "Premium",
        "refresh": "Aktualisieren",
        "hello": "Hallo",
        "get_premium_hint": "Nur MP4 verfügbar — hol dir Premium für alle Formate!",
        "custom_name": "Eigener Name",
        "name_placeholder": "Neuer Anzeigename...",
        "save_name": "Name speichern",
        "name_saved": "Name gespeichert!",
        "name_free_hint": "Du kannst deinen Namen 1× gratis ändern.",
        "name_once_used": "Gratis-Nutzer können ihren Namen nur einmal ändern. Hol dir Premium!",
        "name_style": "Glitzer-Effekt (Premium)",
        "style_none": "Kein Effekt",
        "style_glitter": "✨ Glitzer",
        "style_rainbow": "🌈 Regenbogen",
        "style_hearts": "💖 Herzen",
        "style_locked": "Effekte sind nur für Premium-Nutzer.",
        "redeem_code": "Code einlösen",
        "code_placeholder": "z. B. DL-A1B2-C3D4",
        "redeem": "Einlösen",
        "code_ok": "Code eingelöst — Premium ist aktiviert! 🎉",
        "code_bad": "Code ist ungültig oder wurde schon benutzt.",
        "gift_code_title": "🎁 Geschenk-Code erstellen",
        "gift_code_desc": "Erstellt einen zufälligen Code (nur 1× gültig), den du verschicken kannst.",
        "create_code": "Code erstellen",
        "your_code": "Dein Code:",
        "codes_list": "Erstellte Codes",
        "code_unused": "offen",
        "code_used_by": "eingelöst von",
        "days_short": "Tage",
        "color_mode": "Farbe anwenden auf",
        "mode_full": "Ganzes Programm",
        "mode_accent": "Nur Icons & Schrift",
        "checking": "Video wird geprüft...",
        "cancelled": "Abgebrochen.",
        "history": "Letzte Downloads",
        "open_folder": "📂 Ordner öffnen",
        "ask_save": "Vor jedem Download nach Speicherort fragen",
        "no_ffmpeg": "FFmpeg ist nicht installiert! Für MP3/WAV bitte einmal im Terminal ausführen:  winget install ffmpeg  — danach PC neu starten.",
        "ffmpeg_dl": "FFmpeg wird einmalig automatisch installiert (~90 MB)...",
        "design_style": "Design-Stil",
        "design_classic": "Classic 💜",
        "design_retro": "Retro 🎮",
        "custom_color": "Eigene Farbe (Hex-Code)",
        "apply": "Anwenden",
        "invalid_hex": "Ungültiger Hex-Code — z. B. #4F8EFF",
        "radius_slider": "Ecken-Rundung fein einstellen (px)",
        "effects": "Effekte",
        "effect_none": "Kein",
        "effect_aurora": "🌈 Aurora",
        "effect_snow": "❄ Schnee",
        "style_fire": "🔥 Feuer",
        "style_pulse": "💫 Puls",
        "beta_msg": "Premium ist noch in der Beta-Phase und kann deshalb noch nicht gekauft werden.",
        "beta_gift": "Als Dankeschön bekommst du einmalig einen Gutschein für 1 Tag Premium! Löse ihn in den Einstellungen unter 'Code einlösen' ein:",
        "beta_already": "Deinen Beta-Gutschein hast du bereits erhalten.",
        "owner_toggle": "Premium an/aus (Gratis-Ansicht testen)",
        "el_colors_title": "Einzelne Elemente färben",
        "el_hint": "Hex-Code eingeben (z. B. #FF66AA) und Anwenden — ✕ setzt auf automatisch zurück.",
        "el_window": "Hintergrund",
        "el_sidebar": "Seitenleiste",
        "el_card": "Karten",
        "el_button": "Buttons",
        "el_name": "Name (Anzeigename)",
        "el_scrollbar": "Scrollbalken",
        "matching_title": "Matching Mode — automatische Farbanpassung",
        "matching_hint": "Wähle eine Farbrichtung (z. B. Pink) — die App erstellt daraus automatisch ein gut lesbares, zusammenpassendes Design für Hintergrund, Seitenleiste, Karten, Buttons und Name.",
        "matching_apply": "Design erstellen",
        "matching_reset": "Matching zurücksetzen",
        "design_modern": "Modern ✨",
        "platform": "Plattform",
        "resolution": "Auflösung",
        "nowm": "🚫 Ohne Wasserzeichen",
        "direct_link": "🔗 Direkt-Link",
        "auto_label": "🪄 Auto",
        "res_locked": "Diese Auflösung ist nur mit Premium verfügbar. Gratis: 480p & 720p.",
        "platform_mismatch": "Der Link passt nicht zur gewählten Plattform.",
        "direct_premium": "Direkt-Links (Bilder, Dateien) sind nur mit Premium verfügbar.",
        "converting": "Wird umgewandelt...",
        "no_image": "In diesem Link wurde kein Bild gefunden.",
        "web_browser": "🌐 Web-Browser (beliebiger Link)",
        "ai_mode": "🤖 KI-Modus (automatisch)",
        "ai_hint": "🤖 Die KI erkennt automatisch Plattform und beste Auflösung — das Format kannst du hier selbst wählen.",
        "ai_locked": "Der KI-Modus ist nur mit Premium verfügbar.",
        "auto_field": "🤖 automatisch",
        "premium_required_title": "Premium-Funktion",
        "see_premium": "★ Premium ansehen",
        "locked_platform": "Diese Quelle ist nur mit Premium verfügbar.",
        "verify_title": "✉️ E-Mail bestätigen",
        "verify_sending": "Code wird gesendet...",
        "verify_sent": "Wir haben einen 6-stelligen Code gesendet an:",
        "verify_fallback": "E-Mail-Versand ist noch nicht eingerichtet — hier ist dein Code, damit du trotzdem weitermachen kannst:",
        "verify_code_ph": "6-stelliger Code",
        "verify_button": "Bestätigen",
        "verify_resend": "Code erneut senden",
        "verify_cancel": "Abbrechen / abmelden",
        "verify_wrong": "Der Code ist falsch.",
        "verify_expired": "Der Code ist abgelaufen — bitte fordere einen neuen an.",
        "verify_ok": "E-Mail bestätigt! Willkommen 🎉",
        "smtp_title": "✉️ E-Mail-Versand (SMTP)",
        "smtp_desc": "Zugangsdaten für den Versand von Bestätigungscodes. Am besten ein eigenes App-Passwort verwenden (z. B. bei Gmail), nicht dein normales Passwort — es wird lokal auf diesem PC gespeichert.",
        "smtp_host": "SMTP-Server",
        "smtp_port": "Port",
        "smtp_user": "Benutzername",
        "smtp_pass": "App-Passwort",
        "smtp_from": "Absender-Adresse",
        "smtp_save": "Speichern",
        "smtp_test": "Test-Mail senden",
        "smtp_test_ok": "Test-Mail wurde gesendet — bitte Posteingang prüfen.",
        "smtp_test_fail": "Senden fehlgeschlagen:",
        "smtp_not_set": "Bitte zuerst alle Felder ausfüllen und speichern.",
        "smtp_guide": "📋 Anbieter wählen (füllt Server/Port automatisch aus), dann Benutzername + App-Passwort eintragen. Fast jeder Anbieter verlangt heute ein separates App-Passwort statt des normalen Passworts:\n• Gmail: Google-Konto → Sicherheit → 2-Faktor aktivieren → 'App-Passwörter'\n• Outlook/Hotmail: account.microsoft.com → Sicherheit → 'App-Kennwörter'\n• GMX / Web.de: Einstellungen → 'POP3/IMAP-Zugang' aktivieren + App-Passwort erzeugen\n• Yahoo: Account-Sicherheit → 'App-Passwörter erzeugen'\n• iCloud: appleid.apple.com → Sicherheit → 'App-spezifisches Passwort'\n• ProtonMail: braucht die kostenpflichtige 'ProtonMail Bridge'-App (normales SMTP geht bei Proton sonst nicht)",
        "smtp_provider": "Anbieter (Voreinstellung)",
        "smtp_ssl": "SSL verwenden (Port 465 statt 587)",
        "email_tpl_title": "✏️ E-Mail-Text bearbeiten",
        "email_tpl_desc": "Platzhalter: {code} = Bestätigungscode, {app} = App-Name, {made_by} = Entwickler-Zeile, {email} = Empfänger-Adresse.",
        "email_tpl_subject": "Betreff",
        "email_tpl_body": "Nachricht",
        "email_tpl_save": "Text speichern",
        "email_tpl_reset": "Auf Standard zurücksetzen",
        "email_tpl_saved": "✓ E-Mail-Text gespeichert.",
        "email_tpl_no_code": "⚠ Achtung: {code} kommt im Text nicht vor — der Code wird trotzdem automatisch angehängt.",
        "email_tpl_preview": "Vorschau senden",
        "delete_user_title": "Nutzer löschen",
        "delete_user_confirm": "Dieses Konto wirklich unwiderruflich löschen?",
        "low_contrast_warn": "Achtung: Text könnte auf dieser Farbe schwer lesbar sein.",
        "pick_color": "Farbe wählen",
        "reset_appearance": "🔄 Design auf Standard zurücksetzen",
        "reset_appearance_confirm": "Farben, Form, Effekte und Design-Stil auf die Werkseinstellung zurücksetzen? (SMTP, Sprache und Download-Ordner bleiben unverändert.)",
        "reset_done": "✓ Zurückgesetzt.",
        "export_theme": "💾 Design exportieren",
        "import_theme": "📂 Design importieren",
        "export_ok": "✓ Design gespeichert.",
        "import_ok": "✓ Design geladen.",
        "import_fail": "✗ Datei konnte nicht gelesen werden.",
        "preview_title": "👁 Live-Vorschau",
        "autostart": "Mit Windows starten",
        "info_updates": "ℹ️ Info & Updates",
        "version_label": "Version",
        "check_updates": "🔄 Nach Updates suchen",
        "up_to_date": "✓ Du bist auf dem neuesten Stand.",
        "concurrent_dl": "Gleichzeitige Downloads (max.)",
        "concurrent_note": "Gilt für die Warteschlange (📋 Mehrere Links) auf der Download-Seite — legt fest, wie viele Links gleichzeitig heruntergeladen werden.",
        "bandwidth_limit": "Geschwindigkeits-Limit",
        "bandwidth_unlimited": "Unbegrenzt",
        "bandwidth_kbps": "KB/s",
        "proxy_title": "Proxy / VPN",
        "proxy_ph": "z. B. http://user:pass@host:port oder socks5://host:port",
        "subs_download": "Untertitel automatisch mitladen (SRT/VTT, falls verfügbar)",
        "clipboard_watch": "Kopierte Links automatisch erkennen & einfügen",
        "auto_sort": "Automatisch in Unterordner sortieren (Bilder/Videos/Musik)",
        "titlebar_progress": "Fortschritt in der Titelleiste anzeigen (z. B. \"App — 42%\")",
        "danger_zone": "⚠️ Zurücksetzen & Sichern",
        "history_search_ph": "🔍 Verlauf durchsuchen...",
        "history_no_match": "Keine Treffer.",
        "confirm_yes": "Ja, fortfahren",
        "confirm_no": "Abbrechen",
        "fix_window": "🔧 Fenster-Form reparieren",
        "filename_tpl_title": "📝 Dateinamens-Vorlage",
        "filename_tpl_desc": "Platzhalter: {title} = Videotitel, {channel} = Kanal/Ersteller, {date} = Datum, {platform} = Plattform.",
        "filename_tpl_ph": "{title}",
        "smart_resume_title": "🔄 Smart Resume",
        "smart_resume_desc": "Bricht das Internet während eines Downloads ab, wird automatisch weitergemacht statt neu zu starten — bei YouTube/TikTok/Insta/Facebook übernimmt das yt-dlp automatisch, bei Direkt-Links (Bilder/PDFs) setzt die App selbst dort fort, wo sie aufgehört hat.",
        "schedule_title": "🕑 Später starten",
        "schedule_time_ph": "z. B. 02:00",
        "scheduled_for": "Geplant für",
        "invalid_time": "Bitte Uhrzeit im Format HH:MM eingeben (z. B. 02:00).",
        "silent_mode": "🔇 Ruhemodus (alle Benachrichtigungen stummschalten)",
        "browser_ext_title": "🧩 Browser-Erweiterung",
        "browser_ext_desc": "Mit der beiliegenden Erweiterung kannst du per Rechtsklick im Browser Links direkt an diese App senden. Installation: chrome://extensions öffnen → Entwicklermodus an → 'Entpackte Erweiterung laden' → den Ordner 'browser-extension' auswählen.",
        "browser_ext_toggle": "Verbindung zur Browser-Erweiterung aktivieren",
        "link_received": "🔗 Link aus dem Browser empfangen!",
        "duplicate_title": "Bereits heruntergeladen",
        "duplicate_msg": "Diesen Link hast du bereits heruntergeladen:",
        "duplicate_continue": "Trotzdem herunterladen",
        "buy_on_website": "Premium auf unserer Webseite kaufen (PayPal)",
        "checkout_title": "🌐 Premium-Webseite (PayPal-Kauf)",
        "checkout_desc": "Trägt die Adressen deiner gehosteten Checkout-Webseite und deines Backend-Servers ein. Beides musst du selbst einrichten (siehe README.md des Backends) — Anthropic/Claude kann dafür keinen Server bereitstellen.",
        "backend_url_label": "Backend-Server-URL",
        "checkout_url_label": "Checkout-Webseiten-URL",
        "try_trial": "1 Tag kostenlos testen",
        "trial_active_title": "Viel Spaß mit Premium!",
        "trial_active_msg": "Du hast jetzt 1 Tag Premium freigeschaltet — genieß Downloader<3 in voller Pracht! 🎉",
        "trial_already_title": "Schon getestet",
        "trial_already_msg": "Deinen kostenlosen Testtag hast du bereits genutzt. Für dauerhaftes Premium schau auf der Webseite vorbei!",
        "sub_lang_label": "Untertitel-Sprache",
        "sub_lang_all": "Alle verfügbaren",
        "embed_metadata": "🎵 Titel, Interpret & Cover-Bild einbetten",
        "stats_title": "📊 Statistik",
        "stats_total_files": "Downloads insgesamt",
        "stats_total_size": "Gesamtgröße",
        "stats_top_platform": "Häufigste Quelle",
        "export_csv": "📄 Verlauf als CSV exportieren",
        "export_csv_ok": "✓ CSV gespeichert.",
        "preview_loading": "🔎 Lade Vorschau...",
        "preview_channel": "Kanal",
        "preview_duration": "Dauer",
        "preview_confirm": "Herunterladen",
        "preview_cancel": "Abbrechen",
        "playlist_mode": "📺 Ganze Playlist/Kanal laden (Premium)",
        "clip_mode": "✂️ Nur einen Ausschnitt laden (Premium)",
        "clip_from": "Von (mm:ss)",
        "clip_to": "Bis (mm:ss)",
        "clip_invalid": "Bitte Zeiten im Format mm:ss eingeben, z. B. 1:30.",
        "subscriptions_title": "🔔 Kanal-Abos (Premium)",
        "subscriptions_desc": "Neue Videos von abonnierten Kanälen werden automatisch heruntergeladen, solange die App geöffnet ist.",
        "add_subscription": "Kanal hinzufügen",
        "subscription_ph": "YouTube-Kanal-Link",
        "no_subscriptions": "Noch keine Kanäle abonniert.",
        "batch_mode": "Mehrere Links (einer pro Zeile) — Premium",
        "queue_progress": "Download",
        "queue_done": "Warteschlange fertig!",
        "queue_running": "laufen gerade",
        "batch_max_hint": "Maximal so viele Links wie unter Einstellungen → Gleichzeitige Downloads eingestellt:",
        "batch_too_many": "Zu viele Links — es werden nur die ersten genutzt, passend zu deiner Einstellung 'Gleichzeitige Downloads'",
        "font_title": "Schriftart & Größe",
        "font_default": "Standard",
        "font_size_label": "Größe:",
        "font_hint": "Gilt für die ganze App (außer Retro-Design, das hat seine eigene Pixel-Schrift). Nach dem Ändern wird die Seite kurz neu aufgebaut.",
        "wallpaper_mode": "🖼️ Wallpaper-Download (Premium)",
        "wallpaper_windows": "PC / Windows",
        "wallpaper_processing": "Wird für dein Gerät zugeschnitten...",
        "sub_lang_custom": "Andere (Code eingeben)",
        "sub_lang_hint": "🌍 Übersetzt nur die Untertitel (Text zum Mitlesen), nicht die gesprochene Sprache selbst (kein Dubbing). Funktioniert am besten bei YouTube — dort übersetzt YouTube automatisch in praktisch jede Sprache. Bei 'Andere' einfach den Sprachcode eingeben (z. B. sv=Schwedisch, th=Thai, vi=Vietnamesisch).",
        "app_tour": "App-Tour (alle Funktionen erklärt)",
        "performance_mode": "Sparmodus (für ältere/schwächere Computer)",
        "performance_mode_hint": "Schaltet animierte Effekte (Aurora/Schnee) ab und prüft die Zwischenablage seltener — läuft dadurch flüssiger auf älterer Hardware.",
        "export_backup": "Alle Einstellungen sichern",
        "import_backup": "Sicherung wiederherstellen",
        "quick_presets": "Schnellwahl:",
        "preset_music": "Musik",
        "preset_video": "Video",
        "favorites": "Favoriten",
        "favorite_name_ph": "Name (z. B. Lieblingskanal)",
        "add_favorite": "Aktuellen Link speichern",
        "no_favorites": "Noch keine Favoriten gespeichert.",
        "disk_free": "frei auf diesem Laufwerk",
        "sound_on_complete": "Ton bei fertigem Download",
        "playlist_url_ph": "Link zur Playlist oder zum Kanal einfügen...",
        "playlist_url_label": "Eigenes Link-Feld für die Playlist/den Kanal (nicht das Feld oben):",
        "clip_url_label": "Eigenes Link-Feld für den Ausschnitt (nicht das Feld oben):",
        "clip_url_ph": "Link zum Video für den Ausschnitt einfügen...",
        "wallpaper_url_label": "Eigenes Link-Feld für das Wallpaper-Bild (nicht das Feld oben):",
        "wallpaper_url_ph": "Link zum Bild einfügen...",
        "upscaling": "Wird hochskaliert...",
        "auto_upscale": "🔍 Automatisch hochskalieren, wenn Auflösung nicht verfügbar ist",
        "auto_upscale_hint": "Wenn ein Video z. B. nur in 1080p vorliegt, du aber 4K gewählt hast, wird die Datei auf 4K vergrößert. Achtung: Das erfindet keine echten Bilddetails, macht das Video also nicht wirklich schärfer — nur größer.",
        "upscaling_title": "Wird hochskaliert...",
        "upscaling_desc": "Kann je nach Videolänge einige Minuten dauern. Das Fenster schließt sich automatisch, wenn es fertig ist.",
        "upscale_probe_failed": "⚠ Konnte die Auflösung nicht prüfen (ffprobe nicht gefunden) — Hochskalieren übersprungen.",
        "ai_studio": "KI-Studio",
        "ai_studio_intro": "Erstelle Text, Bilder oder Videos per Prompt — über Googles Gemini-API mit deinem EIGENEN, kostenlos erhältlichen API-Schlüssel. Die App speichert oder nutzt keinen eigenen Schlüssel; alle Kosten/Limits laufen über dein Google-Konto.",
        "api_key_label": "Gemini API-Schlüssel",
        "api_key_hint": "Kostenlos erhältlich unter aistudio.google.com/apikey (Google-Konto nötig). Wird nur lokal auf deinem PC gespeichert.",
        "api_key_missing": "Bitte zuerst deinen Gemini API-Schlüssel eintragen und speichern.",
        "ai_generate": "Generieren",
        "ai_generating": "Wird generiert...",
        "ai_done": "Fertig!",
        "ai_save": "Speichern",
        "ai_saved": "✓ Gespeichert.",
        "ai_text_title": "Text & Chat",
        "ai_image_title": "Bild-Generierung",
        "ai_image_ph": "z. B. 'Ein Cover-Bild für einen Lofi-Song, pastellfarben'",
        "ai_no_image_returned": "Die API hat kein Bild zurückgegeben (evtl. Modellzugriff fehlt).",
        "ai_video_title": "Video-Generierung (experimentell)",
        "ai_video_hint": "⚠ Video-Generierung (Veo) braucht oft besonderen Zugriff bei Google, den nicht jeder kostenlose API-Schlüssel automatisch hat — falls es fehlschlägt, liegt es meist daran, nicht an einem App-Fehler. Kann mehrere Minuten dauern.",
        "ai_video_ph": "z. B. 'Ein Sonnenuntergang am Strand, Zeitraffer'",
        "ai_video_generating": "Wird angefragt...",
        "ai_video_waiting": "Video wird erstellt, das kann einige Minuten dauern...",
        "ai_video_timeout": "Zeitüberschreitung — hat zu lange gedauert.",
        "auto_upscale_short": "Hochskalieren (Premium)",
        "owner_verifying": "Owner-Login wird geprüft...",
        "owner_verify_no_backend": "Owner-Login braucht eine eingerichtete Server-Adresse (Admin → Backend-URL). Ohne Internetverbindung nicht möglich, außer dieses Gerät wurde schon einmal verifiziert.",
        "owner_verify_failed": "✗ Falsches Owner-Passwort.",
        "owner_verify_not_configured": "⚠ Der Server hat noch kein OWNER_PASSWORD eingerichtet (siehe premium-backend/README.md).",
        "owner_verify_old_backend": "⚠ Der Server kennt diese Prüfung noch nicht — hast du die neue app.py schon bei GitHub hochgeladen? (Render deployt dann automatisch neu.)",
        "premium_synced": "🌍 Premium-Status mit deinem Konto synchronisiert!",
        "cloud_sync_title": "☁️ Cloud-Sicherung",
        "cloud_sync_hint": "Sichert Einstellungen, Design, Verlauf, Favoriten und Kanal-Abos an dein Konto gebunden (E-Mail-Passwort/SMTP werden NICHT mitgesichert). Auf einem neuen Gerät einfach 'Wiederherstellen' klicken.",
        "cloud_backup_now": "Jetzt sichern",
        "cloud_restore_now": "Wiederherstellen",
        "cloud_working": "Wird bearbeitet...",
        "cloud_backup_ok": "Erfolgreich gesichert!",
        "cloud_error": "Fehlgeschlagen",
        "cloud_restore_confirm": "Das überschreibt deine aktuellen lokalen Einstellungen/Verlauf mit der gespeicherten Cloud-Version. Fortfahren?",
        "cloud_found_offer": "Für dieses Konto wurde eine Cloud-Sicherung von einem anderen Gerät gefunden! Jetzt wiederherstellen (Einstellungen, Verlauf, Favoriten, Abos)?",
        "smtp_private_hint": "🔑 Willst du diese Zugangsdaten (inkl. Passwort) mit auf einen neuen PC nehmen, ohne alles neu abzutippen? Exportiere sie in eine Datei, die NUR du behältst — nicht auf GitHub hochladen, nicht teilen, nicht in die App-ZIP legen!",
        "smtp_export_private": "Zugangsdaten exportieren (privat!)",
        "smtp_import_private": "Zugangsdaten importieren",
        "owner_verify_error": "✗ Server nicht erreichbar — Internetverbindung prüfen.",
        "contact_title": "❓ Probleme oder Feedback?",
        "contact_desc": "Schreib uns direkt aus der App — wir bekommen deine Nachricht per E-Mail.",
        "contact_ph": "Beschreibe dein Problem oder deine Idee...",
        "contact_send": "Nachricht senden",
        "contact_sending": "Wird gesendet...",
        "contact_ok": "✓ Danke! Deine Nachricht ist angekommen.",
        "contact_fail": "✗ Senden fehlgeschlagen — der Owner hat evtl. noch kein E-Mail-Postfach eingerichtet.",
        "contact_empty": "Bitte erst eine Nachricht eingeben.",
        "advanced_options": "Erweiterte Optionen",
        "show_preview": "Video-Vorschau vor dem Download anzeigen (Titel, Kanal, Dauer, Thumbnail)",
    },
    "en": {
        "choose_language": "Which language do you prefer?",
        "german": "Deutsch",
        "english": "English",
        "continue": "Continue",
        "welcome": "Welcome to Downloader<3",
        "create_account": "Create account",
        "login": "Log in",
        "email": "Email",
        "password": "Password",
        "register": "Register",
        "have_account": "Already have an account? Log in",
        "no_account": "No account yet? Register",
        "invalid_email": "Please enter a valid email address.",
        "pw_too_short": "Password must be at least 4 characters.",
        "user_exists": "This email is already registered.",
        "wrong_login": "Email or password is incorrect.",
        "download": "Download",
        "settings": "Settings",
        "premium": "Premium",
        "admin": "Admin",
        "logout": "Log out",
        "paste_link": "Paste link here (YouTube, TikTok, Instagram, Facebook)...",
        "paste_link_premium": "Paste link here (YouTube, images, direct files)...",
        "format": "Format",
        "start_download": "Download",
        "downloading": "Downloading...",
        "done": "Done!",
        "dl_complete": "Download complete",
        "dl_complete_msg": "Your file was downloaded successfully:",
        "dl_failed": "Download failed",
        "only_youtube_free": "The free version only supports YouTube links. Get Premium for other links!",
        "format_locked": "This format requires Premium. Free: MP4 only.",
        "no_ytdlp": "yt-dlp is not installed. Please run:  pip install yt-dlp",
        "language": "Language",
        "notifications": "Notifications",
        "notifications_desc": "Show a notification when a download finishes",
        "accent_color": "Accent color",
        "corner_style": "Shape style",
        "appearance": "Mode",
        "dark": "Dark",
        "light": "Light",
        "download_folder": "Download folder",
        "choose_folder": "Choose folder",
        "square": "Square",
        "round": "Round",
        "oval": "Oval",
        "premium_title": "Downloader<3 Premium",
        "premium_active": "Premium is active",
        "premium_until": "Premium active until:",
        "premium_forever": "Premium active: unlimited",
        "premium_pitch": "With Premium you get:",
        "perk_1": "• All formats: MP3, WAV, M4A, WEBM & MP4",
        "perk_2": "• Downloads from other links (images: PNG, JPG, direct files)",
        "perk_3": "• Supports the development of Downloader<3",
        "buy_premium": "Buy Premium – 30 days (Beta)",
        "buy_demo_note": "Note: Premium is still in its beta phase.",
        "purchased": "Premium activated for 30 days. Enjoy!",
        "owner_badge": "OWNER — Premium forever",
        "admin_title": "Admin panel (owner only)",
        "admin_desc": "Grant Premium to registered users and choose the duration.",
        "user_email": "User's email",
        "duration_days": "Duration (days)",
        "forever": "Unlimited",
        "grant": "Grant Premium",
        "revoke": "Revoke Premium",
        "user_not_found": "No user found with this email.",
        "granted": "Premium granted to",
        "revoked": "Premium revoked from",
        "registered_users": "Registered users",
        "status_free": "Free",
        "status_premium": "Premium",
        "refresh": "Refresh",
        "hello": "Hello",
        "get_premium_hint": "Only MP4 available — get Premium for all formats!",
        "custom_name": "Custom name",
        "name_placeholder": "New display name...",
        "save_name": "Save name",
        "name_saved": "Name saved!",
        "name_free_hint": "You can change your name once for free.",
        "name_once_used": "Free users can only change their name once. Get Premium!",
        "name_style": "Glitter effect (Premium)",
        "style_none": "No effect",
        "style_glitter": "✨ Glitter",
        "style_rainbow": "🌈 Rainbow",
        "style_hearts": "💖 Hearts",
        "style_locked": "Effects are Premium only.",
        "redeem_code": "Redeem code",
        "code_placeholder": "e.g. DL-A1B2-C3D4",
        "redeem": "Redeem",
        "code_ok": "Code redeemed — Premium activated! 🎉",
        "code_bad": "Code is invalid or already used.",
        "gift_code_title": "🎁 Create gift code",
        "gift_code_desc": "Creates a random one-time code you can send to someone.",
        "create_code": "Create code",
        "your_code": "Your code:",
        "codes_list": "Created codes",
        "code_unused": "unused",
        "code_used_by": "used by",
        "days_short": "days",
        "color_mode": "Apply color to",
        "mode_full": "Whole program",
        "mode_accent": "Icons & text only",
        "checking": "Checking video...",
        "cancelled": "Cancelled.",
        "history": "Recent downloads",
        "open_folder": "📂 Open folder",
        "ask_save": "Ask where to save before each download",
        "no_ffmpeg": "FFmpeg is not installed! For MP3/WAV please run once in a terminal:  winget install ffmpeg  — then restart your PC.",
        "ffmpeg_dl": "Installing FFmpeg automatically (one time, ~90 MB)...",
        "design_style": "Design style",
        "design_classic": "Classic 💜",
        "design_retro": "Retro 🎮",
        "custom_color": "Custom color (hex code)",
        "apply": "Apply",
        "invalid_hex": "Invalid hex code — e.g. #4F8EFF",
        "radius_slider": "Fine-tune corner radius (px)",
        "effects": "Effects",
        "effect_none": "None",
        "effect_aurora": "🌈 Aurora",
        "effect_snow": "❄ Snow",
        "style_fire": "🔥 Fire",
        "style_pulse": "💫 Pulse",
        "beta_msg": "Premium is still in beta and cannot be purchased yet.",
        "beta_gift": "As a thank-you you get a one-time voucher for 1 day of Premium! Redeem it in Settings under 'Redeem code':",
        "beta_already": "You have already received your beta voucher.",
        "owner_toggle": "Premium on/off (test the free view)",
        "el_colors_title": "Color individual elements",
        "el_hint": "Enter a hex code (e.g. #FF66AA) and Apply — ✕ resets to automatic.",
        "el_window": "Background",
        "el_sidebar": "Sidebar",
        "el_card": "Cards",
        "el_button": "Buttons",
        "el_name": "Name (display name)",
        "el_scrollbar": "Scrollbar",
        "matching_title": "Matching mode — automatic color matching",
        "matching_hint": "Pick a color direction (e.g. pink) — the app automatically builds a readable, matching design for background, sidebar, cards, buttons and name.",
        "matching_apply": "Create design",
        "matching_reset": "Reset matching",
        "design_modern": "Modern ✨",
        "platform": "Platform",
        "resolution": "Resolution",
        "nowm": "🚫 No watermark",
        "direct_link": "🔗 Direct link",
        "auto_label": "🪄 Auto",
        "res_locked": "This resolution requires Premium. Free: 480p & 720p.",
        "platform_mismatch": "The link doesn't match the selected platform.",
        "direct_premium": "Direct links (images, files) require Premium.",
        "converting": "Converting...",
        "no_image": "No image was found in this link.",
        "web_browser": "🌐 Web browser (any link)",
        "ai_mode": "🤖 AI mode (automatic)",
        "ai_hint": "🤖 AI automatically detects the platform and best resolution — you can still choose the format yourself.",
        "ai_locked": "AI mode requires Premium.",
        "auto_field": "🤖 automatic",
        "premium_required_title": "Premium feature",
        "see_premium": "★ View Premium",
        "locked_platform": "This source is only available with Premium.",
        "verify_title": "✉️ Verify your email",
        "verify_sending": "Sending code...",
        "verify_sent": "We sent a 6-digit code to:",
        "verify_fallback": "Email sending isn't set up yet — here's your code so you can continue anyway:",
        "verify_code_ph": "6-digit code",
        "verify_button": "Verify",
        "verify_resend": "Resend code",
        "verify_cancel": "Cancel / log out",
        "verify_wrong": "That code is incorrect.",
        "verify_expired": "That code has expired — please request a new one.",
        "verify_ok": "Email verified! Welcome 🎉",
        "smtp_title": "✉️ Email sending (SMTP)",
        "smtp_desc": "Credentials used to send verification codes. Best to use a dedicated app password (e.g. Gmail), not your normal password — it's stored locally on this PC.",
        "smtp_host": "SMTP server",
        "smtp_port": "Port",
        "smtp_user": "Username",
        "smtp_pass": "App password",
        "smtp_from": "From address",
        "smtp_save": "Save",
        "smtp_test": "Send test email",
        "smtp_test_ok": "Test email sent — please check the inbox.",
        "smtp_test_fail": "Sending failed:",
        "smtp_not_set": "Please fill in and save all fields first.",
        "smtp_guide": "📋 Pick a provider (fills in server/port automatically), then enter your username and an app password. Almost every provider now requires a separate app password instead of your normal one:\n• Gmail: Google Account → Security → turn on 2-Step Verification → 'App passwords'\n• Outlook/Hotmail: account.microsoft.com → Security → 'App passwords'\n• GMX / Web.de: Settings → enable 'POP3/IMAP access' + generate an app password\n• Yahoo: Account security → 'Generate app password'\n• iCloud: appleid.apple.com → Security → 'App-specific password'\n• ProtonMail: needs the paid 'ProtonMail Bridge' app (plain SMTP doesn't work otherwise on Proton)",
        "smtp_provider": "Provider (preset)",
        "smtp_ssl": "Use SSL (port 465 instead of 587)",
        "email_tpl_title": "✏️ Edit email text",
        "email_tpl_desc": "Placeholders: {code} = verification code, {app} = app name, {made_by} = developer line, {email} = recipient address.",
        "email_tpl_subject": "Subject",
        "email_tpl_body": "Message",
        "email_tpl_save": "Save text",
        "email_tpl_reset": "Reset to default",
        "email_tpl_saved": "✓ Email text saved.",
        "email_tpl_no_code": "⚠ Note: {code} doesn't appear in the text — the code will still be appended automatically.",
        "email_tpl_preview": "Send preview",
        "delete_user_title": "Delete user",
        "delete_user_confirm": "Really delete this account permanently?",
        "low_contrast_warn": "Warning: text may be hard to read on this color.",
        "pick_color": "Pick a color",
        "reset_appearance": "🔄 Reset design to default",
        "reset_appearance_confirm": "Reset colors, shape, effects and design style to factory defaults? (SMTP, language and download folder stay unchanged.)",
        "reset_done": "✓ Reset done.",
        "export_theme": "💾 Export theme",
        "import_theme": "📂 Import theme",
        "export_ok": "✓ Theme saved.",
        "import_ok": "✓ Theme loaded.",
        "import_fail": "✗ Could not read that file.",
        "preview_title": "👁 Live preview",
        "autostart": "Start with Windows",
        "info_updates": "ℹ️ Info & Updates",
        "version_label": "Version",
        "check_updates": "🔄 Check for updates",
        "up_to_date": "✓ You're on the latest version.",
        "concurrent_dl": "Concurrent downloads (max)",
        "concurrent_note": "Applies to the queue (📋 Multiple links) on the download page — sets how many links download at the same time.",
        "bandwidth_limit": "Speed limit",
        "bandwidth_unlimited": "Unlimited",
        "bandwidth_kbps": "KB/s",
        "proxy_title": "Proxy / VPN",
        "proxy_ph": "e.g. http://user:pass@host:port or socks5://host:port",
        "subs_download": "Auto-download subtitles (SRT/VTT, if available)",
        "clipboard_watch": "Detect & auto-fill copied links",
        "auto_sort": "Auto-sort into subfolders (images/videos/music)",
        "titlebar_progress": "Show progress in the window title (e.g. \"App — 42%\")",
        "danger_zone": "⚠️ Reset & Backup",
        "history_search_ph": "🔍 Search history...",
        "history_no_match": "No matches.",
        "confirm_yes": "Yes, continue",
        "confirm_no": "Cancel",
        "fix_window": "🔧 Fix window shape",
        "filename_tpl_title": "📝 Filename template",
        "filename_tpl_desc": "Placeholders: {title} = video title, {channel} = channel/creator, {date} = date, {platform} = platform.",
        "filename_tpl_ph": "{title}",
        "smart_resume_title": "🔄 Smart Resume",
        "smart_resume_desc": "If the internet drops during a download, it continues automatically instead of restarting — for YouTube/TikTok/Insta/Facebook this is handled by yt-dlp itself, and for direct links (images/PDFs) the app resumes exactly where it left off.",
        "schedule_title": "🕑 Start later",
        "schedule_time_ph": "e.g. 02:00",
        "scheduled_for": "Scheduled for",
        "invalid_time": "Please enter a time as HH:MM (e.g. 02:00).",
        "silent_mode": "🔇 Silent mode (mute all notifications)",
        "browser_ext_title": "🧩 Browser extension",
        "browser_ext_desc": "The included extension lets you right-click a link in your browser and send it straight to this app. Install: open chrome://extensions → enable Developer mode → 'Load unpacked' → select the 'browser-extension' folder.",
        "browser_ext_toggle": "Enable connection to the browser extension",
        "link_received": "🔗 Link received from the browser!",
        "duplicate_title": "Already downloaded",
        "duplicate_msg": "You've already downloaded this link:",
        "duplicate_continue": "Download anyway",
        "buy_on_website": "Buy Premium on our website (PayPal)",
        "checkout_title": "🌐 Premium website (PayPal purchase)",
        "checkout_desc": "Enter the addresses of your hosted checkout website and backend server. You need to set both up yourself (see the backend's README.md) — Anthropic/Claude cannot host a server for you.",
        "backend_url_label": "Backend server URL",
        "checkout_url_label": "Checkout website URL",
        "try_trial": "Try Premium free for 1 day",
        "trial_active_title": "Enjoy Premium!",
        "trial_active_msg": "You've unlocked 1 day of Premium — enjoy Downloader<3 in full! 🎉",
        "trial_already_title": "Already tried",
        "trial_already_msg": "You've already used your free trial day. For lasting Premium, check out the website!",
        "sub_lang_label": "Subtitle language",
        "sub_lang_all": "All available",
        "embed_metadata": "🎵 Embed title, artist & cover art",
        "stats_title": "📊 Statistics",
        "stats_total_files": "Total downloads",
        "stats_total_size": "Total size",
        "stats_top_platform": "Most-used source",
        "export_csv": "📄 Export history as CSV",
        "export_csv_ok": "✓ CSV saved.",
        "preview_loading": "🔎 Loading preview...",
        "preview_channel": "Channel",
        "preview_duration": "Duration",
        "preview_confirm": "Download",
        "preview_cancel": "Cancel",
        "playlist_mode": "📺 Download whole playlist/channel (Premium)",
        "clip_mode": "✂️ Download only a clip (Premium)",
        "clip_from": "From (mm:ss)",
        "clip_to": "To (mm:ss)",
        "clip_invalid": "Please enter times as mm:ss, e.g. 1:30.",
        "subscriptions_title": "🔔 Channel subscriptions (Premium)",
        "subscriptions_desc": "New videos from subscribed channels download automatically while the app is open.",
        "add_subscription": "Add channel",
        "subscription_ph": "YouTube channel link",
        "no_subscriptions": "No channels subscribed yet.",
        "batch_mode": "Multiple links (one per line) — Premium",
        "queue_progress": "Download",
        "queue_done": "Queue finished!",
        "queue_running": "running now",
        "batch_max_hint": "Max as many links as set under Settings → Concurrent downloads:",
        "batch_too_many": "Too many links — only the first ones will be used, matching your 'Concurrent downloads' setting",
        "font_title": "Font & Size",
        "font_default": "Default",
        "font_size_label": "Size:",
        "font_hint": "Applies to the whole app (except Retro design, which has its own pixel font). The page rebuilds briefly after changing this.",
        "wallpaper_mode": "🖼️ Wallpaper download (Premium)",
        "wallpaper_windows": "PC / Windows",
        "wallpaper_processing": "Fitting to your device...",
        "sub_lang_custom": "Other (enter code)",
        "sub_lang_hint": "🌍 Translates only the subtitles (text to read along), not the spoken language itself (no dubbing). Works best on YouTube — it auto-translates into almost any language there. For 'Other', just type the language code (e.g. sv=Swedish, th=Thai, vi=Vietnamese).",
        "app_tour": "App tour (all features explained)",
        "performance_mode": "Performance mode (for older/weaker computers)",
        "performance_mode_hint": "Turns off animated effects (Aurora/Snow) and checks the clipboard less often — runs smoother on older hardware.",
        "export_backup": "Backup all settings",
        "import_backup": "Restore backup",
        "quick_presets": "Quick pick:",
        "preset_music": "Music",
        "preset_video": "Video",
        "favorites": "Favorites",
        "favorite_name_ph": "Name (e.g. favorite channel)",
        "add_favorite": "Save current link",
        "no_favorites": "No favorites saved yet.",
        "disk_free": "free on this drive",
        "sound_on_complete": "Sound when download finishes",
        "playlist_url_ph": "Paste the playlist or channel link here...",
        "playlist_url_label": "Separate link field for the playlist/channel (not the field above):",
        "clip_url_label": "Separate link field for the clip (not the field above):",
        "clip_url_ph": "Paste the video link for the clip here...",
        "wallpaper_url_label": "Separate link field for the wallpaper image (not the field above):",
        "wallpaper_url_ph": "Paste the image link here...",
        "upscaling": "Upscaling...",
        "auto_upscale": "🔍 Auto-upscale when the chosen resolution isn't available",
        "auto_upscale_hint": "If a video is only available in 1080p but you selected 4K, the file gets resized up to 4K. Note: this doesn't invent real image detail, so the video won't actually look sharper — just bigger.",
        "upscaling_title": "Upscaling...",
        "upscaling_desc": "This can take a few minutes depending on the video length. This window closes automatically when done.",
        "upscale_probe_failed": "⚠ Could not check the resolution (ffprobe not found) — upscaling skipped.",
        "ai_studio": "AI Studio",
        "ai_studio_intro": "Create text, images, or videos from a prompt — via Google's Gemini API using your OWN, freely available API key. The app doesn't store or use its own key; all costs/limits run through your Google account.",
        "api_key_label": "Gemini API key",
        "api_key_hint": "Get one free at aistudio.google.com/apikey (Google account required). Stored only locally on your PC.",
        "api_key_missing": "Please enter and save your Gemini API key first.",
        "ai_generate": "Generate",
        "ai_generating": "Generating...",
        "ai_done": "Done!",
        "ai_save": "Save",
        "ai_saved": "✓ Saved.",
        "ai_text_title": "Text & Chat",
        "ai_image_title": "Image generation",
        "ai_image_ph": "e.g. 'A cover image for a lofi song, pastel colors'",
        "ai_no_image_returned": "The API didn't return an image (model access might be missing).",
        "ai_video_title": "Video generation (experimental)",
        "ai_video_hint": "⚠ Video generation (Veo) often needs special access from Google that not every free API key automatically has — if it fails, that's usually why, not an app bug. Can take several minutes.",
        "ai_video_ph": "e.g. 'A sunset at the beach, timelapse'",
        "ai_video_generating": "Requesting...",
        "ai_video_waiting": "Generating video, this can take a few minutes...",
        "ai_video_timeout": "Timed out — took too long.",
        "auto_upscale_short": "Upscale (Premium)",
        "owner_verifying": "Verifying owner login...",
        "owner_verify_no_backend": "Owner login needs a configured server address (Admin → Backend URL). Not possible without internet unless this device was already verified before.",
        "owner_verify_failed": "✗ Wrong owner password.",
        "owner_verify_not_configured": "⚠ The server does not have OWNER_PASSWORD set up yet (see premium-backend/README.md).",
        "owner_verify_old_backend": "⚠ The server does not know this check yet — have you uploaded the new app.py to GitHub? (Render redeploys automatically.)",
        "premium_synced": "🌍 Premium status synced with your account!",
        "cloud_sync_title": "☁️ Cloud Backup",
        "cloud_sync_hint": "Backs up settings, design, history, favorites, and channel subscriptions tied to your account (email password/SMTP are NOT included). On a new device, just click Restore.",
        "cloud_backup_now": "Back up now",
        "cloud_restore_now": "Restore",
        "cloud_working": "Working...",
        "cloud_backup_ok": "Backed up successfully!",
        "cloud_error": "Failed",
        "cloud_restore_confirm": "This will overwrite your current local settings/history with the saved cloud version. Continue?",
        "cloud_found_offer": "A cloud backup from another device was found for this account! Restore it now (settings, history, favorites, subscriptions)?",
        "smtp_private_hint": "🔑 Want to bring these credentials (incl. password) to a new PC without retyping everything? Export them to a file that ONLY you keep — never upload to GitHub, never share, never put in the app ZIP!",
        "smtp_export_private": "Export credentials (private!)",
        "smtp_import_private": "Import credentials",
        "owner_verify_error": "✗ Server unreachable — check your internet connection.",
        "contact_title": "❓ Issues or feedback?",
        "contact_desc": "Message us right from the app — we'll get it by email.",
        "contact_ph": "Describe your issue or idea...",
        "contact_send": "Send message",
        "contact_sending": "Sending...",
        "contact_ok": "✓ Thanks! Your message got through.",
        "contact_fail": "✗ Sending failed — the owner may not have set up an email inbox yet.",
        "contact_empty": "Please enter a message first.",
        "advanced_options": "Advanced options",
        "show_preview": "Show video preview before downloading (title, channel, duration, thumbnail)",
    },
}

# ----------------------------------------------------------------------------
# Datenspeicher (lokal, JSON)
# ----------------------------------------------------------------------------
class Store:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)
        self.data = {
            "settings": {
                "language": None,
                "notifications": True,
                "accent": "Violet",
                "corner_style": "rund",
                "appearance": "dark",
                "color_mode": "accent",
                "design": "classic",
                "custom_accent": None,
                "radius_px": None,
                "sidebar_collapsed": False,
                "effect": "none",
                "el_colors": {"window": None, "sidebar": None,
                              "card": None, "button": None,
                              "name": None, "scrollbar": None},
                "ask_save": True,
                "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
                "smtp": {"host": "smtp.gmail.com", "port": 587,
                         "user": "lisawer008@gmail.com",
                         "password": "",  # aus Sicherheitsgründen NIE fest im Code — pro PC einmalig eintragen
                         "from_addr": "lisawer008@gmail.com",
                         "use_ssl": False},
                "email_template": {
                    "subject": "{app}: your verification code is {code}",
                    "body": ("Hi there,\n\n"
                            "Thank you for using Downloader<3. Please use "
                            "the following security code to verify your "
                            "email address:\n\n"
                            "    {code}\n\n"
                            "For security reasons, this code will expire "
                            "in 15 minutes!\n\n"
                            "If you didn't request this code, you can "
                            "safely ignore this email."),
                },
                "autostart": False,
                "concurrent_downloads": 3,
                "bandwidth_kb": 0,
                "proxy_url": "",
                "download_subs": False,
                "clipboard_watch": False,
                "auto_sort": False,
                "titlebar_progress": True,
                "embed_metadata": True,
                "sub_lang": "en",
                "auto_upscale": False,
                "show_preview": True,
                "font_family": "",
                "font_scale": 1.0,
                "performance_mode": False,
                "gemini_api_key": "",
                "sound_on_complete": True,
                "filename_template": "{title}",
                "silent_mode": False,
                "browser_bridge": True,
                "backend_url": "https://downloader3-backend.onrender.com",
                "checkout_url": "https://lizziies.github.io/downloader3-checkout/",
            },
            "users": {},
            "codes": {},
            "history": [],
            "subscriptions": [],
            "favorites": [],
            "session": None,
        }
        self.load()
        self.save()
        self._seed_owners()

    def _seed_owners(self):
        """Owner-Konten werden angelegt, aber OHNE nutzbares Passwort — das
        wird erst beim ersten Login auf diesem Gerät per Server-Prüfung
        gesetzt (siehe App._verify_owner_login). So steht das echte
        Owner-Passwort nirgends im verteilten Programmcode."""
        changed = False
        for owner in OWNER_EMAILS:
            if owner not in self.data["users"]:
                self.data["users"][owner] = {
                    "pw": None,
                    "owner_verified": False,
                    "premium_until": "forever",
                    "created": datetime.date.today().isoformat(),
                    "name": OWNER_NAMES.get(owner, owner.split("@")[0]),
                    "name_changed": False,
                    "name_style": "glitter",
                    "verified": True,
                    "tour_seen": True,
                }
                self._log_email(owner)
                changed = True
        if changed:
            self.save()

    @staticmethod
    def _log_email(email: str):
        """Speichert jede registrierte E-Mail zusätzlich in emails.txt."""
        try:
            existing = ""
            if os.path.exists(EMAILS_FILE):
                with open(EMAILS_FILE, "r", encoding="utf-8") as f:
                    existing = f.read()
            if email not in existing:
                with open(EMAILS_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{email}  ({datetime.date.today().isoformat()})\n")
        except Exception:
            pass

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.data["settings"].update(saved.get("settings", {}))
                self.data["users"] = saved.get("users", {})
                self.data["codes"] = saved.get("codes", {})
                self.data["history"] = saved.get("history", [])
                self.data["subscriptions"] = saved.get("subscriptions", [])
                self.data["favorites"] = saved.get("favorites", [])
                self.data["session"] = saved.get("session")
                # Migration: Konten von vor diesem Update hatten noch keine
                # Verifizierung — die nicht rückwirkend aussperren.
                for u in self.data["users"].values():
                    if "verified" not in u:
                        u["verified"] = True

                # Migration: bestehende Installationen (mit alter, leerer
                # Konfiguration) bekommen die neuen Standard-Werte für
                # SMTP/Server/Webseite nachgetragen, statt bei leer zu
                # bleiben. Nur leere Felder werden ersetzt — eigene,
                # bereits eingetragene Werte bleiben unangetastet.
                s = self.data["settings"]
                smtp = s.setdefault("smtp", {})
                if not smtp.get("host"):
                    smtp["host"] = "smtp.gmail.com"
                if not smtp.get("user"):
                    smtp["user"] = "lisawer008@gmail.com"
                if not smtp.get("from_addr"):
                    smtp["from_addr"] = "lisawer008@gmail.com"
                if not smtp.get("port"):
                    smtp["port"] = 587
                if not s.get("backend_url"):
                    s["backend_url"] = "https://downloader3-backend.onrender.com"
                if not s.get("checkout_url"):
                    s["checkout_url"] = "https://lizziies.github.io/downloader3-checkout/"
                tpl = s.setdefault("email_template", {})
                if not tpl.get("body") or not tpl.get("subject"):
                    tpl["subject"] = "{app}: your verification code is {code}"
                    tpl["body"] = (
                        "Hi there,\n\n"
                        "Thank you for using Downloader<3. Please use "
                        "the following security code to verify your "
                        "email address:\n\n"
                        "    {code}\n\n"
                        "For security reasons, this code will expire "
                        "in 15 minutes!\n\n"
                        "If you didn't request this code, you can "
                        "safely ignore this email.")
            except Exception:
                pass

    def add_history(self, filepath: str, url: str = None):
        size = 0
        try:
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
        except Exception:
            pass
        self.data.setdefault("history", []).append({
            "file": filepath,
            "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "url": url,
            "size": size,
        })
        self.data["history"] = self.data["history"][-200:]

        # 📊 Lebenszeit-Statistik — bleibt erhalten, auch wenn der sichtbare
        # Verlauf oben irgendwann gekürzt wird.
        stats = self.data.setdefault(
            "stats", {"total_files": 0, "total_bytes": 0, "platforms": {}})
        stats["total_files"] += 1
        stats["total_bytes"] += size
        plat = "other"
        if url:
            for key, rgx in PLATFORM_URL_RE.items():
                if rgx.match(url):
                    plat = key
                    break
        stats["platforms"][plat] = stats["platforms"].get(plat, 0) + 1
        self.save()

    def find_duplicate(self, url: str):
        """Gibt den letzten Verlaufs-Eintrag mit derselben URL zurück
        (oder None) — für die Duplikat-Warnung vor dem Download."""
        for item in reversed(self.data.get("history", [])):
            if item.get("url") == url:
                return item
        return None

    def save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # --- Nutzer ---
    @staticmethod
    def hash_pw(pw: str) -> str:
        return hashlib.sha256(("coolgrab::" + pw).encode("utf-8")).hexdigest()

    def register(self, email: str, pw: str) -> bool:
        email = email.strip().lower()
        if email in self.data["users"]:
            return False
        self.data["users"][email] = {
            "pw": self.hash_pw(pw),
            "premium_until": "forever" if email in OWNER_EMAILS else None,
            "created": datetime.date.today().isoformat(),
            "name": email.split("@")[0],
            "name_changed": False,
            "name_style": "none",
            "verified": False,
            "vcode_hash": None,
            "vcode_expires": None,
        }
        self._log_email(email)
        self.save()
        return True

    # --- E-Mail-Verifizierung ---
    def is_verified(self, email: str) -> bool:
        email = email.strip().lower()
        return bool(self.data["users"].get(email, {}).get("verified", False))

    @staticmethod
    def _hash_code(email: str, code: str) -> str:
        return hashlib.sha256(
            f"coolgrab_verify::{email}::{code}".encode("utf-8")).hexdigest()

    def start_verification(self, email: str) -> str:
        """Erzeugt einen neuen 6-stelligen Code (15 Min. gültig) und
        gibt ihn im Klartext zurück, damit der Aufrufer ihn verschicken
        oder anzeigen kann."""
        email = email.strip().lower()
        code = f"{secrets.randbelow(1000000):06d}"
        expires = (datetime.datetime.now()
                  + datetime.timedelta(minutes=15)).isoformat()
        u = self.data["users"].setdefault(email, {})
        u["vcode_hash"] = self._hash_code(email, code)
        u["vcode_expires"] = expires
        self.save()
        return code

    def check_verification(self, email: str, code: str) -> str:
        """Gibt 'ok', 'wrong' oder 'expired' zurück."""
        email = email.strip().lower()
        u = self.data["users"].get(email, {})
        expires = u.get("vcode_expires")
        if not expires:
            return "wrong"
        if datetime.datetime.now() > datetime.datetime.fromisoformat(expires):
            return "expired"
        if u.get("vcode_hash") != self._hash_code(email, code.strip()):
            return "wrong"
        u["verified"] = True
        u["vcode_hash"] = None
        u["vcode_expires"] = None
        self.save()
        return "ok"

    def login(self, email: str, pw: str) -> bool:
        email = email.strip().lower()
        user = self.data["users"].get(email)
        if user and user["pw"] == self.hash_pw(pw):
            self.data["session"] = email
            self.save()
            return True
        return False

    def logout(self):
        self.data["session"] = None
        self.save()

    @property
    def current_email(self):
        return self.data.get("session")

    def is_owner(self, email=None) -> bool:
        email = email or self.current_email
        return email in OWNER_EMAILS

    def is_premium(self, email=None) -> bool:
        email = email or self.current_email
        if email is None:
            return False
        if self.is_owner(email):
            return not self.data["users"].get(email, {}).get(
                "owner_premium_off", False)
        user = self.data["users"].get(email)
        if not user:
            return False
        until = user.get("premium_until")
        if until is None:
            return False
        if until == "forever":
            return True
        try:
            return datetime.date.fromisoformat(until) >= datetime.date.today()
        except Exception:
            return False

    def premium_until(self, email=None):
        email = email or self.current_email
        user = self.data["users"].get(email, {})
        return user.get("premium_until")

    def grant_premium(self, email: str, days=None) -> bool:
        """days=None => unbegrenzt"""
        email = email.strip().lower()
        if email not in self.data["users"]:
            return False
        if days is None:
            self.data["users"][email]["premium_until"] = "forever"
        else:
            until = datetime.date.today() + datetime.timedelta(days=int(days))
            self.data["users"][email]["premium_until"] = until.isoformat()
        self.save()
        return True

    def revoke_premium(self, email: str) -> bool:
        email = email.strip().lower()
        if email not in self.data["users"] or email in OWNER_EMAILS:
            return False
        self.data["users"][email]["premium_until"] = None
        self.save()
        return True

    def delete_user(self, email: str) -> bool:
        """Löscht ein Konto vollständig. Owner können nicht gelöscht werden."""
        email = email.strip().lower()
        if email not in self.data["users"] or email in OWNER_EMAILS:
            return False
        del self.data["users"][email]
        if self.data.get("session") == email:
            self.data["session"] = None
        self.save()
        return True

    # --- Namen ---
    def display_name(self, email=None) -> str:
        email = email or self.current_email
        u = self.data["users"].get(email, {})
        return u.get("name") or (email or "?").split("@")[0]

    def name_style(self, email=None) -> str:
        email = email or self.current_email
        style = self.data["users"].get(email, {}).get("name_style", "none")
        return style if self.is_premium(email) else "none"

    def can_change_name(self, email=None) -> bool:
        email = email or self.current_email
        if self.is_premium(email):
            return True
        return not self.data["users"].get(email, {}).get("name_changed", False)

    def set_name(self, name: str, style=None) -> bool:
        email = self.current_email
        if not self.can_change_name(email):
            return False
        u = self.data["users"][email]
        u["name"] = name.strip()[:24]
        u["name_changed"] = True
        if style is not None and self.is_premium(email):
            u["name_style"] = style
        self.save()
        return True

    # --- Geschenk-Codes ---
    def create_gift_code(self, days=None) -> str:
        """days=None => unbegrenzt. Code ist zufällig und nur 1x gültig."""
        code = "DL-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper()
        self.data.setdefault("codes", {})[code] = {
            "days": "forever" if days is None else int(days),
            "used_by": None,
            "created": datetime.date.today().isoformat(),
        }
        self.save()
        return code

    def redeem_code(self, code: str) -> bool:
        code = code.strip().upper()
        c = self.data.get("codes", {}).get(code)
        if not c or c.get("used_by"):
            return False
        days = c["days"]
        self.grant_premium(self.current_email,
                           None if days == "forever" else days)
        c["used_by"] = self.current_email
        self.save()
        return True


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.store = Store()
        self.title(APP_NAME)
        self.geometry("1040x660")
        self.minsize(1000, 620)

        # Laufzeit-Zustand (nicht gespeichert) — muss VOR route() existieren,
        # da route() bereits beim ersten Aufruf darauf zugreift.
        self._shape_job = None
        self._last_shape_size = None
        self._verified_this_run = set()
        self._radius_debounce = None
        self._last_clipboard = None
        self._scroll_areas = []
        self._queue = []
        self._queue_active = False
        self._queue_total = 0
        self._wheel_router_bound = False

        self.apply_theme()
        self.route()

        # 🪟 Rundet das ECHTE Programmfenster (nicht nur Buttons/Karten
        # innen drin) passend zur Eckig/Rund/Oval-Einstellung. Funktioniert
        # nur unter Windows (SetWindowRgn) — auf Mac/Linux bleibt das
        # Fenster technisch bedingt rechteckig.
        self.after(120, self._apply_window_shape)
        if self.store.data["settings"].get("clipboard_watch"):
            self._start_clipboard_watch()
        if self.store.data["settings"].get("browser_bridge", True):
            self._start_local_bridge()
        self.after(5000, self._subscription_loop)
        self.bind("<Configure>", self._on_window_configure)

    def _start_local_bridge(self):
        """🧩 Lokaler HTTP-Listener (nur localhost) für die
        Browser-Erweiterung 'An Downloader<3 senden'. Nimmt Links per
        Rechtsklick im Browser entgegen und trägt sie ins Download-Feld
        ein."""
        if getattr(self, "_bridge_started", False):
            return
        self._bridge_started = True
        import http.server
        import urllib.parse as _up
        app_ref = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods",
                                 "GET, OPTIONS")

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self):
                parsed = _up.urlparse(self.path)
                if parsed.path == "/add":
                    qs = _up.parse_qs(parsed.query)
                    link = (qs.get("url") or [""])[0]
                    if link and app_ref.store.data["settings"].get(
                            "browser_bridge", True):
                        app_ref.after(0, lambda: app_ref._receive_shared_link(
                            link))
                    self.send_response(200)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok": true}')
                else:
                    self.send_response(404)
                    self._cors()
                    self.end_headers()

        def serve():
            try:
                server = http.server.HTTPServer(("127.0.0.1", 47812),
                                                 Handler)
                server.serve_forever()
            except Exception:
                pass  # Port evtl. belegt — Bridge bleibt dann einfach aus

        threading.Thread(target=serve, daemon=True).start()

    def _receive_shared_link(self, url: str):
        """Wird aufgerufen, wenn die Browser-Erweiterung einen Link
        geschickt hat."""
        if self.store.current_email is None or not self.store.is_verified(
                self.store.current_email):
            return
        self.page_download()
        entry = getattr(self, "url_entry", None)
        if entry is not None:
            try:
                entry.delete(0, "end")
                entry.insert(0, url)
            except Exception:
                pass
        self.notify(APP_NAME, self.t("link_received"))

    def _check_subscriptions(self):
        """🔔 Prüft alle abonnierten Kanäle auf ein neues Video und lädt
        es automatisch herunter. Läuft im Hintergrund-Thread — nur für
        Premium-Nutzer aktiv, läuft nur solange die App offen ist."""
        if yt_dlp is None or not self.store.is_premium():
            return
        subs = self.store.data.get("subscriptions", [])
        changed = False
        for sub in subs:
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                       "extract_flat": True,
                                       "playlistend": 1}) as ydl:
                    info = ydl.extract_info(sub["url"], download=False)
                entries = info.get("entries") or [info]
                if not entries:
                    continue
                latest = entries[0]
                vid = latest.get("id")
                was_known = sub.get("last_video_id") is not None
                if not vid or vid == sub.get("last_video_id"):
                    continue
                video_url = latest.get("url") or latest.get("webpage_url")
                if not video_url:
                    continue
                sub["last_video_id"] = vid
                changed = True
                if was_known:
                    # Nur herunterladen, wenn wir schon einen früheren Stand
                    # kannten (verhindert einen Download-Schwall beim
                    # allerersten Hinzufügen eines Kanals mit voller Historie)
                    self.after(0, lambda u=video_url:
                              self._auto_subscription_download(u))
            except Exception:
                continue
        if changed:
            self.store.save()

    def _auto_subscription_download(self, url):
        """Startet einen automatischen Download für ein neu erkanntes
        Abo-Video (im Hintergrund, beste Qualität, Auto-Format)."""
        if getattr(self, "_queue_active", False):
            return  # Nicht mitten in eine laufende Warteschlange pfuschen
        s = self.store.data["settings"]
        title_safe = "abo_video"
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "noplaylist": True,
                                   "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            fmt = self._auto_fmt(url, info)
            suggested = f"{self._render_filename(info, 'youtube')}.{fmt}"
            os.makedirs(s["download_dir"], exist_ok=True)
            path = os.path.join(s["download_dir"], suggested)
            threading.Thread(target=self._download_worker,
                             args=(url, fmt, "youtube",
                                  RES_HEIGHT["4K"], path),
                             daemon=True).start()
            self.notify(APP_NAME, "🔔 " + suggested)
        except Exception:
            pass

    def _subscription_loop(self):
        """Prüft alle 10 Minuten neu, solange die App läuft."""
        if self.store.data.get("subscriptions"):
            threading.Thread(target=self._check_subscriptions,
                             daemon=True).start()
        self.after(600000, self._subscription_loop)

    def _start_clipboard_watch(self):
        """Prüft alle 1.5s die Zwischenablage; erkennt sie einen neuen Link,
        wird er automatisch ins Download-Feld eingetragen (falls die
        Download-Seite gerade offen ist)."""
        def check():
            if not self.store.data["settings"].get("clipboard_watch"):
                return
            try:
                text = self.clipboard_get().strip()
            except Exception:
                text = ""
            if (text and text != self._last_clipboard
                    and re.match(r"^https?://", text, re.IGNORECASE)):
                self._last_clipboard = text
                entry = getattr(self, "url_entry", None)
                if entry is not None:
                    try:
                        if entry.winfo_exists() and not entry.get().strip():
                            entry.insert(0, text)
                    except Exception:
                        pass
            self.after(4000 if self.store.data["settings"].get(
                "performance_mode") else 1500, check)
        check()

    def _on_window_configure(self, event):
        if event.widget is not self:
            return
        w, h = event.width, event.height
        if (w, h) == getattr(self, "_last_shape_size", None):
            # Keine echte Größenänderung (z. B. nur durch Scrollen intern
            # ausgelöst) — nichts tun, das verhindert Verzerrungen.
            return
        if self._shape_job:
            try:
                self.after_cancel(self._shape_job)
            except Exception:
                pass
        self._shape_job = self.after(120, self._apply_window_shape)

    def _clear_window_shape(self):
        """Setzt die Fensterform sofort auf normal-rechteckig zurück —
        Not-Aus-Knopf, falls die Fensterform sich mal verklemmen sollte."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            ctypes.windll.user32.SetWindowRgn(self.winfo_id(), None, True)
        except Exception:
            pass

    def _apply_window_shape(self):
        """Formt das native OS-Fenster passend zur Form-Einstellung
        (Eckig = 0, Rund = mittel, Oval = stark abgerundet). 'Oval' heißt
        hier stark abgerundete Ecken, nicht ein wörtliches Ellipsen-Fenster
        — sonst würde der rechteckige Inhalt zu stark abgeschnitten."""
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()

        # Sicherheitssperre: niemals auf eine Größe zuschneiden, die
        # kleiner als die eingestellte Mindestgröße ist. Das verhindert,
        # dass eine kurzzeitig falsche Zwischenmessung (z. B. während
        # einer Scrollbar-Interaktion) das Fenster auf einen schmalen
        # Streifen zusammenschneidet.
        try:
            min_w, min_h = self.minsize()
        except Exception:
            min_w, min_h = 820, 560
        if w < min_w or h < min_h:
            return

        self._last_shape_size = (w, h)
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = self.winfo_id()
            ellipse = max(0, min(int(self.radius) * 2, min(w, h)))
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, ellipse, ellipse)
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass  # bei Problemen bleibt das Fenster einfach rechteckig

    # --- Helfer -------------------------------------------------------------
    def t(self, key: str) -> str:
        lang = self.store.data["settings"]["language"] or "en"
        return T[lang].get(key, key)

    def send_email(self, to_addr: str, subject: str, body: str):
        """Verschickt eine E-Mail über die in den Admin-Einstellungen
        hinterlegten SMTP-Zugangsdaten. Gibt (ok, fehlertext) zurück."""
        smtp = self.store.data["settings"].get("smtp") or {}
        host, port = smtp.get("host"), smtp.get("port")
        user, pw = smtp.get("user"), smtp.get("password")
        from_addr = smtp.get("from_addr") or user
        use_ssl = smtp.get("use_ssl", False)
        if not (host and port and user and pw and from_addr):
            return False, "not_configured"
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr
            if use_ssl:
                # z. B. Port 465 (implizites SSL)
                with smtplib.SMTP_SSL(host, int(port), timeout=20) as server:
                    server.login(user, pw)
                    server.sendmail(from_addr, [to_addr], msg.as_string())
            else:
                # z. B. Port 587 (STARTTLS)
                with smtplib.SMTP(host, int(port), timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(user, pw)
                    server.sendmail(from_addr, [to_addr], msg.as_string())
            return True, None
        except smtplib.SMTPAuthenticationError:
            return False, ("Login abgelehnt — Benutzername/App-Passwort "
                          "prüfen (bei Gmail: 2FA + App-Passwort nötig).")
        except (TimeoutError, OSError) as e:
            return False, f"Verbindung fehlgeschlagen: {e}"
        except Exception as e:
            return False, str(e)

    def send_verification_code(self, email: str, code: str):
        """Nutzt das in den Admin-Einstellungen hinterlegte, änderbare
        E-Mail-Template. Fällt auf einen Standardtext zurück, falls das
        Template kaputt/leer ist oder {code} vergessen wurde."""
        tpl = self.store.data["settings"].get("email_template") or {}
        subject_t = tpl.get("subject") or "{app}: your verification code is {code}"
        body_t = tpl.get("body") or ("Your {app} verification code:\n\n"
                                     "    {code}\n\nThis code expires in "
                                     "15 minutes.\n\n— {made_by}")
        ctx = {"app": APP_NAME, "code": code, "made_by": MADE_BY,
              "email": email}
        try:
            subject = subject_t.format(**ctx)
            body = body_t.format(**ctx)
        except (KeyError, IndexError):
            # Unbekannter Platzhalter im Template — auf Nummer sicher gehen
            subject = f"{APP_NAME}: your verification code is {code}"
            body = f"Your verification code: {code}\n\n— {MADE_BY}"
        if "{code}" not in body_t and code not in body:
            body += f"\n\nCode: {code}"

        # 1) Zuerst über den Server versuchen — funktioniert auf JEDEM
        # Gerät ohne lokal eingetragenes Passwort (genau wie Owner-Login).
        backend = self.store.data["settings"].get("backend_url", "").strip()
        if backend:
            try:
                body_data = json.dumps({
                    "to": email, "code": code,
                    "subject": subject_t, "body": body_t,
                }).encode()
                req = urllib.request.Request(
                    f"{backend.rstrip('/')}/api/send-code", data=body_data,
                    method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    result = json.loads(r.read().decode())
                if result.get("ok"):
                    return True, None
            except Exception:
                pass  # fällt unten auf lokales SMTP zurück

        # 2) Rückfall: lokal eingetragenes SMTP (z. B. eigener Mailserver)
        return self.send_email(email, subject, body)

    def _verify_owner_login(self, email, pw, err_label):
        """👑 Prüft ein Owner-Login einmalig gegen den Backend-Server
        (das echte Passwort steht nur dort als Umgebungsvariable, nie im
        verteilten Programmcode). Bei Erfolg wird lokal ein Passwort-Hash
        gespeichert, damit spätere Logins auf demselben Gerät auch ohne
        Internet funktionieren."""
        backend = self.store.data["settings"].get("backend_url", "").strip()
        if not backend:
            self.after(0, lambda: err_label.configure(
                text=self.t("owner_verify_no_backend"),
                text_color="#F87171"))
            return
        try:
            body = json.dumps({"email": email, "password": pw}).encode()
            req = urllib.request.Request(
                f"{backend.rstrip('/')}/api/verify-owner", data=body,
                method="POST", headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read().decode())
            except urllib.error.HTTPError as he:
                # Server hat geantwortet (kein Netzwerkproblem!), aber
                # abgelehnt oder ist nicht eingerichtet — genau unterscheiden.
                try:
                    data = json.loads(he.read().decode())
                except Exception:
                    data = {}
                if he.code == 404:
                    # Der Endpunkt existiert gar nicht -> die neue app.py
                    # wurde noch nicht auf den Server hochgeladen/deployt.
                    self.after(0, lambda: err_label.configure(
                        text=self.t("owner_verify_old_backend"),
                        text_color="#FBBF24"))
                    return
                if he.code == 503 or data.get("error") == "not configured":
                    self.after(0, lambda: err_label.configure(
                        text=self.t("owner_verify_not_configured"),
                        text_color="#FBBF24"))
                    return
                self.after(0, lambda: err_label.configure(
                    text=self.t("owner_verify_failed"),
                    text_color="#F87171"))
                return
            if data.get("ok"):
                user = self.store.data["users"].get(email)
                if user is not None:
                    user["pw"] = self.store.hash_pw(pw)
                    user["owner_verified"] = True
                self.store.data["session"] = email
                self.store.save()
                self.after(0, self.route)
            else:
                self.after(0, lambda: err_label.configure(
                    text=self.t("owner_verify_failed"),
                    text_color="#F87171"))
        except Exception:
            self.after(0, lambda: err_label.configure(
                text=self.t("owner_verify_error"),
                text_color="#F87171"))

    def _offer_cloud_restore_if_available(self, email):
        """☁️ Wird nach einer NEUEN lokalen Registrierung aufgerufen —
        prüft, ob für diese E-Mail schon eine Cloud-Sicherung existiert
        (z. B. von einem alten Gerät) und bietet an, sie wiederherzustellen."""
        backend = self.store.data["settings"].get("backend_url", "").strip()
        if not backend:
            return
        try:
            url = (f"{backend.rstrip('/')}/api/restore-settings?email="
                  + urllib.parse.quote(email))
            with urllib.request.urlopen(url, timeout=10) as r:
                result = json.loads(r.read().decode())
        except Exception:
            return
        if not result.get("ok"):
            return  # keine Sicherung vorhanden — nichts zu tun

        def ask():
            if self.confirm_dialog(self.t("cloud_sync_title"),
                                   self.t("cloud_found_offer")):
                ok, _ = self.cloud_restore(email)
                if ok:
                    self.apply_theme()
                    self.screen_main()
        self.after(600, ask)

    def cloud_backup(self):
        """☁️ Speichert Einstellungen, Verlauf, Favoriten und Abos für das
        aktuelle Konto auf dem Server (Passwörter/SMTP werden NICHT
        mitgesichert). Gibt (ok, error) zurück."""
        backend = self.store.data["settings"].get("backend_url", "").strip()
        email = self.store.current_email
        if not backend or not email:
            return False, "no_backend_or_email"
        safe_settings = {k: v for k, v in
                        self.store.data["settings"].items() if k != "smtp"}
        payload = {
            "settings": safe_settings,
            "history": self.store.data.get("history", []),
            "favorites": self.store.data.get("favorites", []),
            "subscriptions": self.store.data.get("subscriptions", []),
            "stats": self.store.data.get("stats", {}),
        }
        try:
            body = json.dumps({"email": email, "data": payload}).encode()
            req = urllib.request.Request(
                f"{backend.rstrip('/')}/api/backup-settings", data=body,
                method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                result = json.loads(r.read().decode())
            return result.get("ok", False), result.get("error")
        except Exception as e:
            return False, str(e)

    def cloud_restore(self, email=None):
        """☁️ Holt die gespeicherte Sicherung für das Konto zurück und
        wendet sie lokal an. Gibt (ok, error) zurück."""
        backend = self.store.data["settings"].get("backend_url", "").strip()
        email = email or self.store.current_email
        if not backend or not email:
            return False, "no_backend_or_email"
        try:
            url = (f"{backend.rstrip('/')}/api/restore-settings?email="
                  + urllib.parse.quote(email))
            with urllib.request.urlopen(url, timeout=25) as r:
                result = json.loads(r.read().decode())
            if not result.get("ok"):
                return False, result.get("error")
            data = result["data"]
            smtp_backup = self.store.data["settings"].get("smtp")
            self.store.data["settings"].update(data.get("settings", {}))
            if smtp_backup:  # eigenes lokales SMTP nie überschreiben
                self.store.data["settings"]["smtp"] = smtp_backup
            self.store.data["history"] = data.get(
                "history", self.store.data.get("history", []))
            self.store.data["favorites"] = data.get(
                "favorites", self.store.data.get("favorites", []))
            self.store.data["subscriptions"] = data.get(
                "subscriptions", self.store.data.get("subscriptions", []))
            if data.get("stats"):
                self.store.data["stats"] = data["stats"]
            self.store.save()
            return True, None
        except Exception as e:
            return False, str(e)

    def sync_premium_from_server(self, email, silent=True):
        """🌍 Fragt den Server, ob dieses Konto (per E-Mail) Premium hat —
        so bleibt ein Kauf über jedes Gerät/jede Neuinstallation hinweg
        erhalten, nicht nur auf dem PC, wo es eingelöst wurde. Übernimmt
        den Server-Stand nur, wenn er GRÜNZÜGIGER ist als der lokale."""
        backend = self.store.data["settings"].get("backend_url", "").strip()
        if not backend or email not in self.store.data["users"]:
            return
        try:
            url = (f"{backend.rstrip('/')}/api/account-status?email="
                  + urllib.parse.quote(email))
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
            server_until = data.get("premium_until")
            if not server_until:
                return
            local_until = self.store.data["users"][email].get(
                "premium_until")

            def _more_generous(a, b):
                if a == "forever" or b == "forever":
                    return "forever"
                if not a:
                    return b
                if not b:
                    return a
                return max(a, b)

            merged = _more_generous(local_until, server_until)
            if merged != local_until:
                self.store.data["users"][email]["premium_until"] = merged
                self.store.save()
                if not silent:
                    self.after(0, lambda: self.notify(
                        APP_NAME, self.t("premium_synced")))
                self.after(0, self.screen_main)
        except Exception:
            pass  # kein Internet o.ä. — lokaler Stand bleibt einfach gültig

    def redeem_code_universal(self, code: str) -> bool:
        """Löst einen Code ein — probiert zuerst lokale (vom Owner im
        Admin-Panel vergebene) Codes, dann — falls konfiguriert — einen
        über die Premium-Webseite (PayPal) gekauften Code beim Backend."""
        if self.store.redeem_code(code):
            return True
        backend = self.store.data["settings"].get("backend_url")
        if not backend:
            return False
        try:
            email = self.store.current_email or ""
            url = (f"{backend.rstrip('/')}/api/redeem?code="
                  + urllib.parse.quote(code.strip())
                  + "&email=" + urllib.parse.quote(email))
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
            if data.get("ok"):
                days = data.get("days")
                self.store.grant_premium(
                    self.store.current_email,
                    None if days in (None, "forever") else days)
                return True
        except Exception:
            pass
        return False

    @property
    def accent(self):
        s = self.store.data["settings"]
        c = s.get("custom_accent")
        if c:
            return {"main": c, "hover": self._mix(c, "#000000", 0.22)}
        return ACCENTS[s["accent"]]

    @property
    def radius(self):
        s = self.store.data["settings"]
        if s.get("radius_px") is not None:
            return int(s["radius_px"])
        return CORNER_STYLES[s["corner_style"]]

    @property
    def is_retro(self) -> bool:
        return self.store.data["settings"].get("design") == "retro"

    @property
    def is_modern(self) -> bool:
        return self.store.data["settings"].get("design") == "modern"

    def _retro_family(self) -> str:
        """Sucht eine Pixel-/Retro-Schrift auf dem System."""
        if not hasattr(self, "_retro_fam"):
            try:
                import tkinter.font as tkfont
                fams = set(tkfont.families())
            except Exception:
                fams = set()
            self._retro_fam = next(
                (f for f in ("Press Start 2P", "VCR OSD Mono",
                             "OCR A Extended", "OCR-A", "Consolas")
                 if f in fams), "Consolas")
        return self._retro_fam

    def font(self, size=13, weight="normal"):
        s = self.store.data["settings"]
        scale = s.get("font_scale", 1.0)
        size = max(8, round(size * scale))
        if self.is_retro:
            return ctk.CTkFont(family=self._retro_family(),
                               size=max(9, size - 2), weight=weight)
        custom_family = s.get("font_family")
        if custom_family:
            return ctk.CTkFont(family=custom_family, size=size,
                               weight=weight)
        return ctk.CTkFont(size=size, weight=weight)

    def rt(self, text: str) -> str:
        """Im Retro-Design wird Text in GROSSBUCHSTABEN angezeigt."""
        return text.upper() if self.is_retro else text

    @staticmethod
    def _mix(hex_color: str, target: str, t: float) -> str:
        """Mischt hex_color mit target (t = Anteil von target)."""
        r1, g1, b1 = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        r2, g2, b2 = (int(target[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % (round(r1 + (r2 - r1) * t),
                                  round(g1 + (g2 - g1) * t),
                                  round(b1 + (b2 - b1) * t))

    def tint(self, level: int):
        """Hintergrundfarbe je nach Design und Farbmodus.
        level 0 = Fenster, 1 = Sidebar, 2 = Karten."""
        s = self.store.data["settings"]
        el = s.get("el_colors") or {}
        key = {0: "window", 1: "sidebar", 2: "card"}[level]
        if el.get(key):
            return el[key]
        if s["color_mode"] == "full":
            base = self.accent["main"]
            if s["appearance"] == "light":
                t = {0: 0.90, 1: 0.82, 2: 0.74}[level]
                return self._mix(base, "#FFFFFF", t)
            t = {0: 0.87, 1: 0.80, 2: 0.72}[level]
            return self._mix(base, "#000000", t)
        if self.is_retro:
            # Dunkles Navy wie im Launcher-Look
            return {0: "#050B16", 1: "#0B1B3E", 2: "#081226"}[level]
        if self.is_modern and s["appearance"] == "dark":
            # Modern: weiche, edle Grautöne
            return {0: "#0E0F14", 1: "#15161D", 2: "#1B1D26"}[level]
        return None

    @staticmethod
    def _lum(hex_color: str) -> float:
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _contrast_ratio(self, hex1: str, hex2: str) -> float:
        l1, l2 = self._lum(hex1), self._lum(hex2)
        lighter, darker = max(l1, l2), min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def _low_contrast(self, bg_hex: str) -> bool:
        """True, wenn die automatisch gewählte Schrift auf diesem
        Hintergrund schwer lesbar wäre (Kontrast-Sicherheitscheck)."""
        text_hex = "#111827" if self._lum(bg_hex) > 0.5 else "#F3F4F6"
        return self._contrast_ratio(bg_hex, text_hex) < 3.0

    def text_on(self, level: int, muted: bool = False):
        """Automatisch lesbare Schriftfarbe für die Fläche (level 0/1/2).
        None = Theme entscheidet (kein eigener Hintergrund gesetzt)."""
        bg = self.tint(level)
        if bg is None:
            return None
        if self._lum(bg) > 0.5:  # helle Fläche → dunkle Schrift
            return "#6B7280" if muted else "#111827"
        return "#9CA3AF" if muted else "#F3F4F6"

    def muted(self):
        """Gedämpfte Textfarbe, die auf den Karten immer lesbar ist."""
        return self.text_on(2, muted=True) or "#9CA3AF"

    def apply_matching(self, base: str):
        """🪄 Matching Mode: erstellt aus einer Farbrichtung automatisch
        ein zusammenpassendes, gut lesbares Farbschema für alle Elemente."""
        import colorsys
        s = self.store.data["settings"]
        dark = self.is_retro or s["appearance"] == "dark"
        target = "#000000" if dark else "#FFFFFF"

        # Farbe kräftig genug machen, damit sie als Akzent wirkt
        r, g, b = (int(base[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, sat, val = colorsys.rgb_to_hsv(r, g, b)
        if sat > 0.05:  # bei Weiß/Grau/Schwarz Sättigung nicht erzwingen
            sat = max(sat, 0.55)
            val = max(val, 0.75)
        r2, g2, b2 = colorsys.hsv_to_rgb(h, sat, val)
        base2 = "#%02x%02x%02x" % (int(r2 * 255), int(g2 * 255), int(b2 * 255))

        # Buttons: falls zu hell für weiße Schrift, abdunkeln (Lesbarkeit!)
        btn = base2
        if self._lum(btn) > 0.62:
            btn = self._mix(btn, "#000000", 0.38)
        # Im Retro-Design sind Buttons Rahmen auf dunklem Grund — zu dunkle
        # Farben würden unsichtbar, also ggf. aufhellen
        if self.is_retro and self._lum(btn) < 0.30:
            btn = self._mix(btn, "#FFFFFF", 0.35)

        if self.is_retro:
            # Retro: tiefere Navy-Töne, leicht mit der Wunschfarbe getönt
            ratios = (0.93, 0.87, 0.81)
            navy = "#050B16"
            el = {
                "window": self._mix(self._mix(base2, target, ratios[0]),
                                    navy, 0.40),
                "sidebar": self._mix(self._mix(base2, target, ratios[1]),
                                     navy, 0.35),
                "card": self._mix(self._mix(base2, target, ratios[2]),
                                  navy, 0.35),
                "button": btn,
                "name": self._mix(base2, "#FFFFFF", 0.50),
                "scrollbar": btn,
            }
        else:
            el = {
                "window": self._mix(base2, target, 0.90),
                "sidebar": self._mix(base2, target, 0.82),
                "card": self._mix(base2, target, 0.74),
                "button": btn,
                "name": (self._mix(base2, "#FFFFFF", 0.45) if dark
                         else self._mix(base2, "#000000", 0.40)),
                "scrollbar": btn,
            }
        s["custom_accent"] = btn.upper()
        s["el_colors"] = {k: v.upper() for k, v in el.items()}
        self.store.save()
        self.apply_theme()
        self.screen_main()

    def reset_matching(self):
        s = self.store.data["settings"]
        s["custom_accent"] = None
        s["el_colors"] = {"window": None, "sidebar": None,
                          "card": None, "button": None, "name": None,
                          "scrollbar": None}
        self.store.save()
        self.apply_theme()
        self.screen_main()

    def reset_appearance(self):
        if not self.confirm_dialog(self.t("reset_appearance"),
                                   self.t("reset_appearance_confirm")):
            return
        s = self.store.data["settings"]
        s["accent"] = "Violet"
        s["custom_accent"] = None
        s["corner_style"] = "rund"
        s["radius_px"] = None
        s["design"] = "classic"
        s["effect"] = "none"
        s["color_mode"] = "accent"
        s["appearance"] = "dark"
        s["font_family"] = ""
        s["font_scale"] = 1.0
        s["el_colors"] = {"window": None, "sidebar": None, "card": None,
                          "button": None, "name": None, "scrollbar": None}
        self.store.save()
        self.apply_theme()
        self.screen_main()
        self.after(30, self._apply_window_shape)

    def export_full_backup(self):
        """💾 Sichert ALLE Einstellungen (nicht nur Design) als Datei —
        SMTP-Passwort wird bewusst NICHT mitgesichert (Sicherheit)."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="downloader3_backup.json",
            filetypes=[("JSON", "*.json")], title=self.t("export_backup"))
        if not path:
            return
        s = dict(self.store.data["settings"])
        if "smtp" in s:
            s["smtp"] = {**s["smtp"], "password": ""}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
            messagebox.showinfo(APP_NAME, self.t("export_ok"))
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def import_full_backup(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title=self.t("import_backup"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                backup = json.load(f)
            s = self.store.data["settings"]
            for key, val in backup.items():
                if key == "smtp" and "smtp" in s:
                    s["smtp"].update({k: v for k, v in val.items()
                                     if k != "password" or v})
                else:
                    s[key] = val
            self.store.save()
            self.apply_theme()
            self.route()
            self.after(30, self._apply_window_shape)
            messagebox.showinfo(APP_NAME, self.t("import_ok"))
        except Exception:
            messagebox.showerror(APP_NAME, self.t("import_fail"))

    def export_theme(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="MeinDesign.json",
            filetypes=[("JSON", "*.json")], title=self.t("export_theme"))
        if not path:
            return
        s = self.store.data["settings"]
        theme = {k: s.get(k) for k in (
            "accent", "custom_accent", "corner_style", "radius_px",
            "design", "effect", "color_mode", "appearance", "el_colors",
            "font_family", "font_scale")}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(theme, f, indent=2, ensure_ascii=False)
            messagebox.showinfo(APP_NAME, self.t("export_ok"))
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def import_theme(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title=self.t("import_theme"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                theme = json.load(f)
            s = self.store.data["settings"]
            for key in ("accent", "custom_accent", "corner_style",
                       "radius_px", "design", "effect", "color_mode",
                       "appearance", "el_colors", "font_family",
                       "font_scale"):
                if key in theme:
                    s[key] = theme[key]
            self.store.save()
            self.apply_theme()
            self.screen_main()
            self.after(30, self._apply_window_shape)
            messagebox.showinfo(APP_NAME, self.t("import_ok"))
        except Exception:
            messagebox.showerror(APP_NAME, self.t("import_fail"))

    def set_autostart(self, enable: bool) -> bool:
        """Trägt (oder entfernt) einen Autostart-Eintrag in der Windows-
        Registry ein. Auf anderen Systemen wird nichts unternommen."""
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                 winreg.KEY_SET_VALUE)
            name = "Downloader3"
            if enable:
                exe = sys.executable
                script = os.path.abspath(sys.argv[0])
                cmd = f'"{exe}" "{script}"'
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def seg_kw(self) -> dict:
        """Farben für Segment-Knöpfe mit automatisch gutem Kontrast —
        passt sich an Akzentfarbe, Design-Stil und Hell/Dunkel an."""
        a = self.accent["main"]
        ref = self.tint(2)
        if ref is not None:
            dark = self._lum(ref) < 0.5
        else:
            dark = (self.is_retro
                    or self.store.data["settings"]["appearance"] == "dark")
        target = "#000000" if dark else "#FFFFFF"
        if self._lum(a) > 0.62:
            a_sel = self._mix(a, "#000000", 0.35)
        else:
            a_sel = a
        uns = self._mix(a_sel, target, 0.62)
        txt = "#FFFFFF" if self._lum(a_sel) < 0.6 else "#111827"
        return {
            "selected_color": a_sel,
            "selected_hover_color": self._mix(a_sel, "#000000", 0.2),
            "unselected_color": uns,
            "unselected_hover_color": self._mix(uns, "#000000", 0.2),
            "text_color": txt,
            "corner_radius": self.radius,
        }

    def card_kw(self, level: int = 2) -> dict:
        c = self.tint(level)
        return {"fg_color": c} if c else {}

    def scrollbar_color(self):
        """Farbe für alle Scrollbalken — passt sich automatisch der
        Akzentfarbe an, kann aber auch einzeln übersteuert werden (siehe
        Einstellungen → Einzelne Elemente färben)."""
        c = (self.store.data["settings"].get("el_colors") or {}).get(
            "scrollbar")
        return c or self.accent["main"]

    def _draw_mini_preview(self, parent):
        """Zeichnet ein winziges, schematisches Abbild der App-Oberfläche
        (Sidebar/Karte/Button) mit den GERADE aktuellen Farben — eine
        Live-Vorschau direkt in den Einstellungen."""
        w, h = 320, 130
        win_bg = self.tint(0) or "#1A1A1A"
        side_bg = self.tint(1) or "#242424"
        card_bg = self.tint(2) or "#2B2B2B"
        btn_bg = self.accent["main"]
        txt_side = self.text_on(1) or "#FFFFFF"
        txt_card = self.text_on(2) or "#FFFFFF"
        txt_btn = "#111827" if self._lum(btn_bg) > 0.5 else "#FFFFFF"

        canvas = tk.Canvas(parent, width=w, height=h,
                           highlightthickness=1,
                           highlightbackground=self.muted(), bd=0,
                           bg=win_bg)
        canvas.pack(anchor="w", padx=20, pady=(0, 10))

        r = max(0, min(self.radius, 14))
        canvas.create_rectangle(0, 0, 60, h, fill=side_bg, outline="")
        canvas.create_text(30, 16, text="💜", font=(self._retro_family()
                          if self.is_retro else "Arial", 12))
        for i, label in enumerate(["⬇", "★", "⚙"]):
            canvas.create_text(30, 44 + i * 22, text=label,
                              fill=txt_side, font=("Arial", 11))

        cx0, cy0, cx1, cy1 = 74, 14, w - 14, h - 14
        self._round_rect(canvas, cx0, cy0, cx1, cy1, r, card_bg)
        canvas.create_text(cx0 + 14, cy0 + 16, text="Aa", anchor="w",
                          fill=txt_card, font=("Arial", 13, "bold"))
        canvas.create_line(cx0 + 14, cy0 + 34, cx1 - 14, cy0 + 34,
                           fill=txt_card, dash=(1, 3))
        self._round_rect(canvas, cx0 + 14, cy1 - 34, cx0 + 104, cy1 - 12,
                         min(r, 10), btn_bg)
        canvas.create_text(cx0 + 59, cy1 - 23, text=self.t("start_download"),
                          fill=txt_btn, font=("Arial", 10, "bold"))

    @staticmethod
    def _round_rect(canvas, x0, y0, x1, y1, r, fill):
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        if r <= 0:
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="")
            return
        points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
                  x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
                  x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        canvas.create_polygon(points, fill=fill, outline="", smooth=True)

    def make_scroll_area(self, parent, colored=True, height=None, padx=0):
        """Container mit vertikalem UND horizontalem Scrollbalken.
        Nutzt ein rohes tk.Canvas + create_window, weil die native
        CTkScrollableFrame kein horizontales Scrollen unterstützt.
        height=None füllt den verfügbaren Platz; sonst feste Pixelhöhe
        (z. B. für kleinere, eingebettete Listen wie den Verlauf)."""
        holder = ctk.CTkFrame(parent, fg_color="transparent",
                              height=height if height else 0)
        if height:
            holder.pack(fill="x", padx=padx, pady=(0, 24))
            holder.pack_propagate(False)
        else:
            holder.pack(fill="both", expand=True)
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        cbg = self.tint(2)
        if not cbg:
            pair = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
            cbg = pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]

        canvas = tk.Canvas(holder, highlightthickness=0, bd=0, bg=cbg)
        canvas.grid(row=0, column=0, sticky="nsew")

        sc = self.scrollbar_color()
        sc_hover = self._mix(sc, "#000000", 0.2)
        vsb = ctk.CTkScrollbar(holder, orientation="vertical",
                               command=canvas.yview,
                               corner_radius=self.radius,
                               button_color=sc, button_hover_color=sc_hover)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ctk.CTkScrollbar(holder, orientation="horizontal",
                               command=canvas.xview,
                               corner_radius=self.radius,
                               button_color=sc, button_hover_color=sc_hover)
        hsb.grid(row=1, column=0, sticky="ew")
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        card = ctk.CTkFrame(canvas, corner_radius=self.radius,
                            **(self.card_kw(2) if colored
                               else {"fg_color": "transparent"}))
        canvas.create_window((0, 0), window=card, anchor="nw")
        card.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Registrieren statt global zu binden — so kann jede verschachtelte
        # Liste (z. B. der Verlauf) unabhängig von der Gesamtseite scrollen,
        # je nachdem, worüber die Maus gerade steht.
        self._register_scroll_area(canvas, card)
        return card

    def _register_scroll_area(self, canvas, card):
        """Merkt sich einen Scroll-Bereich zur zentralen Maus-Rad-Steuerung
        (siehe _route_wheel) — verhindert, dass sich mehrere verschachtelte
        Scroll-Bereiche gegenseitig das Mausrad wegnehmen."""
        areas = getattr(self, "_scroll_areas", None)
        if areas is None:
            areas = []
            self._scroll_areas = areas
        areas[:] = [a for a in areas if a["canvas"].winfo_exists()]
        areas.append({"canvas": canvas, "card": card})
        if not getattr(self, "_wheel_router_bound", False):
            self._wheel_router_bound = True
            self.bind_all("<MouseWheel>", self._route_wheel)
            self.bind_all("<Shift-MouseWheel>", self._route_wheel_h)

    def _find_scroll_target(self, widget):
        """Sucht den am tiefsten verschachtelten (also spezifischsten)
        registrierten Scroll-Bereich, der das angegebene Widget enthält."""
        best, best_depth = None, None
        for area in list(getattr(self, "_scroll_areas", [])):
            card = area["card"]
            if not card.winfo_exists():
                continue
            w, depth, found = widget, 0, False
            while w is not None:
                if w == card:
                    found = True
                    break
                w = getattr(w, "master", None)
                depth += 1
            if found and (best_depth is None or depth < best_depth):
                best, best_depth = area["canvas"], depth
        return best

    def _route_wheel(self, e):
        target = self._find_scroll_target(e.widget)
        if target is not None and target.winfo_exists():
            target.yview_scroll(-int(e.delta / 120), "units")

    def _route_wheel_h(self, e):
        target = self._find_scroll_target(e.widget)
        if target is not None and target.winfo_exists():
            target.xview_scroll(-int(e.delta / 120), "units")

    def apply_theme(self):
        # Der Hell/Dunkel-Modus richtet sich nach der ECHTEN Helligkeit der
        # Flächen (auch bei Matching Mode / eigenen Farben), damit die
        # Standard-Schrift immer lesbar bleibt.
        mode = ("dark" if self.is_retro
                else self.store.data["settings"]["appearance"])
        ref = self.tint(2) or self.tint(0)
        if ref is not None:
            mode = "light" if self._lum(ref) > 0.5 else "dark"
        ctk.set_appearance_mode(mode)
        c = self.tint(0)
        if c:
            self.configure(fg_color=c)
        else:
            self.configure(fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def route(self):
        self.clear()
        email = self.store.current_email
        if self.store.data["settings"]["language"] is None:
            self.screen_language()
        elif email is None:
            self.screen_auth()
        elif not self.store.is_verified(email):
            self.screen_verify(email)
        elif (not self.store.is_owner(email)
              and email not in self._verified_this_run):
            # Bei jedem Login (auch mit bestehendem Konto) erneut den
            # Bestätigungscode verlangen — außer für Owner.
            self.screen_verify(email, force_new=True)
        else:
            self.screen_main()

    def notify(self, title: str, msg: str):
        if self.store.data["settings"].get("silent_mode"):
            return
        if self.store.data["settings"].get("sound_on_complete", True):
            try:
                if sys.platform == "win32":
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                else:
                    self.bell()
            except Exception:
                pass
        if not self.store.data["settings"]["notifications"]:
            return
        if plyer_notification is not None:
            try:
                plyer_notification.notify(title=title, message=msg,
                                          app_name=APP_NAME, timeout=6)
                return
            except Exception:
                pass
        messagebox.showinfo(title, msg)

    def _opt_text_color(self):
        """Kontrast-sichere Textfarbe für Dropdown-Menüs (CTkOptionMenu),
        passend zur tatsächlichen Akzentfarbe — verhindert unlesbaren
        Text bei sehr hellen (z. B. per Matching Mode gewählten) Farben."""
        bg = self.accent["main"]
        return "#111827" if self._lum(bg) > 0.6 else "#F9FAFB"

    def btn(self, parent, **kw):
        if "text" in kw:
            kw["text"] = self.rt(kw["text"])
        kw.setdefault("corner_radius", self.radius)
        bcol = (self.store.data["settings"].get("el_colors") or {}).get("button")
        if bcol:
            if self.is_retro:
                kw.setdefault("fg_color", "#0A1633")
                kw.setdefault("border_width", 2)
                kw.setdefault("border_color", bcol)
                kw.setdefault("text_color", bcol)
                kw.setdefault("hover_color", self._mix(bcol, "#000000", 0.68))
            else:
                kw.setdefault("fg_color", bcol)
                kw.setdefault("hover_color", self._mix(bcol, "#000000", 0.22))
        if self.is_retro:
            kw.setdefault("fg_color", "#0A1633")
            kw.setdefault("hover_color",
                          self._mix(self.accent["main"], "#000000", 0.68))
            kw.setdefault("border_width", 2)
            kw.setdefault("border_color", self.accent["main"])
            kw.setdefault("text_color", self.accent["main"])
        else:
            kw.setdefault("fg_color", self.accent["main"])
            kw.setdefault("hover_color", self.accent["hover"])
        # 🔤 Automatischer Kontrast: Egal wie hell/dunkel die gewählte
        # Akzent-/Button-Farbe ist (z. B. durch Matching Mode) — die
        # Textfarbe passt sich automatisch an, damit nichts unlesbar wird.
        if "text_color" not in kw:
            bg = kw.get("fg_color")
            if isinstance(bg, str) and bg.startswith("#") and len(bg) == 7:
                kw["text_color"] = ("#111827" if self._lum(bg) > 0.6
                                    else "#F9FAFB")
        kw.setdefault("font", self.font(size=14, weight="bold"))
        kw.setdefault("height", 42)
        return ctk.CTkButton(parent, **kw)

    # --- Screen 1: Sprachauswahl (erster Start) ------------------------------
    def screen_language(self):
        frame = ctk.CTkFrame(self, corner_radius=self.radius, **self.card_kw(2))
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="💜 " + APP_NAME,
                     font=self.font(size=34, weight="bold"),
                     text_color=self.accent["main"]).pack(padx=60, pady=(40, 6))
        ctk.CTkLabel(frame, text="Which language do you prefer?\nWelche Sprache bevorzugst du?",
                     font=self.font(size=16)).pack(padx=60, pady=(0, 24))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(pady=(0, 24))
        self.btn(row, text="🇩🇪  Deutsch", width=170,
                 command=lambda: self.set_language("de")).pack(side="left", padx=10)
        self.btn(row, text="🇬🇧  English", width=170,
                 command=lambda: self.set_language("en")).pack(side="left", padx=10)

        ctk.CTkLabel(frame, text=MADE_BY, font=self.font(size=11),
                     text_color="#6B7280").pack(pady=(0, 14))

    def set_language(self, lang):
        self.store.data["settings"]["language"] = lang
        self.store.save()
        self.route()

    # --- Screen 2: Konto erstellen / Login -----------------------------------
    def screen_auth(self, mode="register"):
        self.clear()
        frame = ctk.CTkFrame(self, corner_radius=self.radius, **self.card_kw(2))
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="💜 " + self.t("welcome"),
                     font=self.font(size=26, weight="bold"),
                     text_color=self.accent["main"]).pack(padx=70, pady=(36, 4))

        def toggle_lang():
            s = self.store.data["settings"]
            s["language"] = "en" if s["language"] == "de" else "de"
            self.store.save()
            self.screen_auth(mode)

        current = self.store.data["settings"]["language"]
        ctk.CTkButton(frame, text="🌐 Deutsch / English",
                      fg_color="transparent", hover=False, height=20,
                      text_color=self.muted(), font=self.font(size=11),
                      command=toggle_lang).pack()

        title = self.t("create_account") if mode == "register" else self.t("login")
        ctk.CTkLabel(frame, text=title, font=self.font(size=16)).pack(pady=(0, 18))

        email_e = ctk.CTkEntry(frame, placeholder_text=self.t("email"),
                               width=320, height=42, corner_radius=self.radius)
        email_e.pack(pady=6)
        pw_e = ctk.CTkEntry(frame, placeholder_text=self.t("password"), show="•",
                            width=320, height=42, corner_radius=self.radius)
        pw_e.pack(pady=6)

        err = ctk.CTkLabel(frame, text="", text_color="#F87171")
        err.pack()

        def submit():
            email, pw = email_e.get().strip(), pw_e.get()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                err.configure(text=self.t("invalid_email")); return
            if len(pw) < 4:
                err.configure(text=self.t("pw_too_short")); return
            if mode == "register":
                if not self.store.register(email, pw):
                    err.configure(text=self.t("user_exists")); return
                self.store.login(email, pw)
                threading.Thread(target=self.sync_premium_from_server,
                                 args=(email.lower(), False),
                                 daemon=True).start()
                threading.Thread(
                    target=self._offer_cloud_restore_if_available,
                    args=(email.lower(),), daemon=True).start()
                self.route()
            else:
                email_l = email.lower()
                user = self.store.data["users"].get(email_l)
                if (email_l in OWNER_EMAILS and user is not None
                        and not user.get("owner_verified", False)):
                    # Erste Owner-Anmeldung auf diesem Gerät -> einmalige
                    # Server-Prüfung (das echte Passwort steht nirgends
                    # im Programmcode, nur auf dem Backend-Server).
                    err.configure(text="🔄 " + self.t("owner_verifying"),
                                 text_color=self.muted())
                    threading.Thread(target=self._verify_owner_login,
                                     args=(email_l, pw, err),
                                     daemon=True).start()
                    return
                if not self.store.login(email, pw):
                    err.configure(text=self.t("wrong_login")); return
                threading.Thread(target=self.sync_premium_from_server,
                                 args=(email_l, False),
                                 daemon=True).start()
                self.route()

        label = self.t("register") if mode == "register" else self.t("login")
        self.btn(frame, text=label, width=320, command=submit).pack(pady=(8, 8))

        switch_text = self.t("have_account") if mode == "register" else self.t("no_account")
        switch_mode = "login" if mode == "register" else "register"
        ctk.CTkButton(frame, text=switch_text, fg_color="transparent",
                      hover=False, text_color=self.accent["main"],
                      command=lambda: self.screen_auth(switch_mode)).pack(pady=(0, 8))

        ctk.CTkLabel(frame, text=MADE_BY, font=self.font(size=11),
                     text_color="#6B7280").pack(pady=(0, 16))

    # --- Screen 2b: E-Mail-Verifizierung --------------------------------------
    def screen_verify(self, email, force_new=False):
        self.clear()
        frame = ctk.CTkFrame(self, corner_radius=self.radius, **self.card_kw(2))
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text=self.t("verify_title"),
                     font=self.font(size=22, weight="bold"),
                     text_color=self.accent["main"]).pack(padx=60,
                                                          pady=(36, 10))

        status_lbl = ctk.CTkLabel(frame, text="🔄 " + self.t("verify_sending"),
                                  wraplength=360, justify="center")
        status_lbl.pack(padx=40, pady=(0, 4))

        code_display = ctk.CTkEntry(frame, width=200, height=40,
                                    justify="center", state="disabled",
                                    corner_radius=self.radius,
                                    font=self.font(size=16, weight="bold"))
        # (wird nur befüllt & eingeblendet, wenn kein SMTP eingerichtet ist)

        user = self.store.data["users"].get(email, {})
        needs_new_code = (force_new
                          or not user.get("vcode_hash")
                          or not user.get("vcode_expires")
                          or datetime.datetime.now()
                          > datetime.datetime.fromisoformat(
                              user["vcode_expires"]))

        def deliver(code):
            def worker():
                ok, err = self.send_verification_code(email, code)
                self.after(0, lambda: show_result(ok, err))
            threading.Thread(target=worker, daemon=True).start()

        def show_result(ok, err=None):
            if ok:
                status_lbl.configure(
                    text="✓ " + self.t("verify_sent") + f"\n{email}")
                code_display.pack_forget()
            else:
                extra = ""
                if err and err != "not_configured":
                    extra = f"\n\n⚠ {err}"
                status_lbl.configure(
                    text="📋 " + self.t("verify_fallback") + extra)
                code_display.configure(state="normal")
                code_display.delete(0, "end")
                code_display.insert(0, current_code[0])
                code_display.configure(state="readonly")
                code_display.pack(pady=(4, 4))

        current_code = [None]
        if needs_new_code:
            current_code[0] = self.store.start_verification(email)
            deliver(current_code[0])
        else:
            status_lbl.configure(text=self.t("verify_sent") + f"\n{email}")

        code_e = ctk.CTkEntry(frame, placeholder_text=self.t("verify_code_ph"),
                              width=220, height=42, justify="center",
                              corner_radius=self.radius,
                              font=self.font(size=16))
        code_e.pack(pady=(14, 6))

        err = ctk.CTkLabel(frame, text="", text_color="#F87171")
        err.pack()

        def confirm():
            result = self.store.check_verification(email, code_e.get())
            if result == "ok":
                self._verified_this_run.add(email)
                self.route()
            elif result == "expired":
                err.configure(text=self.t("verify_expired"))
            else:
                err.configure(text=self.t("verify_wrong"))

        self.btn(frame, text=self.t("verify_button"), width=220,
                 command=confirm).pack(pady=(6, 8))

        def resend():
            current_code[0] = self.store.start_verification(email)
            status_lbl.configure(text="🔄 " + self.t("verify_sending"))
            code_display.pack_forget()
            deliver(current_code[0])

        ctk.CTkButton(frame, text=self.t("verify_resend"),
                      fg_color="transparent", hover=False,
                      text_color=self.accent["main"],
                      command=resend).pack(pady=(0, 4))

        def cancel():
            self.store.logout()
            self.route()

        ctk.CTkButton(frame, text=self.t("verify_cancel"),
                      fg_color="transparent", hover=False,
                      text_color=self.muted(),
                      font=self.font(size=11),
                      command=cancel).pack(pady=(0, 24))

    # --- Hauptfenster mit Sidebar --------------------------------------------
    def screen_main(self):
        self.clear()
        self._fx_gen = getattr(self, "_fx_gen", 0) + 1
        s = self.store.data["settings"]
        collapsed = s.get("sidebar_collapsed", False)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=(64 if collapsed else 210),
                               corner_radius=0, **self.card_kw(1))
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        def toggle_sidebar():
            s["sidebar_collapsed"] = not collapsed
            self.store.save()
            self.screen_main()

        ctk.CTkButton(sidebar, text=("▶" if collapsed else "◀"),
                      width=30, height=30, corner_radius=self.radius,
                      fg_color="transparent",
                      text_color=self.accent["main"],
                      hover_color=self._mix(self.accent["main"],
                                            "#000000", 0.68),
                      font=self.font(size=13, weight="bold"),
                      command=toggle_sidebar).pack(
                          anchor=("center" if collapsed else "e"),
                          padx=8, pady=(10, 0))

        if collapsed:
            ctk.CTkLabel(sidebar, text="💜",
                         font=self.font(size=22)).pack(pady=(4, 4))
            if self.store.is_owner():
                ctk.CTkLabel(sidebar, text="👑",
                             font=self.font(size=14)).pack(pady=(0, 6))
            elif self.store.is_premium():
                ctk.CTkLabel(sidebar, text="★", text_color="#FBBF24",
                             font=self.font(size=14)).pack(pady=(0, 6))
        else:
            ctk.CTkLabel(sidebar, text=self.rt("💜 " + APP_NAME),
                         font=self.font(size=22, weight="bold"),
                         text_color=self.accent["main"]).pack(pady=(4, 4))

            name = self.store.display_name()
            style = self.store.name_style()
            deco = {"glitter": "✨ {} ✨", "rainbow": "🌈 {} 🌈",
                    "hearts": "💖 {} 💖", "fire": "🔥 {} 🔥",
                    "pulse": "💫 {} 💫"}.get(style, "{}")
            ctk.CTkLabel(sidebar, text=self.t("hello") + ",",
                         font=self.font(size=12),
                         text_color=self.text_on(1)).pack(pady=(6, 0))
            ncol = (s.get("el_colors") or {}).get("name")
            name_lbl = ctk.CTkLabel(sidebar, text=deco.format(name),
                                    font=self.font(size=15, weight="bold"),
                                    text_color=(ncol if ncol
                                                else self.text_on(1)))
            name_lbl.pack(pady=(0, 6))
            if style in ("glitter", "rainbow", "fire", "pulse"):
                self._animate_name(name_lbl, style)

            if self.store.is_owner():
                ctk.CTkLabel(sidebar, text="👑 " + self.t("owner_badge"),
                             font=self.font(size=11, weight="bold"),
                             text_color="#FBBF24",
                             wraplength=180).pack(pady=(0, 12))
            elif self.store.is_premium():
                ctk.CTkLabel(sidebar, text="★ " + self.t("status_premium"),
                             font=self.font(size=12, weight="bold"),
                             text_color="#FBBF24").pack(pady=(0, 12))
            else:
                ctk.CTkLabel(sidebar, text=self.t("status_free"),
                             font=self.font(size=12),
                             text_color=self.text_on(1, muted=True)
                             or "#9CA3AF").pack(pady=(0, 12))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)

        def nav(text, cmd, icon):
            if collapsed:
                b = ctk.CTkButton(sidebar, text=icon, width=44, height=40,
                                  corner_radius=self.radius,
                                  fg_color="transparent",
                                  hover_color=(self._mix(self.accent["main"],
                                                         "#000000", 0.68)
                                               if self.is_retro
                                               else self.accent["hover"]),
                                  text_color=(self.accent["main"]
                                              if self.is_retro
                                              else self.text_on(1)),
                                  font=self.font(size=17), command=cmd)
                b.pack(padx=8, pady=3)
            else:
                b = ctk.CTkButton(sidebar, text=f"{icon}  {self.rt(text)}",
                                  anchor="w",
                                  corner_radius=self.radius, height=40,
                                  fg_color="transparent",
                                  hover_color=(self._mix(self.accent["main"],
                                                         "#000000", 0.68)
                                               if self.is_retro
                                               else self.accent["hover"]),
                                  text_color=(self.accent["main"]
                                              if self.is_retro
                                              else self.text_on(1)),
                                  font=self.font(size=14), command=cmd)
                b.pack(fill="x", padx=14, pady=3)
            return b

        nav(self.t("download"), self.page_download, "⬇")
        nav(self.t("ai_studio"), self.page_ai_studio, "🎨")
        nav(self.t("premium"), self.page_premium, "★")
        nav(self.t("settings"), self.page_settings, "⚙")
        if self.store.is_owner():
            nav(self.t("admin"), self.page_admin, "👑")

        if not collapsed:
            ctk.CTkLabel(sidebar, text=MADE_BY, font=self.font(size=10),
                         text_color=self.text_on(1, muted=True)
                         or "#6B7280", wraplength=170,
                         justify="center").pack(side="bottom", pady=(0, 8))
        ctk.CTkButton(sidebar,
                      text=("⏻" if collapsed else "⏻  " + self.rt(self.t("logout"))),
                      anchor=("center" if collapsed else "w"),
                      corner_radius=self.radius, height=40,
                      width=(44 if collapsed else 140),
                      fg_color="transparent", hover_color="#7F1D1D",
                      font=self.font(size=14),
                      command=self.do_logout).pack(side="bottom",
                                                   fill=("none" if collapsed else "x"),
                                                   padx=(8 if collapsed else 14),
                                                   pady=(16, 6))

        # Animierte Effekte — im Sparmodus (alte/schwache PCs) abgeschaltet
        effect = s.get("effect", "none")
        if not s.get("performance_mode", False):
            if effect == "aurora":
                self._aurora(self._fx_gen, sidebar)
            elif effect == "snow" and not collapsed:
                self._snow(self._fx_gen, sidebar)

        page = getattr(self, "_page", None) or self.page_download
        if page == getattr(self, "page_admin", None) and not self.store.is_owner():
            page = self.page_download
        page()

        if not getattr(self, "_whats_new_checked", False):
            self._whats_new_checked = True
            email = self.store.current_email
            user = self.store.data["users"].get(email, {})
            if not user.get("tour_seen"):
                self.after(400, self._show_first_tour)
            else:
                self.after(400, self.maybe_show_whats_new)

    def _show_first_tour(self):
        email = self.store.current_email
        user = self.store.data["users"].get(email)
        if user is not None:
            user["tour_seen"] = True
            self.store.save()
        self.show_feature_tour()
        self.after(300, self.maybe_show_whats_new)

    def _animate_name(self, label, style, i=0):
        """Animationen für Premium-Namen."""
        if not label.winfo_exists():
            return
        delay = 320
        if style == "rainbow":
            colors = ["#F87171", "#FB923C", "#FBBF24", "#34D399",
                      "#60A5FA", "#A78BFA", "#F472B6"]
            label.configure(text_color=colors[i % len(colors)])
        elif style == "fire":
            colors = ["#F87171", "#FB923C", "#F59E0B", "#DC2626", "#FDBA74"]
            label.configure(text_color=random.choice(colors))
            delay = 130
        elif style == "pulse":
            sizes = [14, 15, 16, 17, 16, 15]
            ncol = ((self.store.data["settings"].get("el_colors") or {})
                    .get("name")) or self.accent["main"]
            label.configure(font=self.font(size=sizes[i % 6], weight="bold"),
                            text_color=ncol)
            delay = 160
        else:  # glitter
            colors = ["#FDE68A", "#FBBF24", "#FFFFFF", "#F59E0B", "#FEF3C7"]
            label.configure(text_color=colors[i % len(colors)])
        self.after(delay, lambda: self._animate_name(label, style, i + 1))

    def _aurora(self, gen, sidebar, t=0.0):
        """🌈 Aurora: Hintergrundfarbe wandert langsam durch die Farbtöne."""
        if gen != getattr(self, "_fx_gen", 0) or not sidebar.winfo_exists():
            return
        import colorsys
        import math
        base = self.accent["main"]
        r, g, b = (int(base[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, sat, val = colorsys.rgb_to_hsv(r, g, b)
        # Sanft um die eigene Farbrichtung pendeln statt durch alle Farben
        h = (h + 0.09 * math.sin(t * 6.0)) % 1.0
        r2, g2, b2 = colorsys.hsv_to_rgb(h, max(sat, 0.5), val)
        col = "#%02x%02x%02x" % (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        light = self.store.data["settings"]["appearance"] == "light"
        target = "#FFFFFF" if light else "#000000"
        try:
            self.configure(fg_color=self._mix(col, target, 0.88))
            sidebar.configure(fg_color=self._mix(col, target, 0.80))
        except Exception:
            return
        self.after(120, lambda: self._aurora(gen, sidebar, t + 0.004))

    def _snow(self, gen, sidebar):
        """❄ Schnee-Effekt in der Sidebar (wie im Launcher)."""
        import tkinter as tk
        bgcol = self.tint(1) or ("#EBEBEB" if self.store.data["settings"]
                                 ["appearance"] == "light" else "#212121")
        canvas = tk.Canvas(sidebar, height=110, bg=bgcol,
                           highlightthickness=0, bd=0)
        canvas.pack(side="bottom", fill="x", pady=(0, 2))
        w = 190
        flakes = [[random.randint(2, w - 2), random.randint(0, 110),
                   random.uniform(0.5, 1.8), random.choice([1, 1, 2, 2, 3])]
                  for _ in range(16)]
        s2 = self.store.data["settings"]
        sb = self.tint(1)
        dark2 = (self._lum(sb) < 0.5) if sb else (
            self.is_retro or s2["appearance"] == "dark")
        color = ((s2.get("el_colors") or {}).get("name")
                 or ("#FFFFFF" if dark2
                     else self._mix(self.accent["main"], "#000000", 0.15)))
        ids = [canvas.create_oval(0, 0, 0, 0, fill=color, outline="")
               for _ in flakes]

        def step():
            if gen != getattr(self, "_fx_gen", 0) or not canvas.winfo_exists():
                return
            for f, i in zip(flakes, ids):
                f[1] += f[2]
                if f[1] > 112:
                    f[1] = -3
                    f[0] = random.randint(2, w - 2)
                r = f[3]
                canvas.coords(i, f[0] - r, f[1] - r, f[0] + r, f[1] + r)
            self.after(60, step)

        step()

    def do_logout(self):
        self.store.logout()
        self.route()

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    # --- Seite: Download ------------------------------------------------------
    def page_download(self):
        self._page = self.page_download
        self.clear_content()
        premium = self.store.is_premium()

        outer = self.make_scroll_area(self.content, colored=False)

        card = ctk.CTkFrame(outer, corner_radius=self.radius,
                            **self.card_kw(2))
        card.pack(fill="x")

        ctk.CTkLabel(card, text="⬇ " + self.t("download"),
                     font=self.font(size=24, weight="bold")).pack(
                         anchor="w", padx=28, pady=(24, 4))

        muted = self.muted()
        ph = self.t("paste_link_premium") if premium else self.t("paste_link")
        self.url_entry = ctk.CTkEntry(card, placeholder_text=ph, height=48,
                                      corner_radius=self.radius,
                                      font=self.font(size=14))
        self.url_entry.pack(fill="x", padx=28, pady=(14, 18))
        self.url_entry.bind("<Return>", lambda e: self.start_download())

        preset_row = ctk.CTkFrame(card, fg_color="transparent")
        preset_row.pack(fill="x", padx=28, pady=(0, 14))
        ctk.CTkLabel(preset_row, text=self.t("quick_presets"),
                     text_color=muted, font=self.font(size=11)).pack(
                         side="left", padx=(0, 8))

        def preset_music():
            if not premium:
                self.show_premium_dialog(self.t("format_locked"))
                return
            self.fmt_var.set("mp3")

        def preset_video():
            self.fmt_var.set("mp4")

        ctk.CTkButton(preset_row, text="🎵 " + self.t("preset_music"),
                     width=110, height=28, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     font=self.font(size=11),
                     command=preset_music).pack(side="left", padx=(0, 6))
        ctk.CTkButton(preset_row, text="🎬 " + self.t("preset_video"),
                     width=110, height=28, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     font=self.font(size=11),
                     command=preset_video).pack(side="left")
        ctk.CTkButton(preset_row, text="⭐ " + self.t("favorites"),
                     width=110, height=28, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     font=self.font(size=11),
                     command=self.show_favorites_dialog).pack(side="left",
                                                              padx=(6, 0))

        # --- Plattform-Auswahl (inkl. Web-Browser & KI-Modus) ---
        def plat_label(key, text):
            locked = key in ("ai", "direct", "browser") and not premium
            return text + " 🔒" if locked else text

        labels = {"ai": plat_label("ai", self.t("ai_mode")),
                  "youtube": "▶ YouTube", "tiktok": "🎵 TikTok",
                  "instagram": "📷 Instagram", "facebook": "📘 Facebook",
                  "browser": plat_label("browser", self.t("web_browser")),
                  "nowm": self.t("nowm"),
                  "direct": plat_label("direct", self.t("direct_link"))}
        self._plat_by_label = {v: k for k, v in labels.items()}

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=28)
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_columnconfigure(3, weight=1)

        LBL_KW = dict(font=self.font(size=12, weight="bold"),
                      text_color=muted, anchor="w")
        MENU_H = 40

        # Zeile 1: Plattform | Auflösung
        ctk.CTkLabel(grid, text=self.t("platform").upper(),
                     **LBL_KW).grid(row=0, column=0, sticky="w",
                                    pady=(0, 4), padx=(0, 10))
        ctk.CTkLabel(grid, text=self.t("resolution").upper(),
                     **LBL_KW).grid(row=0, column=2, sticky="w",
                                    pady=(0, 4), padx=(16, 10))

        self.plat_var = ctk.StringVar(
            value=self.t("ai_mode") if premium else "▶ YouTube")
        ctk.CTkOptionMenu(grid, values=list(labels.values()),
                          variable=self.plat_var,
                          command=self._platform_changed,
                          height=MENU_H, corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"], text_color=self._opt_text_color(),
                          font=self.font(size=13)).grid(
                              row=1, column=0, sticky="ew", padx=(0, 10),
                              pady=(0, 14))

        self.res_var = ctk.StringVar(value=RES_DISPLAY["720p"])
        self.res_menu = ctk.CTkOptionMenu(
            grid, values=self._res_values(), variable=self.res_var,
            command=self._res_changed, height=MENU_H,
            corner_radius=self.radius, fg_color=self.accent["main"],
            button_color=self.accent["hover"], text_color=self._opt_text_color(), font=self.font(size=13))
        self.res_menu.grid(row=1, column=2, sticky="ew", padx=(16, 0),
                           pady=(0, 14))

        self.upscale_var = ctk.BooleanVar(
            value=self.store.data["settings"].get("auto_upscale", False))

        def toggle_upscale_dl():
            if not premium:
                self.upscale_var.set(False)
                self.show_premium_dialog(self.t("locked_platform"))
                return
            self.store.data["settings"]["auto_upscale"] = \
                self.upscale_var.get()
            self.store.save()

        ctk.CTkCheckBox(
            grid, text="🔍 " + self.t("auto_upscale_short"),
            variable=self.upscale_var, command=toggle_upscale_dl,
            font=self.font(size=11),
            fg_color=self.accent["main"]).grid(
                row=2, column=2, sticky="w", pady=(0, 4), padx=(16, 0))

        # Zeile 2: Format | (Downloadknopf steht separat darunter)
        ctk.CTkLabel(grid, text=self.t("format").upper(),
                     **LBL_KW).grid(row=2, column=0, sticky="w",
                                    pady=(0, 4), padx=(0, 10))

        self.fmt_var = ctk.StringVar(value=self.t("auto_field"))
        self._fmt_by_label = {self.t("auto_field"): "auto"}
        self.fmt_menu = ctk.CTkOptionMenu(
            grid, values=[self.t("auto_field")], variable=self.fmt_var,
            command=self._fmt_changed, height=MENU_H,
            corner_radius=self.radius, fg_color=self.accent["main"],
            button_color=self.accent["hover"], text_color=self._opt_text_color(), font=self.font(size=13))
        self.fmt_menu.grid(row=3, column=0, columnspan=3, sticky="ew",
                           padx=(0, 0), pady=(0, 6))

        # KI-Modus Hinweistext (nur sichtbar, wenn KI-Modus gewählt ist)
        self.ai_hint_lbl = ctk.CTkLabel(
            card, text="🤖 " + self.t("ai_hint"), text_color=muted,
            font=self.font(size=11), wraplength=560, justify="left")
        self.ai_hint_lbl.pack(anchor="w", padx=28, pady=(0, 4))

        if not premium:
            ctk.CTkLabel(card, text="🔒 " + self.t("get_premium_hint"),
                         text_color="#FBBF24",
                         font=self.font(size=12)).pack(anchor="w", padx=28,
                                                        pady=(2, 4))

        # ⚡ Erweiterte Optionen — eigener, klar abgegrenzter Bereich mit
        # fetter Beschriftung, damit sich diese Zusatzfunktionen deutlich
        # vom normalen Text absetzen. Alle Zeilen werden über "after="
        # gepackt, damit sich beim Ein-/Ausblenden (z. B. der Ausschnitt-
        # Zeit) niemals die Reihenfolge verschiebt.
        adv = ctk.CTkFrame(card, corner_radius=self.radius,
                           border_width=1, border_color=self.accent["main"],
                           fg_color=(self.tint(2) or "transparent"))
        adv.pack(fill="x", padx=28, pady=(4, 16))
        ctk.CTkLabel(adv, text="⚡ " + self.t("advanced_options"),
                     font=self.font(size=13, weight="bold"),
                     text_color=self.accent["main"]).pack(anchor="w",
                                                          padx=16,
                                                          pady=(14, 10))
        BOLD = dict(font=self.font(size=13, weight="bold"))

        # 📋 Warteschlange: mehrere Links auf einmal (einer pro Zeile)
        self.batch_var = ctk.BooleanVar(value=False)
        batch_cb = ctk.CTkCheckBox(adv, text="📋 " + self.t("batch_mode"),
                                   variable=self.batch_var,
                                   fg_color=self.accent["main"], **BOLD)
        batch_cb.pack(anchor="w", padx=16, pady=(0, 4))
        max_batch = max(1, int(self.store.data["settings"].get(
            "concurrent_downloads", 1)))
        batch_hint = ctk.CTkLabel(
            adv, text=f"({self.t('batch_max_hint')} {max_batch})",
            text_color=self.muted(), font=self.font(size=11))
        batch_hint.pack(anchor="w", padx=16, pady=(0, 4))

        # Eigener Rahmen mit Zeilennummern-Spalte (wie ein Code-Editor),
        # statt einer leeren, unstrukturiert wirkenden Box.
        batch_container = ctk.CTkFrame(adv, corner_radius=self.radius,
                                      border_width=1,
                                      border_color=self.accent["main"],
                                      **self.card_kw(0))

        gutter_bg = self._mix(self.accent["main"], "#000000", 0.82)
        self.batch_gutter = ctk.CTkTextbox(
            batch_container, width=34, corner_radius=0,
            fg_color=gutter_bg, text_color=self.muted(),
            font=self.font(size=13), wrap="none",
            scrollbar_button_color=gutter_bg,
            scrollbar_button_hover_color=gutter_bg)
        self.batch_gutter.insert("1.0", "1")
        self.batch_gutter.configure(state="disabled")
        self.batch_gutter.pack(side="left", fill="y", padx=(1, 0), pady=1)

        self.batch_box = ctk.CTkTextbox(
            batch_container, height=90, corner_radius=0,
            fg_color="transparent", font=self.font(size=13))
        self.batch_box.pack(side="left", fill="both", expand=True,
                            padx=(4, 1), pady=1)

        def update_batch_gutter(_e=None):
            n_lines = self.batch_box.get("1.0", "end-1c").count("\n") + 1
            self.batch_gutter.configure(state="normal")
            self.batch_gutter.delete("1.0", "end")
            self.batch_gutter.insert(
                "1.0", "\n".join(str(i) for i in range(1, n_lines + 1)))
            self.batch_gutter.configure(state="disabled")

        self.batch_box.bind("<KeyRelease>", update_batch_gutter)

        def toggle_batch():
            if self.batch_var.get():
                self.url_entry.pack_forget()
                batch_container.pack(fill="x", padx=16, pady=(0, 12),
                                     after=batch_hint)
            else:
                batch_container.pack_forget()
                self.url_entry.pack(fill="x", padx=28, pady=(14, 18),
                                    before=grid)

        batch_cb.configure(command=toggle_batch)

        # 📺 Ganze Playlist/Kanal laden (Premium)
        self.playlist_var = ctk.BooleanVar(value=False)
        playlist_cb = ctk.CTkCheckBox(adv, text=self.t("playlist_mode"),
                                      variable=self.playlist_var,
                                      fg_color=self.accent["main"], **BOLD)
        playlist_cb.pack(anchor="w", padx=16, pady=(4, 4))
        playlist_lbl = ctk.CTkLabel(
            adv, text="📺 " + self.t("playlist_url_label"),
            text_color=self.muted(), font=self.font(size=11))
        self.playlist_url_e = ctk.CTkEntry(
            adv, placeholder_text=self.t("playlist_url_ph"), height=36,
            corner_radius=self.radius, border_width=1,
            border_color=self.accent["main"])

        # ✂️ Nur einen Ausschnitt laden (Premium)
        self.clip_var = ctk.BooleanVar(value=False)
        clip_cb = ctk.CTkCheckBox(adv, text=self.t("clip_mode"),
                                  variable=self.clip_var,
                                  fg_color=self.accent["main"], **BOLD)
        clip_cb.pack(anchor="w", padx=16, pady=(0, 4))
        clip_url_lbl = ctk.CTkLabel(
            adv, text="✂️ " + self.t("clip_url_label"),
            text_color=self.muted(), font=self.font(size=11))
        self.clip_url_e = ctk.CTkEntry(
            adv, placeholder_text=self.t("clip_url_ph"), height=36,
            corner_radius=self.radius, border_width=1,
            border_color=self.accent["main"])
        clip_row = ctk.CTkFrame(adv, fg_color="transparent")

        def toggle_playlist():
            if not premium:
                self.playlist_var.set(False)
                self.show_premium_dialog(self.t("locked_platform"))
                return
            if self.playlist_var.get():
                self.clip_var.set(False)
                clip_url_lbl.pack_forget()
                self.clip_url_e.pack_forget()
                clip_row.pack_forget()
                playlist_lbl.pack(anchor="w", padx=16, pady=(0, 2),
                                  after=playlist_cb)
                self.playlist_url_e.pack(fill="x", padx=16, pady=(0, 12),
                                         after=playlist_lbl)
            else:
                playlist_lbl.pack_forget()
                self.playlist_url_e.pack_forget()

        def toggle_clip():
            if not premium:
                self.clip_var.set(False)
                self.show_premium_dialog(self.t("locked_platform"))
                return
            if self.clip_var.get():
                self.playlist_var.set(False)
                playlist_lbl.pack_forget()
                self.playlist_url_e.pack_forget()
                clip_url_lbl.pack(anchor="w", padx=16, pady=(0, 2),
                                  after=clip_cb)
                self.clip_url_e.pack(fill="x", padx=16, pady=(0, 8),
                                     after=clip_url_lbl)
                clip_row.pack(fill="x", padx=16, pady=(0, 12),
                             after=self.clip_url_e)
            else:
                clip_url_lbl.pack_forget()
                self.clip_url_e.pack_forget()
                clip_row.pack_forget()

        playlist_cb.configure(command=toggle_playlist)
        clip_cb.configure(command=toggle_clip)

        ctk.CTkLabel(clip_row, text=self.t("clip_from"), width=90,
                    anchor="w").pack(side="left")
        self.clip_from_e = ctk.CTkEntry(clip_row, width=80, height=30,
                                        corner_radius=self.radius,
                                        placeholder_text="0:00")
        self.clip_from_e.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(clip_row, text=self.t("clip_to"), width=70,
                    anchor="w").pack(side="left")
        self.clip_to_e = ctk.CTkEntry(clip_row, width=80, height=30,
                                      corner_radius=self.radius,
                                      placeholder_text="1:30")
        self.clip_to_e.pack(side="left")

        # 🕑 Später starten (Zeitplanung)
        sched_row = ctk.CTkFrame(adv, fg_color="transparent")
        sched_row.pack(fill="x", padx=16, pady=(4, 14))
        self.sched_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sched_row, text=self.t("schedule_title"),
                       variable=self.sched_var,
                       fg_color=self.accent["main"], **BOLD).pack(
                           side="left", padx=(0, 10))
        self.sched_time_e = ctk.CTkEntry(
            sched_row, placeholder_text=self.t("schedule_time_ph"),
            width=90, height=32, corner_radius=self.radius,
            justify="center")
        self.sched_time_e.pack(side="left")

        # 🖼️ Wallpaper-Download (Premium) — eigener, separater Kasten
        wp_box = ctk.CTkFrame(card, corner_radius=self.radius,
                              border_width=1,
                              border_color=self.accent["main"],
                              **self.card_kw(2))
        wp_box.pack(fill="x", padx=28, pady=(0, 16))

        self.wallpaper_var = ctk.BooleanVar(value=False)
        wallpaper_cb = ctk.CTkCheckBox(wp_box, text=self.t("wallpaper_mode"),
                                      variable=self.wallpaper_var,
                                      fg_color=self.accent["main"], **BOLD)
        wallpaper_cb.pack(anchor="w", padx=16, pady=(14, 4))
        wallpaper_url_lbl = ctk.CTkLabel(
            wp_box, text="🖼️ " + self.t("wallpaper_url_label"),
            text_color=self.muted(), font=self.font(size=11))
        self.wallpaper_url_e = ctk.CTkEntry(
            wp_box, placeholder_text=self.t("wallpaper_url_ph"), height=36,
            corner_radius=self.radius, border_width=1,
            border_color=self.accent["main"])
        wallpaper_row = ctk.CTkFrame(wp_box, fg_color="transparent")
        wp_spacer = ctk.CTkFrame(wp_box, height=10, fg_color="transparent")
        wp_spacer.pack(pady=0)

        device_labels = {"ios": "📱 iOS", "android": "🤖 Android",
                         "windows": "🖥️ " + self.t("wallpaper_windows")}
        self._device_by_label = {v: k for k, v in device_labels.items()}
        self.wallpaper_device_var = ctk.StringVar(value=device_labels["ios"])
        self.wallpaper_res_var = ctk.StringVar(
            value=WALLPAPER_RESOLUTIONS["ios"][0][0])

        def refresh_wallpaper_res(_=None):
            dev = self._device_by_label.get(
                self.wallpaper_device_var.get(), "ios")
            opts = [r[0] for r in WALLPAPER_RESOLUTIONS[dev]]
            self.wallpaper_res_menu.configure(values=opts)
            self.wallpaper_res_var.set(opts[0])

        ctk.CTkOptionMenu(wallpaper_row, values=list(device_labels.values()),
                          variable=self.wallpaper_device_var,
                          command=refresh_wallpaper_res, width=140,
                          height=32, corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"],
                          text_color=self._opt_text_color()).pack(
                              side="left", padx=(0, 8))
        self.wallpaper_res_menu = ctk.CTkOptionMenu(
            wallpaper_row,
            values=[r[0] for r in WALLPAPER_RESOLUTIONS["ios"]],
            variable=self.wallpaper_res_var, width=200, height=32,
            corner_radius=self.radius, fg_color=self.accent["main"],
            button_color=self.accent["hover"],
            text_color=self._opt_text_color())
        self.wallpaper_res_menu.pack(side="left")

        def toggle_wallpaper():
            if not premium:
                self.wallpaper_var.set(False)
                self.show_premium_dialog(self.t("locked_platform"))
                return
            if self.wallpaper_var.get():
                wallpaper_url_lbl.pack(anchor="w", padx=16, pady=(0, 2),
                                       after=wallpaper_cb)
                self.wallpaper_url_e.pack(fill="x", padx=16, pady=(0, 10),
                                          after=wallpaper_url_lbl)
                wallpaper_row.pack(fill="x", padx=16, pady=(0, 14),
                                   after=self.wallpaper_url_e)
            else:
                wallpaper_url_lbl.pack_forget()
                self.wallpaper_url_e.pack_forget()
                wallpaper_row.pack_forget()

        wallpaper_cb.configure(command=toggle_wallpaper)

        # 🌍 Untertitel & Übersetzung — eigener Kasten, direkt erreichbar
        subs_box = ctk.CTkFrame(card, corner_radius=self.radius,
                                border_width=1,
                                border_color=self.accent["main"],
                                **self.card_kw(2))
        subs_box.pack(fill="x", padx=28, pady=(0, 16))

        s_settings = self.store.data["settings"]
        subs_cb_var = ctk.BooleanVar(value=s_settings.get("download_subs",
                                                          False))
        subs_cb = ctk.CTkCheckBox(subs_box, text="🌍 " + self.t(
            "subs_download"), variable=subs_cb_var,
            fg_color=self.accent["main"], **BOLD)
        subs_cb.pack(anchor="w", padx=16, pady=(14, 8))

        subs_lang_row = ctk.CTkFrame(subs_box, fg_color="transparent")
        sub_langs_dl = {"en": "English", "de": "Deutsch", "es": "Español",
                        "fr": "Français", "pt": "Português",
                        "it": "Italiano", "ja": "日本語", "ko": "한국어",
                        "zh": "中文", "ru": "Русский",
                        "all": self.t("sub_lang_all"),
                        "custom": self.t("sub_lang_custom")}
        cur_lang_dl = s_settings.get("sub_lang", "en")
        is_custom_dl = cur_lang_dl not in sub_langs_dl
        sub_var_dl = ctk.StringVar(
            value=self.t("sub_lang_custom") if is_custom_dl
            else sub_langs_dl.get(cur_lang_dl, "English"))
        custom_lang_dl_e = ctk.CTkEntry(subs_lang_row, width=90, height=32,
                                        corner_radius=self.radius,
                                        placeholder_text="sv, th, vi...")
        if is_custom_dl:
            custom_lang_dl_e.insert(0, cur_lang_dl)

        def save_custom_lang_dl(_e=None):
            code = custom_lang_dl_e.get().strip().lower()
            if code:
                s_settings["sub_lang"] = code
                self.store.save()

        custom_lang_dl_e.bind("<FocusOut>", save_custom_lang_dl)
        custom_lang_dl_e.bind("<Return>", save_custom_lang_dl)

        def change_sub_lang_dl(v):
            rev = {val: key for key, val in sub_langs_dl.items()}
            key = rev.get(v, "en")
            if key == "custom":
                custom_lang_dl_e.pack(side="left", padx=(8, 0))
            else:
                custom_lang_dl_e.pack_forget()
                s_settings["sub_lang"] = key
                self.store.save()

        ctk.CTkLabel(subs_lang_row, text=self.t("sub_lang_label"),
                    width=140, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(subs_lang_row, values=list(sub_langs_dl.values()),
                          variable=sub_var_dl, command=change_sub_lang_dl,
                          width=160, height=32, corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"],
                          text_color=self._opt_text_color()).pack(
                              side="left")
        if is_custom_dl:
            custom_lang_dl_e.pack(side="left", padx=(8, 0))

        def toggle_subs_dl():
            s_settings["download_subs"] = subs_cb_var.get()
            self.store.save()
            if subs_cb_var.get():
                subs_lang_row.pack(fill="x", padx=16, pady=(0, 6),
                                   after=subs_cb)
                subs_hint.pack(anchor="w", padx=16, pady=(0, 14))
            else:
                subs_lang_row.pack_forget()
                subs_hint.pack_forget()

        subs_cb.configure(command=toggle_subs_dl)
        subs_hint = ctk.CTkLabel(subs_box, text=self.t("sub_lang_hint"),
                                 text_color=self.muted(),
                                 font=self.font(size=11), wraplength=520,
                                 justify="left")
        if subs_cb_var.get():
            subs_lang_row.pack(fill="x", padx=16, pady=(0, 6),
                               after=subs_cb)
            subs_hint.pack(anchor="w", padx=16, pady=(0, 14))
        else:
            wp_spacer2 = ctk.CTkFrame(subs_box, height=6,
                                     fg_color="transparent")
            wp_spacer2.pack()

        # Trennlinie vor dem Aktionsbereich — wirkt strukturierter
        sep = ctk.CTkFrame(card, height=1,
                           fg_color=self._mix(muted, self.tint(2) or
                                              ("#000000" if self.store
                                               .data["settings"]
                                               ["appearance"] == "dark"
                                               else "#FFFFFF"), 0.7))
        sep.pack(fill="x", padx=28, pady=(10, 16))

        action_row = ctk.CTkFrame(card, fg_color="transparent")
        action_row.pack(fill="x", padx=28, pady=(0, 22))
        self.dl_btn = self.btn(action_row,
                               text="⬇  " + self.t("start_download"),
                               width=220, height=46,
                               command=self.start_download)
        self.dl_btn.pack(side="left")

        prog_col = ctk.CTkFrame(action_row, fg_color="transparent")
        prog_col.pack(side="left", fill="x", expand=True, padx=(18, 0))
        self.progress = ctk.CTkProgressBar(prog_col, corner_radius=self.radius,
                                           progress_color=self.accent["main"],
                                           height=10)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(4, 4))

        stat_row = ctk.CTkFrame(prog_col, fg_color="transparent")
        stat_row.pack(fill="x")
        self.status_lbl = ctk.CTkLabel(stat_row, text="",
                                       font=self.font(size=12),
                                       text_color=muted)
        self.status_lbl.pack(side="left")
        self.pct_lbl = ctk.CTkLabel(stat_row, text="",
                                    font=self.font(size=12, weight="bold"),
                                    text_color=self.accent["main"])
        self.pct_lbl.pack(side="right")

        self._platform_changed(self.plat_var.get())

        # Verlauf mit Such-/Filterfunktion
        history = self.store.data.get("history", [])
        if history:
            stats = self.store.data.get(
                "stats", {"total_files": 0, "total_bytes": 0, "platforms": {}})
            size_gb = stats.get("total_bytes", 0) / (1024 ** 3)
            size_txt = (f"{size_gb:.2f} GB" if size_gb >= 1
                       else f"{stats.get('total_bytes', 0) / (1024**2):.1f} MB")
            plats = stats.get("platforms", {})
            top_plat = max(plats, key=plats.get).capitalize() if plats else "—"

            stats_row = ctk.CTkFrame(outer, fg_color="transparent")
            stats_row.pack(fill="x", padx=28, pady=(18, 4))
            ctk.CTkLabel(
                stats_row,
                text=(f"📊 {stats.get('total_files', 0)} "
                     f"{self.t('stats_total_files').lower()}  ·  "
                     f"{size_txt}  ·  {self.t('stats_top_platform')}: "
                     f"{top_plat}"),
                font=self.font(size=12), text_color=self.muted()).pack(
                    side="left")

            def export_csv():
                path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    initialfile="downloader3_verlauf.csv",
                    filetypes=[("CSV", "*.csv")],
                    title=self.t("export_csv"))
                if not path:
                    return
                import csv as _csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = _csv.writer(f)
                    w.writerow(["Date", "File", "URL", "Size (bytes)"])
                    for item in reversed(self.store.data.get("history", [])):
                        w.writerow([item.get("date", ""),
                                   os.path.basename(item.get("file", "")),
                                   item.get("url", ""),
                                   item.get("size", 0)])
                messagebox.showinfo(APP_NAME, self.t("export_csv_ok"))

            ctk.CTkButton(stats_row, text=self.t("export_csv"), width=200,
                         height=28, corner_radius=self.radius,
                         fg_color="transparent", border_width=1,
                         border_color=self.accent["main"],
                         text_color=self.accent["main"],
                         hover_color=self.accent["hover"],
                         font=self.font(size=11),
                         command=export_csv).pack(side="right")

            ctk.CTkLabel(outer, text="🕓 " + self.t("history"),
                         font=self.font(size=16, weight="bold")).pack(
                             anchor="w", padx=28, pady=(6, 6))

            search_e = ctk.CTkEntry(outer,
                                    placeholder_text=self.t("history_search_ph"),
                                    height=48, corner_radius=self.radius,
                                    font=self.font(size=14))
            search_e.pack(fill="x", padx=28, pady=(0, 10))

            hist_frame = self.make_scroll_area(outer, colored=True,
                                               height=170, padx=28)

            def render_history(*_):
                query = search_e.get().strip().lower()
                for w in hist_frame.winfo_children():
                    w.destroy()
                filtered = [item for item in reversed(history)
                           if query in os.path.basename(
                               item["file"]).lower()]
                if not filtered:
                    ctk.CTkLabel(hist_frame, text=self.t("history_no_match"),
                                text_color=self.muted()).pack(pady=12)
                    return
                for item in filtered[:30]:
                    row = ctk.CTkFrame(hist_frame, fg_color="transparent")
                    row.pack(fill="x", pady=3, padx=4)
                    name = os.path.basename(item["file"])
                    if len(name) > 46:
                        name = name[:43] + "..."
                    ctk.CTkLabel(row, text=f"✓  {name}", anchor="w").pack(
                        side="left", padx=8)
                    ctk.CTkLabel(row, text=item.get("date", ""),
                                text_color=self.muted(),
                                font=self.font(size=11)).pack(side="right",
                                                              padx=8)
                    ctk.CTkButton(row, text=self.t("open_folder"), width=150,
                                  height=28, corner_radius=self.radius,
                                  font=self.font(size=12),
                                  fg_color="transparent", border_width=1,
                                  border_color=self.accent["main"],
                                  text_color=self.accent["main"],
                                  hover_color=self.accent["hover"],
                                  command=lambda p=item["file"]:
                                  self.open_folder(p)).pack(side="right",
                                                            padx=6)

            search_e.bind("<KeyRelease>", render_history)
            render_history()

    # --- Auswahl-Logik -------------------------------------------------------
    def _res_values(self):
        premium = self.store.is_premium()
        return [RES_DISPLAY[r] if (premium or r in RES_FREE_SET)
                else RES_DISPLAY[r] + " 🔒" for r in RES_LIST]

    def _fmt_label(self, ext: str) -> str:
        lang = self.store.data["settings"]["language"] or "en"
        info = FORMAT_INFO if lang == "de" else FORMAT_INFO_EN
        icon, cat = info.get(ext, ("📦", ""))
        return f"{icon} {ext.upper()} — {cat}" if cat else ext.upper()

    def _fmt_values(self, key):
        premium = self.store.is_premium()
        self._fmt_by_label = {}
        if key == "nowm":
            label = self._fmt_label("mp4")
            self._fmt_by_label[label] = "mp4"
            return [label]
        if key == "direct":
            self._fmt_by_label[self.t("auto_field")] = "auto"
            return [self.t("auto_field")]
        d = PLATFORM_FORMATS[key]
        vals = []
        if premium:
            self._fmt_by_label[self.t("auto_field")] = "auto"
            vals.append(self.t("auto_field"))
        for f in d["free"]:
            label = self._fmt_label(f)
            self._fmt_by_label[label] = f
            vals.append(label)
        for f in d["premium"]:
            label = self._fmt_label(f)
            if not premium:
                label += " 🔒"
            self._fmt_by_label[label] = f
            vals.append(label)
        return vals

    def _ai_fmt_values(self):
        """🤖 KI-Modus: Plattform ist noch unbekannt (wird erst beim
        Download aus dem Link erkannt) — deshalb hier die Vereinigung
        aller möglichen Formate anbieten. AI-Modus ist ohnehin nur mit
        Premium nutzbar, also braucht kein Format ein 🔒."""
        self._fmt_by_label = {self.t("auto_field"): "auto"}
        seen = ["mp4"]
        for d in PLATFORM_FORMATS.values():
            for f in d["premium"]:
                if f not in seen:
                    seen.append(f)
        vals = [self.t("auto_field")]
        for f in seen:
            label = self._fmt_label(f)
            self._fmt_by_label[label] = f
            vals.append(label)
        return vals

    def _fmt_default_label(self, vals):
        """Findet in einer Liste von Format-Labels die passende Anzeige
        für 'mp4' (Standard-Auswahl beim Plattformwechsel)."""
        for v in vals:
            if self._fmt_by_label.get(v.replace(" 🔒", "")) == "mp4" \
                    or self._fmt_by_label.get(v) == "mp4":
                return v
        return vals[0]

    def _platform_changed(self, label):
        key = self._plat_by_label.get(label, "ai")

        if key == "ai" and not self.store.is_premium():
            self.show_premium_dialog(self.t("ai_locked"))
            key = "youtube"
            self.plat_var.set("▶ YouTube")
        if key == "direct" and not self.store.is_premium():
            self.show_premium_dialog(self.t("direct_premium"))
            key = "youtube"
            self.plat_var.set("▶ YouTube")
        if key == "browser" and not self.store.is_premium():
            self.show_premium_dialog(self.t("locked_platform"))
            key = "youtube"
            self.plat_var.set("▶ YouTube")

        if key == "ai":
            # KI entscheidet nur über Plattform & Auflösung — die
            # Auflösung bleibt automatisch, das Format kann man selbst
            # wählen.
            self.res_menu.configure(values=[self.t("auto_field")],
                                    state="disabled")
            self.res_var.set(self.t("auto_field"))
            vals = self._ai_fmt_values()
            self.fmt_menu.configure(values=vals, state="normal")
            self.fmt_var.set(self.t("auto_field"))
            self.ai_hint_lbl.pack(anchor="w", padx=28, pady=(0, 4))
        else:
            self.res_menu.configure(values=self._res_values(),
                                    state="normal")
            cur = self.res_var.get().replace(" 🔒", "")
            if cur not in RES_DISPLAY_REV or cur == self.t("auto_field"):
                self.res_var.set(RES_DISPLAY["720p"])
            self.fmt_menu.configure(state="normal")
            vals = self._fmt_values(key)
            self.fmt_menu.configure(values=vals)
            self.fmt_var.set(self._fmt_default_label(vals))
            self.ai_hint_lbl.pack_forget()

    def _res_changed(self, v):
        if "🔒" in v:
            self.show_premium_dialog(self.t("res_locked"))
            self.res_var.set(RES_DISPLAY["720p"])

    def _fmt_changed(self, v):
        if "🔒" in v:
            self.show_premium_dialog(self.t("format_locked"))
            vals = self.fmt_menu.cget("values")
            self.fmt_var.set(self._fmt_default_label(vals))

    def open_folder(self, path):
        folder = path if os.path.isdir(path) else (os.path.dirname(path) or path)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    @staticmethod
    def _safe_name(title: str) -> str:
        return re.sub(r'[\\/:*?"<>|]+', "", title).strip() or "download"

    def _render_filename(self, info, plat) -> str:
        """📝 Baut den Dateinamen nach der in den Einstellungen hinterlegten
        Vorlage (Platzhalter: {title} {channel} {date} {platform})."""
        tpl = self.store.data["settings"].get("filename_template") or "{title}"
        raw_date = info.get("upload_date") or ""
        if len(raw_date) == 8:
            date = f"{raw_date[6:8]}.{raw_date[4:6]}.{raw_date[0:4]}"
        else:
            date = datetime.date.today().strftime("%d.%m.%Y")
        ctx = {
            "title": info.get("title") or "video",
            "channel": info.get("uploader") or info.get("channel") or "unknown",
            "date": date,
            "platform": plat,
        }
        try:
            name = tpl.format(**ctx)
        except Exception:
            name = ctx["title"]
        return self._safe_name(name)

    # --- Download-Ablauf -----------------------------------------------------
    @staticmethod
    def _parse_mmss(text):
        """Wandelt 'mm:ss' oder 'h:mm:ss' in Sekunden um, None bei Fehler."""
        try:
            parts = [int(p) for p in text.strip().split(":")]
        except ValueError:
            return None
        if not parts or any(p < 0 for p in parts):
            return None
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return secs

    def start_download(self):
        # 🖼️ Wallpaper-Download (Premium)
        if getattr(self, "wallpaper_var", None) and self.wallpaper_var.get():
            if not self.store.is_premium():
                self.show_premium_dialog(self.t("locked_platform"))
                return
            url = self.wallpaper_url_e.get().strip()
            if not url:
                return
            dev = self._device_by_label.get(
                self.wallpaper_device_var.get(), "ios")
            res_label = self.wallpaper_res_var.get()
            match = next((r for r in WALLPAPER_RESOLUTIONS[dev]
                         if r[0] == res_label), WALLPAPER_RESOLUTIONS[dev][0])
            _, target_w, target_h = match
            path = filedialog.asksaveasfilename(
                defaultextension=".jpg",
                initialfile=f"wallpaper_{target_w}x{target_h}.jpg",
                filetypes=[("JPEG", "*.jpg")], title=self.t("wallpaper_mode"))
            if not path:
                return
            self.dl_btn.configure(state="disabled")
            self.status_lbl.configure(text="🔎 " + self.t("checking"))
            threading.Thread(target=self._download_wallpaper,
                             args=(url, path, target_w, target_h, dev),
                             daemon=True).start()
            return

        # 📋 Warteschlange: mehrere Links (einer pro Zeile) nacheinander
        if getattr(self, "batch_var", None) and self.batch_var.get():
            if not self.store.is_premium():
                self.show_premium_dialog(self.t("locked_platform"))
                return
            text = self.batch_box.get("1.0", "end").strip()
            urls = [u.strip() for u in text.splitlines() if u.strip()]
            if not urls:
                return
            max_batch = max(1, int(self.store.data["settings"].get(
                "concurrent_downloads", 1)))
            if len(urls) > max_batch:
                messagebox.showwarning(
                    APP_NAME,
                    f"{self.t('batch_too_many')} ({max_batch}).")
                urls = urls[:max_batch]
            self._queue = urls
            self._queue_total = len(urls)
            self._queue_active = True
            self._process_queue()
            return

        premium_check = self.store.is_premium()
        if (premium_check and getattr(self, "playlist_var", None)
                and self.playlist_var.get()):
            url = self.playlist_url_e.get().strip()
        elif (premium_check and getattr(self, "clip_var", None)
                and self.clip_var.get()):
            url = self.clip_url_e.get().strip()
        else:
            url = self.url_entry.get().strip()
        if not url:
            return
        premium = self.store.is_premium()
        plat = self._plat_by_label.get(self.plat_var.get(), "ai")

        # 📺 Playlist/Kanal & ✂️ Ausschnitt (Premium) — vorab validieren
        self._dl_playlist = premium and self.playlist_var.get()
        self._dl_clip = None
        if premium and self.clip_var.get():
            f = self._parse_mmss(self.clip_from_e.get() or "0:00")
            t = self._parse_mmss(self.clip_to_e.get())
            if f is None or t is None or t <= f:
                messagebox.showwarning(APP_NAME, self.t("clip_invalid"))
                return
            self._dl_clip = (f, t)

        # --- 🤖 KI-Modus: Plattform & Auflösung automatisch, Format frei ---
        if plat == "ai":
            if not premium:
                self.show_premium_dialog(self.t("ai_locked"))
                return
            if yt_dlp is None:
                messagebox.showerror(APP_NAME, self.t("no_ytdlp")); return
            detected = next((k for k, r in PLATFORM_URL_RE.items()
                             if r.match(url)), "browser")
            plat = detected
            fmt_label = self.fmt_var.get().replace(" 🔒", "")
            fmt = self._fmt_by_label.get(fmt_label, fmt_label)
            res = "4K"  # Premium → immer beste verfügbare Qualität
        else:
            res = RES_DISPLAY_REV.get(self.res_var.get().replace(" 🔒", ""),
                                      "720p")
            fmt_label = self.fmt_var.get().replace(" 🔒", "")
            fmt = self._fmt_by_label.get(fmt_label, fmt_label)

            if res not in RES_FREE_SET and not premium:
                self.show_premium_dialog(self.t("res_locked"))
                return
            if plat == "direct":
                if not premium:
                    self.show_premium_dialog(self.t("direct_premium"))
                    return
            else:
                if plat == "browser" and not premium:
                    self.show_premium_dialog(self.t("locked_platform"))
                    return
                if fmt not in ("mp4", "auto") and not premium:
                    self.show_premium_dialog(self.t("format_locked"))
                    return
                if plat == "nowm":
                    if not any(r.match(url)
                              for r in PLATFORM_URL_RE.values()):
                        messagebox.showwarning(APP_NAME,
                                               self.t("platform_mismatch"))
                        return
                    fmt = "mp4"
                elif plat != "browser" and not PLATFORM_URL_RE[plat].match(url):
                    messagebox.showwarning(APP_NAME,
                                           self.t("platform_mismatch"))
                    return
                if yt_dlp is None:
                    messagebox.showerror(APP_NAME, self.t("no_ytdlp"))
                    return

        # --- Duplikat-Warnung ---
        dup = self.store.find_duplicate(url)
        if dup:
            if not self.confirm_dialog(
                    self.t("duplicate_title"),
                    self.t("duplicate_msg") + f"\n{os.path.basename(dup['file'])}"
                    + f"  ({dup.get('date', '')})",
                    yes_text=self.t("duplicate_continue"), danger=False):
                return

        # --- 🕑 Später starten (Zeitplanung) ---
        if getattr(self, "sched_var", None) and self.sched_var.get():
            time_str = self.sched_time_e.get().strip()
            try:
                hh, mm = map(int, time_str.split(":"))
                now = datetime.datetime.now()
                target = now.replace(hour=hh, minute=mm, second=0,
                                     microsecond=0)
                if target <= now:
                    target += datetime.timedelta(days=1)
                delay_ms = int((target - now).total_seconds() * 1000)
            except (ValueError, IndexError):
                messagebox.showwarning(APP_NAME, self.t("invalid_time"))
                return
            self.dl_btn.configure(state="disabled")
            self.status_lbl.configure(
                text=f"🕑 {self.t('scheduled_for')} {time_str}")
            self.after(delay_ms, lambda: self._start_prepared(
                url, fmt, plat, RES_HEIGHT[res]))
            return

        self._start_prepared(url, fmt, plat, RES_HEIGHT[res])

    def _start_prepared(self, url, fmt, plat, res_h):
        self.dl_btn.configure(state="disabled")
        self.status_lbl.configure(text="🔎 " + self.t("checking"))
        self.pct_lbl.configure(text="")
        self.progress.set(0)
        threading.Thread(target=self._prepare,
                         args=(url, fmt, plat, res_h),
                         daemon=True).start()

    def _process_queue(self):
        """📋 Startet die Warteschlange mit ECHTER Parallelität — so viele
        Downloads gleichzeitig, wie unter Einstellungen → "Gleichzeitige
        Downloads" eingestellt ist. Läuft über eigene Worker-Threads statt
        über die normale Einzel-Download-Anzeige (die für nur EIN aktives
        Bild gedacht ist)."""
        queue = getattr(self, "_queue", [])
        if not queue:
            self._queue_active = False
            return
        n = max(1, int(self.store.data["settings"].get(
            "concurrent_downloads", 1)))
        n = min(n, len(queue))
        self._queue_lock = threading.Lock()
        self._queue_active_count = 0
        self._queue_done_count = 0
        self.dl_btn.configure(state="disabled")
        self.progress.set(0)
        self.pct_lbl.configure(text="")
        self._update_queue_status()
        for _ in range(n):
            threading.Thread(target=self._queue_worker, daemon=True).start()

    def _update_queue_status(self):
        total = self._queue_total
        done = self._queue_done_count
        active = self._queue_active_count
        extra = (f"  ·  {active} {self.t('queue_running')}"
                if active > 1 else "")
        self.status_lbl.configure(
            text=f"📋 {self.t('queue_progress')} {done}/{total}{extra}")
        if total:
            self.progress.set(done / total)

    def _queue_worker(self):
        """Ein einzelner paralleler Download-Arbeiter — holt sich Links
        aus der gemeinsamen Warteschlange, bis nichts mehr übrig ist."""
        while True:
            with self._queue_lock:
                if not self._queue:
                    return
                url = self._queue.pop(0)
                self._queue_active_count += 1
            self.after(0, self._update_queue_status)
            try:
                self._download_one_sync(url)
            except Exception:
                pass
            finished_all = False
            with self._queue_lock:
                self._queue_active_count -= 1
                self._queue_done_count += 1
                if not self._queue and self._queue_active_count == 0:
                    finished_all = True
            self.after(0, self._update_queue_status)
            if finished_all:
                self.after(0, self._queue_finished)
                return

    def _queue_finished(self):
        self._queue_active = False
        self.status_lbl.configure(text="✓ " + self.t("queue_done"))
        self.pct_lbl.configure(text="")
        self.dl_btn.configure(state="normal")
        self.notify(self.t("queue_done"), "")
        self.page_download()

    def _download_one_sync(self, url):
        """Lädt EINEN Link komplett herunter — synchron, wird von einem
        Warteschlangen-Worker aufgerufen. Rührt bewusst NICHT die geteilte
        Fortschrittsanzeige an (das würde bei mehreren gleichzeitigen
        Downloads nur durcheinander flackern) — der Gesamtfortschritt wird
        stattdessen zentral über _update_queue_status gezeigt."""
        detected = next((k for k, r in PLATFORM_URL_RE.items()
                         if r.match(url)), "browser")
        premium = self.store.is_premium()
        res = "4K" if premium else "720p"
        s = self.store.data["settings"]
        self._dl_playlist = False
        self._dl_clip = None
        if detected == "direct" or not any(
                r.match(url) for r in PLATFORM_URL_RE.values()):
            name = (url.split("?")[0].rstrip("/").split("/")[-1]
                    or "download")
            if "." not in name:
                name += ".bin"
            os.makedirs(s["download_dir"], exist_ok=True)
            path = os.path.join(s["download_dir"], self._safe_name(name))
            final = self._download_direct(url, path)
        else:
            if yt_dlp is None:
                return
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "noplaylist": True,
                                   "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            fmt = self._auto_fmt(url, info)
            suggested = f"{self._render_filename(info, detected)}.{fmt}"
            os.makedirs(s["download_dir"], exist_ok=True)
            path = os.path.join(s["download_dir"], suggested)
            final = self._download_media(url, fmt, RES_HEIGHT[res], path)
        final = self._auto_sort_file(final)
        self.after(0, lambda: self.store.add_history(final, url))

    def _auto_fmt(self, url, info) -> str:
        """Auto-Modus (Premium): erkennt selbst das beste Format."""
        low = url.lower().split("?")[0]
        for ext in ("gif", "jpg", "jpeg", "png", "webp"):
            if low.endswith("." + ext):
                return "jpg" if ext == "jpeg" else ext
        if (info.get("ext") or "").lower() == "gif":
            return "gif"
        if info.get("vcodec") in (None, "none"):
            return "mp3"  # reiner Ton
        text = " ".join([str(info.get("title", "")),
                         " ".join(info.get("categories") or []),
                         " ".join(info.get("tags") or [])]).lower()
        if info.get("artist") or "music" in text or "musik" in text \
                or "official video" in text or "official audio" in text:
            return "wav"  # Musik-Video -> beste Audioqualitaet
        return "mp4"

    def _show_video_preview(self, info, on_confirm, on_cancel):
        """🎬 Zeigt Thumbnail, Titel, Kanal & Dauer, bevor der eigentliche
        Download beginnt — so sieht man vorher, ob es wirklich das
        richtige Video ist."""
        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("420x430")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        img_holder = ctk.CTkLabel(win, text="🎬",
                                  font=self.font(size=40),
                                  fg_color=self._mix(self.accent["main"],
                                                     "#000000", 0.75),
                                  corner_radius=self.radius,
                                  width=380, height=214)
        img_holder.pack(padx=20, pady=(20, 12))

        thumb_url = info.get("thumbnail")
        if thumb_url and Image is not None:
            def load_thumb():
                try:
                    req = urllib.request.Request(
                        thumb_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = r.read()
                    pil_img = Image.open(io.BytesIO(data)).convert("RGB")
                    w, h = pil_img.size
                    ratio = min(380 / w, 214 / h)
                    new_size = (max(1, int(w * ratio)),
                               max(1, int(h * ratio)))
                    pil_img = pil_img.resize(new_size)
                    ctk_img = ctk.CTkImage(light_image=pil_img,
                                           dark_image=pil_img,
                                           size=new_size)

                    def apply():
                        if img_holder.winfo_exists():
                            img_holder.configure(image=ctk_img, text="")
                            # Wichtig: Referenz dauerhaft festhalten, sonst
                            # räumt Python das Bild sofort wieder weg und
                            # die Vorschau bleibt leer.
                            img_holder._preview_image_ref = ctk_img
                    self.after(0, apply)
                except Exception:
                    pass
            threading.Thread(target=load_thumb, daemon=True).start()

        title = info.get("title") or "?"
        channel = info.get("uploader") or info.get("channel") or "?"
        dur = info.get("duration")
        if dur:
            m, s = divmod(int(dur), 60)
            h, m = divmod(m, 60)
            dur_txt = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        else:
            dur_txt = "—"

        ctk.CTkLabel(win, text=title, font=self.font(size=14, weight="bold"),
                     text_color=self.text_on(2) or None, wraplength=380,
                     justify="center").pack(padx=20, pady=(0, 6))
        ctk.CTkLabel(
            win,
            text=(f"📺 {self.t('preview_channel')}: {channel}    "
                 f"⏱ {self.t('preview_duration')}: {dur_txt}"),
            text_color=self.muted(), font=self.font(size=12),
            wraplength=380, justify="center").pack(padx=20, pady=(0, 18))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(0, 22))

        def confirm():
            win.destroy()
            on_confirm()

        def cancel():
            win.destroy()
            on_cancel()

        self.btn(btn_row, text="⬇ " + self.t("preview_confirm"), width=170,
                 height=40, command=confirm).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text=self.t("preview_cancel"), width=140,
                      height=40, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color=self.muted(),
                      text_color=self.text_on(2) or self.muted(),
                      command=cancel).pack(side="left", padx=6)

    def _preview_cancelled(self):
        self.status_lbl.configure(text=self.t("cancelled"))
        self.dl_btn.configure(state="normal")

    def _prepare(self, url, fmt, plat, res_h):
        try:
            if plat == "direct" or fmt == "pdf":
                name = (url.split("?")[0].rstrip("/").split("/")[-1]
                        or "download")
                if "." not in name:
                    name += ".pdf" if fmt == "pdf" else ".bin"
                suggested = self._safe_name(name)
                self.after(0, lambda: self._ask_and_start(url, fmt, plat,
                                                          res_h, suggested))
            else:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                       "noplaylist": True,
                                       "skip_download": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                if fmt == "auto":
                    fmt = self._auto_fmt(url, info)
                title = self._render_filename(info, plat)
                suggested = f"{title}.{fmt}"

                show_preview = (self.store.data["settings"].get(
                    "show_preview", True)
                    and not getattr(self, "_dl_playlist", False))
                if show_preview:
                    self.after(0, lambda: self._show_video_preview(
                        info,
                        on_confirm=lambda: self._ask_and_start(
                            url, fmt, plat, res_h, suggested),
                        on_cancel=self._preview_cancelled))
                else:
                    self.after(0, lambda: self._ask_and_start(
                        url, fmt, plat, res_h, suggested))
        except Exception as e:
            self.after(0, lambda e=e: self._download_error(str(e)))

    def _ask_and_start(self, url, fmt, plat, res_h, suggested):
        s = self.store.data["settings"]
        if s.get("ask_save", True) and not getattr(self, "_queue_active", False):
            path = filedialog.asksaveasfilename(
                initialdir=s["download_dir"],
                initialfile=suggested,
                defaultextension="." + suggested.rsplit(".", 1)[-1],
                title=self.t("start_download"))
            if not path:
                self.status_lbl.configure(text=self.t("cancelled"))
                self.dl_btn.configure(state="normal")
                return
            s["download_dir"] = os.path.dirname(path)
            self.store.save()
        else:
            os.makedirs(s["download_dir"], exist_ok=True)
            path = os.path.join(s["download_dir"], suggested)

        self.status_lbl.configure(text=self.t("downloading"))
        threading.Thread(target=self._download_worker,
                         args=(url, fmt, plat, res_h, path),
                         daemon=True).start()

    def _download_worker(self, url, fmt, plat, res_h, path):
        try:
            if plat == "direct":
                final = self._download_direct(url, path)
            else:
                final = self._download_media(url, fmt, res_h, path)
            self.after(0, lambda: self._download_done(final, url))
        except Exception as e:
            self.after(0, lambda e=e: self._download_error(str(e)))

    def _progress_hook(self, d):
        if getattr(self, "_queue_active", False):
            # Im Warteschlangen-Modus laufen mehrere Downloads gleichzeitig
            # — die geteilte Fortschrittsanzeige würde nur flackern.
            # Der Gesamtfortschritt wird stattdessen zentral gezeigt.
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            if total:
                p = got / total
                txt = f"{p * 100:.0f} %"
                if speed:
                    txt += f"  ·  {speed / 1048576:.1f} MB/s"

                def upd(p=p, t=txt):
                    self.progress.set(p)
                    self.pct_lbl.configure(text=t)
                    if self.store.data["settings"].get("titlebar_progress",
                                                        True):
                        self.title(f"{APP_NAME} — {p * 100:.0f}%")
                self.after(0, upd)

    def _show_upscale_dialog(self, from_h, to_h):
        """🔍 Zeigt ein Fenster im App-Design, solange die Hochskalierung
        läuft, damit der Nutzer sieht, dass gerade etwas passiert."""
        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("380x220")
        win.resizable(False, False)
        try:
            win.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception:
            pass
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="🔍", font=self.font(size=32)).pack(
            pady=(26, 6))
        ctk.CTkLabel(win, text=self.t("upscaling_title"),
                     font=self.font(size=15, weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(0, 6))
        ctk.CTkLabel(win, text=f"{from_h}p → {to_h}p",
                     font=self.font(size=13, weight="bold"),
                     text_color=self.text_on(2) or None).pack()
        ctk.CTkLabel(win, text=self.t("upscaling_desc"),
                     wraplength=320, justify="center",
                     font=self.font(size=11),
                     text_color=self.muted()).pack(padx=20, pady=(6, 14))
        bar = ctk.CTkProgressBar(win, mode="indeterminate",
                                 progress_color=self.accent["main"],
                                 width=280, corner_radius=self.radius)
        bar.pack(pady=(0, 20))
        bar.start()
        self._upscale_win = win

    def _close_upscale_dialog(self):
        win = getattr(self, "_upscale_win", None)
        if win is not None:
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
            self._upscale_win = None

    def _maybe_upscale(self, file_path: str, target_height: int, ffexe: str,
                       loc):
        """🔍 Automatische Hochskalierung: Prüft die TATSÄCHLICHE Auflösung
        der heruntergeladenen Datei — ist sie niedriger als die gewählte
        Auflösung (z. B. weil das Original nur in 1080p statt 4K
        vorliegt), wird sie hochskaliert. WICHTIG: das erfindet keine
        echten Bilddetails, es vergrößert nur die Pixelzahl (schärft die
        Datei nicht wirklich)."""
        if not self.store.data["settings"].get("auto_upscale"):
            return file_path
        if not self.store.is_premium():
            return file_path

        # Mehrere mögliche ffprobe-Pfade durchprobieren, statt beim ersten
        # Fehlschlag sofort und lautlos aufzugeben.
        candidates = []
        if loc:
            candidates.append(os.path.join(loc, "ffprobe.exe"))
            candidates.append(os.path.join(loc, "ffprobe"))
        candidates.append("ffprobe")
        if shutil.which("ffprobe"):
            candidates.insert(0, shutil.which("ffprobe"))

        actual_height = 0
        last_error = None
        for ffprobe in candidates:
            try:
                out = subprocess.run(
                    [ffprobe, "-v", "quiet", "-select_streams", "v:0",
                     "-show_entries", "stream=height", "-of", "csv=p=0",
                     file_path], capture_output=True, text=True, timeout=15)
                val = out.stdout.strip()
                if val:
                    actual_height = int(val)
                    break
            except Exception as e:
                last_error = e
                continue

        if actual_height <= 0:
            # ffprobe konnte die Auflösung nicht ermitteln — sichtbarer
            # Hinweis statt stillem Aufgeben, damit man weiß, woran's liegt.
            if last_error is not None:
                self.after(0, lambda: self.status_lbl.configure(
                    text="⚠ " + self.t("upscale_probe_failed")))
            return file_path
        if actual_height >= target_height:
            return file_path  # schon groß genug

        self.after(0, lambda: self.status_lbl.configure(
            text="🔍 " + self.t("upscaling")))
        self.after(0, lambda: self._show_upscale_dialog(
            actual_height, target_height))
        base, ext = os.path.splitext(file_path)
        tmp_out = base + "_upscaled" + ext
        try:
            subprocess.run(
                [ffexe, "-y", "-i", file_path,
                 "-vf", f"scale=-2:{target_height}:flags=lanczos",
                 "-c:a", "copy", tmp_out],
                check=True, capture_output=True, timeout=600)
            os.replace(tmp_out, file_path)
        except Exception:
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except Exception:
                    pass
        self.after(0, self._close_upscale_dialog)
        return file_path

    def _ensure_ffmpeg(self):
        """Gibt den ffmpeg-Ordner zurueck (None = ist schon im PATH).
        Laedt auf Windows einmalig eine portable Version herunter."""
        if shutil.which("ffmpeg"):
            return None
        exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
        if os.path.exists(exe):
            return FFMPEG_DIR
        if sys.platform != "win32":
            raise RuntimeError(self.t("no_ffmpeg"))

        self.after(0, lambda: self.status_lbl.configure(
            text="⏬ " + self.t("ffmpeg_dl")))
        os.makedirs(FFMPEG_DIR, exist_ok=True)
        tmp = os.path.join(APP_DIR, "ffmpeg_tmp.zip")
        req = urllib.request.Request(FFMPEG_URL,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r, \
                open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    p = got / total
                    self.after(0, lambda p=p: (
                        self.progress.set(p),
                        self.pct_lbl.configure(
                            text=f"FFmpeg {p * 100:.0f} %")))

        import zipfile
        with zipfile.ZipFile(tmp) as z:
            for member in z.namelist():
                low = member.lower().replace("\\", "/")
                if low.endswith("bin/ffmpeg.exe") \
                        or low.endswith("bin/ffprobe.exe"):
                    target = os.path.join(FFMPEG_DIR,
                                          os.path.basename(member))
                    with z.open(member) as srcf, open(target, "wb") as dst:
                        shutil.copyfileobj(srcf, dst)
        try:
            os.remove(tmp)
        except Exception:
            pass
        if not os.path.exists(exe):
            raise RuntimeError(self.t("no_ffmpeg"))
        self.after(0, lambda: (self.progress.set(0),
                               self.pct_lbl.configure(text=""),
                               self.status_lbl.configure(
                                   text=self.t("downloading"))))
        return FFMPEG_DIR

    def _download_media(self, url, fmt, res_h, path):
        """Laedt Video/Audio/Bild von YouTube, TikTok, Instagram, Facebook."""
        base = path.rsplit(".", 1)[0]

        # --- PDF: kein Video/Audio, einfacher Datei-Download reicht ---
        if fmt == "pdf":
            return self._download_direct(url, base + ".pdf")

        has_ff = True
        loc = None
        try:
            loc = self._ensure_ffmpeg()
        except Exception:
            has_ff = False
        ffexe = os.path.join(loc, "ffmpeg.exe") if loc else "ffmpeg"

        want_playlist = getattr(self, "_dl_playlist", False)
        clip = getattr(self, "_dl_clip", None)

        opts = {
            "outtmpl": (base + ("_%(playlist_index)s" if want_playlist
                                else "") + ".%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "noplaylist": not want_playlist,
            "quiet": True,
            "no_warnings": True,
            # 🔄 Smart Resume: bei Verbindungsabbruch automatisch erneut
            # versuchen und dort fortsetzen, wo es aufgehört hat
            # (yt-dlp macht das intern über seine eigene .part-Datei).
            "continuedl": True,
            "retries": 10,
            "fragment_retries": 10,
        }
        if clip:
            # ✂️ Nur den gewählten Zeitbereich herunterladen (yt-dlp
            # schneidet direkt beim Download, lädt nicht das ganze Video).
            f, t = clip
            opts["download_ranges"] = lambda info, ydl, f=f, t=t: [
                {"start_time": f, "end_time": t}]
            opts["force_keyframes_at_cuts"] = True

        s = self.store.data["settings"]
        if s.get("bandwidth_kb"):
            opts["ratelimit"] = int(s["bandwidth_kb"]) * 1024  # Bytes/s
        if s.get("proxy_url"):
            opts["proxy"] = s["proxy_url"]
        if s.get("download_subs"):
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitlesformat"] = "srt/vtt"
            lang = s.get("sub_lang", "en")
            opts["subtitleslangs"] = ["all"] if lang == "all" else [lang]
        if loc:
            opts["ffmpeg_location"] = loc

        # 🎵 Metadaten & Cover einbetten (Titel, Interpret/Kanal, Thumbnail
        # als Cover) — funktioniert bei Audio- und Video-Formaten, sofern
        # FFmpeg verfügbar ist.
        embed = has_ff and s.get("embed_metadata", True) and fmt not in (
            "jpg", "png", "webp", "gif", "pdf", "3gp")
        if embed:
            opts["writethumbnail"] = True

        # --- Bilder (jpg/png/webp von Foto-Posts) ---
        if fmt in ("jpg", "png", "webp"):
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "noplaylist": True,
                                   "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            low = url.lower().split("?")[0]
            if any(low.endswith("." + e)
                   for e in ("jpg", "jpeg", "png", "webp", "gif")):
                img_url = url
            else:
                img_url = info.get("thumbnail")
            if not img_url:
                raise RuntimeError(self.t("no_image"))
            tmp = base + ".imgtmp"
            req = urllib.request.Request(img_url,
                                         headers={"User-Agent":
                                                  "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, \
                    open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            out = base + "." + fmt
            if has_ff:
                self.after(0, lambda: self.status_lbl.configure(
                    text="⚙ " + self.t("converting")))
                subprocess.run([ffexe, "-y", "-i", tmp, out],
                               check=True, capture_output=True)
                os.remove(tmp)
            else:
                os.replace(tmp, out)
            return out

        # --- Audio ---
        if fmt in AUDIO_FMTS:
            if not has_ff:
                raise RuntimeError(self.t("no_ffmpeg"))
            codec = "vorbis" if fmt == "ogg" else fmt
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": "192",
            }]
            if embed:
                opts["postprocessors"].append(
                    {"key": "FFmpegMetadata", "add_metadata": True})
                if fmt != "wav":  # WAV unterstützt kein eingebettetes Cover
                    opts["postprocessors"].append({"key": "EmbedThumbnail"})
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
            return self._find_output(base, fmt)

        # --- Video (mp4/webm/mkv/mov/3gp/gif) ---
        if has_ff:
            opts["format"] = (f"bestvideo[height<={res_h}][ext=mp4]"
                              f"+bestaudio[ext=m4a]"
                              f"/best[height<={res_h}][ext=mp4]"
                              f"/best[height<={res_h}]/best")
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = (f"best[height<={res_h}][ext=mp4]"
                              f"/best[height<={res_h}]/best")
        if embed and fmt in ("mp4", "mkv", "mov"):
            opts["postprocessors"] = [
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ]
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        if want_playlist:
            # Playlist/Kanal: mehrere Dateien entstanden -> Ordner zurückgeben
            return os.path.dirname(base) or "."

        src_file = self._find_output(base, "mp4")
        if has_ff and fmt not in ("gif",):
            src_file = self._maybe_upscale(src_file, res_h, ffexe, loc)

        if fmt != "mp4":
            if not has_ff:
                raise RuntimeError(self.t("no_ffmpeg"))
            self.after(0, lambda: self.status_lbl.configure(
                text="⚙ " + self.t("converting")))
            out = base + "." + fmt
            if fmt == "gif":
                cmd = [ffexe, "-y", "-i", src_file,
                       "-vf", "fps=12,scale=480:-1:flags=lanczos",
                       "-loop", "0", out]
            else:
                cmd = [ffexe, "-y", "-i", src_file, out]
            subprocess.run(cmd, check=True, capture_output=True)
            if os.path.exists(src_file) and src_file != out:
                os.remove(src_file)
            return out
        return src_file

    @staticmethod
    def _find_output(base, ext):
        cand = base + "." + ext
        if os.path.exists(cand):
            return cand
        folder = os.path.dirname(base) or "."
        stem = os.path.basename(base)
        for f in os.listdir(folder):
            if f.startswith(stem):
                return os.path.join(folder, f)
        return cand

    def _download_wallpaper(self, url, path, target_w, target_h, device):
        """🖼️ Lädt ein Bild herunter und passt es exakt an die gewählte
        Geräte-Auflösung an. Bei PC/Windows wird gestreckt (füllt den
        Monitor exakt, wie bei Windows' "Strecken"-Anpassung) — bei
        Handys wird stattdessen mittig zugeschnitten, damit Gesichter/
        Motive nicht verzerrt werden. Ein kleines Ausgangsbild (z. B.
        schlechte Handyfoto-Qualität) wird dabei automatisch auf die
        Ziel-Auflösung hochskaliert."""
        try:
            if Image is None:
                raise RuntimeError("Pillow (PIL) ist nicht verfügbar.")
            self.after(0, lambda: self.status_lbl.configure(
                text="⬇ " + self.t("downloading")))
            req = urllib.request.Request(url, headers={"User-Agent":
                                                       "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")

            self.after(0, lambda: self.status_lbl.configure(
                text="🖼️ " + self.t("wallpaper_processing")))
            if device == "windows":
                # PC/Windows: exakt strecken, füllt den Monitor 1:1 aus
                out_img = img.resize((target_w, target_h), Image.LANCZOS)
            else:
                # Handy: mittig zuschneiden (Seitenverhältnis bleibt echt)
                src_ratio = img.width / img.height
                dst_ratio = target_w / target_h
                if src_ratio > dst_ratio:
                    new_h = target_h
                    new_w = max(target_w, int(new_h * src_ratio))
                else:
                    new_w = target_w
                    new_h = max(target_h, int(new_w / src_ratio))
                img = img.resize((new_w, new_h), Image.LANCZOS)
                left = (new_w - target_w) // 2
                top = (new_h - target_h) // 2
                out_img = img.crop((left, top, left + target_w,
                                   top + target_h))

            out_img.save(path, quality=95)
            self.after(0, lambda: self._download_done(path, url))
        except Exception as e:
            self.after(0, lambda e=e: self._download_error(str(e)))

    def _download_direct(self, url, path):
        """Premium: direkte Dateien (PNG, JPG, PDF, ...) von Links.
        🔄 Smart Resume: bricht die Verbindung ab, wird beim nächsten
        Versuch mit demselben Ziel-Pfad per HTTP-Range dort fortgesetzt,
        wo es aufgehört hat, statt neu anzufangen."""
        s = self.store.data["settings"]
        opener = urllib.request
        if s.get("proxy_url"):
            proxy = s["proxy_url"]
            handler = urllib.request.ProxyHandler({"http": proxy,
                                                   "https": proxy})
            opener = urllib.request.build_opener(handler)
        opener_fn = opener.open if opener is not urllib.request else \
            urllib.request.urlopen
        bw_bytes = int(s.get("bandwidth_kb", 0)) * 1024 if s.get(
            "bandwidth_kb") else 0

        tmp_path = path + ".part"
        resume_pos = os.path.getsize(tmp_path) if os.path.exists(tmp_path) \
            else 0
        headers = {"User-Agent": "Mozilla/5.0"}
        if resume_pos:
            headers["Range"] = f"bytes={resume_pos}-"
        req = urllib.request.Request(url, headers=headers)

        with opener_fn(req, timeout=60) as r:
            # Server unterstützt evtl. kein Range -> von vorne beginnen
            supports_range = getattr(r, "status", 200) == 206
            if resume_pos and not supports_range:
                resume_pos = 0
            mode = "ab" if resume_pos else "wb"
            total = int(r.headers.get("Content-Length") or 0) + resume_pos
            got = resume_pos
            t0 = datetime.datetime.now()
            with open(tmp_path, mode) as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if bw_bytes:
                        elapsed = (datetime.datetime.now()
                                  - t0).total_seconds()
                        expected = (got - resume_pos) / bw_bytes
                        if expected > elapsed:
                            import time as _time
                            _time.sleep(expected - elapsed)
                    if total:
                        p = got / total
                        self.after(0, lambda p=p: (
                            self.progress.set(p),
                            self.pct_lbl.configure(text=f"{p * 100:.0f} %")))
        os.replace(tmp_path, path)
        return path

    def _auto_sort_file(self, filepath: str) -> str:
        """Verschiebt die fertige Datei automatisch in Unterordner/Bilder,
        /Videos oder /Musik — falls in den Einstellungen aktiviert."""
        if not self.store.data["settings"].get("auto_sort"):
            return filepath
        ext = filepath.rsplit(".", 1)[-1].lower()
        folder_map = {
            "jpg": "Bilder", "jpeg": "Bilder", "png": "Bilder",
            "webp": "Bilder", "gif": "Bilder",
            "mp4": "Videos", "webm": "Videos", "mkv": "Videos",
            "mov": "Videos", "3gp": "Videos",
            "mp3": "Musik", "wav": "Musik", "m4a": "Musik",
            "aac": "Musik", "flac": "Musik", "ogg": "Musik",
        }
        sub = folder_map.get(ext)
        if not sub:
            return filepath
        base_dir = os.path.dirname(filepath)
        target_dir = os.path.join(base_dir, sub)
        try:
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, os.path.basename(filepath))
            if os.path.abspath(target) != os.path.abspath(filepath):
                shutil.move(filepath, target)
            return target
        except Exception:
            return filepath

    def _download_done(self, filepath, url=None):
        is_folder = os.path.isdir(filepath)
        if not is_folder:
            filepath = self._auto_sort_file(filepath)
        self.progress.set(1)
        self.pct_lbl.configure(text="100 %")
        name = os.path.basename(filepath.rstrip(os.sep)) or filepath
        if is_folder:
            self.status_lbl.configure(
                text="✓ " + self.t("done") + "  →  📁 " + name)
        else:
            self.status_lbl.configure(
                text="✓ " + self.t("done") + "  →  " + name)
        self.dl_btn.configure(state="normal")
        self.title(APP_NAME)
        self.store.add_history(filepath, url)
        self.notify(self.t("dl_complete"),
                    self.t("dl_complete_msg") + "\n" + name)
        self.page_download()

    def _download_error(self, msg):
        self.progress.set(0)
        self.pct_lbl.configure(text="")
        self.title(APP_NAME)
        if len(msg) > 160:
            msg = msg[:157] + "..."
        self.status_lbl.configure(text="✗ " + msg)
        self.dl_btn.configure(state="normal")
        messagebox.showerror(self.t("dl_failed"), msg)

    def page_ai_studio(self):
        """🎨 KI-Studio: Text-, Bild- und Video-Generierung über Googles
        Gemini-API — mit dem EIGENEN, kostenlos erhältlichen API-Schlüssel
        des Nutzers (bring-your-own-key), nicht über einen Schlüssel der
        App selbst."""
        self._page = self.page_ai_studio
        self.clear_content()
        outer = self.make_scroll_area(self.content, colored=False)
        card = ctk.CTkFrame(outer, corner_radius=self.radius,
                            **self.card_kw(2))
        card.pack(fill="x")

        ctk.CTkLabel(card, text="🎨 " + self.t("ai_studio"),
                     font=self.font(size=24, weight="bold")).pack(
                         anchor="w", padx=24, pady=(22, 6))
        ctk.CTkLabel(card, text=self.t("ai_studio_intro"),
                     text_color=self.muted(), font=self.font(size=12),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=24,
                                                          pady=(0, 14))

        s = self.store.data["settings"]
        key_row = ctk.CTkFrame(card, fg_color="transparent")
        key_row.pack(fill="x", padx=24, pady=(0, 6))
        ctk.CTkLabel(key_row, text=self.t("api_key_label"), width=140,
                    anchor="w").pack(side="left")
        key_e = ctk.CTkEntry(key_row, width=320, height=34,
                             corner_radius=self.radius, show="•",
                             placeholder_text="AIza...")
        if s.get("gemini_api_key"):
            key_e.insert(0, s["gemini_api_key"])
        key_e.pack(side="left", padx=(0, 8))

        def save_key():
            s["gemini_api_key"] = key_e.get().strip()
            self.store.save()

        self.btn(key_row, text=self.t("apply"), width=100, height=34,
                 command=save_key).pack(side="left")
        ctk.CTkLabel(
            card, text=self.t("api_key_hint"), text_color=self.muted(),
            font=self.font(size=11), wraplength=560,
            justify="left").pack(anchor="w", padx=24, pady=(2, 18))

        def get_key():
            k = s.get("gemini_api_key", "").strip()
            if not k:
                messagebox.showwarning(APP_NAME, self.t("api_key_missing"))
                return None
            return k

        # --- 💬 Text/Chat ---
        chat_box_frame = ctk.CTkFrame(card, corner_radius=self.radius,
                                      border_width=1,
                                      border_color=self.accent["main"],
                                      **self.card_kw(2))
        chat_box_frame.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(chat_box_frame, text="💬 " + self.t("ai_text_title"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=16, pady=(14, 6))
        chat_prompt = ctk.CTkTextbox(chat_box_frame, height=70,
                                    corner_radius=self.radius,
                                    font=self.font(size=13))
        chat_prompt.pack(fill="x", padx=16, pady=(0, 8))
        chat_result = ctk.CTkTextbox(chat_box_frame, height=140,
                                     corner_radius=self.radius,
                                     font=self.font(size=13),
                                     state="disabled")
        chat_result.pack(fill="x", padx=16, pady=(0, 8))
        chat_status = ctk.CTkLabel(chat_box_frame, text="",
                                   font=self.font(size=11))
        chat_status.pack(anchor="w", padx=16, pady=(0, 6))

        def run_chat():
            key = get_key()
            if not key:
                return
            prompt = chat_prompt.get("1.0", "end").strip()
            if not prompt:
                return
            chat_status.configure(text="🔄 " + self.t("ai_generating"),
                                  text_color=self.muted())
            threading.Thread(target=self._gemini_generate_text,
                             args=(key, prompt, chat_result, chat_status),
                             daemon=True).start()

        self.btn(chat_box_frame, text="✨ " + self.t("ai_generate"),
                 width=160, height=36, command=run_chat).pack(
                     anchor="w", padx=16, pady=(0, 16))

        # --- 🖼️ Bild-Generierung ---
        img_box_frame = ctk.CTkFrame(card, corner_radius=self.radius,
                                     border_width=1,
                                     border_color=self.accent["main"],
                                     **self.card_kw(2))
        img_box_frame.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(img_box_frame, text="🖼️ " + self.t("ai_image_title"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=16, pady=(14, 6))
        img_prompt = ctk.CTkEntry(
            img_box_frame, placeholder_text=self.t("ai_image_ph"),
            height=38, corner_radius=self.radius)
        img_prompt.pack(fill="x", padx=16, pady=(0, 8))
        img_preview = ctk.CTkLabel(
            img_box_frame, text="🖼️", font=self.font(size=36),
            fg_color=self._mix(self.accent["main"], "#000000", 0.8),
            corner_radius=self.radius, width=340, height=200)
        img_preview.pack(padx=16, pady=(0, 8))
        img_status = ctk.CTkLabel(img_box_frame, text="",
                                  font=self.font(size=11))
        img_status.pack(anchor="w", padx=16, pady=(0, 6))
        img_btn_row = ctk.CTkFrame(img_box_frame, fg_color="transparent")
        img_btn_row.pack(anchor="w", padx=16, pady=(0, 16))
        self._ai_last_image = {"bytes": None}

        def run_image():
            key = get_key()
            if not key:
                return
            prompt = img_prompt.get().strip()
            if not prompt:
                return
            img_status.configure(text="🔄 " + self.t("ai_generating"),
                                 text_color=self.muted())
            threading.Thread(target=self._gemini_generate_image,
                             args=(key, prompt, img_preview, img_status),
                             daemon=True).start()

        def save_image():
            if not self._ai_last_image.get("bytes"):
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile="ki_bild.png",
                filetypes=[("PNG", "*.png")])
            if not path:
                return
            with open(path, "wb") as f:
                f.write(self._ai_last_image["bytes"])
            messagebox.showinfo(APP_NAME, self.t("ai_saved"))

        self.btn(img_btn_row, text="✨ " + self.t("ai_generate"), width=160,
                 height=36, command=run_image).pack(side="left", padx=(0, 8))
        ctk.CTkButton(img_btn_row, text="💾 " + self.t("ai_save"), width=140,
                     height=36, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     command=save_image).pack(side="left")

        # --- 🎬 Video-Generierung (experimentell) ---
        vid_box_frame = ctk.CTkFrame(card, corner_radius=self.radius,
                                     border_width=1,
                                     border_color=self.accent["main"],
                                     **self.card_kw(2))
        vid_box_frame.pack(fill="x", padx=24, pady=(0, 22))
        ctk.CTkLabel(vid_box_frame, text="🎬 " + self.t("ai_video_title"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(vid_box_frame, text=self.t("ai_video_hint"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=520, justify="left").pack(anchor="w",
                                                          padx=16,
                                                          pady=(0, 8))
        vid_prompt = ctk.CTkEntry(
            vid_box_frame, placeholder_text=self.t("ai_video_ph"),
            height=38, corner_radius=self.radius)
        vid_prompt.pack(fill="x", padx=16, pady=(0, 8))
        vid_status = ctk.CTkLabel(vid_box_frame, text="",
                                  font=self.font(size=11), wraplength=520,
                                  justify="left")
        vid_status.pack(anchor="w", padx=16, pady=(0, 6))
        self._ai_last_video = {"path": None}
        vid_btn_row = ctk.CTkFrame(vid_box_frame, fg_color="transparent")
        vid_btn_row.pack(anchor="w", padx=16, pady=(0, 16))

        def run_video():
            key = get_key()
            if not key:
                return
            prompt = vid_prompt.get().strip()
            if not prompt:
                return
            vid_status.configure(text="🔄 " + self.t("ai_video_generating"),
                                 text_color=self.muted())
            threading.Thread(target=self._gemini_generate_video,
                             args=(key, prompt, vid_status),
                             daemon=True).start()

        self.btn(vid_btn_row, text="✨ " + self.t("ai_generate"), width=160,
                 height=36, command=run_video).pack(side="left")

    def _gemini_generate_text(self, key, prompt, result_box, status_lbl):
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/"
                  f"models/gemini-2.0-flash:generateContent?key={key}")
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]

            def apply():
                result_box.configure(state="normal")
                result_box.delete("1.0", "end")
                result_box.insert("1.0", text)
                result_box.configure(state="disabled")
                status_lbl.configure(text="✓ " + self.t("ai_done"),
                                     text_color="#34D399")
            self.after(0, apply)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: status_lbl.configure(
                text="✗ " + msg[:200], text_color="#F87171"))

    def _gemini_generate_image(self, key, prompt, preview_lbl, status_lbl):
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/"
                  f"models/gemini-2.0-flash-exp:generateContent?key={key}")
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT",
                                                            "IMAGE"]},
            }).encode()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode())
            parts = data["candidates"][0]["content"]["parts"]
            img_b64 = None
            for p in parts:
                if "inlineData" in p:
                    img_b64 = p["inlineData"]["data"]
                    break
            if not img_b64:
                raise RuntimeError(self.t("ai_no_image_returned"))
            import base64
            img_bytes = base64.b64decode(img_b64)
            self._ai_last_image["bytes"] = img_bytes

            if Image is not None:
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                w, h = pil_img.size
                ratio = min(340 / w, 200 / h)
                new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
                pil_img = pil_img.resize(new_size)
                ctk_img = ctk.CTkImage(light_image=pil_img,
                                       dark_image=pil_img, size=new_size)

                def apply():
                    if preview_lbl.winfo_exists():
                        preview_lbl.configure(image=ctk_img, text="")
                        preview_lbl._ai_image_ref = ctk_img
                    status_lbl.configure(text="✓ " + self.t("ai_done"),
                                         text_color="#34D399")
                self.after(0, apply)
            else:
                self.after(0, lambda: status_lbl.configure(
                    text="✓ " + self.t("ai_done"), text_color="#34D399"))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: status_lbl.configure(
                text="✗ " + msg[:200], text_color="#F87171"))

    def _gemini_generate_video(self, key, prompt, status_lbl):
        """🎬 Experimentell: Video-Generierung über Googles Veo-Modell.
        Läuft asynchron (kann mehrere Minuten dauern) — braucht je nach
        Google-Konto ggf. besonderen Zugriff (nicht jeder API-Schlüssel
        hat automatisch Zugriff auf Video-Generierung)."""
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/"
                  f"models/veo-2.0-generate-001:predictLongRunning"
                  f"?key={key}")
            body = json.dumps({
                "instances": [{"prompt": prompt}],
            }).encode()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                op = json.loads(r.read().decode())
            op_name = op.get("name")
            if not op_name:
                raise RuntimeError(str(op))

            self.after(0, lambda: status_lbl.configure(
                text="🔄 " + self.t("ai_video_waiting"),
                text_color=self.muted()))

            poll_url = (f"https://generativelanguage.googleapis.com/v1beta/"
                       f"{op_name}?key={key}")
            done = False
            result = None
            for _ in range(60):  # bis zu ~10 Minuten warten
                time.sleep(10)
                with urllib.request.urlopen(poll_url, timeout=30) as r:
                    result = json.loads(r.read().decode())
                if result.get("done"):
                    done = True
                    break
            if not done:
                raise RuntimeError(self.t("ai_video_timeout"))

            samples = (result.get("response", {})
                      .get("generateVideoResponse", {})
                      .get("generatedSamples", []))
            if not samples:
                raise RuntimeError(str(result.get("error", result)))
            video_uri = samples[0]["video"]["uri"]

            path = None

            def ask_path():
                nonlocal path
                path = filedialog.asksaveasfilename(
                    defaultextension=".mp4", initialfile="ki_video.mp4",
                    filetypes=[("MP4", "*.mp4")])

            self.after(0, ask_path)
            # kurz warten, bis der Save-Dialog im Hauptthread beantwortet ist
            for _ in range(300):
                if path is not None:
                    break
                time.sleep(0.1)
            if not path:
                self.after(0, lambda: status_lbl.configure(
                    text=self.t("cancelled")))
                return

            dl_url = video_uri if "key=" in video_uri else (
                video_uri + ("&" if "?" in video_uri else "?") + f"key={key}")
            req2 = urllib.request.Request(dl_url)
            with urllib.request.urlopen(req2, timeout=120) as r, \
                    open(path, "wb") as f:
                shutil.copyfileobj(r, f)

            self.after(0, lambda: status_lbl.configure(
                text="✓ " + self.t("ai_done"), text_color="#34D399"))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: status_lbl.configure(
                text="✗ " + msg[:250] + "  (" + self.t("ai_video_hint")
                + ")", text_color="#F87171"))

    def page_premium(self):
        self._page = self.page_premium
        self.clear_content()
        outer = self.make_scroll_area(self.content, colored=False)
        card = ctk.CTkFrame(outer, corner_radius=self.radius, **self.card_kw(2))
        card.pack(fill="x")

        ctk.CTkLabel(card, text="★ " + self.t("premium_title"),
                     font=self.font(size=24, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=24, pady=(22, 8))

        if self.store.is_premium():
            until = self.store.premium_until()
            if until == "forever" or self.store.is_owner():
                txt = self.t("premium_forever")
            else:
                txt = f"{self.t('premium_until')} {until}"
            ctk.CTkLabel(card, text="✓ " + self.t("premium_active"),
                         font=self.font(size=16, weight="bold"),
                         text_color="#34D399").pack(anchor="w", padx=24)
            ctk.CTkLabel(card, text=txt).pack(anchor="w", padx=24, pady=(2, 22))
        else:
            ctk.CTkLabel(card, text=self.t("premium_pitch"),
                         font=self.font(size=15, weight="bold")).pack(
                             anchor="w", padx=24, pady=(4, 4))
            for k in ("perk_1", "perk_2", "perk_3"):
                ctk.CTkLabel(card, text=self.t(k)).pack(anchor="w", padx=32)

            checkout_url = self.store.data["settings"].get("checkout_url")
            if checkout_url:
                import webbrowser
                self.btn(
                    card, text="🌐 " + self.t("buy_on_website"), width=320,
                    fg_color="#F59E0B", hover_color="#D97706",
                    command=lambda: webbrowser.open(checkout_url)).pack(
                        anchor="w", padx=24, pady=(16, 6))

            self.btn(card, text="🎁  " + self.t("try_trial"), width=320,
                     command=self.buy_premium).pack(anchor="w", padx=24,
                                                    pady=(6, 22))

        # --- 🎁 Code einlösen (jetzt hier statt in den Einstellungen) ---
        sep = ctk.CTkFrame(
            card, height=1,
            fg_color=self._mix(self.muted(), self.tint(2) or
                               ("#000000" if self.store.data["settings"]
                                ["appearance"] == "dark" else "#FFFFFF"),
                               0.75))
        sep.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(card, text="🎁 " + self.t("redeem_code"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=24, pady=(0, 6))
        code_row = ctk.CTkFrame(card, fg_color="transparent")
        code_row.pack(anchor="w", padx=24, fill="x")
        code_e = ctk.CTkEntry(code_row, placeholder_text=self.t("code_placeholder"),
                              width=240, height=38, corner_radius=self.radius)
        code_e.pack(side="left", padx=(0, 10))

        def redeem():
            if self.redeem_code_universal(code_e.get()):
                code_msg.configure(text="✓ " + self.t("code_ok"),
                                   text_color="#34D399")
                self.notify(APP_NAME, self.t("code_ok"))
                self.screen_main()
            else:
                code_msg.configure(text="✗ " + self.t("code_bad"),
                                   text_color="#F87171")

        self.btn(code_row, text=self.t("redeem"), width=150, height=38,
                 command=redeem).pack(side="left")
        code_msg = ctk.CTkLabel(card, text="", font=self.font(size=11))
        code_msg.pack(anchor="w", padx=24, pady=(6, 22))

        # --- ❓ Probleme oder Feedback? (an beide Owner per E-Mail) ---
        sep_contact = ctk.CTkFrame(
            card, height=1,
            fg_color=self._mix(self.muted(), self.tint(2) or
                               ("#000000" if self.store.data["settings"]
                                ["appearance"] == "dark" else "#FFFFFF"),
                               0.75))
        sep_contact.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(card, text=self.t("contact_title"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=24, pady=(0, 4))
        ctk.CTkLabel(card, text=self.t("contact_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=24)

        contact_box = ctk.CTkTextbox(card, height=90,
                                     corner_radius=self.radius,
                                     font=self.font(size=13))
        contact_box.pack(fill="x", padx=24, pady=(8, 6))
        contact_msg = ctk.CTkLabel(card, text="", font=self.font(size=11))
        contact_msg.pack(anchor="w", padx=24, pady=(0, 6))

        def send_contact():
            text = contact_box.get("1.0", "end").strip()
            if not text:
                contact_msg.configure(text="⚠ " + self.t("contact_empty"),
                                      text_color="#FBBF24")
                return
            contact_msg.configure(text="🔄 " + self.t("contact_sending"),
                                  text_color=self.muted())
            sender = self.store.current_email

            def worker():
                subject = f"{APP_NAME}: Nachricht von {sender}"
                body = (f"Von: {sender}\n"
                       f"Premium: {self.store.is_premium(sender)}\n"
                       f"Version: {APP_VERSION}\n\n{text}")
                any_ok = False
                for owner in OWNER_EMAILS:
                    ok, _ = self.send_email(owner, subject, body)
                    any_ok = any_ok or ok
                self.after(0, lambda: (
                    contact_msg.configure(
                        text=("✓ " + self.t("contact_ok")) if any_ok
                        else ("✗ " + self.t("contact_fail")),
                        text_color="#34D399" if any_ok else "#F87171"),
                    contact_box.delete("1.0", "end") if any_ok else None))

            threading.Thread(target=worker, daemon=True).start()

        self.btn(card, text="✉ " + self.t("contact_send"), width=220,
                 height=36, command=send_contact).pack(anchor="w",
                                                       padx=24,
                                                       pady=(0, 22))

        # --- 🔔 Kanal-Abos (Premium) ---
        if self.store.is_premium():
            sep2 = ctk.CTkFrame(
                card, height=1,
                fg_color=self._mix(self.muted(), self.tint(2) or
                                   ("#000000" if self.store.data["settings"]
                                    ["appearance"] == "dark" else "#FFFFFF"),
                                   0.75))
            sep2.pack(fill="x", padx=24, pady=(0, 16))

            ctk.CTkLabel(card, text=self.t("subscriptions_title"),
                         font=self.font(size=15, weight="bold")).pack(
                             anchor="w", padx=24, pady=(0, 4))
            ctk.CTkLabel(card, text=self.t("subscriptions_desc"),
                         text_color=self.muted(), font=self.font(size=11),
                         wraplength=560, justify="left").pack(anchor="w",
                                                              padx=24)

            sub_row = ctk.CTkFrame(card, fg_color="transparent")
            sub_row.pack(anchor="w", padx=24, pady=(8, 8), fill="x")
            sub_e = ctk.CTkEntry(sub_row,
                                 placeholder_text=self.t("subscription_ph"),
                                 width=340, height=36,
                                 corner_radius=self.radius)
            sub_e.pack(side="left", padx=(0, 8))

            def add_subscription():
                link = sub_e.get().strip()
                if not link:
                    return
                subs = self.store.data.setdefault("subscriptions", [])
                if not any(x["url"] == link for x in subs):
                    subs.append({"url": link, "last_video_id": None})
                    self.store.save()
                    threading.Thread(target=self._check_subscriptions,
                                     daemon=True).start()
                self.screen_main()

            self.btn(sub_row, text=self.t("add_subscription"), width=150,
                     height=36, command=add_subscription).pack(side="left")

            subs = self.store.data.get("subscriptions", [])
            if not subs:
                ctk.CTkLabel(card, text=self.t("no_subscriptions"),
                            text_color=self.muted()).pack(anchor="w",
                                                          padx=24,
                                                          pady=(0, 20))
            else:
                for sub in subs:
                    row = ctk.CTkFrame(card, fg_color="transparent")
                    row.pack(fill="x", padx=24, pady=2)
                    ctk.CTkLabel(row, text="📺 " + sub["url"],
                                anchor="w").pack(side="left")

                    def make_remove(u=sub["url"]):
                        def remove():
                            self.store.data["subscriptions"] = [
                                x for x in self.store.data["subscriptions"]
                                if x["url"] != u]
                            self.store.save()
                            self.screen_main()
                        return remove

                    ctk.CTkButton(row, text="✕", width=28, height=24,
                                 corner_radius=self.radius,
                                 fg_color="transparent", border_width=1,
                                 border_color="#F87171",
                                 text_color="#F87171",
                                 hover_color="#7F1D1D",
                                 command=make_remove()).pack(side="right")
                ctk.CTkLabel(card, text="").pack(pady=(0, 16))

        if self.store.is_owner():
            u = self.store.data["users"][self.store.current_email]
            ow_var = ctk.BooleanVar(value=not u.get("owner_premium_off", False))

            def toggle_owner():
                u["owner_premium_off"] = not ow_var.get()
                self.store.save()
                self.screen_main()

            ctk.CTkSwitch(card, text="👑 " + self.t("owner_toggle"),
                          variable=ow_var, command=toggle_owner,
                          progress_color=self.accent["main"]).pack(
                              anchor="w", padx=24, pady=(0, 22))

    def buy_premium(self):
        email = self.store.current_email
        user = self.store.data["users"][email]
        if user.get("beta_code_claimed"):
            self._show_trial_dialog(already=True)
            return
        self.store.grant_premium(email, days=1)
        user["beta_code_claimed"] = True
        self.store.save()
        self.screen_main()
        self._show_trial_dialog(already=False)

    def _show_trial_dialog(self, already: bool):
        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("420x250")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="🎁" if not already else "💜",
                     font=self.font(size=34)).pack(pady=(26, 6))
        title = self.t("trial_active_title") if not already \
            else self.t("trial_already_title")
        msg = self.t("trial_active_msg") if not already \
            else self.t("trial_already_msg")
        ctk.CTkLabel(win, text=title, font=self.font(size=16, weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(0, 6))
        ctk.CTkLabel(win, text=msg, wraplength=360, justify="center",
                     font=self.font(size=13),
                     text_color=self.text_on(2) or None).pack(
                         padx=24, pady=(0, 20))
        self.btn(win, text="OK", width=140,
                 command=win.destroy).pack(pady=(0, 20))

    def show_favorites_dialog(self):
        """⭐ Zeigt gespeicherte Lieblings-Links — anklicken füllt das
        Link-Feld, plus Möglichkeit den aktuellen Link zu speichern."""
        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("420x420")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="⭐ " + self.t("favorites"),
                     font=self.font(size=17, weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(20, 10))

        add_row = ctk.CTkFrame(win, fg_color="transparent")
        add_row.pack(padx=20, pady=(0, 10), fill="x")
        name_e = ctk.CTkEntry(add_row,
                              placeholder_text=self.t("favorite_name_ph"),
                              height=34, corner_radius=self.radius)
        name_e.pack(side="left", fill="x", expand=True, padx=(0, 8))

        list_frame = ctk.CTkScrollableFrame(
            win, corner_radius=self.radius, height=220, **self.card_kw(2),
            scrollbar_button_color=self.scrollbar_color(),
            scrollbar_button_hover_color=self._mix(
                self.scrollbar_color(), "#000000", 0.2))
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        def refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            favs = self.store.data.get("favorites", [])
            if not favs:
                ctk.CTkLabel(list_frame, text=self.t("no_favorites"),
                            text_color=self.muted()).pack(pady=10)
            for fav in favs:
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)

                def use_fav(url=fav["url"]):
                    if hasattr(self, "url_entry"):
                        self.url_entry.delete(0, "end")
                        self.url_entry.insert(0, url)
                    win.destroy()

                ctk.CTkButton(row, text="🔗 " + fav["name"], anchor="w",
                             fg_color="transparent",
                             hover_color=self._mix(self.accent["main"],
                                                   "#000000", 0.75),
                             text_color=self.text_on(2) or None,
                             command=use_fav).pack(side="left", fill="x",
                                                   expand=True)

                def remove_fav(url=fav["url"]):
                    self.store.data["favorites"] = [
                        f for f in self.store.data["favorites"]
                        if f["url"] != url]
                    self.store.save()
                    refresh_list()

                ctk.CTkButton(row, text="✕", width=28, height=26,
                             corner_radius=self.radius,
                             fg_color="transparent", border_width=1,
                             border_color="#F87171", text_color="#F87171",
                             hover_color="#7F1D1D",
                             command=remove_fav).pack(side="right")

        def add_favorite():
            url = getattr(self, "url_entry", None)
            url = url.get().strip() if url else ""
            name = name_e.get().strip() or url[:40]
            if not url:
                return
            favs = self.store.data.setdefault("favorites", [])
            if not any(f["url"] == url for f in favs):
                favs.append({"name": name, "url": url})
                self.store.save()
            name_e.delete(0, "end")
            refresh_list()

        self.btn(add_row, text="+ " + self.t("add_favorite"), width=140,
                 height=34, command=add_favorite).pack(side="left")
        refresh_list()

    def maybe_show_whats_new(self):
        """📣 Zeigt einmalig pro Update, was sich geändert hat."""
        seen = self.store.data["settings"].get("last_seen_version")
        if seen == APP_VERSION or APP_VERSION not in CHANGELOG:
            if seen != APP_VERSION:
                self.store.data["settings"]["last_seen_version"] = APP_VERSION
                self.store.save()
            return
        lang = self.store.data["settings"]["language"] or "en"
        items = CHANGELOG[APP_VERSION].get(lang,
                                           CHANGELOG[APP_VERSION]["en"])

        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("460x420")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="📣", font=self.font(size=36)).pack(
            pady=(20, 4))
        title = (f"Was ist neu in {APP_VERSION}" if lang == "de"
                else f"What's new in {APP_VERSION}")
        ctk.CTkLabel(win, text=title, font=self.font(size=17,
                                                     weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(0, 12))

        list_frame = ctk.CTkScrollableFrame(
            win, corner_radius=self.radius, height=260, **self.card_kw(2),
            scrollbar_button_color=self.scrollbar_color(),
            scrollbar_button_hover_color=self._mix(
                self.scrollbar_color(), "#000000", 0.2))
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        for item in items:
            ctk.CTkLabel(list_frame, text="• " + item, anchor="w",
                        justify="left", wraplength=380,
                        text_color=self.text_on(2) or None,
                        font=self.font(size=12)).pack(anchor="w", padx=8,
                                                      pady=3)

        def close():
            self.store.data["settings"]["last_seen_version"] = APP_VERSION
            self.store.save()
            win.destroy()

        self.btn(win, text="✓ OK", width=140, command=close).pack(
            pady=(0, 20))

    def show_feature_tour(self):
        """❓ App-Tour: Schritt-für-Schritt-Erklärung aller Funktionen —
        blättert wie eine kleine Präsentation durch, mit Icon + kurzer
        Erklärung pro Schritt."""
        lang = self.store.data["settings"]["language"] or "en"
        steps_de = [
            ("⬇", "Download", "Link einfügen (YouTube, TikTok, Instagram, Facebook oder direkte Bild-/Dateilinks) und auf Download klicken."),
            ("🤖", "KI-Modus", "Erkennt automatisch Plattform und beste Auflösung — du musst nur noch das Format wählen."),
            ("🎬", "Video-Vorschau", "Vor dem Download siehst du Thumbnail, Titel, Kanal und Dauer, um sicherzugehen, dass es das richtige Video ist."),
            ("🎵", "Formate & Metadaten", "MP4 ist gratis, alle anderen Formate (MP3, WAV, MKV, ...) sind Premium. Titel, Interpret und Cover-Bild werden automatisch eingebettet."),
            ("📺", "Playlist/Kanal & ✂️ Ausschnitt", "Premium: lade eine ganze Playlist/Kanal auf einmal, oder nur einen bestimmten Zeitbereich eines Videos."),
            ("📋", "Warteschlange", "Premium: mehrere Links auf einmal einfügen (einer pro Zeile) — die App lädt sie automatisch nacheinander bzw. parallel herunter, je nach Einstellung."),
            ("🖼️", "Wallpaper-Download", "Premium: Bild-Link einfügen, Gerät (iPhone/Android/PC) und Auflösung wählen — die App passt das Bild automatisch perfekt an, sogar bei schlechter Ausgangsqualität."),
            ("🌍", "Untertitel & Übersetzung", "Untertitel automatisch mitladen, in fast jeder Sprache — übersetzt aber nur den Text, nicht die gesprochene Sprache."),
            ("🔍", "Automatische Hochskalierung", "Ist das Original kleiner als die gewählte Auflösung, kann die App es hochskalieren (macht es größer, nicht schärfer)."),
            ("★", "Premium", "Premium-Website (PayPal), 1 Tag gratis testen, oder einen Code einlösen. Kontaktformular für Fragen/Probleme."),
            ("⚙", "Einstellungen", "Design, Farben, Schriftart, Effekte, Downloads-Verhalten, Autostart, Browser-Erweiterung und vieles mehr."),
            ("👑", "Admin (nur Owner)", "Nutzer verwalten, Premium vergeben, Geschenk-Codes erstellen, E-Mail-Versand einrichten."),
        ]
        steps_en = [
            ("⬇", "Download", "Paste a link (YouTube, TikTok, Instagram, Facebook, or direct image/file links) and click Download."),
            ("🤖", "AI mode", "Automatically detects the platform and best resolution — you just pick the format."),
            ("🎬", "Video preview", "Before downloading you see the thumbnail, title, channel and duration, so you know it's the right video."),
            ("🎵", "Formats & metadata", "MP4 is free, all other formats (MP3, WAV, MKV, ...) are Premium. Title, artist and cover art get embedded automatically."),
            ("📺", "Playlist/channel & ✂️ Clip", "Premium: download a whole playlist/channel at once, or just a specific time range of a video."),
            ("📋", "Queue", "Premium: paste multiple links at once (one per line) — the app downloads them automatically, one after another or in parallel depending on your setting."),
            ("🖼️", "Wallpaper download", "Premium: paste an image link, pick a device (iPhone/Android/PC) and resolution — the app fits the image perfectly, even from low-quality sources."),
            ("🌍", "Subtitles & translation", "Auto-download subtitles in almost any language — translates only the text, not the spoken language."),
            ("🔍", "Auto-upscale", "If the original is smaller than your chosen resolution, the app can upscale it (makes it bigger, not sharper)."),
            ("★", "Premium", "Premium website (PayPal), a free 1-day trial, or redeeming a code. Contact form for questions/issues."),
            ("⚙", "Settings", "Design, colors, font, effects, download behavior, autostart, browser extension, and much more."),
            ("👑", "Admin (owner only)", "Manage users, grant Premium, create gift codes, set up email sending."),
        ]
        steps = steps_de if lang == "de" else steps_en
        state = {"i": 0}

        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("440x340")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        icon_lbl = ctk.CTkLabel(win, text="", font=self.font(size=44))
        icon_lbl.pack(pady=(24, 6))
        title_lbl = ctk.CTkLabel(win, text="", font=self.font(size=17,
                                                              weight="bold"),
                                 text_color=self.accent["main"])
        title_lbl.pack(pady=(0, 8))
        desc_lbl = ctk.CTkLabel(win, text="", wraplength=380,
                                justify="center", font=self.font(size=13),
                                text_color=self.text_on(2) or None)
        desc_lbl.pack(padx=24, pady=(0, 12))
        step_lbl = ctk.CTkLabel(win, text="", text_color=self.muted(),
                                font=self.font(size=11))
        step_lbl.pack()

        def render():
            icon, title, desc = steps[state["i"]]
            icon_lbl.configure(text=icon)
            title_lbl.configure(text=title)
            desc_lbl.configure(text=desc)
            step_lbl.configure(text=f"{state['i'] + 1} / {len(steps)}")
            back_btn.configure(state="disabled" if state["i"] == 0
                              else "normal")
            next_btn.configure(
                text=("✓ " + ("Fertig" if lang == "de" else "Done"))
                if state["i"] == len(steps) - 1
                else ("Weiter →" if lang == "de" else "Next →"))

        def go_next():
            if state["i"] == len(steps) - 1:
                win.destroy()
            else:
                state["i"] += 1
                render()

        def go_back():
            state["i"] = max(0, state["i"] - 1)
            render()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(16, 20))
        back_btn = ctk.CTkButton(
            btn_row, text=("← Zurück" if lang == "de" else "← Back"),
            width=130, height=38, corner_radius=self.radius,
            fg_color="transparent", border_width=1,
            border_color=self.muted(),
            text_color=self.text_on(2) or self.muted(), command=go_back)
        back_btn.pack(side="left", padx=6)
        next_btn = self.btn(btn_row, width=150, height=38, command=go_next,
                            text="")
        next_btn.pack(side="left", padx=6)
        render()

    def confirm_dialog(self, title: str, message: str,
                       yes_text=None, danger=True) -> bool:
        """Bestätigungs-Dialog im App-Design (statt des schlichten
        Windows-Fensters). Blockiert, bis der Nutzer wählt."""
        result = {"ok": False}
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("440x230")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="⚠️", font=self.font(size=32)).pack(
            pady=(24, 4))
        ctk.CTkLabel(win, text=title, font=self.font(size=16, weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(0, 6))
        ctk.CTkLabel(win, text=message, wraplength=380, justify="center",
                     font=self.font(size=13),
                     text_color=self.text_on(2) or None).pack(
                         padx=20, pady=(0, 20))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(0, 20))

        def yes():
            result["ok"] = True
            win.destroy()

        self.btn(btn_row, text=yes_text or self.t("confirm_yes"), width=170,
                 fg_color=("#DC2626" if danger else self.accent["main"]),
                 hover_color=("#B91C1C" if danger else self.accent["hover"]),
                 command=yes).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text=self.t("confirm_no"), width=140,
                      corner_radius=self.radius, fg_color="transparent",
                      border_width=1, border_color=self.muted(),
                      text_color=self.text_on(2) or self.muted(),
                      command=win.destroy).pack(side="left", padx=6)

        win.wait_window()
        return result["ok"]

    def show_premium_dialog(self, message: str):
        """Schönerer, einheitlicher Premium-Hinweis statt eines
        schlichten Windows-Warnfensters."""
        win = ctk.CTkToplevel(self)
        win.title(APP_NAME)
        win.geometry("420x260")
        win.resizable(False, False)
        win.grab_set()
        card_bg = self.tint(2)
        if card_bg:
            win.configure(fg_color=card_bg)

        ctk.CTkLabel(win, text="🔒", font=self.font(size=34)).pack(
            pady=(26, 6))
        ctk.CTkLabel(win, text=self.t("premium_required_title"),
                     font=self.font(size=17, weight="bold"),
                     text_color=self.accent["main"]).pack(pady=(0, 8))
        ctk.CTkLabel(win, text=message, wraplength=360, justify="center",
                     font=self.font(size=13),
                     text_color=self.text_on(2) or None).pack(
                         padx=24, pady=(0, 20))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(0, 24))

        def go_premium():
            win.destroy()
            self.page_premium()

        self.btn(btn_row, text=self.t("see_premium"), width=170,
                 height=40, command=go_premium).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="OK", width=90, height=40,
                      corner_radius=self.radius, fg_color="transparent",
                      border_width=1, border_color=self.muted(),
                      text_color=self.text_on(2) or self.muted(),
                      hover_color=self._mix(self.accent["main"],
                                            "#000000", 0.75),
                      command=win.destroy).pack(side="left", padx=6)

    # --- Seite: Einstellungen ----------------------------------------------------
    def page_settings(self):
        self._page = self.page_settings
        self.clear_content()

        card = self.make_scroll_area(self.content)

        ctk.CTkLabel(card, text="⚙ " + self.t("settings"),
                     font=self.font(size=24, weight="bold")).pack(
                         anchor="w", padx=20, pady=(16, 14))

        s = self.store.data["settings"]

        def section(title):
            sep = ctk.CTkFrame(
                card, height=1,
                fg_color=self._mix(self.muted(), self.tint(2) or
                                   ("#000000" if s["appearance"] == "dark"
                                    else "#FFFFFF"), 0.75))
            sep.pack(fill="x", padx=20, pady=(16, 0))
            ctk.CTkLabel(card, text=title,
                         font=self.font(size=14, weight="bold")).pack(
                             anchor="w", padx=20, pady=(10, 4))

        # Sprache
        section(self.t("language"))
        lang_var = ctk.StringVar(value="Deutsch" if s["language"] == "de" else "English")

        def change_lang(v):
            s["language"] = "de" if v == "Deutsch" else "en"
            self.store.save()
            self.screen_main()

        ctk.CTkOptionMenu(card, values=["Deutsch", "English"], variable=lang_var,
                          command=change_lang, corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"], text_color=self._opt_text_color()).pack(anchor="w", padx=20)

        # Design-Stil (Classic / Retro)
        section("🎮 " + self.t("design_style"))
        d_map = {self.t("design_classic"): "classic",
                 self.t("design_retro"): "retro",
                 self.t("design_modern"): "modern"}
        rev_d = {v: k for k, v in d_map.items()}
        d_var = ctk.StringVar(value=rev_d[s.get("design", "classic")])

        def change_design(v):
            s["design"] = d_map[v]
            # Eigene Hintergrund-Farben (Fenster/Sidebar/Karten) würden den
            # Design-Stil sonst dauerhaft überdecken — beim Stil-Wechsel
            # daher zurücksetzen, damit man den neuen Look auch sieht.
            # Button-/Name-/Scrollbalken-Farben bleiben erhalten.
            el2 = s.setdefault("el_colors", {})
            el2["window"] = None
            el2["sidebar"] = None
            el2["card"] = None
            self.store.save()
            self.apply_theme()
            self.screen_main()

        ctk.CTkSegmentedButton(card, values=list(d_map.keys()),
                               variable=d_var, command=change_design,
                               **self.seg_kw()).pack(anchor="w", padx=20)

        # 🔤 Schriftart & -größe
        section("🔤 " + self.t("font_title"))
        font_row = ctk.CTkFrame(card, fg_color="transparent")
        font_row.pack(anchor="w", padx=20, fill="x")

        try:
            import tkinter.font as _tkfont
            all_fams = sorted(set(_tkfont.families()))
        except Exception:
            all_fams = []
        common_fonts = [f for f in
                        ("Arial", "Segoe UI", "Verdana", "Georgia",
                         "Comic Sans MS", "Times New Roman", "Consolas",
                         "Courier New", "Trebuchet MS", "Tahoma")
                        if f in all_fams] or ["Arial"]
        font_labels = [self.t("font_default")] + common_fonts
        cur_family = s.get("font_family") or self.t("font_default")
        font_var = ctk.StringVar(value=cur_family if cur_family in
                                 font_labels else self.t("font_default"))

        def change_font(v):
            s["font_family"] = "" if v == self.t("font_default") else v
            self.store.save()
            self.screen_main()

        ctk.CTkOptionMenu(font_row, values=font_labels, variable=font_var,
                          command=change_font, width=200, height=32,
                          corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"],
                          text_color=self._opt_text_color()).pack(
                              side="left", padx=(0, 16))

        ctk.CTkLabel(font_row, text=self.t("font_size_label")).pack(
            side="left", padx=(0, 8))
        size_val = ctk.DoubleVar(value=s.get("font_scale", 1.0))
        size_lbl = ctk.CTkLabel(font_row, text=f"{int(size_val.get()*100)}%",
                                width=45)

        def size_move(v):
            size_lbl.configure(text=f"{int(float(v)*100)}%")

        def size_release(_e=None):
            s["font_scale"] = round(size_val.get(), 2)
            self.store.save()
            self.screen_main()

        size_slider = ctk.CTkSlider(font_row, from_=0.8, to=1.4,
                                    number_of_steps=12, variable=size_val,
                                    command=size_move, width=160,
                                    progress_color=self.accent["main"],
                                    button_color=self.accent["main"],
                                    button_hover_color=self.accent["hover"])
        size_slider.pack(side="left", padx=(0, 8))
        size_slider.bind("<ButtonRelease-1>", size_release)
        size_lbl.pack(side="left")
        ctk.CTkLabel(card, text=self.t("font_hint"), text_color=self.muted(),
                     font=self.font(size=11), wraplength=560,
                     justify="left").pack(anchor="w", padx=20, pady=(4, 0))

        # 👁 Mini-Live-Vorschau: zeigt sofort, wie Sidebar/Karten/Buttons
        # mit den aktuellen Farben aussehen — wird bei jeder Farbänderung
        # automatisch mit neu gezeichnet, da die Seite dann neu aufgebaut wird.
        ctk.CTkLabel(card, text=self.t("preview_title"),
                     font=self.font(size=12, weight="bold"),
                     text_color=self.muted()).pack(anchor="w", padx=20,
                                                   pady=(10, 4))
        self._draw_mini_preview(card)

        # Animierte Effekte
        section("✨ " + self.t("effects"))
        fx_map = {self.t("effect_none"): "none",
                  self.t("effect_aurora"): "aurora",
                  self.t("effect_snow"): "snow"}
        rev_fx = {v: k for k, v in fx_map.items()}
        fx_var = ctk.StringVar(value=rev_fx[s.get("effect", "none")])

        def change_fx(v):
            s["effect"] = fx_map[v]
            self.store.save()
            self.apply_theme()
            self.screen_main()

        ctk.CTkSegmentedButton(card, values=list(fx_map.keys()),
                               variable=fx_var, command=change_fx,
                               **self.seg_kw()).pack(anchor="w", padx=20)

        # 🐢 Sparmodus für ältere/schwächere Rechner
        perf_var = ctk.BooleanVar(value=s.get("performance_mode", False))

        def toggle_perf():
            s["performance_mode"] = perf_var.get()
            self.store.save()
            self.screen_main()

        ctk.CTkSwitch(card, text="🐢 " + self.t("performance_mode"),
                      variable=perf_var, command=toggle_perf,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(8, 0))
        ctk.CTkLabel(card, text=self.t("performance_mode_hint"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)

        # Benachrichtigungen
        section(self.t("notifications"))
        notif_var = ctk.BooleanVar(value=s["notifications"])

        def toggle_notif():
            s["notifications"] = notif_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("notifications_desc"),
                      variable=notif_var, command=toggle_notif,
                      progress_color=self.accent["main"]).pack(anchor="w", padx=20)

        # Eigener Name + Glitzer-Effekt
        section("✏ " + self.t("custom_name"))
        premium = self.store.is_premium()
        me = self.store.data["users"].get(self.store.current_email, {})

        name_row = ctk.CTkFrame(card, fg_color="transparent")
        name_row.pack(anchor="w", padx=20, fill="x")
        name_e = ctk.CTkEntry(name_row, placeholder_text=self.t("name_placeholder"),
                              width=240, height=38, corner_radius=self.radius)
        name_e.insert(0, self.store.display_name())
        name_e.pack(side="left", padx=(0, 10))

        style_labels = {
            "none": self.t("style_none"), "glitter": self.t("style_glitter"),
            "rainbow": self.t("style_rainbow"), "hearts": self.t("style_hearts"),
            "fire": self.t("style_fire"), "pulse": self.t("style_pulse"),
        }
        rev_style = {v: k for k, v in style_labels.items()}
        style_var = ctk.StringVar(
            value=style_labels.get(me.get("name_style", "none"),
                                   self.t("style_none")))
        style_menu = ctk.CTkOptionMenu(name_row, values=list(style_labels.values()),
                                       variable=style_var,
                                       corner_radius=self.radius,
                                       fg_color=self.accent["main"],
                                       button_color=self.accent["hover"], text_color=self._opt_text_color())
        style_menu.pack(side="left", padx=(0, 10))
        if not premium:
            style_menu.configure(state="disabled")

        name_msg = ctk.CTkLabel(
            card,
            text=self.t("name_free_hint") + "  " + ("" if premium else "🔒 " + self.t("style_locked"))
            if not premium else "",
            text_color=self.muted(), font=self.font(size=11))
        name_msg.pack(anchor="w", padx=20)

        def save_name():
            new = name_e.get().strip()
            if not new:
                return
            style = rev_style.get(style_var.get(), "none")
            if self.store.set_name(new, style):
                name_msg.configure(text="✓ " + self.t("name_saved"),
                                   text_color="#34D399")
                self.screen_main()
            else:
                name_msg.configure(text="🔒 " + self.t("name_once_used"),
                                   text_color="#FBBF24")

        self.btn(name_row, text=self.t("save_name"), width=150, height=38,
                 command=save_name).pack(side="left")

        # Farbe
        section(self.t("accent_color"))
        color_row = ctk.CTkFrame(card, fg_color="transparent")
        color_row.pack(anchor="w", padx=20)
        for name, col in ACCENTS.items():
            def pick(n=name):
                s["accent"] = n
                s["custom_accent"] = None
                self.store.save()
                self.apply_theme()
                self.screen_main()
            ctk.CTkButton(color_row, text="", width=36, height=36,
                          corner_radius=18, fg_color=col["main"],
                          hover_color=col["hover"], border_width=3,
                          border_color="#FFFFFF" if s["accent"] == name else col["main"],
                          command=pick).pack(side="left", padx=5)

        # Eigene Hex-Farbe (wie "Custom #4f8eff")
        hex_row = ctk.CTkFrame(card, fg_color="transparent")
        hex_row.pack(anchor="w", padx=20, pady=(8, 0))
        hex_e = ctk.CTkEntry(hex_row, placeholder_text="#4F8EFF",
                             width=130, height=34, corner_radius=self.radius)
        if s.get("custom_accent"):
            hex_e.insert(0, s["custom_accent"])
        hex_e.pack(side="left", padx=(0, 8))
        hex_msg = ctk.CTkLabel(hex_row, text=self.t("custom_color"),
                               text_color=self.muted(), font=self.font(size=11))

        def apply_hex():
            v = hex_e.get().strip()
            if not v.startswith("#"):
                v = "#" + v
            if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                s["custom_accent"] = v.upper()
                self.store.save()
                self.apply_theme()
                self.screen_main()
            else:
                hex_msg.configure(text="✗ " + self.t("invalid_hex"),
                                  text_color="#F87171")

        self.btn(hex_row, text=self.t("apply"), width=110, height=34,
                 command=apply_hex).pack(side="left", padx=(0, 8))

        def pick_color_native():
            initial = hex_e.get().strip() or self.accent["main"]
            try:
                _, hexval = colorchooser.askcolor(color=initial,
                                                  title=self.t("pick_color"))
            except Exception:
                hexval = None
            if hexval:
                hex_e.delete(0, "end")
                hex_e.insert(0, hexval.upper())
                apply_hex()

        ctk.CTkButton(hex_row, text="🎨", width=40, height=34,
                      corner_radius=self.radius, fg_color="transparent",
                      border_width=1, border_color=self.accent["main"],
                      text_color=self.accent["main"],
                      hover_color=self.accent["hover"],
                      command=pick_color_native).pack(side="left",
                                                      padx=(0, 8))
        hex_msg.pack(side="left")

        # 🎨 Einzelne Elemente einzeln färben
        section("🎨 " + self.t("el_colors_title"))
        ctk.CTkLabel(card, text=self.t("el_hint"), text_color=self.muted(),
                     font=self.font(size=11)).pack(anchor="w", padx=20)
        el = s.setdefault("el_colors", {"window": None, "sidebar": None,
                                        "card": None, "button": None})

        def el_row(key, label_text):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(anchor="w", padx=20, pady=2, fill="x")
            ctk.CTkLabel(row, text=label_text, width=110,
                         anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, placeholder_text="#RRGGBB", width=110,
                             height=30, corner_radius=self.radius)
            if el.get(key):
                e.insert(0, el[key])
            e.pack(side="left", padx=(0, 6))

            warn_lbl = ctk.CTkLabel(card, text="", text_color="#FBBF24",
                                    font=self.font(size=11))

            def refresh():
                self.store.save()
                self.apply_theme()
                self.screen_main()

            def check_contrast():
                v = el.get(key)
                if v and key in ("window", "sidebar", "card", "button") \
                        and self._low_contrast(v):
                    warn_lbl.configure(text="⚠ " + self.t("low_contrast_warn"))
                    warn_lbl.pack(anchor="w", padx=(130, 20), pady=(0, 4))
                else:
                    warn_lbl.pack_forget()

            def apply_el():
                v = e.get().strip()
                if not v:
                    el[key] = None
                    refresh(); return
                if not v.startswith("#"):
                    v = "#" + v
                if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                    el[key] = v.upper()
                    refresh()

            def reset_el():
                el[key] = None
                refresh()

            def pick_native():
                initial = e.get().strip() or "#FFFFFF"
                try:
                    _, hexval = colorchooser.askcolor(
                        color=initial, title=self.t("pick_color"))
                except Exception:
                    hexval = None
                if hexval:
                    e.delete(0, "end")
                    e.insert(0, hexval.upper())
                    apply_el()

            self.btn(row, text=self.t("apply"), width=100, height=30,
                     command=apply_el).pack(side="left", padx=(0, 6))
            ctk.CTkButton(row, text="🎨", width=30, height=30,
                          corner_radius=self.radius, fg_color="transparent",
                          border_width=1, border_color=self.accent["main"],
                          text_color=self.accent["main"],
                          hover_color=self.accent["hover"],
                          command=pick_native).pack(side="left", padx=(0, 6))
            ctk.CTkButton(row, text="✕", width=30, height=30,
                          corner_radius=self.radius, fg_color="transparent",
                          border_width=1, border_color="#9CA3AF",
                          text_color=self.muted(), hover_color="#7F1D1D",
                          command=reset_el).pack(side="left")
            check_contrast()

            # Farbvorschläge zum Anklicken
            presets = ["#F87171", "#FB923C", "#FBBF24", "#34D399",
                       "#22D3EE", "#60A5FA", "#A78BFA", "#F472B6",
                       "#FFFFFF", "#111827"]
            sw_row = ctk.CTkFrame(card, fg_color="transparent")
            sw_row.pack(anchor="w", padx=(20 + 110, 20), pady=(0, 6))

            def make_pick(color):
                def pick_sw():
                    el[key] = color
                    refresh()
                return pick_sw

            for color in presets:
                ctk.CTkButton(sw_row, text="", width=20, height=20,
                              corner_radius=10, fg_color=color,
                              hover_color=self._mix(color, "#000000", 0.25),
                              border_width=2,
                              border_color=("#FFFFFF" if el.get(key) == color
                                            else color),
                              command=make_pick(color)).pack(side="left",
                                                             padx=2)

        el_row("window", self.t("el_window"))
        el_row("sidebar", self.t("el_sidebar"))
        el_row("card", self.t("el_card"))
        el_row("button", self.t("el_button"))
        el_row("name", self.t("el_name"))
        el_row("scrollbar", self.t("el_scrollbar"))

        # 🪄 Matching Mode — automatische Farbanpassung
        section("🪄 " + self.t("matching_title"))
        ctk.CTkLabel(card, text=self.t("matching_hint"), text_color=self.muted(),
                     font=self.font(size=11), wraplength=560,
                     justify="left").pack(anchor="w", padx=20)

        match_row = ctk.CTkFrame(card, fg_color="transparent")
        match_row.pack(anchor="w", padx=20, pady=(6, 2))
        match_hex = ctk.CTkEntry(match_row, placeholder_text="#FF66AA",
                                 width=110, height=32,
                                 corner_radius=self.radius)
        match_hex.pack(side="left", padx=(0, 6))

        def match_from_entry():
            v = match_hex.get().strip()
            if not v.startswith("#"):
                v = "#" + v
            if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                self.apply_matching(v.upper())

        self.btn(match_row, text="🪄 " + self.t("matching_apply"), width=170,
                 height=32, command=match_from_entry).pack(side="left",
                                                           padx=(0, 6))
        ctk.CTkButton(match_row, text=self.t("matching_reset"), width=150,
                      height=32, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color="#9CA3AF", text_color=self.muted(),
                      hover_color="#7F1D1D",
                      command=self.reset_matching).pack(side="left")

        match_sw = ctk.CTkFrame(card, fg_color="transparent")
        match_sw.pack(anchor="w", padx=20, pady=(2, 4))
        match_presets = ["#F43F5E", "#FB923C", "#FBBF24", "#22C55E",
                         "#14B8A6", "#22D3EE", "#3B82F6", "#8B5CF6",
                         "#EC4899", "#F472B6"]

        def make_match(color):
            return lambda: self.apply_matching(color)

        for color in match_presets:
            ctk.CTkButton(match_sw, text="", width=26, height=26,
                          corner_radius=13, fg_color=color,
                          hover_color=self._mix(color, "#000000", 0.25),
                          command=make_match(color)).pack(side="left", padx=3)

        # Farbe anwenden auf: Ganzes Programm / nur Icons & Schrift
        section(self.t("color_mode"))
        cm_map = {self.t("mode_full"): "full",
                  self.t("mode_accent"): "accent"}
        rev_cm = {v: k for k, v in cm_map.items()}
        cm_var = ctk.StringVar(value=rev_cm[s.get("color_mode", "accent")])

        def change_cm(v):
            s["color_mode"] = cm_map[v]
            self.store.save()
            self.apply_theme()
            self.screen_main()

        ctk.CTkSegmentedButton(card, values=list(cm_map.keys()),
                               variable=cm_var, command=change_cm,
                               **self.seg_kw()).pack(anchor="w", padx=20)

        # Form
        section(self.t("corner_style"))
        shape_map = {self.t("square"): "eckig", self.t("round"): "rund",
                     self.t("oval"): "oval"}
        rev = {v: k for k, v in shape_map.items()}
        shape_var = ctk.StringVar(value=rev[s["corner_style"]])

        def change_shape(v):
            s["corner_style"] = shape_map[v]
            s["radius_px"] = None
            self.store.save()
            self.screen_main()
            # Fenster-Neuformung erst NACH dem vollständigen Neuaufbau
            # anstoßen (verhindert Verzerrungen durch eine Race-Condition
            # zwischen Widget-Neuaufbau und Fenster-Umformung).
            self.after(30, self._apply_window_shape)

        ctk.CTkSegmentedButton(card, values=list(shape_map.keys()),
                               variable=shape_var, command=change_shape,
                               **self.seg_kw()).pack(anchor="w", padx=20)

        # Feiner Radius-Regler (0-25 px) — jetzt in Echtzeit, ohne
        # "Anwenden"-Knopf. Der eigentliche (teure) Neuaufbau der Seite
        # wird dabei entprellt (debounced): er läuft erst kurz NACHDEM
        # der Regler losgelassen/nicht mehr bewegt wird — das verhindert
        # das Verzerren/Ruckeln während des Ziehens.
        ctk.CTkLabel(card, text=self.t("radius_slider"),
                     text_color=self.muted(), font=self.font(size=11)).pack(
                         anchor="w", padx=20, pady=(8, 0))
        rad_row = ctk.CTkFrame(card, fg_color="transparent")
        rad_row.pack(anchor="w", padx=20, fill="x")
        rad_val = ctk.IntVar(value=self.radius)
        rad_lbl = ctk.CTkLabel(rad_row, text=f"{self.radius} px", width=50)

        def _rebuild_after_radius():
            self.screen_main()
            self.after(30, self._apply_window_shape)

        def slider_move(v):
            val = int(float(v))
            rad_lbl.configure(text=f"{val} px")
            s["radius_px"] = val
            self.store.save()
            if self._radius_debounce:
                try:
                    self.after_cancel(self._radius_debounce)
                except Exception:
                    pass
            self._radius_debounce = self.after(200, _rebuild_after_radius)

        rad_slider = ctk.CTkSlider(rad_row, from_=0, to=25,
                                   number_of_steps=25, width=240,
                                   variable=rad_val, command=slider_move,
                                   progress_color=self.accent["main"],
                                   button_color=self.accent["main"],
                                   button_hover_color=self.accent["hover"])
        rad_slider.pack(side="left", padx=(0, 10))
        rad_lbl.pack(side="left", padx=(0, 10))

        # Hell/Dunkel
        section(self.t("appearance"))
        mode_map = {self.t("dark"): "dark", self.t("light"): "light"}
        rev_m = {v: k for k, v in mode_map.items()}
        mode_var = ctk.StringVar(value=rev_m[s["appearance"]])

        def change_mode(v):
            s["appearance"] = mode_map[v]
            self.store.save()
            self.apply_theme()

        ctk.CTkSegmentedButton(card, values=list(mode_map.keys()),
                               variable=mode_var, command=change_mode,
                               **self.seg_kw()).pack(anchor="w", padx=20)

        # Download-Ordner
        section(self.t("download_folder"))

        ask_var = ctk.BooleanVar(value=s.get("ask_save", True))

        def toggle_ask():
            s["ask_save"] = ask_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("ask_save"), variable=ask_var,
                      command=toggle_ask,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(0, 10))

        folder_row = ctk.CTkFrame(card, fg_color="transparent")
        folder_row.pack(anchor="w", padx=20, fill="x", pady=(0, 4))
        folder_lbl = ctk.CTkLabel(folder_row, text=s["download_dir"],
                                  text_color=self.muted(),
                                  font=self.font(size=13),
                                  anchor="w")
        folder_lbl.pack(side="left", padx=(0, 12), fill="x", expand=True)

        def pick_folder():
            d = filedialog.askdirectory()
            if d:
                s["download_dir"] = d
                self.store.save()
                folder_lbl.configure(text=d)

        self.btn(folder_row, text="📁 " + self.t("choose_folder"), width=190,
                 command=pick_folder).pack(side="right")

        try:
            usage = shutil.disk_usage(s["download_dir"])
            free_gb = usage.free / (1024 ** 3)
            disk_txt = f"💽 {free_gb:.1f} GB {self.t('disk_free')}"
        except Exception:
            disk_txt = ""
        if disk_txt:
            ctk.CTkLabel(card, text=disk_txt, text_color=self.muted(),
                         font=self.font(size=11)).pack(anchor="w", padx=20,
                                                       pady=(0, 8))

        # --- Autostart ---
        section("🚀 " + self.t("autostart"))
        auto_var = ctk.BooleanVar(value=s.get("autostart", False))

        def toggle_autostart():
            ok = self.set_autostart(auto_var.get())
            s["autostart"] = auto_var.get() if ok else False
            if not ok:
                auto_var.set(False)
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("autostart"), variable=auto_var,
                      command=toggle_autostart,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20)
        if sys.platform != "win32":
            ctk.CTkLabel(card, text="(Windows only)", text_color=self.muted(),
                         font=self.font(size=11)).pack(anchor="w", padx=20)

        # --- Downloads: Limits, Bandbreite, Proxy, Untertitel ---
        section("⬇ " + self.t("concurrent_dl"))
        conc_row = ctk.CTkFrame(card, fg_color="transparent")
        conc_row.pack(anchor="w", padx=20, fill="x")
        conc_val = ctk.IntVar(value=s.get("concurrent_downloads", 3))
        conc_lbl = ctk.CTkLabel(conc_row, text=str(conc_val.get()), width=30)

        def conc_move(v):
            val = int(float(v))
            conc_lbl.configure(text=str(val))
            s["concurrent_downloads"] = val
            self.store.save()

        ctk.CTkSlider(conc_row, from_=1, to=10, number_of_steps=9,
                     width=200, variable=conc_val, command=conc_move,
                     progress_color=self.accent["main"],
                     button_color=self.accent["main"],
                     button_hover_color=self.accent["hover"]).pack(
                         side="left", padx=(0, 10))
        conc_lbl.pack(side="left")
        ctk.CTkLabel(card, text=self.t("concurrent_note"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20, pady=(2, 0))

        section("🚦 " + self.t("bandwidth_limit"))
        bw_row = ctk.CTkFrame(card, fg_color="transparent")
        bw_row.pack(anchor="w", padx=20, fill="x")
        bw_e = ctk.CTkEntry(bw_row, width=100, height=34,
                            corner_radius=self.radius,
                            placeholder_text=self.t("bandwidth_unlimited"))
        if s.get("bandwidth_kb", 0):
            bw_e.insert(0, str(s["bandwidth_kb"]))
        bw_e.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(bw_row, text=self.t("bandwidth_kbps")).pack(side="left")

        def save_bw():
            v = bw_e.get().strip()
            try:
                s["bandwidth_kb"] = max(0, int(v)) if v else 0
            except ValueError:
                s["bandwidth_kb"] = 0
            self.store.save()

        self.btn(bw_row, text=self.t("apply"), width=100, height=34,
                 command=save_bw).pack(side="left", padx=(8, 0))

        section("🌐 " + self.t("proxy_title"))
        proxy_row = ctk.CTkFrame(card, fg_color="transparent")
        proxy_row.pack(anchor="w", padx=20, fill="x")
        proxy_e = ctk.CTkEntry(proxy_row, width=360, height=34,
                              corner_radius=self.radius,
                              placeholder_text=self.t("proxy_ph"))
        if s.get("proxy_url"):
            proxy_e.insert(0, s["proxy_url"])
        proxy_e.pack(side="left", padx=(0, 8))

        def save_proxy():
            s["proxy_url"] = proxy_e.get().strip()
            self.store.save()

        self.btn(proxy_row, text=self.t("apply"), width=100, height=34,
                 command=save_proxy).pack(side="left")

        section("⚡ " + self.t("subs_download"))
        subs_var = ctk.BooleanVar(value=s.get("download_subs", False))

        def toggle_subs():
            s["download_subs"] = subs_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("subs_download"), variable=subs_var,
                      command=toggle_subs,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20)

        sub_langs = {"en": "English", "de": "Deutsch", "es": "Español",
                    "fr": "Français", "pt": "Português", "it": "Italiano",
                    "nl": "Nederlands", "pl": "Polski", "tr": "Türkçe",
                    "ru": "Русский", "ar": "العربية", "hi": "हिन्दी",
                    "ja": "日本語", "ko": "한국어", "zh": "中文",
                    "all": self.t("sub_lang_all"),
                    "custom": self.t("sub_lang_custom")}
        sub_row = ctk.CTkFrame(card, fg_color="transparent")
        sub_row.pack(anchor="w", padx=20, pady=(4, 0), fill="x")
        ctk.CTkLabel(sub_row, text=self.t("sub_lang_label"),
                     width=140, anchor="w").pack(side="left")
        cur_lang = s.get("sub_lang", "en")
        is_custom = cur_lang not in sub_langs
        sub_var = ctk.StringVar(
            value=self.t("sub_lang_custom") if is_custom
            else sub_langs.get(cur_lang, "English"))

        custom_lang_e = ctk.CTkEntry(sub_row, width=90, height=32,
                                     corner_radius=self.radius,
                                     placeholder_text="z. B. sv, th, vi")
        if is_custom:
            custom_lang_e.insert(0, cur_lang)

        def change_sub_lang(v):
            rev = {val: key for key, val in sub_langs.items()}
            key = rev.get(v, "en")
            if key == "custom":
                custom_lang_e.pack(side="left", padx=(8, 0))
            else:
                custom_lang_e.pack_forget()
                s["sub_lang"] = key
                self.store.save()

        def save_custom_lang(_e=None):
            code = custom_lang_e.get().strip().lower()
            if code:
                s["sub_lang"] = code
                self.store.save()

        custom_lang_e.bind("<FocusOut>", save_custom_lang)
        custom_lang_e.bind("<Return>", save_custom_lang)

        ctk.CTkOptionMenu(sub_row, values=list(sub_langs.values()),
                          variable=sub_var, command=change_sub_lang,
                          width=160, height=32, corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"],
                          text_color=self._opt_text_color()).pack(side="left")
        if is_custom:
            custom_lang_e.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(card, text=self.t("sub_lang_hint"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)

        meta_var = ctk.BooleanVar(value=s.get("embed_metadata", True))

        def toggle_meta():
            s["embed_metadata"] = meta_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("embed_metadata"), variable=meta_var,
                      command=toggle_meta,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(10, 0))

        upscale_var = ctk.BooleanVar(value=s.get("auto_upscale", False))

        def toggle_upscale():
            if upscale_var.get() and not self.store.is_premium():
                upscale_var.set(False)
                self.show_premium_dialog(self.t("locked_platform"))
                return
            s["auto_upscale"] = upscale_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text="🔒 " + self.t("auto_upscale")
                      if not self.store.is_premium() else self.t(
                          "auto_upscale"),
                      variable=upscale_var, command=toggle_upscale,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(10, 0))
        ctk.CTkLabel(card, text=self.t("auto_upscale_hint"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)

        preview_var = ctk.BooleanVar(value=s.get("show_preview", True))

        def toggle_preview():
            s["show_preview"] = preview_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text="🎬 " + self.t("show_preview"),
                      variable=preview_var, command=toggle_preview,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(10, 0))

        clip_var = ctk.BooleanVar(value=s.get("clipboard_watch", False))

        def toggle_clip():
            s["clipboard_watch"] = clip_var.get()
            self.store.save()
            if clip_var.get():
                self._start_clipboard_watch()

        ctk.CTkSwitch(card, text=self.t("clipboard_watch"), variable=clip_var,
                      command=toggle_clip,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(6, 0))

        sort_var = ctk.BooleanVar(value=s.get("auto_sort", False))

        def toggle_sort():
            s["auto_sort"] = sort_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("auto_sort"), variable=sort_var,
                      command=toggle_sort,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(6, 0))

        title_var = ctk.BooleanVar(value=s.get("titlebar_progress", True))

        def toggle_title():
            s["titlebar_progress"] = title_var.get()
            self.store.save()
            if not title_var.get():
                self.title(APP_NAME)

        ctk.CTkSwitch(card, text=self.t("titlebar_progress"),
                      variable=title_var, command=toggle_title,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(6, 0))

        # --- 📝 Dateinamens-Vorlage ---
        section(self.t("filename_tpl_title"))
        ctk.CTkLabel(card, text=self.t("filename_tpl_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)
        tpl_row = ctk.CTkFrame(card, fg_color="transparent")
        tpl_row.pack(anchor="w", padx=20, fill="x", pady=(6, 0))
        tpl_e = ctk.CTkEntry(tpl_row, width=360, height=34,
                             corner_radius=self.radius,
                             placeholder_text=self.t("filename_tpl_ph"))
        tpl_e.insert(0, s.get("filename_template", "{title}"))
        tpl_e.pack(side="left", padx=(0, 8))

        def save_tpl():
            s["filename_template"] = tpl_e.get().strip() or "{title}"
            self.store.save()

        self.btn(tpl_row, text=self.t("apply"), width=100, height=34,
                 command=save_tpl).pack(side="left")

        # --- 🔄 Smart Resume (automatisch, nur Hinweistext) ---
        section(self.t("smart_resume_title"))
        ctk.CTkLabel(card, text=self.t("smart_resume_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)

        # --- 🔇 Ruhemodus ---
        silent_var = ctk.BooleanVar(value=s.get("silent_mode", False))

        def toggle_silent():
            s["silent_mode"] = silent_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("silent_mode"), variable=silent_var,
                      command=toggle_silent,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(10, 0))

        sound_var = ctk.BooleanVar(value=s.get("sound_on_complete", True))

        def toggle_sound():
            s["sound_on_complete"] = sound_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text="🔔 " + self.t("sound_on_complete"),
                      variable=sound_var, command=toggle_sound,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(6, 0))

        # --- 🧩 Browser-Erweiterung ---
        section(self.t("browser_ext_title"))
        ctk.CTkLabel(card, text=self.t("browser_ext_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20)
        bridge_var = ctk.BooleanVar(value=s.get("browser_bridge", True))

        def toggle_bridge():
            s["browser_bridge"] = bridge_var.get()
            self.store.save()

        ctk.CTkSwitch(card, text=self.t("browser_ext_toggle"),
                      variable=bridge_var, command=toggle_bridge,
                      progress_color=self.accent["main"]).pack(anchor="w",
                                                               padx=20,
                                                               pady=(6, 0))

        # --- ℹ️ Info & Updates ---
        section(self.t("info_updates"))
        ctk.CTkLabel(card, text=f"{self.t('version_label')}: {APP_VERSION}",
                     text_color=self.muted()).pack(anchor="w", padx=20)
        update_msg = ctk.CTkLabel(card, text="", text_color=self.muted(),
                                  font=self.font(size=11))

        def check_updates():
            update_msg.configure(text=self.t("up_to_date"),
                                 text_color="#34D399")
            update_msg.pack(anchor="w", padx=20, pady=(4, 0))

        self.btn(card, text=self.t("check_updates"), width=200, height=34,
                 command=check_updates).pack(anchor="w", padx=20,
                                            pady=(6, 0))

        ctk.CTkButton(card, text="❓ " + self.t("app_tour"), width=220,
                     height=34, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     command=self.show_feature_tour).pack(anchor="w",
                                                          padx=20,
                                                          pady=(8, 20))

        # --- ⚠️ Danger Zone: Reset & Export/Import (ganz unten) ---
        section(self.t("danger_zone"))
        dz_row = ctk.CTkFrame(card, fg_color="transparent")
        dz_row.pack(anchor="w", padx=20, fill="x", pady=(0, 10))
        self.btn(dz_row, text=self.t("export_theme"), width=170, height=34,
                 command=self.export_theme).pack(side="left", padx=(0, 8))
        self.btn(dz_row, text=self.t("import_theme"), width=170, height=34,
                 command=self.import_theme).pack(side="left", padx=(0, 8))
        ctk.CTkButton(dz_row, text=self.t("reset_appearance"), width=220,
                      height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color="#F87171", text_color="#F87171",
                      hover_color="#7F1D1D",
                      command=self.reset_appearance).pack(side="left",
                                                          padx=(0, 8))

        dz_row2 = ctk.CTkFrame(card, fg_color="transparent")
        dz_row2.pack(anchor="w", padx=20, fill="x", pady=(0, 24))
        ctk.CTkButton(dz_row2, text="💾 " + self.t("export_backup"),
                      width=210, height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color=self.accent["main"],
                      text_color=self.accent["main"],
                      hover_color=self.accent["hover"],
                      command=self.export_full_backup).pack(side="left",
                                                            padx=(0, 8))
        ctk.CTkButton(dz_row2, text="📂 " + self.t("import_backup"),
                      width=210, height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color=self.accent["main"],
                      text_color=self.accent["main"],
                      hover_color=self.accent["hover"],
                      command=self.import_full_backup).pack(side="left")

        if sys.platform == "win32":
            def fix_window():
                self._clear_window_shape()
                self.after(80, self._apply_window_shape)

            ctk.CTkButton(dz_row2, text=self.t("fix_window"), width=190,
                          height=34, corner_radius=self.radius,
                          fg_color="transparent", border_width=1,
                          border_color=self.muted(),
                          text_color=self.text_on(2) or self.muted(),
                          hover_color=self._mix(self.accent["main"],
                                                "#000000", 0.75),
                          command=fix_window).pack(side="left")

        # --- ☁️ Cloud-Sicherung (an dein Konto gebunden) ---
        ctk.CTkLabel(card, text="☁️ " + self.t("cloud_sync_title"),
                     font=self.font(size=15, weight="bold")).pack(
                         anchor="w", padx=20, pady=(4, 2))
        ctk.CTkLabel(card, text=self.t("cloud_sync_hint"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=20,
                                                          pady=(0, 8))
        cloud_row = ctk.CTkFrame(card, fg_color="transparent")
        cloud_row.pack(anchor="w", padx=20, fill="x")
        cloud_status = ctk.CTkLabel(card, text="", font=self.font(size=11))
        cloud_status.pack(anchor="w", padx=20, pady=(6, 24))

        def do_cloud_backup():
            cloud_status.configure(text="🔄 " + self.t("cloud_working"),
                                   text_color=self.muted())

            def worker():
                ok, err = self.cloud_backup()
                text = ("✓ " + self.t("cloud_backup_ok") if ok
                       else "✗ " + self.t("cloud_error") + f" ({err})")
                color = "#34D399" if ok else "#F87171"
                self.after(0, lambda: cloud_status.configure(
                    text=text, text_color=color))
            threading.Thread(target=worker, daemon=True).start()

        def do_cloud_restore():
            if not self.confirm_dialog(self.t("cloud_sync_title"),
                                       self.t("cloud_restore_confirm")):
                return
            cloud_status.configure(text="🔄 " + self.t("cloud_working"),
                                   text_color=self.muted())

            def worker():
                ok, err = self.cloud_restore()
                if ok:
                    self.after(0, self.apply_theme)
                    self.after(0, self.screen_main)
                else:
                    text = "✗ " + self.t("cloud_error") + f" ({err})"
                    self.after(0, lambda: cloud_status.configure(
                        text=text, text_color="#F87171"))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(cloud_row, text="☁️ " + self.t("cloud_backup_now"),
                     width=220, height=34, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     command=do_cloud_backup).pack(side="left", padx=(0, 8))
        ctk.CTkButton(cloud_row, text="☁️ " + self.t("cloud_restore_now"),
                     width=220, height=34, corner_radius=self.radius,
                     fg_color="transparent", border_width=1,
                     border_color=self.accent["main"],
                     text_color=self.accent["main"],
                     hover_color=self.accent["hover"],
                     command=do_cloud_restore).pack(side="left")

    # --- Seite: Admin (nur Owner) --------------------------------------------
    def page_admin(self):
        if not self.store.is_owner():
            return
        self._page = self.page_admin
        self.clear_content()
        outer = self.make_scroll_area(self.content, colored=False)
        card = ctk.CTkFrame(outer, corner_radius=self.radius,
                            **self.card_kw(2))
        card.pack(fill="x")

        ctk.CTkLabel(card, text="👑 " + self.t("admin_title"),
                     font=self.font(size=24, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(card, text=self.t("admin_desc"),
                     text_color=self.muted()).pack(anchor="w", padx=24, pady=(0, 14))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=24)

        email_e = ctk.CTkEntry(row, placeholder_text=self.t("user_email"),
                               width=280, height=40, corner_radius=self.radius)
        email_e.pack(side="left", padx=(0, 10))

        days_e = ctk.CTkEntry(row, placeholder_text=self.t("duration_days"),
                              width=130, height=40, corner_radius=self.radius)
        days_e.pack(side="left", padx=(0, 10))

        forever_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text=self.t("forever"), variable=forever_var,
                        fg_color=self.accent["main"]).pack(side="left")

        msg = ctk.CTkLabel(card, text="")
        msg.pack(anchor="w", padx=24, pady=(6, 0))

        def grant():
            email = email_e.get().strip().lower()
            days = None if forever_var.get() else (days_e.get().strip() or "30")
            if days is not None:
                try:
                    days = max(1, int(days))
                except ValueError:
                    days = 30
            if self.store.grant_premium(email, days):
                msg.configure(text=f"✓ {self.t('granted')} {email}",
                              text_color="#34D399")
                self.refresh_user_list()
            else:
                msg.configure(text="✗ " + self.t("user_not_found"),
                              text_color="#F87171")

        def revoke():
            email = email_e.get().strip().lower()
            if self.store.revoke_premium(email):
                msg.configure(text=f"✓ {self.t('revoked')} {email}",
                              text_color="#34D399")
                self.refresh_user_list()
            else:
                msg.configure(text="✗ " + self.t("user_not_found"),
                              text_color="#F87171")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(anchor="w", padx=24, pady=(10, 16))
        self.btn(btn_row, text="★  " + self.t("grant"), width=190,
                 command=grant).pack(side="left", padx=(0, 10))
        self.btn(btn_row, text=self.t("revoke"), width=190,
                 fg_color="#DC2626", hover_color="#B91C1C",
                 command=revoke).pack(side="left")

        # --- Geschenk-Code erstellen ---
        ctk.CTkLabel(card, text=self.t("gift_code_title"),
                     font=self.font(size=16, weight="bold")).pack(
                         anchor="w", padx=24, pady=(4, 0))
        ctk.CTkLabel(card, text=self.t("gift_code_desc"),
                     text_color=self.muted(),
                     font=self.font(size=11)).pack(anchor="w", padx=24)

        gift_row = ctk.CTkFrame(card, fg_color="transparent")
        gift_row.pack(anchor="w", padx=24, pady=(8, 4), fill="x")

        gift_days_e = ctk.CTkEntry(gift_row,
                                   placeholder_text=self.t("duration_days"),
                                   width=130, height=40,
                                   corner_radius=self.radius)
        gift_days_e.pack(side="left", padx=(0, 10))

        gift_forever = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(gift_row, text=self.t("forever"),
                        variable=gift_forever,
                        fg_color=self.accent["main"]).pack(side="left",
                                                           padx=(0, 10))

        code_out = ctk.CTkEntry(card, width=320, height=40,
                                corner_radius=self.radius,
                                font=self.font(size=15, weight="bold"),
                                justify="center")
        code_out.pack(anchor="w", padx=24, pady=(4, 20))
        code_out.insert(0, self.t("your_code") + " —")
        code_out.configure(state="readonly")

        def make_code():
            days = None if gift_forever.get() else (gift_days_e.get().strip() or "30")
            if days is not None:
                try:
                    days = max(1, int(days))
                except ValueError:
                    days = 30
            code = self.store.create_gift_code(days)
            code_out.configure(state="normal")
            code_out.delete(0, "end")
            code_out.insert(0, code)
            code_out.configure(state="readonly")
            self.refresh_user_list()

        self.btn(gift_row, text="🎁  " + self.t("create_code"), width=190,
                 command=make_code).pack(side="left")

        # --- ✉️ E-Mail-Versand (SMTP) — nur Owner sehen/ändern das ---
        ctk.CTkLabel(card, text=self.t("smtp_title"),
                     font=self.font(size=16, weight="bold")).pack(
                         anchor="w", padx=24, pady=(20, 0))
        ctk.CTkLabel(card, text=self.t("smtp_desc"), text_color=self.muted(),
                     font=self.font(size=11), wraplength=560,
                     justify="left").pack(anchor="w", padx=24)
        ctk.CTkLabel(card, text=self.t("smtp_guide"), text_color=self.muted(),
                     font=self.font(size=11), wraplength=560,
                     justify="left").pack(anchor="w", padx=24, pady=(6, 0))

        smtp = self.store.data["settings"].setdefault(
            "smtp", {"host": "", "port": 587, "user": "",
                     "password": "", "from_addr": "", "use_ssl": False})

        def on_provider(v):
            preset = SMTP_PRESETS.get(v)
            if not preset:
                return
            smtp_host_e.delete(0, "end"); smtp_host_e.insert(0, preset["host"])
            smtp_port_e.delete(0, "end"); smtp_port_e.insert(0, str(preset["port"]))
            ssl_var.set(preset["use_ssl"])

        prov_row = ctk.CTkFrame(card, fg_color="transparent")
        prov_row.pack(anchor="w", padx=24, pady=(10, 0), fill="x")
        ctk.CTkLabel(prov_row, text=self.t("smtp_provider"), width=140,
                     anchor="w").pack(side="left")
        ctk.CTkOptionMenu(prov_row, values=list(SMTP_PRESETS.keys()),
                          command=on_provider, width=260, height=34,
                          corner_radius=self.radius,
                          fg_color=self.accent["main"],
                          button_color=self.accent["hover"], text_color=self._opt_text_color()).pack(side="left")

        def smtp_field(label_text, key, show=None, width=220):
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(anchor="w", padx=24, pady=(8, 0), fill="x")
            ctk.CTkLabel(r, text=label_text, width=140,
                         anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=width, height=34,
                             corner_radius=self.radius, show=show)
            if smtp.get(key):
                e.insert(0, str(smtp[key]))
            e.pack(side="left")
            return e

        smtp_host_e = smtp_field(self.t("smtp_host"), "host", width=260)
        smtp_port_e = smtp_field(self.t("smtp_port"), "port", width=80)
        smtp_user_e = smtp_field(self.t("smtp_user"), "user", width=260)
        smtp_pass_e = smtp_field(self.t("smtp_pass"), "password", show="•")
        smtp_from_e = smtp_field(self.t("smtp_from"), "from_addr", width=260)

        ssl_row = ctk.CTkFrame(card, fg_color="transparent")
        ssl_row.pack(anchor="w", padx=24, pady=(8, 0), fill="x")
        ctk.CTkLabel(ssl_row, text="", width=140).pack(side="left")
        ssl_var = ctk.BooleanVar(value=smtp.get("use_ssl", False))
        ctk.CTkSwitch(ssl_row, text=self.t("smtp_ssl"), variable=ssl_var,
                      progress_color=self.accent["main"]).pack(side="left")

        smtp_msg = ctk.CTkLabel(card, text="", wraplength=560,
                                justify="left", font=self.font(size=11))
        smtp_msg.pack(anchor="w", padx=24, pady=(6, 0))

        def save_smtp():
            smtp["host"] = smtp_host_e.get().strip()
            try:
                smtp["port"] = int(smtp_port_e.get().strip() or 587)
            except ValueError:
                smtp["port"] = 587
            smtp["user"] = smtp_user_e.get().strip()
            smtp["password"] = smtp_pass_e.get()
            smtp["from_addr"] = smtp_from_e.get().strip()
            smtp["use_ssl"] = ssl_var.get()
            self.store.save()
            smtp_msg.configure(text="✓ " + self.t("smtp_save") + " ✓",
                              text_color="#34D399")

        def test_smtp():
            save_smtp()
            if not all([smtp.get("host"), smtp.get("user"),
                       smtp.get("password"), smtp.get("from_addr")]):
                smtp_msg.configure(text="✗ " + self.t("smtp_not_set"),
                                  text_color="#F87171")
                return
            smtp_msg.configure(text="🔄 ...", text_color=self.muted())
            to = self.store.current_email

            def worker():
                ok, err = self.send_email(
                    to, f"{APP_NAME}: SMTP test",
                    "Your SMTP setup works! You can now send "
                    "verification codes.\n\n— " + MADE_BY)
                self.after(0, lambda: (
                    smtp_msg.configure(
                        text=("✓ " + self.t("smtp_test_ok")) if ok
                        else ("✗ " + self.t("smtp_test_fail") + " " + str(err)),
                        text_color="#34D399" if ok else "#F87171")))
            threading.Thread(target=worker, daemon=True).start()

        smtp_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        smtp_btn_row.pack(anchor="w", padx=24, pady=(8, 6))
        self.btn(smtp_btn_row, text=self.t("smtp_save"), width=140,
                 height=34, command=save_smtp).pack(side="left", padx=(0, 8))
        ctk.CTkButton(smtp_btn_row, text="✉ " + self.t("smtp_test"),
                      width=180, height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color=self.accent["main"],
                      text_color=self.accent["main"],
                      hover_color=self.accent["hover"],
                      command=test_smtp).pack(side="left")

        # 🔑 Private Zugangsdaten mitnehmen (inkl. Passwort) — NUR für dich
        # selbst, damit du auf einem neuen PC nicht alles neu abtippen musst.
        # Landet NIE im Programmcode/in der ZIP, nur in einer Datei, die du
        # selbst speicherst.
        ctk.CTkLabel(card, text=self.t("smtp_private_hint"),
                     text_color="#FBBF24", font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=24,
                                                          pady=(0, 6))
        smtp_private_row = ctk.CTkFrame(card, fg_color="transparent")
        smtp_private_row.pack(anchor="w", padx=24, pady=(0, 20))

        def export_smtp_private():
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                initialfile="MEINE_zugangsdaten_NICHT_TEILEN.json",
                filetypes=[("JSON", "*.json")],
                title=self.t("smtp_export_private"))
            if not path:
                return
            smtp_data = self.store.data["settings"].get("smtp", {})
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(smtp_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo(APP_NAME, self.t("export_ok"))
            except Exception as e:
                messagebox.showerror(APP_NAME, str(e))

        def import_smtp_private():
            path = filedialog.askopenfilename(
                filetypes=[("JSON", "*.json")],
                title=self.t("smtp_import_private"))
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    smtp_data = json.load(f)
                self.store.data["settings"]["smtp"] = smtp_data
                self.store.save()
                self.screen_main()
                messagebox.showinfo(APP_NAME, self.t("import_ok"))
            except Exception:
                messagebox.showerror(APP_NAME, self.t("import_fail"))

        ctk.CTkButton(smtp_private_row, text="🔑 " +
                     self.t("smtp_export_private"), width=260, height=32,
                     corner_radius=self.radius, fg_color="transparent",
                     border_width=1, border_color="#FBBF24",
                     text_color="#FBBF24",
                     hover_color=self._mix("#FBBF24", "#000000", 0.75),
                     font=self.font(size=11),
                     command=export_smtp_private).pack(side="left",
                                                       padx=(0, 8))
        ctk.CTkButton(smtp_private_row, text="📂 " +
                     self.t("smtp_import_private"), width=260, height=32,
                     corner_radius=self.radius, fg_color="transparent",
                     border_width=1, border_color="#FBBF24",
                     text_color="#FBBF24",
                     hover_color=self._mix("#FBBF24", "#000000", 0.75),
                     font=self.font(size=11),
                     command=import_smtp_private).pack(side="left")

        # --- ✏️ E-Mail-Text bearbeiten ---
        tpl = self.store.data["settings"].setdefault(
            "email_template",
            {"subject": "{app}: your verification code is {code}",
             "body": ("Your {app} verification code:\n\n    {code}\n\n"
                      "This code expires in 15 minutes.\n\n"
                      "Didn't sign up? Just ignore this email.\n\n"
                      "— {made_by}")})

        ctk.CTkLabel(card, text=self.t("email_tpl_title"),
                     font=self.font(size=16, weight="bold")).pack(
                         anchor="w", padx=24, pady=(4, 0))
        ctk.CTkLabel(card, text=self.t("email_tpl_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(
                         anchor="w", padx=24)

        subj_row = ctk.CTkFrame(card, fg_color="transparent")
        subj_row.pack(anchor="w", padx=24, pady=(8, 0), fill="x")
        ctk.CTkLabel(subj_row, text=self.t("email_tpl_subject"), width=90,
                     anchor="w").pack(side="left")
        tpl_subject_e = ctk.CTkEntry(subj_row, width=400, height=34,
                                     corner_radius=self.radius)
        tpl_subject_e.insert(0, tpl.get("subject", ""))
        tpl_subject_e.pack(side="left")

        ctk.CTkLabel(card, text=self.t("email_tpl_body"),
                     anchor="w").pack(anchor="w", padx=24, pady=(8, 2))
        tpl_body_box = ctk.CTkTextbox(card, width=560, height=140,
                                      corner_radius=self.radius,
                                      font=self.font(size=13))
        tpl_body_box.insert("1.0", tpl.get("body", ""))
        tpl_body_box.pack(anchor="w", padx=24)

        tpl_msg = ctk.CTkLabel(card, text="", text_color=self.muted(),
                               font=self.font(size=11), wraplength=560,
                               justify="left")
        tpl_msg.pack(anchor="w", padx=24, pady=(6, 0))

        def save_template():
            subject = tpl_subject_e.get().strip() or "{app}: {code}"
            body = tpl_body_box.get("1.0", "end").rstrip("\n")
            tpl["subject"] = subject
            tpl["body"] = body
            self.store.save()
            if "{code}" not in subject and "{code}" not in body:
                tpl_msg.configure(text=self.t("email_tpl_no_code"),
                                  text_color="#FBBF24")
            else:
                tpl_msg.configure(text=self.t("email_tpl_saved"),
                                  text_color="#34D399")

        def reset_template():
            default_subject = "{app}: your verification code is {code}"
            default_body = ("Your {app} verification code:\n\n    {code}\n\n"
                            "This code expires in 15 minutes.\n\n"
                            "Didn't sign up? Just ignore this email.\n\n"
                            "— {made_by}")
            tpl_subject_e.delete(0, "end")
            tpl_subject_e.insert(0, default_subject)
            tpl_body_box.delete("1.0", "end")
            tpl_body_box.insert("1.0", default_body)
            tpl["subject"] = default_subject
            tpl["body"] = default_body
            self.store.save()
            tpl_msg.configure(text=self.t("email_tpl_saved"),
                              text_color="#34D399")

        def preview_template():
            save_template()
            to = self.store.current_email
            tpl_msg.configure(text="🔄 ...", text_color=self.muted())

            def worker():
                ok, err = self.send_verification_code(to, "123456")
                self.after(0, lambda: tpl_msg.configure(
                    text=("✓ " + self.t("smtp_test_ok")) if ok
                    else ("✗ " + self.t("smtp_test_fail") + " " + str(err)),
                    text_color="#34D399" if ok else "#F87171"))
            threading.Thread(target=worker, daemon=True).start()

        tpl_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        tpl_btn_row.pack(anchor="w", padx=24, pady=(8, 20))
        self.btn(tpl_btn_row, text=self.t("email_tpl_save"), width=150,
                 height=34, command=save_template).pack(side="left",
                                                        padx=(0, 8))
        ctk.CTkButton(tpl_btn_row, text=self.t("email_tpl_preview"),
                      width=150, height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color=self.accent["main"],
                      text_color=self.accent["main"],
                      hover_color=self.accent["hover"],
                      command=preview_template).pack(side="left", padx=(0, 8))
        ctk.CTkButton(tpl_btn_row, text=self.t("email_tpl_reset"),
                      width=170, height=34, corner_radius=self.radius,
                      fg_color="transparent", border_width=1,
                      border_color="#9CA3AF", text_color=self.muted(),
                      hover_color="#7F1D1D",
                      command=reset_template).pack(side="left")

        # --- 🌐 Premium-Webseite (PayPal-Kauf) ---
        ctk.CTkLabel(card, text=self.t("checkout_title"),
                     font=self.font(size=16, weight="bold")).pack(
                         anchor="w", padx=24, pady=(20, 0))
        ctk.CTkLabel(card, text=self.t("checkout_desc"),
                     text_color=self.muted(), font=self.font(size=11),
                     wraplength=560, justify="left").pack(anchor="w",
                                                          padx=24)

        def url_row(label_text, key):
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(anchor="w", padx=24, pady=(8, 0), fill="x")
            ctk.CTkLabel(r, text=label_text, width=160,
                         anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=360, height=34,
                             corner_radius=self.radius,
                             placeholder_text="https://...")
            if self.store.data["settings"].get(key):
                e.insert(0, self.store.data["settings"][key])
            e.pack(side="left", padx=(0, 8))

            def save():
                self.store.data["settings"][key] = e.get().strip()
                self.store.save()

            self.btn(r, text=self.t("apply"), width=100, height=34,
                     command=save).pack(side="left")

        url_row(self.t("backend_url_label"), "backend_url")
        url_row(self.t("checkout_url_label"), "checkout_url")
        ctk.CTkLabel(card, text="").pack(pady=(0, 8))

        # Nutzerliste
        ctk.CTkLabel(outer, text=self.t("registered_users"),
                     font=self.font(size=16, weight="bold")).pack(
                         anchor="w", padx=28, pady=(18, 6))
        self.user_list = ctk.CTkFrame(outer, corner_radius=self.radius,
                                      **self.card_kw(2))
        self.user_list.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh_user_list()

    def refresh_user_list(self):
        for w in self.user_list.winfo_children():
            w.destroy()
        for email, u in sorted(self.store.data["users"].items()):
            row = ctk.CTkFrame(self.user_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            icon = "👑" if email in OWNER_EMAILS else ("★" if self.store.is_premium(email) else "•")
            status = self.t("status_premium") if self.store.is_premium(email) else self.t("status_free")
            until = u.get("premium_until")
            extra = ""
            if until and until != "forever":
                extra = f"  ({until})"
            elif until == "forever":
                extra = "  (∞)"
            name = u.get("name", email.split("@")[0])
            ctk.CTkLabel(row, text=f"{icon}  {name}  ·  {email}",
                         anchor="w").pack(side="left", padx=8)
            if email not in OWNER_EMAILS:
                def make_delete(em=email):
                    def delete_user():
                        if self.confirm_dialog(
                                self.t("delete_user_title"),
                                self.t("delete_user_confirm") + f"\n{em}"):
                            self.store.delete_user(em)
                            self.refresh_user_list()
                    return delete_user

                ctk.CTkButton(row, text="🗑", width=30, height=24,
                              corner_radius=self.radius,
                              fg_color="transparent", border_width=1,
                              border_color="#F87171", text_color="#F87171",
                              hover_color="#7F1D1D",
                              command=make_delete()).pack(side="right",
                                                          padx=(4, 8))
            ctk.CTkLabel(row, text=status + extra,
                         text_color="#FBBF24" if self.store.is_premium(email) else self.muted()
                         ).pack(side="right", padx=8)

        # Codes-Liste
        codes = self.store.data.get("codes", {})
        if codes:
            ctk.CTkLabel(self.user_list, text="🎁 " + self.t("codes_list"),
                         font=self.font(size=14, weight="bold")).pack(
                             anchor="w", padx=8, pady=(14, 4))
            for code, c in sorted(codes.items()):
                row = ctk.CTkFrame(self.user_list, fg_color="transparent")
                row.pack(fill="x", pady=1)
                dur = "∞" if c["days"] == "forever" else f"{c['days']} {self.t('days_short')}"
                if c.get("used_by"):
                    status = f"✓ {self.t('code_used_by')} {c['used_by']}"
                    col = "#9CA3AF"
                else:
                    status = "● " + self.t("code_unused")
                    col = "#34D399"
                ctk.CTkLabel(row, text=f"{code}  ({dur})",
                             anchor="w").pack(side="left", padx=8)
                ctk.CTkLabel(row, text=status, text_color=col).pack(
                    side="right", padx=8)


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception:
        import traceback
        err = traceback.format_exc()
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(os.path.join(APP_DIR, "error.log"), "w",
                      encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror(APP_NAME,
                         "Fehler beim Start / Error on startup:\n\n"
                         + err[-1200:])
        except Exception:
            print(err)
