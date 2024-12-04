# custom_components/previo_reservations/sensor.py

from datetime import datetime, timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import aiohttp
import xmltodict
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors from a config entry."""
    # Získáme uložené údaje z config entry
    username = entry.data.get("username")
    password = entry.data.get("password")
    hotel_id = entry.data.get("hotel_id")
    rooms = entry.data.get("rooms")

    # Převod seznamu pokojů z textu na seznam
    room_list = [room.strip() for room in rooms.split(",")]

    # Inicializace koordinátoru s uživatelskými údaji
    coordinator = PrevioReservationsCoordinator(hass, username, password, hotel_id)

    # První aktualizace dat pomocí koordinátoru
    await coordinator.async_config_entry_first_refresh()

    # Vytvoření senzorů pro každý pokoj
    sensors = [RoomReservationSensor(room_id, coordinator) for room_id in room_list]
    async_add_entities(sensors)

class PrevioReservationsCoordinator(DataUpdateCoordinator):
    """Koordinátor pro aktualizaci dat z API."""

    def __init__(self, hass: HomeAssistant, username: str, password: str, hotel_id: str):
        """Inicializace koordinátoru s uživatelskými údaji."""
        self.username = username
        self.password = password
        self.hotel_id = hotel_id
        super().__init__(
            hass,
            _LOGGER,
            name="Previo Reservations Coordinator",
            update_interval=timedelta(minutes=15),  # Aktualizace každých 15 minut
        )

    async def _async_update_data(self):
        """Načte data z API."""
        try:
            return await get_reservations(self.hass, self.username, self.password, self.hotel_id)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

async def get_reservations(hass: HomeAssistant, username: str, password: str, hotel_id: str):
    """Funkce pro načtení rezervací z API (asynchronně)."""
    # Získání dnešního data a data zítřka
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # XML payload s dynamickým datem a uživatelskými údaji
    payload = f"""
    <request>
        <login>{username}</login>
        <password>{password}</password>
        <hotId>{hotel_id}</hotId>
        <term>
            <from>{today}</from>
            <to>{tomorrow}</to>
        </term>
    </request>
    """

    url = "https://api.previo.app/x1/hotel/searchReservations"
    headers = {
        "Content-Type": "application/xml",
        "Accept": "application/xml"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=payload) as response:
            if response.status == 200:
                response_text = await response.text()
                # Parse XML response to Python dictionary
                data = xmltodict.parse(response_text)
                reservations = data.get("reservations", {}).get("reservation", [])
                if not isinstance(reservations, list):
                    reservations = [reservations]  # Pokud existuje jen jedna rezervace, zajistíme, aby to byl seznam
                return reservations
            else:
                _LOGGER.error(f"Failed to get reservations. Status code: {response.status}")
                return []

class RoomReservationSensor(Entity):
    """Senzor reprezentující rezervaci pro konkrétní pokoj."""

    def __init__(self, room_id, coordinator):
        """Inicializace senzoru."""
        self._room_id = room_id
        self._coordinator = coordinator
        self._state = "No reservation"
        self._attributes = {}

    async def async_update(self):
        """Aktualizace stavu senzoru."""
        await self._coordinator.async_request_refresh()
        reservations = self._coordinator.data

        # Aktualizace stavu a atributů senzoru na základě dat z API
        self.update_reservation_status(reservations)

    def update_reservation_status(self, reservations):
        """Aktualizace informací o rezervaci pro daný pokoj."""
        for reservation in reservations:
            room_number = reservation.get("object", {}).get("name")
            if room_number == self._room_id:
                # Extrakce dat z rezervace
                term = reservation.get("term", {})
                check_in = term.get("from")
                check_out = term.get("to")
                status_id = reservation.get("status", {}).get("statusId")

                # Aktualizace stavu a atributů
                self._state = "reserved" if status_id == "3" else "available"
                self._attributes = {
                    "check_in": check_in,
                    "check_out": check_out,
                    "status_id": status_id,
                    "room_number": room_number,
                }
                break
        else:
            # Pokud nebyla nalezena žádná rezervace pro daný pokoj
            self._state = "No reservation"
            self._attributes = {}

    @property
    def name(self):
        """Vrátí název senzoru."""
        return f"Room {self._room_id} Reservation"

    @property
    def state(self):
        """Vrátí aktuální stav rezervace."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Vrátí atributy senzoru."""
        return self._attributes

    @property
    def unique_id(self):
        """Vrátí unikátní identifikátor senzoru."""
        return f"room_{self._room_id}"
