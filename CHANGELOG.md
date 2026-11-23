# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versionamento semantico.

## [1.1.0] – 2026-11-23

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
