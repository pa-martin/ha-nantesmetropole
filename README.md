# ha-nantesmetropole

Intégration Home Assistant permettant de créer des devices par type d'infrastructure de la ville de Nantes.

## Fonctionnalités

- 1 service de configuration par type d'infrastructure (Piscine, Déchet, etc.)
- Sélection multiple des infrastructures à créer comme devices
- Mise à jour de la sélection via les options de l'intégration
- Chaque device expose :
  - sa géolocalisation (latitude/longitude)
  - ses horaires d'ouverture du jour
  - son état d'ouverture (`open` / `closed`)

## Source des données

- `244400404_equipements-publics-nantes-metropole`
- `244400404_horaires-equipements-publics-nantes-metropole`
