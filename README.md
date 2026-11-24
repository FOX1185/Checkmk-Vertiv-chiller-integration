# Checkmk – Vertiv Liebert IntelliSlot Unity (CRV / CRC) via SNMP

Plugin SNMP per **Checkmk 2.5** che monitora le unità di condizionamento Vertiv/Liebert con scheda
**IntelliSlot Unity**. Legge in modo dinamico tutti i parametri esposti dalla scheda: crea un servizio per
ogni parametro, con grafici e soglie/stati WARN-CRIT predefiniti per le funzioni principali (aria, acqua,
umidità, ventole, alimentazione, regolazione), sempre configurabili, più un servizio per gli eventi attivi.

**Versione corrente: 1.2.1** – pacchetto [`dist/vertiv_unity-1.2.1.mkp`](dist/vertiv_unity-1.2.1.mkp)

## Ambiente di test

| Componente | Versione / dettaglio |
|---|---|
| Checkmk | **Checkmk Community (Raw) 2.5.0p12**, installazione Docker, core Nagios |
| API plugin usate | `cmk.agent_based.v2`, `cmk.rulesets.v1`, `cmk.graphing.v1` |
| Versione minima dichiarata | Checkmk 2.5.0 |
| SNMP | v2c, community in sola lettura |

| Unità | Modello rilevato | Scheda di rete | Firmware scheda | Controllore | Device ID (lgpAgentDeviceId) | Esito |
|---|---|---|---|---|---|---|
| Liebert CRV300 | `Liebert CRV` | IS-UNITY-DP | **6.5.0.0** (`IS-UNITY_6.5.0.0_00018`) | iCOM (da Device ID) | `lgpIcomCRtypeCRV` | 60 servizi (32 numerici, 23 stati/modalità, 3 testi, eventi, regolazione) – verificato su walk |
| Liebert CRC602 (in progetto "CRV602") | `Liebert CRC305/CRC602` | IS-UNITY-DP | **8.4.7.0** (`IS-UNITY_8.4.7.0_00166`) | PACC FW 1.03.000.00 | `lgpCRC300600` | 42 servizi (26 numerici, 10 stati/modalità, 4 testi, eventi, regolazione) – **verificato in Checkmk** |
| Liebert CRV25 | — | — | 7.8.0.0 (`IS-UNITY_7.8.0.0_00083`) | — | — | non ancora verificato |

Nei walk di test (`tests/snmpwalks/`) seriali e nome di sistema sono sostituiti da segnaposto (`XXXX…`, `UNIT-1`).

MIB di riferimento: Vertiv **SNMP MIB Support Rev 26** (ottobre 2025), in `mibs/rev26/`.

## Documentazione

| Documento | Per chi |
|---|---|
| [docs/MANUALE-UTENTE.md](docs/MANUALE-UTENTE.md) | funzioni, **installazione**, configurazione delle regole, risoluzione problemi |
| [docs/DOCUMENTAZIONE-TECNICA.md](docs/DOCUMENTAZIONE-TECNICA.md) | architettura, componenti, dipendenze, scelte progettuali, problemi incontrati, test, rilascio |
| [CHANGELOG.md](CHANGELOG.md) | modifiche per versione |
| [docs/sviluppo/](docs/sviluppo/) | analisi per fasi: file di mapping e MIB, verifica sui walk, progettazione, anteprima servizi |

## Installazione rapida

```bash
docker cp dist/vertiv_unity-1.2.1.mkp <container>:/tmp/
```

```bash
docker exec -u cmk <container> bash -lc 'mkp add /tmp/vertiv_unity-1.2.1.mkp && mkp enable vertiv_unity 1.2.1 && omd restart'
```

Poi, per ogni unità: Service discovery → **Rescan** → accettare i nuovi servizi → rimuovere i servizi Liebert
standard *vanished* → Activate changes. Dettagli e avvertenze (copie manuali, `omd restart` obbligatorio) nel
[manuale](docs/MANUALE-UTENTE.md#3-installazione).

## Struttura

```
plugin/cmk_addons/plugins/vertiv_unity/   codice (agent_based, rulesets, graphing)
dist/                                     pacchetti MKP
docs/                                     documentazione, file di mapping, tabelle dai walk
mibs/rev26/                               MIB ufficiali Vertiv
tests/                                    test pytest e walk SNMP reali
tools/                                    analisi, anteprima servizi, build MKP
```
