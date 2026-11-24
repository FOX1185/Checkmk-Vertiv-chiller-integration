# Documentazione tecnica – plugin `vertiv_unity` 1.2.1

Plugin SNMP per **Checkmk 2.5** che monitora le unità di condizionamento Vertiv/Liebert dotate di scheda
**IntelliSlot Unity**. Questo documento descrive:
- architettura, componenti e dipendenze;
- scelte progettuali e i motivi;
- problemi incontrati durante lo sviluppo;
- test e procedura di rilascio.

Per l'uso e l'installazione vedere [MANUALE-UTENTE.md](MANUALE-UTENTE.md). Le analisi di dettaglio delle
singole fasi sono in [sviluppo/](sviluppo/).

---

## 1. Ambito

| Voce | Valore |
|---|---|
| Versione | 1.2.1 (file `VERSION`) |
| Checkmk | 2.5.0 o superiore (sviluppato e verificato su Community 2.5.0p12, Docker, core Nagios) |
| Dispositivi verificati | Liebert CRV300 – Unity FW 6.5.0; Liebert CRC602 (indicato in progetto come "CRV602") – Unity FW 8.4.7 |
| Dispositivi previsti | Liebert CRV25 (Unity FW 7.8.0) – non ancora verificato; in generale qualunque unità con scheda Unity che espone la tabella Flexible |
| Protocollo | SNMP v1/v2c/v3 come configurato in Checkmk (verificato v2c, community in sola lettura) |

### Requisiti funzionali e come sono soddisfatti

| Requisito | Realizzazione |
|---|---|
| Un unico plugin per tutti i modelli | una sezione SNMP generica sulla tabella Flexible, nessuna lista di OID per modello |
| Discovery dinamica | ogni riga dichiara tipo, accesso, unità e decimali; la classificazione avviene a runtime |
| Un servizio per parametro | un servizio per data point (numerico, enum, testo) |
| Grafici e perfdata | metrica per ogni numerico, scelta in base all'unità |
| Soglie configurabili | soglie predefinite per aria, acqua, umidità e rugiada (§5.1); regola "Vertiv Unity – numeric parameters" per servizio |
| Stati per enum e testi | mappe di stato predefinite (§5.2), avviso su modifica delle impostazioni, regola "Vertiv Unity – states and modes" |
| Esclusione dei valori non validi | regole di validità (§5): non scoperti; UNKNOWN se diventano non validi |
| Servizio eventi con descrizione | servizio `Events` con etichetta, codice, istanza e severità (scheda, poi tabella predefinita, §5.3) |
| Funzioni importanti con WARN/CRIT | soglie, stati, eventi e controlli incrociati predefiniti; servizio `Cooling Control Deviation` (§5.4) |

---

## 2. Fonte dati

### 2.1 LIEBERT-GP-FLEXIBLE-MIB

Tutti i dati provengono da `lgpFlexibleBasicTable` (`.1.3.6.1.4.1.476.1.42.3.9.20`) e dalla tabella
che la estende, `lgpFlexibleExtendedTable` (`…3.9.30`). L'indice di riga è un `IMPLIED OBJECT IDENTIFIER`
che identifica un data point in modo permanente.

| Colonna | OID | Uso nel plugin |
|---|---|---|
| DataLabel | `…3.9.20.1.10` | nome del servizio / evento |
| Value | `…3.9.20.1.20` | valore testuale (enum, testo, evento) |
| UnitsOfMeasure | `…3.9.20.1.30` | unità mostrata per i valori senza metrica dedicata |
| IntegerValue | `…3.9.30.1.10` | raw per int16/int32 |
| UnsignedIntegerValue | `…3.9.30.1.20` | raw per uint16/uint32 e codice degli enum |
| DecimalPosition | `…3.9.30.1.30` | scala: valore = raw / 10^n |
| DataType | `…3.9.30.1.40` | classificazione (int16, uint16, int32, uint32, text, enum, event16, ipv4, time32) |
| Accessibility | `…3.9.30.1.50` | distingue misure (sola lettura) e impostazioni (lettura-scrittura) |
| UnitsOfMeasureEnum | `…3.9.30.1.60` | scelta della metrica (degC, %RH, h, m³/h, …) |
| DataDescription | `…3.9.30.1.70` | **non letta** (testo lungo e statico) |

### 2.2 Struttura dell'indice (verificata sui walk)

| Indice | Contenuto | Letto |
|---|---|---|
| `1.2.1.<id>[.<istanza>]` | data point dell'unità, unità metriche | sì |
| `1.2.2.<id>[.<istanza>]` | stessi data point in unità imperiali (°F) | no |
| `1.2.100.<id>[.<istanza>]` | eventi dell'unità (`Active Event` / `Inactive Event`) | sì |
| `1.3.20.1.<id>` | modulo sensori della scheda (stato, slot) | no |
| `1.3.20.100.<id>` | eventi del modulo sensori | sì |

Il FW 6.5 omette l'istanza sui data point singoli (`4123`); il FW 8.4 la riporta sempre (`4123.1`).
Il plugin le normalizza entrambe come `4123.1`.

### 2.3 Fonti non utilizzate e motivi

| Fonte | Motivo |
|---|---|
| `lgpConditionsTable` (`…3.2.3`) | **non implementata** su nessuna delle due schede (`No Such Object`) |
| LIEBERT-GP-ENVIRONMENTAL-MIB (`…3.4`) | presente solo sul FW 6.5, assente sul FW 8.4 |
| `lgpConditionControlTable` (`…3.2.4.20`) | solo FW 6.5; stessa informazione delle coppie "Event Control/Type" |
| file `SNMP_upsParams` / `SNMP_upsMibEvents` | riguardano la UPS-MIB, non applicabile (Server Class = AIR) |

### 2.4 Documentazione di riferimento

- MIB ufficiali Vertiv **Rev 26** (ottobre 2025), in `mibs/rev26/`. Il plugin usa `LIEBERT_GP_FLEXIBLE.MIB`
  e `LIEBERT_GP_FLEXIBLE_COND.MIB`, che definisce 1450 codici evento.
- File di mapping scaricati dalle schede (`docs/mapping/`).
- Walk reali delle due unità (`tests/snmpwalks/`), anche ricostruiti in tabella (`docs/walks/`).

---

## 3. Architettura e componenti

```
plugin/cmk_addons/plugins/vertiv_unity/
├── agent_based/vertiv_unity.py   sezione SNMP, parsing, discovery, 4 check plugin
├── rulesets/vertiv_unity.py      4 regole (3 di check, 1 di discovery)
├── graphing/vertiv_unity.py      12 metriche
└── lib/constants.py              costanti condivise con gli script in tools/ (OID base, tipi, accessi)
```

Nel sito Checkmk i file vanno in `~/local/lib/python3/cmk_addons/plugins/vertiv_unity/`.
Checkmk li carica automaticamente in base alla cartella: `cmk_addons.plugins.<famiglia>.<gruppo>`.
`lib/` è la cartella prevista da Checkmk per il codice condiviso: non viene caricata come plugin, ma è importabile.
`lib/constants.py` non importa nulla da Checkmk, così gli script in `tools/` funzionano anche senza un sito.

### 3.1 Flusso

```
SNMP (bulkwalk) ──► snmp_section_vertiv_unity ──► parse_vertiv_unity ──► Section
                     3 alberi OID                    classificazione        │
                                                                            ├─► vertiv_unity_value   (numerici)
                                                                            ├─► vertiv_unity_state   (enum)
                                                                            ├─► vertiv_unity_text    (testi)
                                                                            └─► vertiv_unity_events  (eventi)
```

### 3.2 Sezione SNMP `vertiv_unity`

- **Detection:** `sysObjectID` inizia con `.1.3.6.1.4.1.476.1.42` **e** esiste
  `.1.3.6.1.4.1.476.1.42.3.9.10.0` (`lgpFlexibleTableCount`).
- **Fetch:** tre alberi.

  | Albero | Base | Contenuto |
  |---|---|---|
  | data point | `…3.9` | 9 colonne, sotto-indice `1.2.1` |
  | eventi dell'unità | `…3.9.20.1` | etichetta e valore, sotto-indice `1.2.100` |
  | eventi del modulo sensori | `…3.9.20.1` | etichetta e valore, sotto-indice `1.3.20.100` |

  Righe per ciclo: circa 115 sul CRV602 e circa 220 sul CRV300.
- **Supersedes:** i 18 plugin `liebert_*` di Checkmk (`liebert_temp_air`, `liebert_system`, …), vedi §4.
- **Parsing:** produce `Section(data_points, events, event_config)`.
  - `data_points` è indicizzato per nome servizio.
  - `event_config` contiene abilitazione e severità degli eventi, ricavate dalle coppie
    `<evento> - Event Control` / `<evento> - Event Type` (solo FW 6.5).

### 3.3 Check plugin

| Plugin | Servizio | Discovery | Parametri |
|---|---|---|---|
| `vertiv_unity_value` | `%s` (etichetta) | numerici validi (int16/uint16/int32/uint32) | `levels_upper`, `levels_lower`, `change_state` |
| `vertiv_unity_state` | `%s` | enum validi, escluse le coppie Event Control/Type | `state_map`, `change_state` |
| `vertiv_unity_text` | `%s` | text/ipv4/time32 non vuoti | nessuno |
| `vertiv_unity_events` | `Events` | se esistono data point evento | `default_state`, `event_states` |
| `vertiv_unity_control` | `Cooling Control Deviation` | se sensore di controllo, temperatura e set point sono leggibili | `levels_upper` (predefinito 2 / 4 K) |

Nome del servizio: l'etichetta della scheda; se il data ID ha più istanze, segue il numero di istanza
(`Supply Air Sensor Temperature 2`). Se due data ID diversi avessero la stessa etichetta (non accade sui walk
reali), al nome si aggiunge il data ID tra parentesi.

### 3.4 Regole (rulesets API v1)

| Nome interno | Titolo nella GUI | Tipo | Condizione |
|---|---|---|---|
| `vertiv_unity_value` | Vertiv Unity – numeric parameters | CheckParameters | host + nome servizio |
| `vertiv_unity_state` | Vertiv Unity – states and modes | CheckParameters | host + nome servizio |
| `vertiv_unity_events` | Vertiv Unity – events | CheckParameters | host |
| `vertiv_unity_control` | Vertiv Unity – cooling control deviation | CheckParameters | host |
| `vertiv_unity_discovery` | Vertiv Unity discovery | DiscoveryParameters | host |

### 3.5 Metriche

| Unità scheda (enum) | Metrica | Definita da |
|---|---|---|
| degC 4125, degF 4127 (convertiti in °C) | `temp` | Checkmk |
| %RH 4132 | `humidity` | Checkmk |
| VAC 4100 / A 4106 / W 4114 | `voltage` / `current` / `power` | Checkmk |
| degC delta 4126, degF delta 4128 | `vertiv_unity_temp_delta` (K) | plugin |
| % 4124 | `vertiv_unity_percent` | plugin |
| h 4099 | `vertiv_unity_hours` | plugin |
| s 4097 / min 4098 | `vertiv_unity_seconds` / `vertiv_unity_minutes` | plugin |
| m³/h 4155 / l/min 4158 | `vertiv_unity_flow_m3h` / `vertiv_unity_flow_lpm` | plugin |
| Pa 4130 | `vertiv_unity_pressure_pa` | plugin |
| kW 4115 / kWh 4117 | `vertiv_unity_power_kw` / `vertiv_unity_energy_kwh` | plugin |
| altre / nessuna | `vertiv_unity_value` | plugin |
| — | `vertiv_unity_active_events` | plugin |
| — | `vertiv_unity_setpoint_deviation` (K) | plugin |

---

## 4. Dipendenze

### Runtime

| Dipendenza | Versione | Note |
|---|---|---|
| Checkmk | ≥ 2.5.0 | API `cmk.agent_based.v2`, `cmk.rulesets.v1`, `cmk.graphing.v1` (stabili) |
| Python | quello del sito Checkmk | solo libreria standard (`collections`, `dataclasses`) |

Nessuna libreria esterna, nessun agente, nessun file MIB richiesto sul server Checkmk: gli OID sono numerici.

### Sviluppo e rilascio

| Dipendenza | Uso |
|---|---|
| sorgente Checkmk, tag `v2.5.0p12`: `packages/cmk-plugin-apis` | API per eseguire i test fuori da Checkmk |
| sorgente Checkmk, tag `v2.5.0p12`: `packages/cmk-mkp-tool` | costruzione del pacchetto MKP con il tool ufficiale |
| `pytest` | test |
| `pydantic` | richiesto da `cmk-mkp-tool` e da parte delle API |

---

## 5. Regole di validità dei valori

Un data point è **non valido** se:

| # | Condizione | Esempio reale |
|---|---|---|
| 1 | testo `Unavailable` o `No Support` | 5059.2–10, 8077.3, 7527 |
| 2 | raw `2147483647` o `4294967295` ("nessun dato" della scheda) | 4096–4115, 5079 |
| 3 | int16 raw `-32768` / uint16 raw `65535`: sentinelle **non segnalate** dalla scheda | CRV300 5668–5671; CRV602 5028 = 6553.5 |
| 4 | numerico senza valore interpretabile | — |
| 5 | fuori intervallo plausibile: 4868 mese 1–12, 4869 anno 2000–2100 | CRV300 4868 = 65409 |
| 6 | testo vuoto | 5057.x, slot sensori |

- **Discovery:** il data point non diventa servizio.
- **Check:** il servizio va in UNKNOWN con il motivo, senza perfdata.
- **Data point sparito dalla tabella:** Checkmk lo segnala come "item not found".

### 5.1 Soglie predefinite (dalla 1.1.0)

Definite in `DEFAULT_LEVELS` (data ID → profilo) nel file `agent_based/vertiv_unity.py`.

| Grandezza | Servizi (data ID) | WARN / CRIT superiore | WARN / CRIT inferiore | Riferimento |
|---|---|---|---|---|
| Aria di mandata e sensori ai rack | Supply Air Temperature (5002), Supply Air Sensor Temperature *n* (8077), Remote Sensor Temperature *n* / Average / Minimum / Maximum (5059, 5007, 5005, 5006) | 27 / 32 °C | 15 / 12 °C | ASHRAE TC 9.9 classe A1: consigliato 18–27 °C, ammesso 15–32 °C |
| Aria di ripresa (corridoio caldo) | Return Air Temperature (4291), Return Air Sensor Temperature *n* (8078) | 40 / 45 °C | — | aria calda in uscita dai server; una temperatura bassa non è un problema |
| Umidità di ripresa | Return Humidity (5028), Return Sensor Humidity (8080) | 70 / 80 % | 20 / 15 % | ASHRAE A1: fino all'80 % ammesso; sotto il 20 % aumenta il rischio di scariche elettrostatiche |
| Umidità di mandata | Supply Humidity (5027), Supply Air Theoretical Humidity (8090) | 80 / 90 % | 20 / 15 % | l'aria fredda di mandata ha un'umidità relativa più alta di quella di ripresa |
| Punto di rugiada | Return Dew Point (5004) | 17 / 20 °C | −9 / −12 °C | ASHRAE A1: rugiada massima 17 °C ammessa, minima −9 °C |
| Acqua refrigerata in ingresso all'unità | Chilled Water Inlet Temperature (6311), Supply Fluid Temperature (4624) | 20 / 25 °C | 5 / 3 °C | mandata tipica 7–20 °C; più calda riduce la capacità frigorifera, sotto 5 °C c'è rischio di gelo senza glicole |
| Acqua refrigerata in uscita dall'unità | Chilled Water Outlet Temperature (6312), Outlet Chilled Water Temperature (5668) | 26 / 30 °C | 5 / 3 °C | ritorno tipico: mandata + 5…6 °C |
| Riserva di capacità | Fan Speed (5077), Chilled Water Valve Open Position (5640), Cooling Capacity (Primary) (5078) | solo WARN ≥ 95 % | — | unità al limite, senza riserva (dalla 1.2.0) |
| Tensione F-N | 4096, 4098, 4100 | 253 / 264.5 V | 207 / 195.5 V | 230 V ±10 % / ±15 % (EN 50160) (dalla 1.2.0) |
| Tensione F-F | 4097, 4099, 4101 | 440 / 460 V | 360 / 340 V | 400 V ±10 % / ±15 % (dalla 1.2.0) |

Logica in `check_vertiv_unity_value`:
- per ciascuna soglia (superiore, inferiore), se la regola contiene la chiave (`levels_upper`/`levels_lower`)
  vale la regola, anche quando è "No levels";
- altrimenti vale il profilo, solo se la metrica del data point coincide con quella del profilo (`temp` o
  `humidity`);
- quando si usano soglie predefinite, i dettagli del servizio lo indicano.

Una soglia con CRIT `None` è "solo WARN": la metrica riporta `levels=(warn, None)` e il WARN si genera a
parte, perché `check_levels` richiede sempre una coppia.

Per questo, dalla 1.1.0 `check_default_parameters` non contiene più `levels_upper`/`levels_lower`, e dalla
1.2.0 nemmeno `change_state`.

### 5.2 Stati e avviso su modifica (dalla 1.2.0)

- **`DEFAULT_STATE_MAPS`:**
  - 4706 e 5143 off → CRIT;
  - 5672 Power Supply 2 → WARN;
  - 4707 e 5047 External (Manual) → WARN;
  - invariati 4123, 7528, 5673/5674.
- **Cooling State (5382), mappa dinamica:** off → WARN se `unit_running()` è vero, cioè 7528 = Run oppure
  4706 = on; altrimenti OK.
- **`CHANGE_ALERT_IDS`:** dati per cui `change_state` vale WARN se la regola non lo imposta:
  - set point: 5008, 5331, 5333, 8082, 5029;
  - soglie della scheda: 5014, 5018, 5022, 4625, 5033, 5035;
  - ventilatori: 5049, 5050, 5051;
  - modalità e sensori: 5012, 5013, 5052, 5047, 4707, 7505, 7516, 5058, 7529.

  Il valore di riferimento è `discovered_value`, salvato alla discovery.

### 5.3 Severità degli eventi (dalla 1.2.0)

Ordine di valutazione in `_event_state`:
1. regola per codice o istanza;
2. evento disabilitato sulla scheda → ignorato;
3. severità della scheda (`Event Type`: Message/Warning/Alarm), che **prevale sulla tabella**
   (decisione dell'utente);
4. `DEFAULT_EVENT_STATES`:
   - **CRIT** per 28 codici: fumo, acqua, incendio, flusso d'aria, ventole, flusso acqua, valvola, arresti,
     sovratemperature, pompa condensa, comunicazione interna, alimentazione, riscaldatore;
   - **OK** per 5109, 5110, 5111, 5117;
5. `default_state` (WARN).

Tutti i codici della tabella sono verificati nei file di mapping delle due unità.

### 5.4 Controlli incrociati e regolazione (dalla 1.2.0)

`Section` indicizza i data point per chiave (`by_key`) e offre `valid_value`, `valid_text`, `instances` e
`unit_running`. I controlli incrociati non richiedono letture SNMP aggiuntive.

| Controllo | Condizione | Stato |
|---|---|---|
| Ventole ferme (P3) | 5077 ≤ 0 % e `unit_running()` | CRIT sul servizio Fan Speed |
| Assenza di flusso (P5) | portata < 0.05 m³/h (4155) o < 1 l/min (4158), con 5640 o 5078 ≥ 20 % | CRIT sul servizio della portata |
| Scostamento dal set point (P8) | temperatura regolata − set point > 2 / 4 K | WARN / CRIT sul servizio `Cooling Control Deviation` |

Come si ricava la temperatura regolata (`_control_target`):
- **FW 6.5:** 5012 = Supply / Return / Remote, set point 5008. Per Remote il calcolo è letto da 5013:
  media 5007, oppure massimo dei 5059 (fallback 5006).
- **FW 8.x:** 7505 = `<SupplyAir|ReturnAir|Remote><Average|Max|Min>Temp`, con set point 5331 / 5333 / 8082.
  - media: 5002 / 4291 / 5007;
  - massimo/minimo: calcolato sulle istanze valide di 8077 / 8078 / 5059.
- **Altri modelli o modalità** (es. sensore di controllo non leggibile): il servizio non viene creato.
  Se smette di essere calcolabile dopo la discovery → UNKNOWN.


---

## 6. Scelte progettuali

| Scelta | Motivo |
|---|---|
| Unica fonte: tabella Flexible | È l'unica comune ai due firmware ed è auto-descrittiva (tipo, unità, scala, accesso). I due modelli condividono solo 12 data ID su 42/106: una lista fissa di OID non sarebbe manutenibile. |
| Classificazione dal tipo SNMP dichiarato | Evita di interpretare codici e stati come misure. |
| Valore numerico dal raw, non dalla stringa | Il raw è preciso e permette di riconoscere le sentinelle che nella stringa sembrano valide. |
| Solo ramo `1.2.1` | Il ramo `1.2.2` duplica in °F gli stessi valori. |
| Descrizione lunga (`.30.1.70`) non letta | Testo statico fino a 255 caratteri per riga: costerebbe molto traffico SNMP a ogni ciclo senza aggiungere informazione. |
| Chiave del servizio = etichetta (+ istanza) | Nome leggibile senza prefisso (decisione dell'utente); il data ID resta nei dettagli. Con la stessa etichetta, il data ID può avere significati diversi tra firmware (es. "Fan Control Mode" è 5047 sul CRV300 e 7516 sul CRV602). |
| Parametri di configurazione come servizi | Decisione dell'utente: set point, bande e contaore sono visibili e graficati. Il controllo "cambiato rispetto alla discovery" è opzionale. |
| Evento attivo senza severità nota → WARN | Decisione dell'utente; regolabile per codice. Severità della scheda (Message/Warning/Alarm) usata quando disponibile. |
| Un solo servizio eventi | Requisito; gli eventi sono 61 (CRV602) e 89 (CRV300), tutti normalmente inattivi. |
| Soglie nell'unità mostrata | Comprensibile per l'utente; unica conversione °F→°C per uniformità con la metrica `temp`. |
| Soglie predefinite solo per grandezze con riferimenti riconosciuti (dalla 1.1.0) | Temperature dell'aria, umidità e rugiada seguono ASHRAE TC 9.9; l'acqua refrigerata segue la prassi d'impianto. Set point, contaore, percentuali, portate e tensioni dipendono dal dimensionamento o dalla regione: valori generici produrrebbero falsi allarmi. Le soglie non derivano dai valori misurati. |
| Soglie predefinite nel codice, non nei parametri predefiniti del check | I parametri predefiniti di Checkmk valgono per tutti i servizi di un plugin; qui le soglie dipendono dal data ID. Assenza della chiave = soglia predefinita; chiave presente (anche "No levels") = valore della regola. |
| Soglia predefinita applicata solo se l'unità corrisponde | Se un firmware riportasse un data ID con un'unità diversa da quella attesa, la soglia verrebbe ignorata invece di essere applicata a una grandezza sbagliata. |
| Supersedes dei plugin `liebert_*` | Leggono singole righe della stessa tabella e creerebbero servizi duplicati (es. "Return Temperature" e "Return Air Temperature"), con soglie predefinite che mandavano in CRIT l'umidità. |
| `lgp_info` ("Liebert Info") non sostituito | Mostra l'identità della scheda (modello, FW, seriale), che il plugin non legge. |
| Mappe di stato predefinite solo per pochi enum | Le uniche con semantica chiara (System Status, Operating State, ATS). Gli altri enum sono informativi. |
| Nessun nome simbolico MIB negli eventi | Etichetta e codice bastano; evita di incorporare 1450 nomi nel plugin. |
| Severità della scheda prima della tabella predefinita (1.2.0) | La configurazione della scheda è una scelta esplicita di chi gestisce l'impianto (decisione dell'utente). La tabella copre i firmware che non espongono la severità. |
| Ventole e valvola al 95 %: solo WARN | Non è un guasto ma assenza di riserva. I guasti (ventola ferma, perdita di flusso) sono CRIT tramite eventi e controlli incrociati. |
| Controlli incrociati invece di soglie assolute su portata e ventole | La portata nominale dipende dalla taglia; "nessun flusso con valvola aperta" e "ventole ferme con unità in marcia" sono validi per qualunque unità. |
| Scostamento solo verso l'alto | Raffreddare più del necessario non è un rischio per l'IT; le basse temperature assolute restano coperte dalle soglie dell'aria. |
| Tensioni 230/400 V ±10 %/±15 % | Decisione dell'utente; reti diverse (es. 208/480 V) richiedono una regola. Le tensioni diventano servizi solo se il misuratore è installato. |

---

## 7. Problemi incontrati e soluzioni

| Problema | Causa | Soluzione |
|---|---|---|
| Download MIB Rev 26 bloccato | policy di rete dell'ambiente di sviluppo | MIB caricate dall'utente; confronto preliminare su copie LibreNMS |
| Plugin installato ma nessun servizio; sul CRV300 comparivano servizi `liebert_*` | Checkmk 2.5 valida i plugin al caricamento e **scarta in silenzio** quelli non conformi. (1) Una sezione con più alberi deve annotare il parsing esattamente come `list[StringTable]`, e `from __future__ import annotations` rende le annotazioni stringhe non riconosciute. (2) La base di ogni `SNMPTree` deve essere la più lunga comune a tutte le colonne. | Annotazione corretta, `__future__` rimosso, base `…3.9.20.1` per gli eventi. Aggiunto `tests/test_checkmk_loading.py`, che replica i controlli del sorgente 2.5.0p12. |
| `cmk -L` mostrava i plugin, ma la GUI riportava "Unimplemented check vertiv_unity_…" | La GUI esegue discovery e check tramite l'**automation helper**, che tiene in memoria i plugin caricati all'avvio; `cmk -R` non lo ricarica. | `omd restart` dopo ogni installazione o aggiornamento. |
| Discovery dalla GUI senza risultati | dati SNMP in cache, raccolti prima dell'installazione | pulsante **Rescan** nella pagina di discovery |
| Valori diversi tra colonna testo e raw nello stesso walk (20.8 / 209) | le colonne sono lette in momenti diversi | il plugin usa il raw; nessun impatto |
| Umidità 6553.5, temperature −32768, mese 65409 | sentinelle non segnalate dalla scheda | regole di validità §5 |

Strumenti di diagnosi usati, tutti senza effetti sulla configurazione salvo `-I`:

- `cmk -L | grep vertiv` — plugin caricati;
- `cmk --snmpget <OID> <host>` — verifica della detection;
- `cmk --debug -vv --no-cache --detect-sections=vertiv_unity <host>` — fetch SNMP reale;
- `cmk --debug -v -I --detect-plugins=vertiv_unity_value,… <host>` — discovery da riga di comando, con errori visibili.

---

## 8. Test

| File | Contenuto |
|---|---|
| `tests/conftest.py` | simula il fetch SNMP di Checkmk dai walk: colonne allineate per indice, buchi riempiti con `""` come in `cmk/snmplib/_table.py` |
| `tests/test_vertiv_unity.py` | 22 test: parsing, normalizzazione istanze, discovery per modello (26/10/4 servizi sul CRV602; 32/23/3 sul CRV300), regole di discovery, valori e metriche, soglie, UNKNOWN su valori non validi, mappe di stato, change detection, eventi simulati attivi (default WARN, regole per codice e istanza, severità dalla scheda, eventi disabilitati, modulo sensori) |
| `tests/test_checkmk_loading.py` | 6 test: validazioni di caricamento di Checkmk 2.5 (firma del parsing, detection, alberi SNMP, supersedes, firme e parametri dei check plugin) |

Esecuzione:

```bash
CMK_PLUGIN_APIS=<checkmk>/packages/cmk-plugin-apis python3 -m pytest tests
```

Esito della versione 1.2.1: **44 test superati** (come la 1.2.0). Coprono soglie predefinite e solo WARN, controlli incrociati
(ventole ferme, assenza di flusso), tensioni, nuove mappe di stato, Cooling State dinamico, avviso su
modifica, severità degli eventi (tabella e precedenza della scheda) e il servizio Cooling Control Deviation
su entrambi i firmware. Verifica sul campo: discovery reale sul CRV602 con
41 servizi (26 numerici, 10 stati, 4 testi, 1 eventi; dalla 1.2.0 anche Cooling Control Deviation), come previsto dalla simulazione
([sviluppo/04-anteprima-servizi.md](sviluppo/04-anteprima-servizi.md)).

Strumenti di supporto in `tools/`:

| Script | Funzione |
|---|---|
| `flex_table.py` | ricostruisce la tabella da un walk |
| `preview_services.py` | elenca i servizi che il plugin creerebbe |
| `compare_models.py` | confronta due file di mapping |
| `check_mapping_vs_mib.py` | verifica i file di mapping contro le MIB; scrive la mappa OID → nome in `./oidmap.json` (o nel file indicato come terzo argomento) |
| `build_mkp.py` | costruisce il pacchetto |

---

## 9. Versionamento e rilascio

- Versionamento semantico; la versione corrente è nel file `VERSION`.
  - **patch:** correzioni;
  - **minor:** funzioni compatibili;
  - **major:** cambi di nomi di servizi, metriche o regole, che richiedono una nuova discovery o la
    revisione delle regole.
- Il pacchetto si costruisce con il tool `mkp` ufficiale (non con un archivio fatto a mano):

  ```bash
  CMK_MKP_TOOL=<checkmk>/packages/cmk-mkp-tool python3 tools/build_mkp.py
  ```

  Il risultato è `dist/vertiv_unity-<versione>.mkp`, con:
  - parte `cmk_addons_plugins`;
  - `version.min_required` = 2.5.0;
  - `version.packaged` = 2.5.0p12.
- Rilascio:
  1. aggiornare `VERSION` e `CHANGELOG.md`;
  2. eseguire i test;
  3. costruire l'MKP;
  4. commit, tag `v<versione>`, push.

---

## 10. Limiti noti e sviluppi possibili

- **CRV25 non verificato.** Dovrebbe funzionare senza modifiche; da controllare con
  `tools/preview_services.py` su un suo walk.
- **Mappe di stato provvisorie:** vanno validate con l'esercizio, in particolare 7528 e 4706 (standby, off).
- **Nomi dei servizi legati alle etichette della scheda:** un aggiornamento firmware che cambi un'etichetta
  rinomina il servizio, e serve una nuova discovery.
- **Eventi:** nessun orario di attivazione, perché la `lgpConditionsTable` non è disponibile. Sul FW 8.4 la
  severità non è esposta dalla scheda.
- **Test di loading:** replicano le validazioni della 2.5.0p12; con versioni successive di Checkmk vanno
  ricontrollate.
- **Possibili sviluppi:**
  - inventario HW/SW (modello, seriale, firmware) al posto dei servizi testo;
  - opzione per usare come soglie quelle configurate sulla scheda (5014, 5018, 5022, …);
  - un man page per `cmk -M`.

---

## 11. Struttura del repository

```
plugin/cmk_addons/plugins/vertiv_unity/   codice del plugin
dist/                                     pacchetti MKP rilasciati
docs/MANUALE-UTENTE.md                    guida utente e installazione
docs/DOCUMENTAZIONE-TECNICA.md            questo documento
docs/sviluppo/                            analisi e progettazione per fasi
docs/mapping/                             file di mapping delle schede
docs/walks/                               tabelle Flexible ricostruite
mibs/rev26/                               MIB ufficiali Vertiv Rev 26
tests/                                    test e walk reali
tools/                                    script di analisi e build
VERSION, CHANGELOG.md
```
