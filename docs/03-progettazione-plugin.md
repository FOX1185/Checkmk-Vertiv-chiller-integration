# Fase 4 – Progettazione del plugin (approvata, implementata)

**Target:** Checkmk Community 2.5.0p12. API verificate sul tag `v2.5.0p12` del sorgente Checkmk:
`cmk.agent_based.v2`, `cmk.rulesets.v1`, `cmk.graphing.v1`, plug-in in `cmk_addons.plugins`.

## 1. Struttura

```
~/local/lib/python3/cmk_addons/plugins/vertiv_unity/
├── agent_based/vertiv_unity.py   # sezione SNMP + check plugin
├── rulesets/vertiv_unity.py      # regole: soglie, mappe di stato, eventi, discovery
└── graphing/vertiv_unity.py      # metriche non presenti in Checkmk
```

Distribuzione come pacchetto MKP (installabile da riga di comando con `mkp`).

## 2. Detection

```
sysObjectID inizia con .1.3.6.1.4.1.476.1.42
E esiste .1.3.6.1.4.1.476.1.42.3.9.10.0   (lgpFlexibleTableCount)
```

Indipendente da modello e firmware: riconosce qualunque scheda Unity che espone la tabella Flexible.
Il modello compare nei dettagli (`lgpAgentDeviceId`, `System Model Number`).

## 3. Dati letti (una sola sezione SNMP)

| Albero | Base | Colonne | Scopo |
|---|---|---|---|
| Parametri | `…3.9.{20,30}.1.<col>.1.2.1` | etichetta, valore, unità, int, uint, decimali, tipo, accesso, unità enum | servizi parametro |
| Eventi unità | `…3.9.20.1.<col>.1.2.100` | etichetta, valore | servizio eventi |
| Eventi modulo sensori | `…3.9.20.1.<col>.1.3.20.100` | etichetta, valore | servizio eventi |
| Identità | `…42.2.1` + `…42.2.4.2.1.2` | produttore, modello, FW, seriale, device ID | dettagli |

Il ramo `1.2.2` (°F) e la colonna descrizione `.30.1.70` (testo lungo, statico) **non vengono letti**:
si riduce il carico SNMP. Volume per ciclo: circa 55 righe × 9 colonne (CRV602) e 135 × 9 (CRV300),
in bulkwalk.

Chiave interna: `<data ID>.<istanza>`, con `4123` normalizzato a `4123.1` (FW 6.5 senza suffisso).

## 4. Validità di un valore

Un data point è **non valido** se:

1. valore stringa `Unavailable`, `No Support` o vuoto;
2. raw `2147483647` (int) o `4294967295` (uint);
3. tipo `int16` e raw `−32768`, oppure tipo `uint16` e raw `65535`;
4. numerico ma stringa non convertibile;
5. fuori dall'intervallo plausibile noto: per ora solo 4868 (mese 1–12) e 4869 (anno 2000–2100).

- **Discovery:** i data point non validi non diventano servizi.
- **Check:** se un servizio già scoperto diventa non valido → **UNKNOWN** con il motivo
  (es. "Valore non disponibile dalla scheda: Unavailable"), senza perfdata. Se il data point sparisce dalla
  tabella → Checkmk mostra "item not found" (UNKNOWN).

## 5. Servizi

Nome servizio: `Vertiv <etichetta>` più `<istanza>` se il data ID ha più istanze
(es. `Vertiv Supply Air Sensor Temperature 2`). I dettagli riportano data ID, tipo, accesso e unità.

### 5.1 `vertiv_unity_value` – numerici (int16/uint16/int32/uint32)

- Valore scalato e unità dalla scheda; perfdata sempre.
- Metrica scelta dall'unità:

| Unità scheda | Metrica | Origine |
|---|---|---|
| degC (4125) | `temp` | Checkmk |
| degF (4127) | `temp` (convertita in °C) | Checkmk |
| % RH (4132) | `humidity` | Checkmk |
| VAC (4100) | `voltage` | Checkmk |
| A AC (4106) | `current` | Checkmk |
| W (4114) / kW (4115) | `power` (in W) | Checkmk |
| degC delta (4126) | `vertiv_unity_temp_delta` | plugin |
| % (4124) | `vertiv_unity_percent` | plugin |
| h (4099) | `vertiv_unity_hours` | plugin |
| s / min (4097/4098) | `vertiv_unity_duration` (in s) | plugin |
| m³/h (4155) | `vertiv_unity_flow_m3h` | plugin |
| l/min (4158) | `vertiv_unity_flow_lpm` | plugin |
| Pa (4130) | `vertiv_unity_pressure_pa` | plugin |
| kWh (4117) | `vertiv_unity_energy_kwh` | plugin |
| nessuna / altre | `vertiv_unity_value` | plugin |

- **Soglie:** regola *"Vertiv Unity – parametri numerici"*, per host e per nome servizio (regex),
  con soglie superiori e inferiori WARN/CRIT. Nessuna soglia predefinita.
- Parametri in lettura-scrittura (set point, bande, soglie, contaore): stesso check, con l'opzione
  *"avvisa se il valore cambia rispetto alla discovery"* (predefinito: disattivata).

### 5.2 `vertiv_unity_state` – enum

- Mostra il testo restituito dalla scheda e il codice numerico.
- Mappe predefinite (da validare con l'esercizio):

| Data ID | OK | WARN | CRIT |
|---|---|---|---|
| 4123 System Status | Normal Operation | StartUp, Normal with Warning | Normal with Alarm, Abnormal Operation |
| 7528 System Operating State (CRV602) | Run, Standby | Display Off, Remote Off, Monitoring Off | Lockout |
| 4706 Unit Operating State (CRV300) | on, standby | off | — |
| 5143 System On/Off Control (CRV300) | on | off | — |
| 5673 / 5674 ATS Power Supply Status | OK | — | Not OK |
| tutti gli altri enum | qualunque valore | — | — |

- Regola *"Vertiv Unity – stati"*: per nome servizio, elenco `testo → stato` che sostituisce la mappa
  predefinita; opzione "avvisa se il valore cambia rispetto alla discovery" (utile per le modalità di
  controllo: 5012, 5047, 5052, 7505, 7516, …).
- Le coppie `… - Event Control` / `… - Event Type` **non** diventano servizi: alimentano il servizio eventi.

### 5.3 `vertiv_unity_text` – testo e data/ora

Servizio sempre OK che mostra il valore (System Model Number, Serial Number, Firmware Version,
PACC Firmware, System Name, System Date and Time). Nessun grafico.

### 5.4 `vertiv_unity_events` – un solo servizio *"Vertiv Events"*

- Legge tutti i data point evento dei rami `1.2.100` e `1.3.20.100`.
- Riepilogo: `Nessun evento attivo (40 monitorati)` oppure `2 eventi attivi: Clogged Air Filter [5118],
  Fan Issue 3 [4729.3]`.
- Stato di un evento attivo, in ordine di priorità:
  1. regola utente per codice evento (OK / WARN / CRIT / ignora);
  2. se la scheda espone `Event Control = disabled` → ignorato;
  3. se espone `Event Type`: Message → OK, Warning → WARN, Alarm → CRIT;
  4. predefinito: **CRIT**.
- Il servizio va a CRIT/WARN finché l'evento è attivo e torna OK quando la scheda lo riporta inattivo.
- Riga dettagli per ogni evento attivo: descrizione, codice, nome simbolico MIB (`lgpCondId…`).

## 6. Regole di discovery

Regola *"Vertiv Unity – discovery"* (per host):

- includere / escludere i numerici in lettura-scrittura (predefinito: inclusi);
- includere / escludere gli enum in lettura-scrittura (predefinito: inclusi);
- includere / escludere i testi (predefinito: inclusi);
- elenco di data ID da escludere (es. `5049, 5333`).

## 7. Numero di servizi atteso (dai walk)

| | CRV602 | CRV300 |
|---|---|---|
| numerici | 26 | 33 |
| enum (stati + modalità) | 10 | 23 |
| testi | 4 | 3 |
| eventi | 1 | 1 |
| **totale** | **≈ 41** | **≈ 60** |

## 8. Test previsti

- Test automatici (pytest) con i walk reali in `tests/snmpwalks/`: parsing, classificazione, sentinelle,
  mappe di stato, eventi.
- Varianti sintetiche dei walk: evento attivo, sensore che diventa `Unavailable`, raw 65535/−32768,
  °F nel ramo primario.
- Simulazione in Checkmk con `cmk --snmpwalk` già salvati (host in modalità simulazione) prima del
  collegamento alle unità reali.

## 9. Decisioni dell'utente e modifiche in implementazione

| Punto | Decisione |
|---|---|
| Parametri di configurazione | servizi (con grafico per i numerici) |
| Evento attivo senza severità nota | **WARN** |
| Mappe di stato | come proposte (§5.2), da rivedere dopo l'esercizio |
| Nome servizi | senza prefisso: `Return Air Temperature`; servizio eventi: `Events` |

Modifiche rispetto alla proposta:

- **Sezione identità non letta:** il plugin Checkmk `lgp_info` ("Liebert Info") mostra già produttore,
  modello, firmware e seriale della scheda.
- **Plugin `liebert_*` di Checkmk sostituiti** (`supersedes`): leggono singole righe della stessa tabella e
  creerebbero servizi duplicati.
- **Nome simbolico MIB degli eventi non mostrato:** etichetta e codice evento sono sufficienti ed evitano di
  incorporare 1450 nomi nel plugin.
- **Le soglie si esprimono nell'unità mostrata dal servizio** (°C, %, h, m³/h, kW…); unica conversione:
  °F → °C, per uniformità con la metrica `temp`.
- **"Cambiato rispetto alla discovery"** è disattivato di default e si attiva per servizio con le regole.
