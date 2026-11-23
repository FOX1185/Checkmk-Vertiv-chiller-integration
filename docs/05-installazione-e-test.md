# Installazione e test – plugin `vertiv_unity`

Checkmk Community 2.5.0p12 in Docker, sito `cmk`.

## 1. File del plugin

```
plugin/cmk_addons/plugins/vertiv_unity/
├── agent_based/vertiv_unity.py   sezione SNMP, discovery e check
├── rulesets/vertiv_unity.py      regole (soglie, stati, eventi, discovery)
└── graphing/vertiv_unity.py      metriche aggiuntive
```

Destinazione nel sito: `~/local/lib/python3/cmk_addons/plugins/vertiv_unity/`
(nel container: `/omd/sites/cmk/local/lib/python3/cmk_addons/plugins/vertiv_unity/`).

## 2. Copia nel container

Dalla macchina Docker, nella cartella del repository (sostituire `<container>` con il nome del container
Checkmk, visibile con `docker ps`):

```bash
docker cp plugin/cmk_addons/plugins/vertiv_unity <container>:/omd/sites/cmk/local/lib/python3/cmk_addons/plugins/
```

```bash
docker exec -u root <container> chown -R cmk:cmk /omd/sites/cmk/local/lib/python3/cmk_addons/plugins/vertiv_unity
```

Poi, come utente del sito:

```bash
docker exec -it -u cmk <container> bash -lc 'cmk -R && omd restart apache'
```

`cmk -R` carica i plugin di check; il riavvio di apache serve all'interfaccia web per vedere regole e metriche.

## 3. Prova senza toccare le unità reali (consigliata)

1. Copiare i walk nel sito:
   ```bash
   docker cp tests/snmpwalks/crv602_fw8.4.7 <container>:/omd/sites/cmk/var/check_mk/snmpwalks/test-crv602
   ```
   ```bash
   docker cp tests/snmpwalks/crv300_fw6.5.0 <container>:/omd/sites/cmk/var/check_mk/snmpwalks/test-crv300
   ```
2. Creare due host `test-crv602` e `test-crv300` con IP 127.0.0.1, SNMP v2c e la regola
   **"Simulating SNMP by using a stored SNMP walk"** attiva.
3. Il walk salvato non contiene `sysObjectID`: per la prova aggiungere in testa ai due file la riga
   `.1.3.6.1.2.1.1.2.0 .1.3.6.1.4.1.476.1.42`.
4. Eseguire:
   ```bash
   docker exec -it -u cmk <container> bash -lc 'cmk -vvII test-crv602 && cmk -v test-crv602'
   ```
   Si devono vedere i servizi elencati in `docs/04-anteprima-servizi.md`.

## 4. Attivazione sulle unità reali

Fare una **Service discovery** dei due host (`<IP>`, `<IP>`). Su questi host il plugin
sostituisce i plugin Checkmk `liebert_*`, che leggono singole righe della stessa tabella: i loro servizi
(es. "… Temperature") risultano *vanished* e vanno rimossi con la discovery.

## 5. Regole (Setup → Services → Service monitoring rules, cercare "Vertiv Unity")

| Regola | Uso |
|---|---|
| Vertiv Unity – numeric parameters | soglie WARN/CRIT superiori e inferiori per servizio; stato se un'impostazione cambia |
| Vertiv Unity – states and modes | mappa valore → stato per servizio; stato se una modalità cambia |
| Vertiv Unity – events | stato predefinito evento (WARN), stato per codice evento, ignora |
| Vertiv Unity discovery | includere/escludere impostazioni, modalità, testi; escludere data ID |

Il nome del servizio da usare nella condizione è quello mostrato in Checkmk (es. `Return Air Temperature`).

## 6. Pacchetto MKP (opzionale)

Dopo aver copiato i file nel sito:

```bash
docker exec -it -u cmk <container> bash -lc 'mkp template vertiv_unity'
```

Modificare il file indicato dal comando (`~/tmp/check_mk/vertiv_unity.manifest.temp`: versione, autore),
poi:

```bash
docker exec -it -u cmk <container> bash -lc 'mkp package tmp/check_mk/vertiv_unity.manifest.temp'
```

## 7. Test automatici (sviluppo)

Richiedono le API dei plugin Checkmk 2.5 (cartella `packages/cmk-plugin-apis` del sorgente Checkmk,
tag `v2.5.0p12`), `pytest` e `pydantic`:

```bash
CMK_PLUGIN_APIS=/percorso/checkmk/packages/cmk-plugin-apis python3 -m pytest tests
```

22 test sui due walk reali: discovery, sentinelle, soglie, metriche, stati, eventi attivi (simulati),
severità dalla scheda, regole.
