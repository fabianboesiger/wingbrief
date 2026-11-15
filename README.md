# wingbrief

Prognose-Check für Gleitschirm- und Deltapiloten nach der
[SHV-Meteo-Entscheidungsstrategie V10](https://www.shv-fsvl.ch/fileadmin/files/redakteure/Allgemein/Sicherheit/Sicherheit/Entscheidungsstrategie_Meteo_V10.pdf),
Zeile **Planung**. Die Seite zeigt für heute und die nächsten 4 Tage, je Morgen, Mittag und Nachmittag, welche
SHV-Alarmzeichen und günstigen Zeichen die Prognose zeigt, pro Region und pro Tal. Jeder Check ist anklickbar und
zeigt die SHV-Anforderung, die Regel, die Schwellen mit Quelle und die verglichenen Daten.

> Entscheidungshilfe für die Planung. Sie ersetzt die Beurteilung bei Anreise und vor Ort nicht.
> «Keine Alarmzeichen» ist keine Freigabe.

Quelle der Daten: MeteoSchweiz (Open Government Data).

## Wie es funktioniert

```
GitHub Actions (stündlich, neuer Lauf alle 6 h)
  STAC data.geo.admin.ch ──► ICON-CH2-EPS (Range-Requests auf die unteren 45 Modellflächen)
                         ──► Lokalprognose MeteoSchweiz (Punkte, statistisch verbessert)
  config/climatology.json ─► SwissMetNet-Perzentile («gewohnt»)
        │
        ▼
  Checks (config/checks.yaml) ─► Tag × Abschnitt ─► Ampel je Phänomen ─► Verkettung
        │
        ▼
  public/data/*.json + site/ ──► GitHub Pages        Archiv je Lauf ──► Branch «data»
```

- **Regionen und Täler** (`config/units.yaml`): SHV definiert keine Regionen. Fronten, Wärmegewitter/Luftschichtung
  und überregionaler Wind werden pro Region geprüft (11 Regionen), Regiowind und Föhn pro Tal (20 Täler) mit Talseite,
  Pass, Kretenhöhe und Hinweisen aus der SHV-Karte «Alpines Pumpen».
- **Ampel** (SHV-Logik): *Alarmzeichen*, wenn ein automatischer Alarm-Check zutrifft; *keine Alarmzeichen*, wenn alle
  günstigen Zeichen erfüllt sind; sonst *Achtung*. Tag 3–5: Ensemble (21 Members), Alarm ab 30 %, ok erst ab 80 %,
  sonst *unsicher*. Näherungen heben höchstens auf *Achtung*, Rahmenbedingungen (Jahreszeit, Gelände) lösen allein
  nichts aus.
- **Verkettung**: Anzahl Phänomene mit Alarmzeichen.
- **Anreise und Vor Ort**: als statische Checkliste aus dem Plakat (im Info-Panel); diese Phasen brauchen Messungen und Beobachtungen.
- **Seite** (`site/`): erster Bildschirm nur Tages-Tabs, Ampelkarte und Legende. Ein Gebiet antippen öffnet ein Panel
  mit Morgen/Mittag/Nachmittag und den fünf Phänomenen; weiter zu Begründung, Checks und Check-Detail mit Diagramm.

## Check-Katalog

| ID | Phänomen | SHV-Checkpunkt (Planung) | Daten | Quelle der Schwelle |
|---|---|---|---|---|
| F1 | Fronten | Textprognose | selbst prüfen | – |
| F2 | Fronten | Niederschlagsprognose: organisierter Niederschlag zieht her | ICON TOT_PREC, Ensemble | eigener Vorschlag |
| F3 | Fronten | Bodenwetterkarte: Fronten, Westwindlage | ICON Wind 3000 m, Druck | eigener Vorschlag |
| F4 | Fronten | Konvergenzlinien, Kurzwellentröge | selbst prüfen (geplant) | – |
| F5 | Fronten | Schauer-/Gewittersymbole | ICON LPI, Niederschlag | – |
| F6 | Fronten | Kalte Luft zieht heran | ICON T 1500 m | eigener Vorschlag |
| FG | Fronten | günstig: Hochdrucklage, stabil, wenig Wind | ICON, Ensemble | SHV (< 15 km/h) |
| W1 | Gewitter | Textprognose | selbst prüfen | – |
| W2 | Gewitter | flache Tiefdrucklage | ICON Druck, Wind | eigener Vorschlag |
| W3 | Gewitter | fleckiges Niederschlagsmuster | ICON TOT_PREC | eigener Vorschlag |
| W4 | Gewitter | «sehr gute Thermik» | Näherung CAPE | eigener Vorschlag |
| W5 | Gewitter | Theta-E 850 hPa > 60 °C | ICON T, QV, P | SHV |
| W6 | Gewitter | Labilität ≥ 0.8 °C/100 m, absinkende Inversion | ICON T-Profil | SHV / eigener Vorschlag |
| W7 | Gewitter | Prévitemps | selbst prüfen | – |
| W8 | Gewitter | starke Subsidenz | ICON Druck | eigener Vorschlag |
| WG | Gewitter | günstig: trocken, Inversion, trockene Luft | ICON | eigener Vorschlag |
| R1 | Regiowind | Textprognose | selbst prüfen | – |
| R2 | Regiowind | April–Oktober, nachmittags | Kalender (Rahmenbedingung) | SHV |
| R3 | Regiowind | Topographie | Talmerkmale (Rahmenbedingung) | – |
| R4 | Regiowind | Karte Alpines Pumpen | Talmerkmale (Rahmenbedingung) | SHV-Karte |
| R5 | Regiowind | Oberflächen schneefrei, trocken | ICON SNOWC, Niederschlag | eigener Vorschlag |
| R6 | Regiowind | Talwind am Vortag stark | Lokalprognose + Klimatologie | eigener Vorschlag |
| R7 | Regiowind | Wind 800 m ü. G. verstärkt Talwind | ICON | eigener Vorschlag |
| R8 | Regiowind | weniger Erwärmung als erwartet | Lokalprognose + Klimatologie | eigener Vorschlag |
| R9 | Regiowind | verstärkte Talwinde (10 m) | Lokalprognose + Klimatologie | eigener Vorschlag |
| R10 | Regiowind | Inversion unter Kretenhöhe | ICON T-Profil | eigener Vorschlag |
| RG | Regiowind | günstig: Nov.–März, Schnee, nasse Böden | Kalender, ICON | SHV / eigener Vorschlag |
| U1 | Wind | Textprognose | selbst prüfen | – |
| U2 | Wind | Wind 4000/3000/2000/1500 m ü. G. zu stark | ICON | eigener Vorschlag |
| U3 | Wind | Lokalprognose bodennah zu stark | Lokalprognose | eigener Vorschlag |
| U4 | Wind | kanalisierende Geländeformen | Regionsmerkmal (Rahmenbedingung) | – |
| U5 | Wind | West-Ost-Druck > 2 hPa, zunehmend | ICON Druck, Ensemble | SHV |
| UG | Wind | günstig: Hochdrucklage, < 15 km/h | ICON | SHV |
| O1 | Föhn | Textprognose | selbst prüfen | – |
| O2 | Föhn | Wind 2000 m ü. M., 800 m ü. G.: Föhnkanäle | ICON | eigener Vorschlag |
| O3 | Föhn | Höhenwind rechtwinklig zum Alpenkamm | ICON | eigener Vorschlag |
| O4 | Föhn | Druckdifferenz N-S ausgeprägt/zunehmend | ICON Druck, Ensemble | DHV (3/4 hPa) |
| O5 | Föhn | Labilisierung Frühling/Sommer | Kalender, ICON (Rahmenbedingung) | eigener Vorschlag |
| O6 | Föhn | Tal beginnt an einem Pass am Alpenhauptkamm | Talmerkmal (Rahmenbedingung) | SHV |
| O7 | Föhn | Luv auf Passhöhe 1–2 °C kühler | ICON T beidseits des Passes | SHV |
| OG | Föhn | günstig: luvseitig, keine T-Differenz | ICON | eigener Vorschlag |

Wortlaut, Regeln und Schwellen stehen in [`config/checks.yaml`](config/checks.yaml).

## Lokal ausführen

```bash
python -m venv .venv && . .venv/bin/activate
```

```bash
pip install -e ".[dev]"
```

```bash
pytest -q
```

```bash
python -m wingbrief.main plan --quick --no-ensemble
```

```bash
cd public && python -m http.server 8000
```

`--quick` lädt weniger Zeitschritte (ca. 2 GB statt ca. 5 GB). Der Gitter-Cache liegt in `cache/`.
Die Klimatologie wird mit `python -m wingbrief.main climatology` neu berechnet.

## Auf GitHub Pages betreiben

1. Repository öffentlich lassen (Actions-Minuten für Standard-Runner sind dann frei).
2. *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
3. Workflow «Prognose» einmal manuell starten. Er legt den Branch `data` an (Archiv je Lauf, `state.json`,
   letzte Ausgabe) und veröffentlicht die Seite.

Der Workflow läuft stündlich um :17 und rechnet nur, wenn ein neuer ICON-CH2-Lauf vollständig publiziert ist
(ca. 2.5 h nach Laufstart). Jeder neue Lauf erzeugt einen Commit im Branch `data`; das hält den geplanten Workflow
aktiv. Die Seite warnt, wenn die Daten älter als 6 h sind.

## Grenzen

- Schwellen ohne SHV-Zahl sind eigene Vorschläge oder vom DHV. Sie werden mit dem Archiv kalibriert.
- Höhenwind und -temperatur kommen aus dem Kontrolllauf; das Ensemble wird für Druck und Niederschlag ausgewertet
  (die Mehrflächen-Dateien des Ensembles sind ca. 900 MB pro Zeitschritt).
- ICON-CH1 (1 km) für heute und morgen ist vorbereitet, aber noch nicht eingebunden.
- Textprognose, Prévitemps, Bodenwetterkarte und Segelflugprognose sind keine offenen Daten: «selbst prüfen».
- Startplatz, Landeplatz, Gelände und Mensch sind nicht Teil der Bewertung.

## Lizenz und Quellen

- Daten: MeteoSchweiz, Open Government Data. Quellenangabe «Quelle: MeteoSchweiz».
- Kriterien: SHV/FSVL, Plakat «Meteo-Entscheidungsstrategie» V10, und SHV-Karte «Alpines Pumpen».
- Schweizer Umriss: Natural Earth (gemeinfrei) über world-atlas 2.0.2.
