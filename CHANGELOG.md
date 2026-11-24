# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versionamento semantico.

## [1.2.1] – 2026-11-24

Nessun cambiamento per servizi, soglie, stati o regole: non serve una nuova discovery.

### Modificato
- Costanti comuni (OID base della tabella flessibile, nomi dei tipi e degli accessi) in un unico modulo
  `lib/constants.py`, usato dal plugin e dagli script in `tools/` (contributo di jacklocke).
- Codice semplificato: niente duplicazioni per l'avviso su modifica e per le mappe di stato condivise;
  esclusioni della discovery calcolate una sola volta.
- Regola sulla severità degli eventi: lo stato scelto viene letto senza badare a maiuscole e spazi; un valore
  non riconosciuto fa usare la severità della scheda invece di ignorare l'evento.
- `tools/flex_table.py` usa i nomi completi di tipi e accessi (`read-only` invece di `ro`, `not specified`
  invece di `n/s`); rigenerate le tabelle in `docs/walks/`.
- `tools/check_mapping_vs_mib.py` scrive `oidmap.json` nella cartella corrente (o nel file indicato come
  terzo argomento), non più nella cartella delle MIB.

## [1.2.0] – 2026-11-23

### Aggiunto
- **Severità predefinita degli eventi:**
  - CRIT per fumo, acqua sotto il pavimento, incendio, perdita di flusso d'aria, guasto ventole, perdita di
    flusso d'acqua, guasto valvola, arresti dell'unità, sovratemperature, pompa condensa, comunicazione
    interna, alimentazione, riscaldatore;
  - OK per i messaggi Unit On/Off/Standby e Maintenance Completed.

  La severità configurata sulla scheda resta prioritaria.
- **Riserva di capacità:** WARN (senza CRIT) con Fan Speed, Chilled Water Valve Open Position o Cooling
  Capacity ≥ 95 %.
- **Controlli incrociati:**
  - CRIT se le ventole sono ferme con l'unità in marcia;
  - CRIT se la portata d'acqua è nulla con la valvola aperta ≥ 20 %.
- **Tensioni di alimentazione:** 230 V F-N e 400 V F-F, WARN ±10 %, CRIT ±15 %.
- **Nuovo servizio `Cooling Control Deviation`:** scostamento tra temperatura regolata (sensore e calcolo
  letti dalla scheda) e set point. WARN oltre +2 K, CRIT oltre +4 K. Nuova regola *Vertiv Unity – cooling
  control deviation* e nuova metrica `vertiv_unity_setpoint_deviation`.
- **Stati:**
  - Cooling State off con unità in marcia → WARN;
  - ATS su Power Supply 2 → WARN;
  - Unit/Fan Control Mode in manuale → WARN.

### Modificato
- Unit Operating State e System On/Off Control "off": da WARN a **CRIT**.
- **Avviso su modifica attivo per default** (WARN) per set point, soglie configurate sulla scheda, limiti
  dei ventilatori, modalità e sensori di controllo, stato del teamwork. Si disattiva con la regola
  (stato OK).
- Discovery necessaria solo per aggiungere `Cooling Control Deviation`.

## [1.1.0] – 2026-11-23

Non rilasciata separatamente: inclusa nella 1.2.0.

### Aggiunto
- **Soglie predefinite** per i parametri numerici con riferimenti riconosciuti (ASHRAE TC 9.9, prassi per
  l'acqua refrigerata):
  - aria di mandata e sensori ai rack: 27/32 °C, 15/12 °C;
  - aria di ripresa: 40/45 °C;
  - umidità di ripresa: 70/80 %, 20/15 %;
  - umidità di mandata: 80/90 %, 20/15 %;
  - punto di rugiada: 17/20 °C, −9/−12 °C;
  - acqua refrigerata in ingresso: 20/25 °C, 5/3 °C;
  - acqua refrigerata in uscita: 26/30 °C, 5/3 °C.
- Nei dettagli del servizio è indicato quando sono in uso le soglie predefinite.

### Modificato
- Regola *Vertiv Unity – numeric parameters*: ogni soglia configurata sostituisce quella predefinita;
  "No levels" la disattiva.
- Nessuna nuova discovery necessaria: dopo l'aggiornamento le soglie si applicano ai servizi esistenti.

## [1.0.0] – 2026-11-23

Prima versione.

### Aggiunto
- Sezione SNMP `vertiv_unity` sulla tabella LIEBERT-GP-FLEXIBLE-MIB, con detection per `sysObjectID`
  `.1.3.6.1.4.1.476.1.42` e presenza di `lgpFlexibleTableCount`.
- Discovery dinamica: un servizio per ogni parametro valido.
  - `vertiv_unity_value`: valori numerici, con metriche e soglie.
  - `vertiv_unity_state`: enum, con mappe di stato.
  - `vertiv_unity_text`: testi.
- Servizio `Events` (`vertiv_unity_events`) con gli eventi attivi:
  - eventi dell'unità e del modulo sensori;
  - severità e abilitazione dalla scheda, quando disponibili;
  - WARN predefinito se la severità non è nota.
- Esclusione dei valori non validi: Unavailable, No Support, sentinelle 65535/−32768/2147483647/4294967295,
  valori implausibili, testi vuoti.
- Regole:
  - *Vertiv Unity – numeric parameters*;
  - *Vertiv Unity – states and modes*;
  - *Vertiv Unity – events*;
  - *Vertiv Unity discovery*.
- 12 metriche aggiuntive (portate, ore, percentuali, delta di temperatura, …).
- Sostituzione (`supersedes`) dei 18 plugin `liebert_*` di Checkmk, per evitare servizi duplicati.
- 28 test sui walk reali di CRV300 (FW 6.5.0) e CRC602 (FW 8.4.7), compresi i controlli di caricamento di
  Checkmk 2.5.
- Pacchetto MKP costruito con il tool `mkp` ufficiale di Checkmk 2.5.0p12.

### Corretto durante lo sviluppo (prima del rilascio)
- Il plugin veniva scartato in silenzio da Checkmk:
  - annotazione della funzione di parsing (`list[StringTable]`);
  - base OID degli alberi eventi.
- Documentata la necessità di `omd restart` (automation helper della GUI) e del **Rescan** nella discovery.
