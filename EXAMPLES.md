# Use Cases & Examples — swiss-energy-mcp

Real-world queries by audience. Indicate per example whether an API key is required. (Alle Tools in diesem Server benötigen **keinen API-Key**).

## 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

### Solarpotenzial auf Schulgebäuden prüfen
«Wir überlegen, auf den Dächern des Schulhauses in Wädenswil eine Solaranlage zu installieren. Wie gut ist die Eignung der Dachflächen dort?»
→ `energy_solar_potential(lat=47.2292, lon=8.6653, radius_m=1000)`
**Warum nützlich:** Schulbehörden können schnell eine erste Einschätzung der Solareignung ihrer Liegenschaften vornehmen, bevor sie teure Machbarkeitsstudien in Auftrag geben.

### Exkursion zu Wasserkraftwerken planen
«Welche Wasserkraftwerke gibt es im Umkreis von 20 km um unsere Schule in Chur, die wir auf einer Exkursion besichtigen könnten, und wie gross ist ihre Leistung?»
→ `energy_find_hydro_plants(lat=46.8503, lon=9.5319, radius_m=20000)`
**Warum nützlich:** Lehrpersonen finden unkompliziert reale Anschauungsobjekte für den Physik- oder Geografieunterricht direkt in der Region der Lernenden.

## 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

### Energiestadt-Label der Wohngemeinde
«Unsere Familie ist neu nach Uster gezogen. Ist Uster eigentlich eine offizielle Energiestadt und wie gut schneidet sie ab?»
→ `energy_find_energy_cities(name="Uster")`
**Warum nützlich:** Eltern, die Wert auf Nachhaltigkeit legen, erhalten sofort transparente Fakten zum energiepolitischen Engagement ihrer Wohngemeinde und können dies im Elternrat thematisieren.

### Windenergie in der Nachbarschaft
«Es gibt Gerüchte über neue Windräder. Wo stehen eigentlich die nächsten bestehenden Windenergieanlagen in unserer Region (Winterthur) und wie stark sind diese?»
→ `energy_find_wind_turbines(lat=47.4999, lon=8.7376, radius_m=15000)`
**Warum nützlich:** Faktenbasierte Information hilft, emotionale Diskussionen in der Gemeinde über erneuerbare Energien mit verlässlichen Daten des Bundesamts für Energie zu versachlichen.

## 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

### Regionales Energieprofil
«Ich bereite einen Leserbrief zur kantonalen Energiestrategie vor. Wie sieht eigentlich das komplette Energieprofil für die Region Luzern aktuell aus?»
→ `energy_location_profile(lat=47.0502, lon=8.3093, radius_m=20000)`
**Warum nützlich:** Bietet Bürgerinnen und Bürgern einen sofortigen, umfassenden Überblick über den aktuellen Stand der Energiewende in ihrer eigenen Region, aggregiert aus fünf verschiedenen Datenquellen.

### PV-Grossanlagen und Versorgungssicherheit
«Gibt es in der Nähe von Sion eigentlich grosse Photovoltaik-Anlagen, die nennenswert zur Winterproduktion beitragen?»
→ `energy_find_pv_installations(lat=46.2293, lon=7.3594, radius_m=30000)`
**Warum nützlich:** Macht abstrakte Begriffe wie "Winterstrom" an konkreten, lokalen Grosskraftwerken greifbar und zeigt, wie die Region zur nationalen Versorgungssicherheit beiträgt.

## 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

### Cross-Server: Energiestädte und offene Stadtdaten
«Lass uns die Energiestadt-Kennzahlen von Zürich abrufen und dann mit dem Zürcher Open-Data-Portal nach weiteren städtischen Nachhaltigkeits-Datensätzen suchen.»
→ `energy_find_energy_cities(name="Zürich")`
→ `zh_search_datasets(query="Nachhaltigkeit", limit=5)` (via [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp))
**Warum nützlich:** Demonstriert die Kombination von nationalen BFE-Daten mit kommunalen Open-Data-Katalogen, um umfassende Berichte für die öffentliche Verwaltung zu generieren.

### BFE-Datensätze erkunden
«Welche offenen Datensätze bietet das BFE auf opendata.swiss zum Thema Biogas an?»
→ `energy_search_bfe_datasets(query="biogas", limit=10)`
→ `energy_find_biogas_plants(lat=46.9480, lon=7.4474, radius_m=50000)`
**Warum nützlich:** Entwickler können direkt aus dem Chat heraus den Katalog der offenen Regierungsdaten durchsuchen und die gefundenen Themenbereiche sofort mit den geografischen Tools des Servers validieren.

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **das Solarpotenzial an einer bestimmten Adresse prüfen** | `energy_solar_potential` | Nein |
| **wissen, ob eine Gemeinde das Energiestadt-Label trägt** | `energy_find_energy_cities` | Nein |
| **alle Kraftwerke (Wasser, Wind, Solar) in meiner Region sehen** | `energy_location_profile` | Nein |
| **gezielt nach Wasserkraftwerken oder Windrädern suchen** | `energy_find_hydro_plants`, `energy_find_wind_turbines` | Nein |
| **herausfinden, wo die nächsten Photovoltaik-Grossanlagen stehen** | `energy_find_pv_installations` | Nein |
| **im Katalog des Bundesamts für Energie recherchieren** | `energy_search_bfe_datasets` | Nein |
| **prüfen, ob die GeoAdmin- und opendata.swiss-APIs erreichbar sind** | `energy_check_status` | Nein |
