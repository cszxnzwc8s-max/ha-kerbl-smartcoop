# Kerbl SmartCoop HAS – Kerbl SmartCoop für Home Assistant

Inoffizielle Home-Assistant-Integration für das **Kerbl SmartCoop** Hühnerstall-System
(Steuerung mit WLAN-Connectivity-Modul). Sie liest die Daten aus der Kerbl-Welt-Cloud –
dieselbe, die auch die Kerbl-Welt-App benutzt.

> *Unofficial Home Assistant integration for the Kerbl SmartCoop chicken-coop controller
> (with Wi-Fi connectivity module). Reads data from the Kerbl cloud used by the official app.
> Entity names are German.*

**Nicht mit Kerbl verbunden.** Die Kerbl-Schnittstelle ist nicht öffentlich dokumentiert
und kann sich jederzeit ändern. Nutzung auf eigene Verantwortung.

## Was die Integration liefert

**Status**
- Tür als Tor/Tür-Entität: offen / öffnet / schließt / geschlossen – mit Verlauf und Aktivität jeder Fahrt
- Lüfter läuft (abgeleitet aus Intervall-, Dauerlauf- und Nacht-Logik)
- Licht an/aus
- Letzter Fehlercode als Klartext, mit den letzten 10 Meldungen als Attribut

**Messwerte**
- Lufttemperatur, Wassertemperatur, Helligkeit (Sensor im Stall, %), Akkuspannung

**Einstellbar** (wie in der App, Werte gehen ans Modul, sobald es online ist)
- Tür: Öffnungshelligkeit (10–60 %), Schließhelligkeit (1–15 %), Schließverzögerung (0–60 min)
- Lüfter: Leistung, Intervall, Laufzeit, Aus unter / Dauerbetrieb über (°C), Intervall auch nachts (Schalter)
- Fütterung: Anzahl Tiere, Menge pro Tier
- Strom: Energiesparmodus unter (V)

**Einstellungen (nur lesend)**
- Tür: Öffnungszeiten, Typ
- Lüfter: Leistung, Intervall, Laufzeit, Temperaturschwellen
- Fütterung: Start/Ende, Intervall, Anzahl Tiere, Menge, Behälterstatus
- Licht und Stromversorgung: Modus, Dunkelzeit, Schaltzeiten, Energiesparschwelle
- „Einstellungen synchron“ (ob das Modul die Werte aus der App übernommen hat)
- Rohdaten-Sensor mit dem kompletten Datensatz als Attribute (zur Fehlersuche)

Das Kerbl-Demo-Gerät, das die Cloud bei jedem Konto mitliefert, wird ausgeblendet.

Änderungen kommen live über dieselbe Verbindung wie in der Kerbl-App (Sensor „Live-Verbindung“).
Zusätzlich wird jede Minute abgefragt, falls die Live-Verbindung abreißt.

## Installation über HACS

1. HACS → Menü (⋮) → **Benutzerdefinierte Repositories**
2. URL `https://github.com/cszxnzwc8s-max/ha-kerbl-smartcoop`, Typ **Integration**
3. „Kerbl SmartCoop HAS“ herunterladen und Home Assistant neu starten
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Kerbl SmartCoop HAS**
5. Mit dem Kerbl-Welt-Konto (E-Mail und Passwort aus der App) anmelden

## Bekannte Codes

**Fehler/Meldungen** (`errorReason`, bestätigt über die „Meldungen“-Seite der App)

| Code | Bedeutung |
|---|---|
| 0 | Kein Fehler |
| 8 | Batterie schwach |
| 16 | Wasserheizung aktiv (Info bei Frost) |
| 32 | Wasser leer |
| 512 | Klappenstörung |
| 2048 | Fremdlichtstörung (z. B. Taschenlampe im Stall) |
| 4096 | Uhrzeit Fehler (Moduluhr nach Stromausfall verloren, korrigiert sich per Internet selbst) |

**Tür** (`door.state`): 79 = offen, 67 = geschlossen, 111 = öffnet, 99 = schließt, 63 = bei Klappenstörung stehengeblieben (wird als „offen“, also nicht ganz zu, angezeigt). Bei einer Störung trägt die Tür zusätzlich das Attribut `stoerung` mit dem Wortlaut der Kerbl-App (z. B. „Klappenstörung“).

## Grenzen

- Tür auf/zu, Licht und weitere Einstellungen lassen sich noch nicht steuern.
- Neue Einstellungen erreichen den Stall erst, wenn das Modul online ist.
- Die Tür-Steuerung der Kerbl-Cloud ist ein Umschalter ohne Positionsrückmeldung.
- „Lüfter läuft“ ist abgeleitet, nicht direkt gemessen.

## Hinweis

Diese Integration nutzt die eigene Domain `kerbl_smartcoop_ha` und kann daher neben
anderen Kerbl-Projekten installiert sein, z. B. [code723/kerbl-smartcoop](https://github.com/code723/kerbl-smartcoop)
(Domain `kerbl_smartcoop`). Dasselbe Kerbl-Konto sollte aber nur in einer davon eingerichtet sein.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
