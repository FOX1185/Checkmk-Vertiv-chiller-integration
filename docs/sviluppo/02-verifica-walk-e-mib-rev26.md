# Fase 2 – Verifica sui walk reali e sulla MIB Rev 26

**Data:** 23 novembre 2026 · CRV25 non disponibile: escluso da questa fase.

## 0. Fonti

| File nel repository | Origine | Unità |
|---|---|---|
| `tests/snmpwalks/crv602_fw8.4.7` | `cmk --snmpwalk` (`walk Checkmk CRC602`) | CRV602, FW 8.4.7 |
| `tests/snmpwalks/crv300_fw6.5.0` | `cmk --snmpwalk` (`walk Checkmk CRV300`) | CRV300, FW 6.5.0 |
| `docs/walks/crv602_flex_table.tsv`, `crv300_flex_table.tsv` | tabella ricostruita con `tools/flex_table.py` | una riga per data point, tutte le colonne |
| `mibs/rev26/` | pacchetto ufficiale Vertiv Rev 26 (ottobre 2025) | |

I walk `snmpwalk` per colonna (`walk_<IP>.txt`) hanno gli stessi indici dei walk Checkmk
(verificato) e non sono stati aggiunti al repository. Nessuno dei walk contiene il gruppo `system`
(sysDescr/sysObjectID): per la detection si usano i valori già annotati nel documento di passaggio.

## 1. MIB Rev 26

- `LIEBERT_GP_FLEXIBLE.MIB` è **identica** alla versione 2013 usata nella fase 1: struttura confermata.
- Tutti gli OID dei file di mapping (eventi 40 + 91, oggetti legacy 7 + 173) esistono con lo stesso nome.
- `LIEBERT_GP_FLEXIBLE_COND.MIB` definisce 1450 `lgpCondId` (prima 1280); tutti i 116 codici evento delle
  due unità sono definiti.
- `lgpAgentDeviceId` (`…42.2.4.2.1.2.1`) identifica il prodotto:
  - CRV602 → `.4.12.2.5` = **`lgpCRC300600`** (la macchina è una Liebert **CRC**, modello
    "Liebert CRC305/CRC602": conferma il sysDescr `VERTIV CRC602`);
  - CRV300 → `.4.3.11.1` = **`lgpIcomCRtypeCRV`**.
- Modello scheda: entrambe `IS-UNITY-DP`.

## 2. Colonne estese: popolate

| Colonna | CRV602 (152 righe) | CRV300 (262 righe) | Note |
|---|---|---|---|
| `.20.1.10` etichetta | 152 | 262 | sempre |
| `.20.1.20` valore stringa | 152 | 262 | sempre, anche enum (testo) ed eventi |
| `.20.1.30` unità stringa | 63 | 89 | solo numerici (`deg C`, `% RH`, `%`, `hr`, `m3/h`, `Pa`, `VAC`, …) |
| `.30.1.10` int | 42 | 62 | int16/int32 |
| `.30.1.20` uint | 30 | 87 | uint16/uint32 **ed enum** (codice numerico) |
| `.30.1.30` decimali | 63 | 92 | numerici |
| `.30.1.40` tipo | 152 | 262 | **sempre** |
| `.30.1.50` accesso | 152 | 262 | **sempre** |
| `.30.1.60` unità enum | 63 | 92 | numerici (0 = nessuna unità) |
| `.30.1.70` descrizione | 152 | 262 | sempre |

Tipi osservati: `int16`, `uint16`, `int32`, `enum`, `text`, `time32`, `event16`. La scala è coerente:
`valore = raw / 10^decimali` (es. 4291: raw 209, dec 1 → 20.8 °C).

`1.2.1` è sempre in °C (unità 4125/4126), `1.2.2` sempre in °F (4127/4128): **confermato**.

## 3. Valori non validi – comportamento reale

| Caso | Valore stringa | Raw | Esempi |
|---|---|---|---|
| int16 non disponibile | `Unavailable` | int = **2147483647** | 5059.x, 4096–4115, 5005–5007 |
| int32 non disponibile | `Unavailable` | int = 2147483647 | 5900, 5901 |
| uint16 non disponibile | `Unavailable` | uint = **4294967295** | 7527, 5079, 5081, 4869, 4870 |
| enum non disponibile | `Unavailable` | uint = 4294967295 | CRV602 7536 Monitoring ON/OFF |
| non supportato | `No Support` | colonna raw assente | 8077.3, 8078.2 |
| testo vuoto | `` | — | 5057.x, 6109–6118 |
| **sentinella non segnalata** uint16 | `6553.5` | uint = **65535** | CRV602 5028 Return Humidity |
| **sentinella non segnalata** int16 | `-32768` | int = **−32768** | CRV300 5668–5671 |
| **valore implausibile** | `65409` | uint = 65409 | CRV300 4868 Calculated Next Maintenance Month |

I casi in grassetto **non** sono marcati dalla scheda: il valore stringa sembra valido. Vanno riconosciuti
dal plugin con il raw (`65535` per uint16, `−32768` per int16). Per 4868 (mese, atteso 1–12) serve un
controllo di plausibilità specifico. Effetto collaterale: la vista °F di 5668 vale `-58950` (conversione
della sentinella).

## 4. Eventi

- `lgpConditionsTable` (`…3.2.3`) → **`No Such Object`** su entrambe le unità; `lgpConditionsPresent = 0`.
  La tabella delle condizioni **non è implementata**: tipo/severità dalla MIB Conditions non sono disponibili.
- I data point evento (`1.2.100.*`, `1.3.20.100.*`) hanno tipo `event16`, valore stringa
  `Active Event`/`Inactive Event` e **nessuna colonna numerica**. Fonte unica per il servizio eventi.
- Severità disponibile solo sul CRV300 e solo per 16 eventi configurabili, tramite le coppie
  `<nome> - Event Control` (enabled/disabled) e `<nome> - Event Type` (Message/Warning/Alarm).
  Esempi reali: `Shutdown - Loss Of Power` disabilitato; `Ext Humidifier Lockout` e `Condenser 1 Issue` =
  Warning; gli altri = Alarm.
- CRV300 espone anche la `lgpConditionControlTable` legacy (16 righe): stessa informazione, non necessaria.

## 5. Classificazione automatica (ramo `1.2.1`)

| Classe (tipo + accesso) | CRV602 validi / non validi | CRV300 validi / non validi |
|---|---|---|
| numerico, sola lettura (misure) | 14 / 13 | 13 / 32 |
| numerico, lettura-scrittura (set point, soglie, bande, contaore) | 12 / 0 | 20 / 0 |
| enum, sola lettura (stati) | 8 / 0 | 8 / 0 |
| enum, lettura-scrittura (modalità di controllo) | 2 / 1 | 15 / 0 |
| enum `Event Control`/`Event Type` (configurazione eventi) | — | 32 / 0 |
| testo / data-ora | 4 / 0 | 3 / 10 |

Nessuna etichetta duplicata tra data ID diversi sulla stessa unità: l'etichetta (+ istanza) è utilizzabile
come nome del servizio.

Il ramo `1.3.20` (dispositivo "Sensor", Server Class = MONITOR) contiene solo stato/modello del modulo
sensori, i 10 slot (vuoti) e 2 eventi: si usano solo i 2 eventi.

## 6. Punti chiusi rispetto alla fase 1

| Punto aperto | Esito |
|---|---|
| Colonne estese popolate? | Sì, tipo e accesso sempre; unità e scala per tutti i numerici |
| `1.2.2` = °F? | Sì |
| Sentinella 6553.5 / −32768 | Confermati come raw 65535 / −32768, non segnalati dalla scheda |
| `lgpConditionsTable` | Non implementata |
| Rev 26 | Acquisita, nessuna differenza rilevante |
| Community | Sola lettura (confermato dall'utente) |
