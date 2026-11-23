# Anteprima dei servizi (simulazione sui walk reali)

Generata con `tools/preview_services.py`, parametri predefiniti, nessuna regola utente.

## crv602_fw8.4.7

| Servizio | Tipo | Stato | Output | Metrica |
|---|---|---|---|---|
| Return Air Temperature | numerico | OK | 20.9 °C | temp |
| Supply Air Temperature | numerico | OK | 19.4 °C | temp |
| Remote Sensor Average Temperature | numerico | OK | 18.8 °C | temp |
| Cooling Proportional Band | numerico (impostazione) | OK | 3.0 K | vertiv_unity_temp_delta |
| Humidity Set Point | numerico (impostazione) | OK | 50.0 % | humidity |
| Humidification Proportional Band | numerico (impostazione) | OK | 5.0 % | humidity |
| Remote Sensor Temperature 1 | numerico | OK | 18.8 °C | temp |
| Fan Speed | numerico | OK | 50 % | vertiv_unity_percent |
| Supply Air Temperature Set Point | numerico (impostazione) | OK | 19.0 °C | temp |
| Return Air Temperature Set Point | numerico (impostazione) | OK | 32.0 °C | temp |
| Electric Reheater Hours | numerico (impostazione) | OK | 0 h | vertiv_unity_hours |
| Humidifier Hours | numerico (impostazione) | OK | 0 h | vertiv_unity_hours |
| Fan Hours | numerico (impostazione) | OK | 238 h | vertiv_unity_hours |
| Chilled Water Valve Hours | numerico (impostazione) | OK | 238 h | vertiv_unity_hours |
| Chilled Water Valve Open Position | numerico | OK | 38 % | vertiv_unity_percent |
| Fluid Flow Rate | numerico | OK | 0.3 m³/h | vertiv_unity_flow_m3h |
| Chilled Water Inlet Temperature | numerico | OK | 15.5 °C | temp |
| Chilled Water Outlet Temperature | numerico | OK | 19.9 °C | temp |
| Air Filter Hours | numerico (impostazione) | OK | 238 h | vertiv_unity_hours |
| Supply Air Sensor Temperature 1 | numerico | OK | 19.9 °C | temp |
| Supply Air Sensor Temperature 2 | numerico | OK | 19.0 °C | temp |
| Return Air Sensor Temperature 1 | numerico | OK | 20.9 °C | temp |
| Return Sensor Humidity | numerico | OK | 66.4 % | humidity |
| Remote Sensor Air Temperature Set Point | numerico (impostazione) | OK | 23.0 °C | temp |
| Supply Air Theoretical Humidity | numerico | OK | 75.8 % | humidity |
| Condensate Pump Hours | numerico (impostazione) | OK | 0 h | vertiv_unity_hours |
| System Status | stato | OK | Normal Operation (code 1) |  |
| Server Class | stato | OK | AIR (code 2) |  |
| Cooling State | stato | OK | on (code 1) |  |
| Electric Reheat State | stato | OK | off (code 0) |  |
| Dehumidifier State | stato | OK | off (code 0) |  |
| Humidifier State | stato | OK | off (code 0) |  |
| Water Valve Control Mode | stato (impostazione) | OK | SupplyAirAverageTemp (code 3) |  |
| Fan Control Mode | stato (impostazione) | OK | ReturnAirMaxTemp (code 1) |  |
| System Operating State | stato | OK | Run (code 0) |  |
| Teamwork Status | stato | OK | Single (code 0) |  |
| System Model Number | testo | OK | Liebert CRC305/CRC602 | |
| System Serial Number | testo | OK | CRC602-XXXXX | |
| Firmware Version | testo | OK | 1.03.000.00 | |
| PACC Controller Firmware Version | testo | OK | 1.03.000.00 | |
| Events | eventi | OK | No active events (61 monitored) | vertiv_unity_active_events |

## crv300_fw6.5.0

| Servizio | Tipo | Stato | Output | Metrica |
|---|---|---|---|---|
| Return Air Temperature | numerico | OK | 22.5 °C | temp |
| Supply Fluid Temperature | numerico | OK | 21.5 °C | temp |
| High Supply Fluid Temperature Threshold | numerico (impostazione) | OK | 99.0 °C | temp |
| Auto Restart Delay | numerico (impostazione) | OK | 5 s | vertiv_unity_seconds |
| Supply Air Temperature | numerico | OK | 21.2 °C | temp |
| Return Dew Point | numerico | OK | 15.2 °C | temp |
| Air Temperature Set Point | numerico (impostazione) | OK | 21.0 °C | temp |
| Cooling Proportional Band | numerico (impostazione) | OK | 2.4 K | vertiv_unity_temp_delta |
| Heating Proportional Band | numerico (impostazione) | OK | 5.0 K | vertiv_unity_temp_delta |
| Air Temperature Dead Band | numerico (impostazione) | OK | 0.2 K | vertiv_unity_temp_delta |
| High Supply Air Temperature Threshold | numerico (impostazione) | OK | 26.7 °C | temp |
| Low Supply Air Temperature Threshold | numerico (impostazione) | OK | 8.0 °C | temp |
| High Return Air Temperature Threshold | numerico (impostazione) | OK | 40.0 °C | temp |
| Supply Humidity | numerico | OK | 69.4 % | humidity |
| Return Humidity | numerico | OK | 63.5 % | humidity |
| Humidity Set Point | numerico (impostazione) | OK | 45 % | humidity |
| Humidification Proportional Band | numerico (impostazione) | OK | 5 % | humidity |
| Dehumidification Proportional Band | numerico (impostazione) | OK | 5 % | humidity |
| Humidity Dead Band | numerico (impostazione) | OK | 5.0 % | humidity |
| High Return Humidity Threshold | numerico (impostazione) | OK | 99.0 % | humidity |
| Low Return Humidity Threshold | numerico (impostazione) | OK | 1.0 % | humidity |
| Fan Speed Proportional Band | numerico (impostazione) | OK | 4.0 K | vertiv_unity_temp_delta |
| Fan Speed Manual Set Point | numerico (impostazione) | OK | 70 % | vertiv_unity_percent |
| Fan Speed Maximum Set Point | numerico (impostazione) | OK | 50 % | vertiv_unity_percent |
| Fan Speed Minimum Set Point | numerico (impostazione) | OK | 40 % | vertiv_unity_percent |
| BMS Timeout Period | numerico (impostazione) | OK | 0 min | vertiv_unity_minutes |
| Operating Efficiency | numerico | OK | 75 % | vertiv_unity_percent |
| Fan Speed | numerico | OK | 40 % | vertiv_unity_percent |
| Cooling Capacity (Primary) | numerico | OK | 38 % | vertiv_unity_percent |
| Reheat Utilization | numerico | OK | 0 % | vertiv_unity_percent |
| SuperSaver request sent to CApCom Master | numerico | OK | 0 % | vertiv_unity_percent |
| Power Meter Status | numerico | OK | 0 | vertiv_unity_value |
| System Status | stato | OK | Normal Operation (code 1) |  |
| Server Class | stato | OK | AIR (code 2) |  |
| Unit Operating State | stato | OK | on (code 1) |  |
| Unit Control Mode | stato | OK | Internal (Auto) (code 0) |  |
| Air Temperature Control Sensor | stato (impostazione) | OK | Supply (code 0) |  |
| Remote Sensor Temperature Calculation | stato (impostazione) | OK | Average (code 0) |  |
| Fan Control Mode | stato (impostazione) | OK | Internal (Auto) (code 0) |  |
| Fan Control Sensor | stato (impostazione) | OK | Return (code 2) |  |
| Remote Sensor Function 1 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 2 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 3 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 4 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 5 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 6 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 7 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 8 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 9 | stato (impostazione) | OK | Disable (code 0) |  |
| Remote Sensor Function 10 | stato (impostazione) | OK | Disable (code 0) |  |
| Unit Operating State Reason | stato | OK | Reason Unknown (code 0) |  |
| System On/Off Control | stato (impostazione) | OK | on (code 1) |  |
| Automatic Transfer Switch - Active Power Supply | stato | OK | Power Supply 1 (code 0) |  |
| Automatic Transfer Switch - Power Supply 1 Status | stato | OK | OK (code 0) |  |
| Automatic Transfer Switch - Power Supply 2 Status | stato | OK | OK (code 0) |  |
| System Model Number | testo | OK | Liebert CRV | |
| System Date and Time | testo | OK | 2026-11-23 15:25:51 | |
| System Name | testo | OK | UNIT-1 | |
| Events | eventi | OK | No active events (89 monitored) | vertiv_unity_active_events |
