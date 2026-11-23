# Analisi – soglie e stati WARN/CRIT di tutti i servizi (base 1.1.0)

Obiettivo: le funzioni importanti devono avere soglie o stati WARN/CRIT predefiniti. Ogni proposta si basa
sul significato della grandezza, non sui valori misurati.

Legenda colonna "Oggi":
- **S** = soglie predefinite;
- **M** = mappa di stato;
- **–** = sempre OK.

Le proposte sono numerate (P1…) per decidere punto per punto.

---

## 1. Cosa copre già la scheda (servizio Events)

La scheda genera eventi propri per molti guasti, tra cui:
- *Fan Issue*, *Top/Bottom Fan Issue*, *Loss of Airflow*;
- *Supply Fluid Low Flow*, *Supply Chilled Water Loss of Flow*, *Chilled Water Control Valve Failure*;
- *Clogged Air Filter*, *Filter Maintenance Due*;
- *Smoke Detected*, *Water Under Floor*, *External Fire Detected*;
- *High Power Shutdown*, *Unit Shutdown*, *Unit Partial Shutdown*;
- guasti dei sensori.

Oggi però **ogni evento attivo vale WARN**, salvo la severità configurata sulla scheda (solo FW 6.5, solo
16 eventi). Ne derivano due problemi:

- eventi gravi (fumo, acqua, incendio, perdita di flusso d'aria, arresto) sono solo WARN;
- alcuni "eventi" sono messaggi di stato (*Unit On*, *Unit Off*, *Unit Standby*, *Maintenance Completed*):
  se la scheda li riporta attivi, generano WARN inutili.

**P1 – Severità predefinita per codice evento** (sovrascrivibile dalla regola):

| Severità | Eventi (codice) |
|---|---|
| **CRIT** | Smoke Detected (4720), Water Under Floor (4723), External Fire Detected (5108), Loss of Airflow (7522, 5053), Fan Issue (4729), Top/Bottom Fan Issue (5055, 5056), Supply Fluid Low Flow (7506), Supply Chilled Water Loss of Flow (4980), Ext Loss of Flow (5105), Chilled Water Control Valve Failure (4703), Unit Shutdown (5113), High Power Shutdown (5121), Shutdown - Loss Of Power (4714), Ext Remote Shutdown (5500), Supply Air Over Temperature (5015), Return Air Over Temperature (5023), Ext Over Temperature (5104), Supply Chilled Water Over Temp (4626), Outlet/Inlet Fluid Over Temp (7510, 7511), Ext Condenser Pump High Water (5106), Internal Communications Failure (4300), Power Source 'A'/'B' Issue (6236, 6237), Electrical Heater Failure (7503), Reheater Over Temperature (5068) |
| **WARN** | tutti gli altri: sensori guasti, umidità alta/bassa, sotto-temperatura, filtri, manutenzione, ore superate, teamwork, umidificatore, BMS timeout… (resta il default attuale) |
| **OK** (solo informativo) | Unit On (5109), Unit Off (5110), Unit Standby (5111), Maintenance Completed (5117) |

Se la scheda fornisce la severità (FW 6.5), resta prioritaria la configurazione della scheda o la severità
predefinita? → **Decisione D1.**

---

## 2. Valori numerici

### 2.1 Già coperti nella 1.1.0

Aria di mandata, ripresa e sensori remoti; umidità; punto di rugiada; acqua refrigerata in ingresso e uscita.

### 2.2 Proposte

| Servizio (data ID) | Modelli | Oggi | Proposta | Motivo |
|---|---|---|---|---|
| **Fan Speed** (5077) | entrambi | – | **P2:** WARN ≥ 95 %, CRIT nessuna | Ventilatori al massimo significa che l'unità non ha più riserva. Non è un guasto, quindi WARN. Il guasto vero (ventola ferma) è coperto da *Fan Issue* / *Loss of Airflow*, che con P1 diventano CRIT. |
| | | | **P3:** CRIT se 0 % con unità in marcia (System Operating State = Run / Unit Operating State = on) | Ventola ferma con unità accesa significa niente raffreddamento. Richiede di confrontare due parametri (§4). |
| **Chilled Water Valve Open Position** (5640) / **Cooling Capacity (Primary)** (5078) | CRC602 / CRV300 | – | **P4:** WARN ≥ 95 % | Valvola acqua tutta aperta: l'unità lavora al limite e non può dare di più. |
| **Fluid Flow Rate** (5899) | CRC602 | – | **P5:** CRIT se portata ≈ 0 (< 0.05 m³/h) con valvola aperta ≥ 20 % | Valvola aperta senza flusso significa acqua che non circola. La portata nominale dipende dalla taglia, quindi niente soglia fissa; il confronto con la valvola è valido per qualunque taglia (§4). |
| **Air Filter Hours** (7521) | CRC602 | – | nessuna | L'intervallo di sostituzione è configurato sulla scheda, che genera *Filter Maintenance Due* (WARN). |
| Altri contaore (Fan, Humidifier, Reheater, CW Valve, Condensate Pump) | | – | nessuna | Solo usura; la scheda ha eventi "Hours Exceeded". |
| **Operating Efficiency** (5076), Reheat Utilization (5080), SuperSaver (5667) | CRV300 | – | nessuna | Informativi, nessun valore "giusto" generico. |
| **Power Meter Status** (5675) | CRV300 | – | nessuna | Codice non documentato nella MIB. |
| Tensioni e correnti d'ingresso (4096–4115) | CRV300 | non scoperti (Unavailable) | **P6 (opzionale):** ±10 % / ±15 % su 230 V F-N e 400 V F-F | Utili solo con il power meter installato. I valori nominali dipendono dalla rete (EU/US). |

### 2.3 Impostazioni (set point, bande, soglie della scheda, ritardi)

Oggi sono visibili e graficate; l'avviso "cambiato rispetto alla discovery" è disattivato di default.

**P7:** attivare di default il **WARN su modifica** per le impostazioni che incidono sul comportamento
dell'unità:
- set point: 5008, 5331, 5333, 8082, 5029;
- soglie configurate sulla scheda: 5014, 5018, 5022, 4625, 5033, 5035;
- limiti dei ventilatori: 5050, 5051.

Le bande proporzionali restano senza avviso. Dopo una modifica voluta basta rifare la discovery del servizio.
→ **Decisione D3.**

### 2.4 Controllo di regolazione (nuovo)

**P8 – Scostamento dal set point:** WARN se la temperatura controllata supera il set point di oltre
**2 K**, CRIT oltre **4 K**.
- Il sensore di controllo si ricava dalla scheda, quando la espone: *Air Temperature Control Sensor* sul
  CRV300 (5012), *Water Valve Control Mode* sul CRC602 (7505).
- È l'indicatore più diretto di "l'unità non riesce a raffreddare": scatta prima delle soglie assolute e
  vale anche con set point diversi da quelli tipici.
- Si realizza come servizio aggiuntivo, ad esempio `Cooling Control Deviation` (§4).

---

## 3. Stati (enum)

| Servizio (data ID) | Modelli | Oggi | Proposta |
|---|---|---|---|
| System Status (4123) | entrambi | M: Normal OK; StartUp / Normal with Warning WARN; Normal with Alarm / Abnormal CRIT | invariato |
| System Operating State (7528) | CRC602 | M: Run/Standby OK; Display/Remote/Monitoring Off WARN; Lockout CRIT | invariato (Standby OK per il teamwork) |
| Unit Operating State (4706) | CRV300 | M: on/standby OK; off WARN | **P9:** off → **CRIT** (unità spenta = nessun raffreddamento) |
| System On/Off Control (5143) | CRV300 | M: on OK; off WARN | **P9:** off → **CRIT** |
| **Cooling State** (5382) | CRC602 | – (sempre OK) | **P10:** off → **WARN** se l'unità è in Run, OK se in Standby/spenta (lo stato dell'unità è già segnalato dal suo servizio) |
| Electric Reheat / Dehumidifier / Humidifier State (5386–5388) | CRC602 | – | invariato: sono attuatori che si accendono e spengono normalmente |
| ATS – Power Supply 1/2 Status (5673/5674) | CRV300 | M: Not OK CRIT | invariato |
| **ATS – Active Power Supply** (5672) | CRV300 | – | **P11:** Power Supply 2 → **WARN** (l'unità è sull'alimentazione di riserva) |
| **Unit Control Mode** (4707) | CRV300 | – | **P12:** External (Manual) → **WARN** (regolazione in manuale, esclusa l'automatica) |
| **Fan Control Mode** (5047) | CRV300 | – | **P12:** External (Manual) → **WARN** |
| Unit Operating State Reason (5074) | CRV300 | – | invariato (informativo) |
| Teamwork Status (7529) | CRC602 | – | **P7** (avviso su modifica) |
| Modalità e sensori di controllo (5012, 5013, 5052, 7505, 7516, 5058.x) | | – | **P7** (avviso su modifica) |
| Server Class (4553) | entrambi | – | invariato |

---

## 4. Note di realizzazione

- **P1, P2, P4, P9, P11, P12:** tabelle predefinite nel plugin, come le soglie della 1.1.0. Restano
  sovrascrivibili con le regole esistenti.
- **P3, P5, P8, P10:** richiedono di confrontare più parametri della stessa unità. La sezione li contiene
  già tutti, quindi non servono letture SNMP aggiuntive.
  - P3, P5 e P10 si aggiungono ai servizi esistenti (Fan Speed, Fluid Flow Rate, Cooling State);
  - P8 è un servizio nuovo.
- **P7:** cambia il default di `change_state` solo per i data ID elencati. Effetto collaterale: dopo una
  modifica voluta, il servizio resta in WARN finché non si rifà la discovery.
- **Versione:** tutto insieme sarebbe la **1.2.0** (nuove funzioni, compatibile). Nessuna nuova discovery
  obbligatoria, tranne per il servizio P8 nuovo.

## 5. Decisioni richieste

| # | Domanda | Proposta |
|---|---|---|
| D1 | Severità predefinita per codice evento (P1). Se la scheda ha una severità configurata (FW 6.5), vale quella della scheda o la tabella? | adottare P1; prevale la **configurazione della scheda**, perché è una scelta esplicita dell'impianto |
| D2 | Ventole e capacità (P2, P3, P4, P5) | adottare tutte |
| D3 | WARN su modifica delle impostazioni (P7) | adottare per set point, soglie e modalità; non per le bande |
| D4 | Scostamento dal set point (P8), 2 K / 4 K | adottare |
| D5 | Unità spenta = CRIT (P9), Cooling State (P10), ATS e modalità manuale (P11, P12) | adottare |
| D6 | Tensioni d'ingresso (P6) | rimandare: oggi non disponibili sulle unità |

## 6. Decisioni prese (realizzate nella 1.2.0)

| # | Decisione |
|---|---|
| D1 | P1 adottata; la **severità configurata sulla scheda prevale** sulla tabella predefinita |
| D2 | P2, P3, P4, P5 adottate |
| D3 | P7 adottata (escluse le bande proporzionali) |
| D4 | P8 adottata: servizio `Cooling Control Deviation`, 2 K / 4 K |
| D5 | P9, P10, P11, P12 adottate |
| D6 | P6 adottata: 230 V F-N e 400 V F-F, WARN ±10 %, CRIT ±15 %; se non disponibili non diventano servizi, oppure si escludono con la regola di discovery |
