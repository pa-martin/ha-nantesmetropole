"""Constants for the Nantes Métropole integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "nantesmetropole"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_INFRASTRUCTURE_TYPE = "infrastructure_type"
CONF_INFRASTRUCTURES = "infrastructures"

DATASET_EQUIPMENTS = "244400404_equipements-publics-nantes-metropole"
DATASET_SCHEDULES = "244400404_horaires-equipements-publics-nantes-metropole"

UPDATE_INTERVAL = timedelta(minutes=15)

INFRASTRUCTURE_TYPES: list[str] = [
    "Armée",
    "Cinéma",
    "Collège",
    "Déchet",
    "Ecole",
    "Culturelle",
    "Elémentaire",
    "Gendarmerie",
    "Insertion",
    "Jeunesse",
    "Mairie",
    "Maternelle",
    "Médiathèque",
    "Monument",
    "Musée, Château",
    "Nantes Métropole",
    "Organisme public",
    "Parc",
    "Parc en Enclos",
    "Parc Relais",
    "Parking Ouvrage",
    "Personne agée",
    "Petite enfance",
    "Police",
    "Pompiers",
    "Primaire",
    "Salle d'exposition",
    "Salle de spectacle",
    "Salle et terrain de sport",
    "Santé",
    "Service",
    "Service de l'Etat",
    "Social",
    "Urgence sociale",
    "Vie associative",
]
