# Fase 1–2 – Analisi dei file di mapping Unity e delle MIB Liebert

**Data:** 23 novembre 2026 · **Stato:** verifica documentale, nessun codice di plugin scritto.

## 0. Fonti analizzate

| File (in `docs/mapping/`) | File originale caricato | Modello | Righe utili |
|---|---|---|---|
| `CRV602_SNMP_Parameters.txt` | `SNMP_Parameters_1.txt` | CRV602 (FW 8.4.7) | 159 OID |
| `CRV602_SNMP_Events.txt` | `SNMP_Events_1.txt` | CRV602 | 61 righe / 40 OID distinti |
| `CRV300_SNMP_Parameters.txt` | `SNMP_Parameters.txt` | CRV300 (FW 6.5.0) | 435 OID |
| `CRV300_SNMP_Events.txt` | `SNMP_Events.txt` | CRV300 | 91 OID |

L'attribuzione file → modello è **dedotta**, non dichiarata nei file: i file `_1` contengono i data ID
8077/8078/7505/7516 e i suffissi `.1` del walk CRV602; gli altri contengono 4706, 5668, 5672 (ATS) presenti
solo nel walk CRV300. Da confermare scaricando di nuovo i file dalle due schede.

MIB usate per la verifica (copie Vertiv pubblicate nel repository LibreNMS, `mibs/liebert/`):

| MIB | Revisione |
|---|---|
| LIEBERT-GP-FLEXIBLE-MIB | 2013-05-14 (unica revisione) |
| LIEBERT-GP-FLEXIBLE-CONDITIONS-MIB | 2024-06-07, "GDD Version 8764.1" – 1280 `lgpCondId*` |
| LIEBERT-GP-CONDITIONS-MIB | 2013-02-12 |
| LIEBERT-GP-ENVIRONMENTAL-MIB, -AGENT-MIB, -SYSTEM-MIB, -REGISTRATION-MIB | varie |

**Limite:** il pacchetto ufficiale *Rev 26 (ottobre 2025)* non è stato scaricato: l'host `www.vertiv.com`
è bloccato dalla policy di rete di questo ambiente. Le MIB usate sono precedenti; la struttura delle tabelle
(Flexible MIB, ferma al 2013) non cambia, ma la lista dei `lgpCondId` potrebbe essere più ampia in Rev 26.
Va ripetuto il controllo con `tools/check_mapping_vs_mib.py` sul pacchetto Rev 26 appena disponibile.

---

## 1. Risultato principale: la tabella è auto-descrittiva

Gli OID `…42.3.9.20.1.20.<indice>` non sono parametri "proprietari" sparsi, ma **una colonna di una
tabella standard Liebert**, `lgpFlexibleBasicTable` (LIEBERT-GP-FLEXIBLE-MIB, `lgpFlexible = …42.3.9`).

L'indice di riga è `IMPLIED OBJECT IDENTIFIER` (`lgpFlexibleEntryIndex`): tutto ciò che segue la colonna,
ad es. `1.2.1.4123.1`, è *un unico indice*. La MIB dice che ogni indice è associato a un **data point ID
univoco e permanente**.

### Colonne disponibili

| OID colonna | Nome | Tipo SNMP | Contenuto |
|---|---|---|---|
| `.3.9.20.1.10` | lgpFlexibleEntryDataLabel | DisplayString | etichetta breve |
| `.3.9.20.1.20` | lgpFlexibleEntryValue | DisplayString | **valore già scalato, come stringa** (anche enum e testo) |
| `.3.9.20.1.30` | lgpFlexibleEntryUnitsOfMeasure | DisplayString | unità (vuota se assente) |
| `.3.9.30.1.10` | lgpFlexibleEntryIntegerValue | Integer32 | valore grezzo per int16/int32 |
| `.3.9.30.1.20` | lgpFlexibleEntryUnsignedIntegerValue | Unsigned32 | valore grezzo per uint16/uint32/**enum** |
| `.3.9.30.1.30` | lgpFlexibleEntryDecimalPosition | Unsigned32 | valore reale = grezzo / 10^n |
| `.3.9.30.1.40` | lgpFlexibleEntryDataType | INTEGER | 0 n/s, 1 int16, 2 uint16, 3 int32, 4 uint32, **5 text, 6 enum, 7 event16, 8 event32**, 9 ipv4, 10 time32 |
| `.3.9.30.1.50` | lgpFlexibleEntryAccessibility | INTEGER | 1 readonly, 2 writeonly, 3 readwrite |
| `.3.9.30.1.60` | lgpFlexibleEntryUnitsOfMeasureEnum | INTEGER | 4124 percent, 4125 degC, 4126 degCDelta, 4127 degF, 4132 RH, 4099 hours, 4158 lpm, 4155 m³/h, 4115 kW, 4117 kWh, 4130 Pa, … |
| `.3.9.30.1.70` | lgpFlexibleEntryDataDescription | DisplayString | descrizione lunga (quella troncata a 255 caratteri) |

Conseguenze per la progettazione:

- **Tipo, unità, scala e accessibilità si leggono dalla scheda**, riga per riga. Non serve una lista di OID
  per modello: la discovery può classificare ogni riga con `DataType` + `UnitsOfMeasureEnum`.
  Questo soddisfa il requisito "discovery dinamica" e "non interpretare ogni numero come misura".
- `Accessibility = readwrite` distingue i **parametri di configurazione** (set point, bande, soglie,
  abilitazioni) dalle **misure** (readonly). Utile per decidere cosa graficare e cosa no.
- `DataType = event16/event32` identifica i data point evento.
- Le colonne della tabella di handover erano corrette (`.30.1.70` descrizioni, `.20.1.10` etichette); vanno
  aggiunte `.20.1.30`, `.30.1.20/30/40/50/60`.

> Da verificare con walk reali (sezione 6): la MIB descrive tutte queste colonne, ma non garantisce che il
> firmware Unity le popoli tutte. È il punto più importante della Fase 2.

---

## 2. Struttura dell'indice osservata

| Prefisso indice | CRV602 | CRV300 | Interpretazione |
|---|---|---|---|
| `1.2.1.<id>[.<istanza>]` | 42 ID / 54 righe | 106 ID / 133 righe | parametri del condizionatore, **unità metriche** |
| `1.2.2.<id>[.<istanza>]` | 12 ID / 24 righe | 18 ID / 27 righe | **gli stessi parametri in unità alternative (°F)** |
| `1.2.100.<id>[.<istanza>]` | 38 ID / 59 righe | 78 ID / 87 righe | data point **evento** (Active/Inactive) |
| `1.3.20.1.<id>` | 6109–6118, 4123, 4240, 4553 | idem | secondo "dispositivo" (ordine slot sensori della scheda) |
| `1.3.20.100.<id>` | 5423, 6119 | idem | eventi del secondo dispositivo |

Evidenze:

1. **`1.2.2` non è un ramo di descrizioni alternative** (ipotesi del documento di passaggio): contiene
   *soltanto* data ID di temperatura o di delta-temperatura (4291, 5002, 5007, 5009, 5059, 5331, 5333, 6311,
   6312, 8077, 8078, 8082 su CRV602; in più 4624, 4625, 5004–5022, 5048, 5668 su CRV300). Nessuna umidità,
   ora, percentuale o enum. È quindi la vista in °F degli stessi valori.
   → **La discovery deve usare solo `1.2.1`** (verificare con la colonna unità che `1.2.1` sia degC).
2. Il secondo elemento dell'indice (`2` / `3`) sembra identificare il dispositivo gestito; il terzo il gruppo
   (1 = dati, 2 = unità alternative, 100 = eventi, 20 = gruppo dati del dispositivo 3). Ipotesi coerente con
   entrambi i file ma **non documentata nella MIB**: il plugin deve trattare l'indice come opaco e usare
   come chiave del servizio `<data ID>[.<istanza>]` all'interno di `1.2.1`.
3. **Differenza di firmware sul suffisso di istanza:**
   - FW 8.4.7 (CRV602): *tutti* i data point hanno l'istanza (`4123.1`, `5059.3`).
   - FW 6.5.0 (CRV300): gli scalari **non** hanno suffisso (`4123`), solo i data point multipli lo hanno
     (`5057.1…10`, `5058.x`, `5059.x`, `5060.x`).
   → Il parser deve accettare entrambe le forme e normalizzare `4123` ≡ `4123.1` per avere item stabili.
4. Il data ID è la chiave semantica comune ai due modelli e coincide con il numero del `lgpCondId` per
   gli eventi (es. data point `1.2.100.5118` ↔ `lgpCondId5118CloggedAirFilter`).

---

## 3. Verifica file di mapping ↔ MIB

Script: `tools/check_mapping_vs_mib.py <dir_mib> <dir_file_mapping>`.

| Verifica | CRV602 | CRV300 |
|---|---|---|
| OID eventi presenti nella MIB con lo **stesso nome** | 40/40 | 91/91 |
| OID "legacy" (non Flexible) nei Parameters con nome uguale alla MIB | 7/7 | 173/173 |
| Data ID evento `1.2.100.x` con un `lgpCondIdx` definito nella MIB | 38/38 | 78/78 |

Nessuna discrepanza di nome. I file di mapping sono quindi affidabili come dizionario nomi/enum,
ma **non riportano tipo, unità e scala**: quelle informazioni vanno prese dalla tabella estesa (sez. 1).

### 3.1 Oggetti "legacy" (fuori dalla tabella Flexible)

| Gruppo | CRV602 | CRV300 |
|---|---|---|
| `lgpAgentIdent*` (produttore, modello, FW, seriale, part number) | ✔ | ✔ |
| `lgpAgentReboot` (scrivibile: **da non toccare**) | ✔ | ✔ |
| `lgpSysState` | ✔ | ✔ |
| `lgpConditionControlTable` (`3.2.4.20`, 16 righe) | — | ✔ |
| `lgpEnvTemperature*/Humidity*/State*/Config*/RemoteSensor*` (`3.4.x`) | — | ✔ |
| `lgpSysControlOperationOnOff`, `lgpSysMaintenance*` | — | ✔ |

Il CRV602 (FW 8.4.7) **non espone più** la ENVIRONMENTAL-MIB classica. Il plugin non deve basarsi su di
essa: l'unica base comune è la tabella Flexible. I `lgpAgentIdent*` servono per inventario e per
l'etichetta del modello.

### 3.2 Eventi: due alberi di OID diversi

| Albero | OID | CRV602 | CRV300 |
|---|---|---|---|
| `lgpConditionsWellKnown` (legacy, nomi `lgpCondition…`) | `…42.3.2.1.x` | 0 | 78 |
| `lgpFlexConditionsWellKnown` (`lgpCondId<nnnn>…`) | `…42.3.2.7.1.<id>` | 40 | 13 |

Il CRV300 (FW 6.5) usa prevalentemente gli identificatori legacy, il CRV602 solo i nuovi. Questi OID
sono i valori che compaiono:

- nelle trap, e
- nella colonna `lgpConditionDescr` della **`lgpConditionsTable`** (`…42.3.2.3.1`), la tabella delle
  condizioni attive.

`lgpConditionsTable` (LIEBERT-GP-CONDITIONS-MIB), indice `lgpConditionId`:

| Col. | Nome | Valori |
|---|---|---|
| 2 | lgpConditionDescr | OID → `lgpCondition…` / `lgpCondId…` |
| 3 | lgpConditionTime | sysUpTime all'attivazione |
| 10 | lgpConditionType | 2 message, 4 warning, 6 alarm, 8 fault |
| 12 | lgpConditionCurrentState | 1 active, 2 inactive |
| 14 | lgpConditionSeverity | 0 n/a, 3 minor, 6 major, 9 critical |
| 18 / 19 | Acknowledged / AckReq | |
| `…3.2.2.0` | lgpConditionsPresent | numero di righe |

La tabella contiene **solo le condizioni presenti** (vuota a regime). È la fonte naturale per la severità
richiesta al punto 9.4.

**Proposta per il servizio eventi** (da confermare con i walk):

1. *Fonte primaria:* data point Flexible `1.2.100.*` – hanno già etichetta (`.20.1.10`) e valore testuale
   (`Active Event` / `Inactive Event`), sono indipendenti dal firmware e il data ID coincide con il codice
   evento.
2. *Arricchimento:* `lgpConditionsTable` per tipo/severità/tempo di attivazione; la descrizione si risolve
   con una mappa OID → nome generata dalle MIB (entrambi gli alberi), con fallback sull'OID grezzo.
3. Sul CRV300 esistono anche i parametri `…Event Type` (0 Message, 1 Warning, 2 Alarm) e
   `…Event Control` (enabled/disabled) per 17 eventi configurabili: utili per non allarmare su eventi
   disabilitati, ma non disponibili sul CRV602.

---

## 4. Confronto CRV300 ↔ CRV602

Tabella completa per data ID: appendice A. Riepilogo:

| | CRV602 | CRV300 | Comuni |
|---|---|---|---|
| Data ID parametri (`1.2.1`) | 42 | 106 | **12** (4123, 4240, 4291, 4553, 5002, 5007, 5009, 5028, 5029, 5030, 5059, 5077) |
| Data ID evento (`1.2.100`) | 38 | 78 | **13** (4720, 4723, 5015, 5019, 5023, 5026, 5034, 5036, 5043, 5106, 5108, 5118, 5147) |

La sovrapposizione è bassa: **conferma che una lista fissa di OID non è praticabile** e che la discovery
deve essere guidata dai metadati della tabella.

### 4.1 Stesso nome, semantica diversa (rischio di errata interpretazione)

| Etichetta | CRV300 | CRV602 |
|---|---|---|
| Fan Control Mode | **5047**: 0 Internal (Auto), 1 External (Manual) | **7516**: 0–10, sensore di controllo (ReturnAirAverageTemp … StaticPressure) |
| Supply/Return set point | 5008 Air Temperature Set Point (unico) | 5331 Supply SP + 5333 Return SP + 8082 Remote SP |
| Return Humidity | 5028 valido (63.0) | 5028 = 6553.5 (sentinella), valore reale in **8080.1** |
| Remote sensor | 5057 nome, 5058 funzione, 5059 temp, 5060 issue | solo 5059 temp (+ eventi 5597/5598/7495) |
| Stato macchina | 4706 Unit Operating State (off/on/standby), 5143 On/Off | 7528 System Operating State (Run/Standby/…/Lockout), 7536 Monitoring (16 on / 31 off) |

→ La chiave del servizio deve essere il **data ID**, non l'etichetta; le regole di stato vanno legate al
data ID (o meglio ancora alla coppia data ID + insieme di enum osservato).

### 4.2 Enum comuni e regole di stato candidate

| Data ID | Enum | Stato Checkmk proposto (da validare) |
|---|---|---|
| 4123 System Status | 1 Normal, 2 StartUp, 8 Normal with Warning, 16 Normal with Alarm, 32 Abnormal | 1→OK, 2→WARN, 8→WARN, 16→CRIT, 32→CRIT |
| 4553 Server Class | 1 UPS … 5 MONITOR | solo informativo (AIR atteso) |
| 4706 Unit Operating State | 0 off, 1 on, 2 standby | da decidere con l'esercizio (standby normale in teamwork?) |
| 7528 System Operating State | 0 Run … 5 Lockout | 0→OK, 1→OK/WARN, 3 Remote Off→WARN, 5 Lockout→CRIT (da validare) |
| 5673/5674 ATS PS status | 0 OK, 1 Not OK | 1→CRIT |
| 5382/5386/5387/5388 Stati componenti | 0 off, 1 on | informativo |
| 7505, 7516, 5012, 5052, 5013, 4707, 5047 | modalità/sensore di controllo | informativo; eventuale WARN su cambiamento rispetto alla discovery |
| `…Event Control` / `…Event Type` | configurazione | non come servizi, usati dal servizio eventi |

Le enum non sono nella MIB (la Flexible MIB non le definisce): la fonte sono i file di mapping, mentre la
scheda restituisce già il testo nella colonna valore. Il plugin può mostrare il testo e usare il codice
numerico (`.30.1.20`) per valutare lo stato.

---

## 5. Valori sentinella e non disponibili

| Osservato | Dove | Origine probabile | Regola |
|---|---|---|---|
| `6553.5` | CRV602 5028.1 | uint16 0xFFFF / 10 | escludere se raw uint16 = 65535 |
| `-32768` | CRV300 5668–5671 | int16 0x8000 | escludere se raw int16 = −32768 |
| `Unavailable` | CRV602 7527.1; CRV300 5059.x, 5079, 5081, 5900, 5901 | testo dell'agente | escludere |
| `No Support` | CRV602 8077.3, 8078.2 | testo dell'agente | escludere |
| stringa vuota | CRV300 5057.x (nomi sensori) | testo non configurato | escludere |

Da verificare: per uint32/int32 i valori corrispondenti (0xFFFFFFFF, 0x80000000) e se la colonna estesa
riporta gli stessi sentinella o un campo vuoto. Regola di discovery proposta: un data point viene scoperto
solo se *al momento della discovery* il valore è valido; un valore che diventa non valido dopo la discovery
produce UNKNOWN (non scompare silenziosamente).

---

## 6. Differenze rispetto al documento di passaggio

1. `1.2.2` = unità alternative (°F), non descrizioni alternative (sez. 2).
2. Il CRV602 espone nel file di mapping data ID **assenti dalla tabella del walk**: 4240, 4244, 4335, 4400,
   4553, 5030, 5386, 5387, 5388, 7528, 7536. Il walk andrebbe ripetuto per verificarne i valori.
3. Il CRV300 espone data ID **assenti dalla tabella del walk**: 4096–4101 (tensioni di ingresso),
   4113–4115 (correnti), 4868–4870 (manutenzione), 5005, 5006, 5007, 5031, 5060.x e 65 data point evento.
4. Etichette diverse tra walk e file di mapping per lo stesso ID (CRV300): 4291 "Inlet Air Temperature" vs
   "Return Air Temperature", 5002 "Outlet" vs "Supply", 4553 "System Classification" vs "Server Class".
   Probabilmente il walk riportava la descrizione (`.30.1.70`) o etichette localizzate. → Il nome del
   servizio va costruito in modo stabile (data ID + etichetta letta alla discovery), non sul testo.
5. Le 17 coppie `Event Control/Event Type` del CRV300 sono configurazione: nessun servizio dedicato.
6. Non sono necessari `SNMP_upsMibEvents.txt` / `SNMP_upsParams.txt`: riguardano UPS-MIB (RFC 1628) e le
   unità CRV dichiarano Server Class = AIR. Nessun OID UPS compare nei file analizzati.

---

## 7. Walk da eseguire (Fase 2, prima della progettazione definitiva)

Su entrambe le unità (e sul CRV25 quando disponibile), da `docker exec` nel container Checkmk:

```bash
H=<IP_UNITA>   # ripetere per ogni unità
for c in 3.9.20.1.10 3.9.20.1.20 3.9.20.1.30 3.9.30.1.10 3.9.30.1.20 3.9.30.1.30 3.9.30.1.40 3.9.30.1.50 3.9.30.1.60 3.9.30.1.70 3.9.10 3.2.2 3.2.3; do
  snmpwalk -v2c -c <community> -On -t 5 -r 1 $H 1.3.6.1.4.1.476.1.42.$c
done > walk_$H.txt 2>&1
```

Cosa verificare:

- che le colonne `.30.1.x` (tipo, scala, unità, accessibilità) siano popolate;
- che `1.2.1` sia in degC e `1.2.2` in degF;
- il comportamento raw dei sentinella (6553.5, −32768);
- `lgpFlexibleTableCount` (`3.9.10`) per stimare il costo di un walk completo;
- `lgpConditionsTable` con almeno una condizione attiva (es. disabilitare temporaneamente un sensore remoto
  o simulare il filtro intasato, se possibile in sicurezza) per vedere tipo/severità reali;
- tempi di risposta: la tabella Flexible su CRV300 ha ≥ 260 righe × 10 colonne.

**Da non eseguire:** nessun `snmpset`. `lgpAgentReboot` e le colonne `readwrite` (valori, set point) sono
scrivibili e la community attuale potrebbe avere accesso in scrittura: verificare che sia read-only.

---

## 8. Stato delle attività

- [x] Analizzare `SNMP_Parameters.txt` e `SNMP_Events.txt` (entrambi i modelli)
- [x] Confronto nomi/OID con MIB Liebert (Flexible, Conditions, Flexible-Conditions, Env, Agent, System)
- [x] Identificazione struttura indice, rami `1.2.1` / `1.2.2` / `1.2.100` / `1.3.20`
- [x] Confronto CRV300 ↔ CRV602 per data ID
- [x] Verifica necessità file UPS (non necessari)
- [ ] Acquisire pacchetto MIB **Rev 26** e rieseguire `tools/check_mapping_vs_mib.py`
- [ ] Walk delle colonne estese e della `lgpConditionsTable` (sez. 7)
- [ ] CRV25: SNMP, file di mapping, walk
- [ ] Fase 4: regole di classificazione definitive

---

## Appendice A – Data ID per modello (dai file di mapping)

"scalare (no suffisso)" = OID senza istanza (firmware 6.5). Enum come riportate nei file di mapping.
I due data point del ramo `1.3.20` (sensor order slot 6109–6118, eventi 5423/6119) sono identici sui due
modelli e non sono ripetuti.

### Ramo `1.2.1` – parametri (unità metriche)

| Data ID | Label (file mapping) | CRV602 istanze | CRV300 istanze | Enum (file mapping) |
|---|---|---|---|---|
| 4096 | System Input RMS A-N | — | scalare (no suffisso) |  |
| 4097 | System Input RMS A-B | — | scalare (no suffisso) |  |
| 4098 | System Input RMS B-N | — | scalare (no suffisso) |  |
| 4099 | System Input RMS B-C | — | scalare (no suffisso) |  |
| 4100 | System Input RMS C-N | — | scalare (no suffisso) |  |
| 4101 | System Input RMS C-A | — | scalare (no suffisso) |  |
| 4113 | System Input RMS Current Phase A | — | scalare (no suffisso) |  |
| 4114 | System Input RMS Current Phase B | — | scalare (no suffisso) |  |
| 4115 | System Input RMS Current Phase C | — | scalare (no suffisso) |  |
| 4123 | System Status | 1 | scalare (no suffisso) | {1: 'Normal Operation', 2: 'StartUp', 8: 'Normal with Warning', 16: 'Normal with Alarm', 32: 'Abnormal Operation'} |
| 4240 | System Model Number | 1 | scalare (no suffisso) |  |
| 4244 | System Serial Number | 1 | — |  |
| 4291 | Return Air Temperature | 1 | scalare (no suffisso) |  |
| 4293 | System Date and Time | — | scalare (no suffisso) |  |
| 4329 | System Name | — | scalare (no suffisso) |  |
| 4335 | Firmware Version | 1 | — |  |
| 4400 | PACC Controller Firmware Version | 1 | — |  |
| 4553 | Server Class | 1 | scalare (no suffisso) | {1: 'UPS', 2: 'AIR', 3: 'PMP', 4: 'PDU', 5: 'MONITOR'} |
| 4624 | Supply Fluid Temperature | — | scalare (no suffisso) |  |
| 4625 | High Supply Fluid Temperature Threshold | — | scalare (no suffisso) |  |
| 4706 | Unit Operating State | — | scalare (no suffisso) | {0: 'off', 1: 'on', 2: 'standby'} |
| 4707 | Unit Control Mode | — | scalare (no suffisso) | {0: 'Internal (Auto)', 1: 'External (Manual)'} |
| 4710 | Auto Restart Delay | — | scalare (no suffisso) |  |
| 4715 | Shutdown - Loss Of Power - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 4716 | Shutdown - Loss Of Power - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 4718 | Customer Input 1 - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 4719 | Customer Input 1 - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 4721 | Smoke Detected - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 4722 | Smoke Detected - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 4724 | Water Under Floor - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 4725 | Water Under Floor - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 4727 | Service Required - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 4728 | Service Required - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 4868 | Calculated Next Maintenance Month | — | scalare (no suffisso) |  |
| 4869 | Calculated Next Maintenance Year | — | scalare (no suffisso) |  |
| 4870 | Maintenance Ramp | — | scalare (no suffisso) |  |
| 5002 | Supply Air Temperature | 1 | scalare (no suffisso) |  |
| 5004 | Return Dew Point | — | scalare (no suffisso) |  |
| 5005 | Remote Sensor Minimum Temperature | — | scalare (no suffisso) |  |
| 5006 | Remote Sensor Maximum Temperature | — | scalare (no suffisso) |  |
| 5007 | Remote Sensor Average Temperature | 1 | scalare (no suffisso) |  |
| 5008 | Air Temperature Set Point | — | scalare (no suffisso) |  |
| 5009 | Cooling Proportional Band | 1 | scalare (no suffisso) |  |
| 5010 | Heating Proportional Band | — | scalare (no suffisso) |  |
| 5011 | Air Temperature Dead Band | — | scalare (no suffisso) |  |
| 5012 | Air Temperature Control Sensor | — | scalare (no suffisso) | {0: 'Supply', 1: 'Remote', 2: 'Return'} |
| 5013 | Remote Sensor Temperature Calculation | — | scalare (no suffisso) | {0: 'Average', 1: 'Maximum'} |
| 5014 | High Supply Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5018 | Low Supply Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5022 | High Return Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5027 | Supply Humidity | — | scalare (no suffisso) |  |
| 5028 | Return Humidity | 1 | scalare (no suffisso) |  |
| 5029 | Humidity Set Point | 1 | scalare (no suffisso) |  |
| 5030 | Humidification Proportional Band | 1 | scalare (no suffisso) |  |
| 5031 | Dehumidification Proportional Band | — | scalare (no suffisso) |  |
| 5032 | Humidity Dead Band | — | scalare (no suffisso) |  |
| 5033 | High Return Humidity Threshold | — | scalare (no suffisso) |  |
| 5035 | Low Return Humidity Threshold | — | scalare (no suffisso) |  |
| 5047 | Fan Control Mode | — | scalare (no suffisso) | {0: 'Internal (Auto)', 1: 'External (Manual)'} |
| 5048 | Fan Speed Proportional Band | — | scalare (no suffisso) |  |
| 5049 | Fan Speed Manual Set Point | — | scalare (no suffisso) |  |
| 5050 | Fan Speed Maximum Set Point | — | scalare (no suffisso) |  |
| 5051 | Fan Speed Minimum Set Point | — | scalare (no suffisso) |  |
| 5052 | Fan Control Sensor | — | scalare (no suffisso) | {0: 'Supply', 1: 'Remote', 2: 'Return'} |
| 5057 | Remote Sensor Name | — | 1,2,3,4,5,6,7,8,9,10 |  |
| 5058 | Remote Sensor Function | — | 1,2,3,4,5,6,7,8,9,10 | {0: 'Disable', 1: 'Reference', 2: 'Control'} |
| 5059 | Remote Sensor Temperature | 1,2,3,4,5,6,7,8,9,10 | 1,2,3,4,5,6,7,8,9,10 |  |
| 5074 | Unit Operating State Reason | — | scalare (no suffisso) | {0: 'Reason Unknown', 1: 'Network Display', 2: 'Alarm', 3: 'Schedule', 4: 'Remote System', 5: 'External Input', 6: 'Local Display'} |
| 5075 | BMS Timeout Period | — | scalare (no suffisso) |  |
| 5076 | Operating Efficiency | — | scalare (no suffisso) |  |
| 5077 | Fan Speed | 1 | scalare (no suffisso) |  |
| 5078 | Cooling Capacity (Primary) | — | scalare (no suffisso) |  |
| 5079 | Dehumidifier Utilization | — | scalare (no suffisso) |  |
| 5080 | Reheat Utilization | — | scalare (no suffisso) |  |
| 5081 | Humidifier Utilization | — | scalare (no suffisso) |  |
| 5082 | Ext Loss of Flow - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5083 | Ext Loss of Flow - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5084 | Ext Reheat Lockout - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5085 | Ext Reheat Lockout - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5086 | Ext Humidifier Lockout - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5087 | Ext Humidifier Lockout - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5088 | Ext Compressor Lockout - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5089 | Ext Compressor Lockout - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5090 | Ext Over Temperature - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5091 | Ext Over Temperature - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5092 | Condenser VFD Issue - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5093 | Condenser VFD Issue - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5094 | Condenser TVSS Issue - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5095 | Condenser TVSS Issue - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5096 | Condenser 1 Issue - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5097 | Condenser 1 Issue - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5098 | Customer Input 2 - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5099 | Customer Input 2 - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5100 | Customer Input 3 - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5101 | Customer Input 3 - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5102 | Customer Input 4 - Event Control | — | scalare (no suffisso) | {0: 'disabled', 1: 'enabled'} |
| 5103 | Customer Input 4 - Event Type | — | scalare (no suffisso) | {0: 'Message', 1: 'Warning', 2: 'Alarm'} |
| 5143 | System On/Off Control | — | scalare (no suffisso) | {0: 'off', 1: 'on'} |
| 5331 | Supply Air Temperature Set Point | 1 | — |  |
| 5333 | Return Air Temperature Set Point | 1 | — |  |
| 5366 | Electric Reheater Hours | 1 | — |  |
| 5369 | Humidifier Hours | 1 | — |  |
| 5374 | Fan Hours | 1 | — |  |
| 5382 | Cooling State | 1 | — | {0: 'off', 1: 'on'} |
| 5386 | Electric Reheat State | 1 | — | {0: 'off', 1: 'on'} |
| 5387 | Dehumidifier State | 1 | — | {0: 'off', 1: 'on'} |
| 5388 | Humidifier State | 1 | — | {0: 'off', 1: 'on'} |
| 5614 | Chilled Water Valve Hours | 1 | — |  |
| 5640 | Chilled Water Valve Open Position | 1 | — |  |
| 5667 | SuperSaver request sent to CApCom Master | — | scalare (no suffisso) |  |
| 5668 | Outlet Chilled Water Temperature | — | scalare (no suffisso) |  |
| 5669 | Water Flow Rate (l/min) | — | scalare (no suffisso) |  |
| 5670 | Water Flow Rate (m3/h) | — | scalare (no suffisso) |  |
| 5671 | Cooling Capacity in KW | — | scalare (no suffisso) |  |
| 5672 | Automatic Transfer Switch - Active Power Supply | — | scalare (no suffisso) | {0: 'Power Supply 1', 1: 'Power Supply 2'} |
| 5673 | Automatic Transfer Switch - Power Supply 1 Status | — | scalare (no suffisso) | {0: 'OK', 1: 'Not OK'} |
| 5674 | Automatic Transfer Switch - Power Supply 2 Status | — | scalare (no suffisso) | {0: 'OK', 1: 'Not OK'} |
| 5675 | Power Meter Status | — | scalare (no suffisso) |  |
| 5899 | Fluid Flow Rate | 1 | — |  |
| 5900 | Energy Consumption | — | scalare (no suffisso) |  |
| 5901 | Instantaneous Power | — | scalare (no suffisso) |  |
| 6311 | Chilled Water Inlet Temperature | 1 | — |  |
| 6312 | Chilled Water Outlet Temperature | 1 | — |  |
| 7505 | Water Valve Control Mode | 1 | — | {0: 'ReturnAirAverageTemp', 1: 'ReturnAirMaxTemp', 2: 'ReturnAirMinTemp', 3: 'SupplyAirAverageTemp', 4: 'SupplyAirMaxTemp', 5: 'SupplyAirMinTemp', 6: 'RemoteAverageTemp', 7: 'RemoteMaxTemp', 8: 'RemoteMinTemp'} |
| 7516 | Fan Control Mode | 1 | — | {0: 'ReturnAirAverageTemp', 1: 'ReturnAirMaxTemp', 2: 'ReturnAirMinTemp', 3: 'SupplyAirAverageTemp', 4: 'SupplyAirMaxTemp', 5: 'SupplyAirMinTemp', 6: 'RemoteAverageTemp', 7: 'RemoteMaxTemp', 8: 'RemoteMinTemp', 9: 'TemperatureDiff', 10: 'StaticPressure'} |
| 7521 | Air Filter Hours | 1 | — |  |
| 7527 | Fan Static Pressure | 1 | — |  |
| 7528 | System Operating State | 1 | — | {0: 'Run', 1: 'Standby', 2: 'Display Off', 3: 'Remote Off', 4: 'Monitoring Off', 5: 'Lockout'} |
| 7529 | Teamwork Status | 1 | — | {0: 'Single', 1: 'TeamworkMode0', 2: 'TeamworkMode1', 3: 'TeamworkMode2', 4: 'TeamworkMode3'} |
| 7536 | Monitoring ON/OFF | 1 | — | {16: 'on', 31: 'off'} |
| 8077 | Supply Air Sensor Temperature | 1,2,3 | — |  |
| 8078 | Return Air Sensor Temperature | 1,2 | — |  |
| 8080 | Return Sensor Humidity | 1 | — |  |
| 8082 | Remote Sensor Air Temperature Set Point | 1 | — |  |
| 8090 | Supply Air Theoretical Humidity | 1 | — |  |
| 8122 | Condensate Pump Hours | 1 | — |  |

### Ramo `1.2.2` – stessi parametri in unità alternative (°F)

| Data ID | Label (file mapping) | CRV602 istanze | CRV300 istanze | Enum (file mapping) |
|---|---|---|---|---|
| 4291 | Return Air Temperature | 1 | scalare (no suffisso) |  |
| 4624 | Supply Fluid Temperature | — | scalare (no suffisso) |  |
| 4625 | High Supply Fluid Temperature Threshold | — | scalare (no suffisso) |  |
| 5002 | Supply Air Temperature | 1 | scalare (no suffisso) |  |
| 5004 | Return Dew Point | — | scalare (no suffisso) |  |
| 5005 | Remote Sensor Minimum Temperature | — | scalare (no suffisso) |  |
| 5006 | Remote Sensor Maximum Temperature | — | scalare (no suffisso) |  |
| 5007 | Remote Sensor Average Temperature | 1 | scalare (no suffisso) |  |
| 5008 | Air Temperature Set Point | — | scalare (no suffisso) |  |
| 5009 | Cooling Proportional Band | 1 | scalare (no suffisso) |  |
| 5010 | Heating Proportional Band | — | scalare (no suffisso) |  |
| 5011 | Air Temperature Dead Band | — | scalare (no suffisso) |  |
| 5014 | High Supply Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5018 | Low Supply Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5022 | High Return Air Temperature Threshold | — | scalare (no suffisso) |  |
| 5048 | Fan Speed Proportional Band | — | scalare (no suffisso) |  |
| 5059 | Remote Sensor Temperature | 1,2,3,4,5,6,7,8,9,10 | 1,2,3,4,5,6,7,8,9,10 |  |
| 5331 | Supply Air Temperature Set Point | 1 | — |  |
| 5333 | Return Air Temperature Set Point | 1 | — |  |
| 5668 | Outlet Chilled Water Temperature | — | scalare (no suffisso) |  |
| 6311 | Chilled Water Inlet Temperature | 1 | — |  |
| 6312 | Chilled Water Outlet Temperature | 1 | — |  |
| 8077 | Supply Air Sensor Temperature | 1,2,3 | — |  |
| 8078 | Return Air Sensor Temperature | 1,2 | — |  |
| 8082 | Remote Sensor Air Temperature Set Point | 1 | — |  |

### Ramo `1.2.100` – data point evento

| Data ID | Label (file mapping) | CRV602 istanze | CRV300 istanze | Enum (file mapping) |
|---|---|---|---|---|
| 4270 | Customer Input 1 | — | scalare (no suffisso) |  |
| 4271 | Customer Input 2 | — | scalare (no suffisso) |  |
| 4272 | Customer Input 3 | — | scalare (no suffisso) |  |
| 4273 | Customer Input 4 | — | scalare (no suffisso) |  |
| 4300 | Internal Communications Failure | 1 | — |  |
| 4626 | Supply Chilled Water Over Temp | — | scalare (no suffisso) |  |
| 4651 | Supply Fluid Temp Sensor Issue | — | scalare (no suffisso) |  |
| 4669 | Compressor 1 High Head Pressure | — | scalare (no suffisso) |  |
| 4681 | Compressor 1 Short Cycle | — | scalare (no suffisso) |  |
| 4703 | Chilled Water Control Valve Failure | — | scalare (no suffisso) |  |
| 4714 | Shutdown - Loss Of Power | — | scalare (no suffisso) |  |
| 4720 | Smoke Detected | 1 | scalare (no suffisso) |  |
| 4723 | Water Under Floor | 1 | scalare (no suffisso) |  |
| 4726 | Service Required | — | scalare (no suffisso) |  |
| 4729 | Fan Issue | 1,2,3,4,5,6,7,8,9,10 | — |  |
| 4980 | Supply Chilled Water Loss of Flow | — | scalare (no suffisso) |  |
| 5015 | Supply Air Over Temperature | 1 | scalare (no suffisso) |  |
| 5019 | Supply Air Under Temperature | 1 | scalare (no suffisso) |  |
| 5023 | Return Air Over Temperature | 1 | scalare (no suffisso) |  |
| 5026 | Supply Air Sensor Issue | 1,2,3 | scalare (no suffisso) |  |
| 5034 | High Return Humidity | 1 | scalare (no suffisso) |  |
| 5036 | Low Return Humidity | 1 | scalare (no suffisso) |  |
| 5037 | Humidifier Hours Exceeded | — | scalare (no suffisso) |  |
| 5038 | Dehumidifier Hours Exceeded | — | scalare (no suffisso) |  |
| 5039 | Humidifier Under Current | — | scalare (no suffisso) |  |
| 5040 | Humidifier Over Current | — | scalare (no suffisso) |  |
| 5041 | Humidifier Low Water | — | scalare (no suffisso) |  |
| 5042 | Humidifier Cylinder Worn | — | scalare (no suffisso) |  |
| 5043 | Humidifier Issue | 1 | scalare (no suffisso) |  |
| 5044 | Ext Humidifier Lockout | — | scalare (no suffisso) |  |
| 5045 | Humidifier Control Board Not Detected | — | scalare (no suffisso) |  |
| 5046 | Return Humidity Out Of Proportional Band | — | scalare (no suffisso) |  |
| 5053 | Loss of Air Flow | — | scalare (no suffisso) |  |
| 5054 | Fan Hours Exceeded | — | scalare (no suffisso) |  |
| 5055 | Top Fan Issue | — | scalare (no suffisso) |  |
| 5056 | Bottom Fan Issue | — | scalare (no suffisso) |  |
| 5060 | Remote Sensor Issue | — | 1,2,3,4,5,6,7,8,9,10 |  |
| 5062 | Compressor 1 Low Suction Pressure | — | scalare (no suffisso) |  |
| 5063 | Compressor 1 Hours Exceeded | — | scalare (no suffisso) |  |
| 5064 | Dig Scroll Comp 1 Temp Sensor Issue | — | scalare (no suffisso) |  |
| 5065 | Dig Scroll Comp 1 Over Temp | — | scalare (no suffisso) |  |
| 5066 | Compressor 1 Low Pressure Transducer Issue | — | scalare (no suffisso) |  |
| 5067 | Ext Compressor Lockout | — | scalare (no suffisso) |  |
| 5068 | Reheater Over Temperature | — | scalare (no suffisso) |  |
| 5069 | Electric Reheater Hours Exceeded | — | scalare (no suffisso) |  |
| 5070 | Ext Reheat Lockout | — | scalare (no suffisso) |  |
| 5071 | Condenser 1 Issue | — | scalare (no suffisso) |  |
| 5104 | Ext Over Temperature | — | scalare (no suffisso) |  |
| 5105 | Ext Loss of Flow | — | scalare (no suffisso) |  |
| 5106 | Ext Condenser Pump High Water | 1 | scalare (no suffisso) |  |
| 5107 | Ext Standby Glycol Pump On | — | scalare (no suffisso) |  |
| 5108 | External Fire Detected | 1 | scalare (no suffisso) |  |
| 5109 | Unit On | — | scalare (no suffisso) |  |
| 5110 | Unit Off | — | scalare (no suffisso) |  |
| 5111 | Unit Standby | — | scalare (no suffisso) |  |
| 5112 | Unit Partial Shutdown | — | scalare (no suffisso) |  |
| 5113 | Unit Shutdown | — | scalare (no suffisso) |  |
| 5114 | Water Leakage Detector Sensor Issue | — | scalare (no suffisso) |  |
| 5115 | BMS Communications Timeout | — | scalare (no suffisso) |  |
| 5116 | Maintenance Due | — | scalare (no suffisso) |  |
| 5117 | Maintenance Completed | — | scalare (no suffisso) |  |
| 5118 | Clogged Air Filter | 1 | scalare (no suffisso) |  |
| 5119 | RAM Battery Issue | — | scalare (no suffisso) |  |
| 5120 | Master Unit Communication Lost | — | scalare (no suffisso) |  |
| 5121 | High Power Shutdown | — | scalare (no suffisso) |  |
| 5146 | Compressor 1 Pump Down Issue | — | scalare (no suffisso) |  |
| 5147 | Return Air Sensor Issue | 1,2 | scalare (no suffisso) |  |
| 5148 | Compressor 1 High Pressure Transducer Issue | — | scalare (no suffisso) |  |
| 5335 | Return Air Under Temperature | 1 | — |  |
| 5418 | Unit Code Missing | — | scalare (no suffisso) |  |
| 5500 | Ext Remote Shutdown | 1 | — |  |
| 5513 | Compressor Capacity Reduced | — | scalare (no suffisso) |  |
| 5588 | Unspecified General Event | — | scalare (no suffisso) |  |
| 5597 | Remote Sensor Over Temperature | 1 | — |  |
| 5598 | Remote Sensor Under Temperature | 1 | — |  |
| 5629 | Static Pressure Sensor Issue | — | scalare (no suffisso) |  |
| 5902 | Return Humidity Sensor Issue | 1 | — |  |
| 5910 | Static Pressure Sensor Out of Range | — | scalare (no suffisso) |  |
| 5911 | Fluid Temperature Sensor Issue | — | scalare (no suffisso) |  |
| 5912 | Fluid Flow Sensor Issue | — | scalare (no suffisso) |  |
| 6105 | External Condenser TVSS Issue | — | scalare (no suffisso) |  |
| 6232 | SEC Unspecified General Event | — | scalare (no suffisso) |  |
| 6233 | SEC Communication Lost | — | scalare (no suffisso) |  |
| 6236 | Power Source 'A' Issue | — | scalare (no suffisso) |  |
| 6237 | Power Source 'B' Issue | — | scalare (no suffisso) |  |
| 6313 | Chilled Water Inlet Temperature Sensor Failure | 1 | — |  |
| 6314 | Chilled Water Outlet Temperature Sensor Failure | 1 | — |  |
| 7495 | External Air Sensor Issue | 1,2,3,4,5,6,7,8,9,10 | — |  |
| 7503 | Electrical Heater Failure | 1 | — |  |
| 7506 | Supply Fluid Low Flow | 1 | — |  |
| 7509 | Outlet Fluid Under Temp | 1 | — |  |
| 7510 | Outlet Fluid Over Temp | 1 | — |  |
| 7511 | Inlet Fluid Over Temp | 1 | — |  |
| 7512 | Inlet Fluid Under Temp | 1 | — |  |
| 7522 | Loss of Airflow | 1 | — |  |
| 7523 | Teamwork Master is offline or not connected to the network | 1 | — |  |
| 7524 | Loss of Teamwork Slave | 1 | — |  |
| 7525 | Repeated Teamwork Address | 1 | — |  |
| 7537 | Filter Maintenance Due | 1 | — |  |
| 7558 | Water Flow Sensor Failure | 1 | — |  |
| 7561 | Custom Alarm | 1 | — |  |
| 7563 | Fan Static Pressure Sensor Failure | 1 | — |  |
| 8072 | 10DI Sensor Communication Fail | 1 | — |  |
