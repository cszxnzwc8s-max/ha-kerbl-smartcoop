# Kerbl SmartCoop für Home Assistant

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
- Tür offen/geschlossen (Binary Sensor), inkl. Bewegungsrichtung „öffnet“/„schließt“ als Attribut
- Lüfter läuft (abgeleitet aus Intervall-, Dauerlauf- und Nacht-Logik)
- Licht an/aus
- Letzter Fehlercode als Klartext, mit den letzten 10 Meldungen als Attribut

**Messwerte**
- Lufttemperatur, Wassertemperatur, Helligkeit (Sensor im Stall, %), Akkuspannung

**Einstellungen (nur lesend)**
- Tür: Öffnungs-/Schließhelligkeit, Öffnungszeiten, Schließverzögerung, Typ
- Lüfter: Leistung, Intervall, Laufzeit, Temperaturschwellen
- Fütterung: Start/Ende, Intervall, Anzahl Tiere, Menge, Behälterstatus
- Licht und Stromversorgung: Modus, Dunkelzeit, Schaltzeiten, Energiesparschwelle
- „Einstellungen synchron“ (ob das Modul die Werte aus der App übernommen hat)
- Rohdaten-Sensor mit dem kompletten Datensatz als Attribute (zur Fehlersuche)

Das Kerbl-Demo-Gerät, das die Cloud bei jedem Konto mitliefert, wird ausgeblendet.

Daten werden jede Minute abgefragt. Die Cloud aktualisiert die Helligkeit etwa alle 10 Minuten.

## Installation über HACS

1. HACS → Menü (⋮) → **Benutzerdefinierte Repositories**
2. URL `https://github.com/cszxnzwc8s-max/ha-kerbl-smartcoop`, Typ **Integration**
3. „Kerbl SmartCoop“ herunterladen und Home Assistant neu starten
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Kerbl SmartCoop**
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

**Tür** (`door.state`): 79 = offen, 67 = geschlossen, 111 = öffnet, 99 = schließt.

## Grenzen

- Steuern (Tür, Licht, Einstellungen) ist noch nicht enthalten.
- Die Tür-Steuerung der Kerbl-Cloud ist ein Umschalter ohne Positionsrückmeldung.
- „Lüfter läuft“ ist abgeleitet, nicht direkt gemessen.

## Hinweis

Es gibt ein älteres, unabhängiges Projekt mit derselben Integrations-Domain
(`kerbl_smartcoop`): [code723/kerbl-smartcoop](https://github.com/code723/kerbl-smartcoop) (MIT).
Beide nicht gleichzeitig installieren.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
