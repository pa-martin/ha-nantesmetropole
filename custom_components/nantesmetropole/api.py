"""API client for Nantes Métropole open data datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from aiohttp import ClientSession

from .const import DATASET_EQUIPMENTS, DATASET_SCHEDULES

BASE_URL = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets"

WEEKDAY_FR = {
    0: "lundi",
    1: "mardi",
    2: "mercredi",
    3: "jeudi",
    4: "vendredi",
    5: "samedi",
    6: "dimanche",
}


@dataclass(slots=True)
class OpenRange:
    """One opening range for a day."""

    start: str
    end: str


@dataclass(slots=True)
class Infrastructure:
    """Infrastructure metadata."""

    name: str
    infra_type: str
    latitude: float | None
    longitude: float | None
    address: str | None


@dataclass(slots=True)
class InfrastructureState:
    """Infrastructure state and schedule."""

    infrastructure: Infrastructure
    opening_ranges: list[OpenRange]
    is_open: bool


class NantesMetropoleApi:
    """Access Nantes Métropole datasets."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_fetch_infrastructures(self, infra_type: str) -> list[Infrastructure]:
        """Fetch available infrastructures for one type."""
        where = self._build_type_where(infra_type)
        rows = await self._async_fetch_records(DATASET_EQUIPMENTS, where, limit=1000)

        infrastructures: dict[str, Infrastructure] = {}
        for row in rows:
            infrastructure = self._parse_infrastructure(row, infra_type)
            if infrastructure is None:
                continue
            infrastructures[infrastructure.name] = infrastructure

        if infrastructures:
            return sorted(infrastructures.values(), key=lambda item: item.name)

        # Fallback: at least return distinct names from schedule dataset.
        schedule_rows = await self._async_fetch_records(
            DATASET_SCHEDULES,
            f'type = "{_escape_value(infra_type)}"',
            select="nom",
            group_by="nom",
            limit=1000,
        )
        for row in schedule_rows:
            name = self._extract_name(row)
            if not name:
                continue
            infrastructures[name] = Infrastructure(
                name=name,
                infra_type=infra_type,
                latitude=None,
                longitude=None,
                address=None,
            )

        return sorted(infrastructures.values(), key=lambda item: item.name)

    async def async_fetch_infrastructure_state(
        self, infrastructure: Infrastructure, now_dt: datetime
    ) -> InfrastructureState:
        """Fetch opening schedules and state for one infrastructure."""
        weekday = WEEKDAY_FR[now_dt.weekday()]
        today = now_dt.date()
        where = (
            f'type = "{_escape_value(infrastructure.infra_type)}" '
            f'and nom = "{_escape_value(infrastructure.name)}"'
        )
        rows = await self._async_fetch_records(DATASET_SCHEDULES, where, limit=200)

        ranges: list[OpenRange] = []
        current_time = now_dt.time()
        is_open = False

        for row in rows:
            row_weekday = _normalize_weekday(
                _read_first(row, ["jour", "jour_semaine", "joursemaine"])
            )
            if row_weekday and row_weekday != weekday:
                continue

            if not _is_row_active_for_date(row, today):
                continue

            start = _normalize_hour(_read_first(row, ["heuredebut", "heure_debut"]))
            end = _normalize_hour(_read_first(row, ["heurefin", "heure_fin"]))
            if not start or not end:
                continue

            ranges.append(OpenRange(start=start, end=end))

            start_time = _parse_time(start)
            end_time = _parse_time(end)
            if start_time <= current_time <= end_time:
                is_open = True

        ranges.sort(key=lambda item: item.start)
        return InfrastructureState(
            infrastructure=infrastructure,
            opening_ranges=ranges,
            is_open=is_open,
        )

    async def _async_fetch_records(
        self,
        dataset: str,
        where: str,
        *,
        limit: int,
        select: str | None = None,
        group_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch records from one dataset."""
        params: dict[str, Any] = {"where": where, "limit": limit}
        if select:
            params["select"] = select
        if group_by:
            params["group_by"] = group_by

        async with self._session.get(f"{BASE_URL}/{dataset}/records", params=params) as response:
            response.raise_for_status()
            payload: dict[str, Any] = await response.json()
        results = payload.get("results", [])
        if not isinstance(results, list):
            return []
        return [item for item in results if isinstance(item, dict)]

    @staticmethod
    def _build_type_where(infra_type: str) -> str:
        escaped = _escape_value(infra_type)
        return (
            f'type = "{escaped}" '
            f'or categorie = "{escaped}" '
            f'or catégorie = "{escaped}" '
            f'or typeequipement = "{escaped}" '
            f'or type_equipement = "{escaped}"'
        )

    @staticmethod
    def _extract_name(row: dict[str, Any]) -> str | None:
        name = _read_first(
            row,
            [
                "nom",
                "nom_usuel",
                "nomoffre",
                "nom_offre",
                "nom_equipement",
                "name",
            ],
        )
        if isinstance(name, str):
            trimmed = name.strip()
            return trimmed or None
        return None

    def _parse_infrastructure(
        self, row: dict[str, Any], default_type: str
    ) -> Infrastructure | None:
        name = self._extract_name(row)
        if not name:
            return None

        latitude, longitude = _extract_coordinates(row)
        address = _read_first(
            row,
            [
                "adresse",
                "adresse1",
                "adresse_1",
                "voie",
                "localisation",
            ],
        )
        infra_type = _read_first(
            row,
            ["type", "categorie", "catégorie", "typeequipement", "type_equipement"],
        )

        return Infrastructure(
            name=name,
            infra_type=infra_type if isinstance(infra_type, str) and infra_type else default_type,
            latitude=latitude,
            longitude=longitude,
            address=address if isinstance(address, str) else None,
        )


def _read_first(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _extract_coordinates(row: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = _safe_float(_read_first(row, ["lat", "latitude", "y"]))
    lon = _safe_float(_read_first(row, ["lon", "lng", "longitude", "x"]))
    if lat is not None and lon is not None:
        return lat, lon

    geopoint = _read_first(row, ["geo_point_2d", "geopoint", "location"])
    if isinstance(geopoint, dict):
        return _safe_float(geopoint.get("lat")), _safe_float(geopoint.get("lon"))
    if isinstance(geopoint, list) and len(geopoint) >= 2:
        return _safe_float(geopoint[0]), _safe_float(geopoint[1])

    geometry = row.get("geo_shape")
    if isinstance(geometry, dict):
        coords = geometry.get("geometry", {}).get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            lon = _safe_float(coords[0])
            lat = _safe_float(coords[1])
            return lat, lon

    return None, None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_weekday(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().lower()


def _normalize_hour(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    hour = value.strip()
    if not hour:
        return None
    if len(hour) == 5:
        return hour
    if len(hour) >= 8:
        return hour[:5]
    return None


def _is_row_active_for_date(row: dict[str, Any], today: date) -> bool:
    start_raw = _read_first(row, ["datedebut", "date_debut", "date_debut_validite"])
    end_raw = _read_first(row, ["datefin", "date_fin", "date_fin_validite"])

    start = _parse_date(start_raw)
    end = _parse_date(end_raw)

    if start and today < start:
        return False
    return not (end and today > end)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_time(value: str) -> time:
    if value == "24:00":
        return time(23, 59, 59)
    return time.fromisoformat(value)


def _escape_value(value: str) -> str:
    return value.replace('"', '\\"')
