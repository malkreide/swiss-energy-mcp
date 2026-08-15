# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `python scripts/record_fixtures.py`.

Eine Antwort je **Abfrageform**, nicht je Endpunkt: dieser Server spricht mit
zwei Hosts, aber in zehn Abfrageformen (`identify` je Layer, `find` je Layer,
`package_search` je Suche). Zwei Dateien wuerden die Portfolio-Regel erfuellen
und fast nichts belegen.

Die Antworten stammen aus dem echten `EnergyHTTPClient` (gleicher User-Agent,
gleiches Timeout, gleiche DNS-Pinning-Transportschicht wie im Betrieb),
abgegriffen ueber einen httpx-Response-Hook. Ausgeloest hat sie jeweils das
Werkzeug selbst — so belegt die Aufzeichnung auch, dass das Werkzeug genau
diese Abfrage schickt.

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der
Trefferzeilen. Kein Feld einer behaltenen Zeile ist angetastet, und `count`
steht wie geliefert — CKAN meldet dort die Gesamtzahl der Treffer, nicht die
Zahl der gelieferten Zeilen, und genau die liest der Server aus.

Die Fehlerpfade — Timeout, 5xx, leere Trefferliste, `success: false` — bleiben
handgeschrieben. Sie lassen sich nicht auf Zuruf aufzeichnen und sind als
Erfindung in Ordnung.

Aufnahmeort ist Mont Crosin im Berner Jura (47.18 N, 7.03 E, 10 km): der
einzige Punkt, an dem alle sieben BFE-Layer etwas liefern. Ein Satz, in dem
ein Layer leer ist, belegt dessen Form nicht.

## `find_energiestaedte_name.json`

- **Werkzeuge:** `energy_check_status`, `energy_find_energy_cities`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/find?layer=ch.bfe.energiestaedte&searchText=Z%C3%BCrich&searchField=name&lang=de&f=json&returnGeometry=false`
- **Auswahl:** ungekuerzt (1 Trefferzeilen)
- **Groesse:** 574 Bytes
- **SHA-256:** `fe35dcf5436f7a817952d282a0af82f6098204cda52f1cd7e953d605207d85d2`

## `identify_biogasanlagen.json`

- **Werkzeuge:** `energy_find_biogas_plants`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.biogasanlagen&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** ungekuerzt (2 Trefferzeilen)
- **Groesse:** 4597 Bytes
- **SHA-256:** `a3dd3bdbfa4eb75e7aa252a351063d5869e6a984eea508249bf93b103bdeadf5`

## `identify_elektrizitaetsproduktionsanlagen.json`

- **Werkzeuge:** `energy_find_power_plants`, `energy_location_profile`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.elektrizitaetsproduktionsanlagen&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** die ersten 5 von 201 Trefferzeilen, aus 155674 Bytes Rohantwort
- **Groesse:** 4941 Bytes
- **SHA-256:** `6759a618508c9209221da9145d6f38fc2cf94f990a68379b5335eb3679355192`

## `identify_energiestaedte.json`

- **Werkzeuge:** `energy_find_energy_cities`, `energy_location_profile`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.energiestaedte&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** die ersten 5 von 7 Trefferzeilen, aus 2999 Bytes Rohantwort
- **Groesse:** 2763 Bytes
- **SHA-256:** `175f40d82860181a6e6ade53fc59665ac7fb653ef3c2fd1025bf7759185444b1`

## `identify_photovoltaik_grossanlagen.json`

- **Werkzeuge:** `energy_find_pv_installations`, `energy_location_profile`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.photovoltaik-grossanlagen&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** ungekuerzt (1 Trefferzeilen)
- **Groesse:** 1015 Bytes
- **SHA-256:** `b83804fce9bdd9fe6cbab3a72691a017cc440cb66692f081e890a526af0aa29d`

## `identify_solarenergie_eignung_daecher.json`

- **Werkzeuge:** `energy_solar_potential`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.solarenergie-eignung-daecher&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** die ersten 5 von 201 Trefferzeilen, aus 385059 Bytes Rohantwort
- **Groesse:** 14486 Bytes
- **SHA-256:** `720d99fad2f5c2670e8a4671b7d59ad8b02a5ef159bac59ef68d7879fa98baa6`

## `identify_statistik_wasserkraftanlagen.json`

- **Werkzeuge:** `energy_find_hydro_plants`, `energy_location_profile`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.statistik-wasserkraftanlagen&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** die ersten 5 von 14 Trefferzeilen, aus 11872 Bytes Rohantwort
- **Groesse:** 5251 Bytes
- **SHA-256:** `1744e89924043a7bcf7b4ded4d80d1bbf1c9cef7114b81062caea9104f468033`

## `identify_windenergieanlagen.json`

- **Werkzeuge:** `energy_find_wind_turbines`, `energy_location_profile`
- **URL:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&geometryType=esriGeometryEnvelope&layers=all%3Ach.bfe.windenergieanlagen&tolerance=500&sr=2056&imageDisplay=1000%2C1000%2C96&mapExtent=2559025.4862437546%2C1215530.6016745574%2C2579025.4862437546%2C1235530.6016745574&lang=de&f=json&returnGeometry=false`
- **Auswahl:** die ersten 5 von 21 Trefferzeilen, aus 175660 Bytes Rohantwort
- **Groesse:** 37168 Bytes
- **SHA-256:** `0e6b0fb45393674a0f558d9022ece08b3a24bf219ddf0d39c212cb1278180b72`

## `package_search_rows1.json`

- **Werkzeuge:** `energy_check_status`
- **URL:** `https://ckan.opendata.swiss/api/3/action/package_search?q=solar+organization%3Abundesamt-fur-energie-bfe&rows=1&start=0&sort=score+desc`
- **Auswahl:** ungekuerzt (1 Trefferzeilen)
- **Groesse:** 31248 Bytes
- **SHA-256:** `de0ffe4b87c0f0aabc463c3eb06c5109b47a0bcdffbd7605fb65d8ba682fec28`

## `package_search_rows10.json`

- **Werkzeuge:** `energy_search_bfe_datasets`
- **URL:** `https://ckan.opendata.swiss/api/3/action/package_search?q=wasserkraft+organization%3Abundesamt-fur-energie-bfe&rows=10&start=0&sort=score+desc`
- **Auswahl:** die ersten 5 von 10 Trefferzeilen, aus 131298 Bytes Rohantwort
- **Groesse:** 90461 Bytes
- **SHA-256:** `deb0b1fcdd51cfa8ac0fa15b9ca50776a43bde14cb6834dbf4666df44b1b5fd4`
