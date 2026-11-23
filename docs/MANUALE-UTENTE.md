# Manuale utente – plugin `vertiv_unity` 1.0.0

Monitoraggio SNMP in Checkmk delle unità di condizionamento **Vertiv/Liebert** con scheda di rete
**IntelliSlot Unity** (es. Liebert CRV, CRC).

---

## 1. Cosa fa

Il plugin legge dalla scheda Unity **tutti i parametri che l'unità rende disponibili** e crea
automaticamente un servizio Checkmk per ciascuno. Non serve configurare OID o modelli: il plugin riconosce
da solo tipo, unità di misura e decimali di ogni valore.

| Tipo di servizio | Esempi | Cosa mostra |
|---|---|---|
| **Valori numerici** | Return Air Temperature, Supply Humidity, Fan Speed, Fluid Flow Rate, Fan Hours | valore con unità, grafico, soglie configurabili |
| **Impostazioni numeriche** | Air Temperature Set Point, Cooling Proportional Band, High Supply Air Temperature Threshold | valore e grafico; avviso opzionale se qualcuno le modifica |
| **Stati** | System Status, System Operating State, Unit Operating State, ATS Power Supply Status | stato attuale e codice, con valutazione OK/WARN/CRIT |
| **Modalità** | Fan Control Mode, Water Valve Control Mode, Air Temperature Control Sensor | modalità attuale; avviso opzionale se cambia |
| **Testi** | System Model Number, System Serial Number, Firmware Version, System Name | valore (sempre OK) |
| **Events** | un solo servizio | eventi/allarmi attivi con descrizione e codice |

Il nome del servizio è quello che la scheda assegna al parametro, ad esempio `Return Air Temperature`. Se un
parametro ha più sensori, si aggiunge il numero (`Supply Air Sensor Temperature 2`). Nei dettagli di ogni
servizio si leggono il **data ID**, il tipo e se il valore è in sola lettura o modificabile.

Servizi tipici:

| Unità | Servizi |
|---|---|
| CRC602 | 41 (26 numerici, 10 stati/modalità, 4 testi, Events) |
| CRV300 | 59 (32 numerici, 23 stati/modalità, 3 testi, Events) |

### Valori non disponibili

I parametri che la scheda dichiara ma per cui non ha un valore valido **non diventano servizi**. Rientrano in
questo caso:
- valori "Unavailable" o "No Support";
- sensori non collegati;
- valori fittizi come `6553.5`, `-32768` o il mese `65409`.

Se un valore già monitorato diventa non disponibile (es. un sensore scollegato), il servizio va in
**UNKNOWN** con il motivo.

### Stati predefiniti

| Servizio | OK | WARN | CRIT |
|---|---|---|---|
| System Status | Normal Operation | StartUp, Normal with Warning | Normal with Alarm, Abnormal Operation |
| System Operating State | Run, Standby | Display Off, Remote Off, Monitoring Off | Lockout |
| Unit Operating State | on, standby | off | — |
| System On/Off Control | on | off | — |
| ATS Power Supply 1/2 Status | OK | — | Not OK |
| tutti gli altri stati e modalità | qualunque valore | — | — |

Si possono cambiare con una regola (§4.2).

### Servizio Events

Elenca gli eventi della scheda attivi in quel momento: CRC602 ne controlla 61, CRV300 89. Riepiloghi
tipici: `No active events (61 monitored)` oppure `1 active event(s), Clogged Air Filter [5118]`.

Stato di un evento attivo, nell'ordine:
1. regola per codice evento, se presente (§4.3);
2. se sulla scheda l'evento è **disabilitato** → ignorato;
3. se la scheda indica la severità (Message / Warning / Alarm) → OK / WARN / CRIT;
4. altrimenti → **WARN** (modificabile).

La severità e l'abilitazione per evento sono disponibili solo su alcuni firmware. Sul CRV300 riguardano
16 eventi configurabili.

Quando la scheda riporta l'evento come inattivo, il servizio torna OK.

---

## 2. Requisiti

- Checkmk **2.5.0 o superiore**: Community o edizioni commerciali.
- Scheda IntelliSlot Unity con SNMP abilitato. Basta una community in **sola lettura**: il plugin non
  scrive mai sulla scheda.
- Host configurato in Checkmk come dispositivo SNMP (v2c consigliato).

Testato con:

| Versione Checkmk | Unità | Scheda |
|---|---|---|
| Checkmk Community 2.5.0p12 (Docker) | Liebert CRV300 | Unity FW 6.5.0 |
| Checkmk Community 2.5.0p12 (Docker) | Liebert CRC602 | Unity FW 8.4.7 |

---

## 3. Installazione

Il pacchetto è `dist/vertiv_unity-1.0.0.mkp`. Negli esempi:
- il sito si chiama `cmk`;
- `<container>` è il nome del container Docker di Checkmk (`docker ps`).

### 3.1 Prima di iniziare: rimuovere un'eventuale copia manuale

Se in passato i file del plugin sono stati copiati a mano, vanno rimossi. Altrimenti il pacchetto non si
installa, perché trova file "non pacchettizzati" con lo stesso nome.

```bash
docker exec -u cmk <container> rm -rf /omd/sites/cmk/local/lib/python3/cmk_addons/plugins/vertiv_unity
```

### 3.2 Installare il pacchetto

Copiare il file nel container:

```bash
docker cp dist/vertiv_unity-1.0.0.mkp <container>:/tmp/
```

Aggiungere e attivare il pacchetto come utente del sito:

```bash
docker exec -u cmk <container> bash -lc 'mkp add /tmp/vertiv_unity-1.0.0.mkp && mkp enable vertiv_unity 1.0.0'
```

In alternativa, se l'edizione la prevede, si può usare la GUI: **Setup → Maintenance → Extension
packages → Upload package**, poi attivare il pacchetto.

### 3.3 Riavviare il sito (obbligatorio)

```bash
docker exec -u cmk <container> omd restart
```

> **Importante:** non basta `cmk -R`. L'interfaccia web esegue discovery e controlli tramite un processo
> (*automation helper*) che carica i plugin solo all'avvio del sito. Senza `omd restart`, la discovery dalla
> GUI non trova nulla oppure mostra servizi **"Unimplemented check vertiv_unity_… – Check plug-in not
> implemented"**.

### 3.4 Verificare che il plugin sia caricato

```bash
docker exec -u cmk <container> bash -lc 'cmk -L | grep vertiv'
```

Devono comparire 4 righe:

```
vertiv_unity_events     snmp
vertiv_unity_state      snmp
vertiv_unity_text       snmp
vertiv_unity_value      snmp
```

Se non compaiono, vedere §6.

### 3.5 Discovery dei servizi

Per ogni unità:

1. **Setup → Hosts →** host → **Service discovery** (oppure "Run service discovery").
2. Premere **Rescan**. Senza il Rescan, la pagina può mostrare dati in cache raccolti prima
   dell'installazione e non trovare nulla di nuovo.
3. I nuovi servizi compaiono tra gli *undecided*: aggiungerli con **Accept all** o selezionandoli.
4. Tra i servizi **vanished** compaiono quelli dei plugin Liebert standard di Checkmk, che questo plugin
   sostituisce: "Status Liebert …", "System events", "Maintenance", "Return Temperature",
   "Supply Temperature", "Supply/Return Humidity", "Cooling Capacity (Primary)", "Fan Speed" (versione
   Liebert) e simili. **Rimuoverli.**
5. **Activate changes.**

"Liebert Info" (modello, firmware e seriale della scheda) non viene sostituito e può restare.

---

## 4. Configurazione

Le regole sono in **Setup → Services → Service monitoring rules**: cercare *Vertiv Unity*. La regola di
discovery è in **Setup → Services → Discovery rules**. Nelle regole per servizio, la condizione
"Parameter (service name)" accetta il nome del servizio o un'espressione regolare (es.
`Return Air Temperature` oppure `Supply Air Sensor Temperature.*`).

### 4.1 Vertiv Unity – numeric parameters

| Opzione | Effetto |
|---|---|
| Upper levels | WARN/CRIT se il valore **supera** le soglie |
| Lower levels | WARN/CRIT se il valore **scende sotto** le soglie |
| State if the value differs from the one found at discovery | stato da assegnare se un'impostazione viene modificata (OK = controllo disattivato) |

Le soglie sono nell'unità mostrata dal servizio: °C per le temperature, % per umidità e percentuali, h per i
contaore, m³/h per le portate e così via. Non ci sono soglie predefinite.

Esempi:
- *Return Air Temperature*: Upper levels 27 / 30.
- *Air Filter Hours*: Upper levels 2000 / 2500, come promemoria manutenzione.
- *Chilled Water Inlet Temperature*: Lower levels 6 / 4.
- *Air Temperature Set Point*: "State if the value differs…" = WARN, per accorgersi di modifiche al set
  point.

Dopo una modifica voluta di un set point, rifare la discovery del servizio per accettare il nuovo valore.

### 4.2 Vertiv Unity – states and modes

| Opzione | Effetto |
|---|---|
| Map values to states | elenco *valore → stato* che sostituisce gli stati predefiniti per quei valori (il valore è il testo mostrato, senza distinzione tra maiuscole e minuscole) |
| State if the value differs from the one found at discovery | avviso se la modalità/stato cambia rispetto alla discovery |

Esempi:
- *Unit Operating State*: `standby` → WARN, se l'unità non deve mai andare in standby.
- *Cooling State*: `off` → CRIT.
- *Fan Control Mode*: "State if the value differs…" = WARN.

### 4.3 Vertiv Unity – events

| Opzione | Effetto |
|---|---|
| State of an active event without known severity | predefinito WARN |
| State per event code | per un codice (es. `5118`) o una singola istanza (es. `4729.3`): OK, WARN, CRIT, UNKNOWN o **Ignore** |

Esempi:
- `4720` (Smoke Detected) → CRIT;
- `4723` (Water Under Floor) → CRIT;
- `7537` (Filter Maintenance Due) → WARN;
- `7561` (Custom Alarm) → Ignore, se non usato.

Il codice di un evento è quello tra parentesi quadre nell'output del servizio. Gli elenchi dei codici per
modello sono in `docs/mapping/*_SNMP_Events.txt`.

### 4.4 Vertiv Unity discovery

| Opzione | Predefinito | Effetto |
|---|---|---|
| Numeric settings | sì | servizi per set point, bande, soglie e contaore |
| Control modes | sì | servizi per le modalità di controllo modificabili |
| Text values | sì | servizi per modello, seriale, firmware, nome |
| Exclude data IDs | — | data ID da non monitorare (es. `5049`, oppure `5059.3` per una sola istanza); il data ID è nei dettagli del servizio |

Dopo una modifica di questa regola, rifare la discovery: Rescan, poi rimuovere i servizi *vanished*.

---

## 5. Aggiornamento e disinstallazione

**Aggiornamento** a una nuova versione `X.Y.Z`:

```bash
docker cp dist/vertiv_unity-X.Y.Z.mkp <container>:/tmp/
```

```bash
docker exec -u cmk <container> bash -lc 'mkp add /tmp/vertiv_unity-X.Y.Z.mkp && mkp enable vertiv_unity X.Y.Z && omd restart'
```

Poi Rescan della discovery, se le note di rilascio lo indicano.

**Disinstallazione:**

```bash
docker exec -u cmk <container> bash -lc 'mkp disable vertiv_unity 1.0.0 && mkp remove vertiv_unity 1.0.0 && omd restart'
```

Poi rifare la discovery: i servizi del plugin risultano *vanished*, mentre i servizi Liebert standard
ricompaiono.

**Elenco dei pacchetti installati:** `mkp list`.

---

## 6. Risoluzione dei problemi

| Sintomo | Causa probabile | Cosa fare |
|---|---|---|
| `cmk -L \| grep vertiv` non mostra nulla | pacchetto non attivo, oppure plugin non caricato per un errore | `mkp list`; poi `cmk --debug -v -I --detect-plugins=vertiv_unity_value <host>` e inviare l'output |
| "Unimplemented check vertiv_unity_…" nella GUI | sito non riavviato dopo l'installazione | `omd restart`, poi Rescan |
| La discovery dalla GUI non trova nuovi servizi | dati in cache | pulsante **Rescan** |
| Ancora nessun servizio | l'unità non viene riconosciuta | verificare `cmk --snmpget .1.3.6.1.2.1.1.2.0 <host>` (deve iniziare con `.1.3.6.1.4.1.476.1.42`) e `cmk --snmpget .1.3.6.1.4.1.476.1.42.3.9.10.0 <host>` (deve restituire un numero) |
| Servizi doppi (es. "Return Temperature" e "Return Air Temperature") | servizi Liebert standard rimasti dalla discovery precedente | rimuovere i servizi *vanished* |
| Servizio in UNKNOWN "Value not available" | sensore scollegato o valore non valido sulla scheda | controllare l'unità; se il parametro non serve, escluderlo (§4.4) |
| Un servizio ha cambiato nome dopo un aggiornamento firmware | la scheda ha cambiato l'etichetta del parametro | rifare la discovery e aggiornare le regole che usano il vecchio nome |

Per verificare cosa legge il plugin da un'unità, senza modificare nulla:

```bash
docker exec -u cmk <container> bash -lc 'cmk --debug -vv --no-cache --detect-sections=vertiv_unity <host> 2>&1 | tail -40'
```

---

## 7. Prova senza le unità reali (facoltativa)

1. Copiare un walk salvato, ad esempio `tests/snmpwalks/crv602_fw8.4.7`, in
   `/omd/sites/cmk/var/check_mk/snmpwalks/<nome-host>`.
2. I walk salvati non contengono il `sysObjectID`: aggiungere come **prima riga** del file:
   `.1.3.6.1.2.1.1.2.0 .1.3.6.1.4.1.476.1.42`
3. Creare l'host `<nome-host>` con IP 127.0.0.1 e SNMP v2c, e una regola **"Simulating SNMP by using a
   stored SNMP walk"** che lo includa.
4. Fare la discovery come al §3.5.
