"""Midea local x40 device."""

import json
import logging
from enum import StrEnum
from typing import Any

from midealocal.const import DeviceType, ProtocolVersion
from midealocal.device import MideaDevice

from .message import MessageQuery, MessageSet, MessageX40Response

_LOGGER = logging.getLogger(__name__)

DIRECTION_MIN_VALUE = 60
DIRECTION_MAX_VALUE = 120
VENTILATION_FAN_SPEED = 2
DIRECTION_OSCILLATE = 0xFD
DIRECTION_STOP = 0xFE
DIRECTION_00 = 0x00  # Unknown
DIRECTION_FF = 0xFF  # None


class DeviceAttributes(StrEnum):
    """Midea x40 device attributes."""

    light = "light"
    fan_speed = "fan_speed"
    direction = "direction"
    oscillation = "oscillation"
    ventilation = "ventilation"
    anion = "anion"
    smelly_sensor = "smelly_sensor"
    current_temperature = "current_temperature"


class MideaX40Device(MideaDevice):
    """Midea x40 Device."""

    def __init__(
        self,
        name: str,
        device_id: int,
        ip_address: str,
        port: int,
        token: str,
        key: str,
        device_protocol: ProtocolVersion,
        model: str,
        subtype: int,
        customize: str,
    ) -> None:
        """Initialize Midea x40 Device."""
        super().__init__(
            name=name,
            device_id=device_id,
            device_type=DeviceType.X40,
            ip_address=ip_address,
            port=port,
            token=token,
            key=key,
            device_protocol=device_protocol,
            model=model,
            subtype=subtype,
            attributes={
                DeviceAttributes.light: False,
                DeviceAttributes.fan_speed: 0,
                DeviceAttributes.direction: None,  # 60~120 or None
                DeviceAttributes.oscillation: None,  # bool or None
                DeviceAttributes.ventilation: False,
                DeviceAttributes.anion: None,
                DeviceAttributes.smelly_sensor: False,
                DeviceAttributes.current_temperature: None,
            },
        )
        self._fields: dict[str, Any] = {}
        self._precision_halves: bool | None = None
        self._default_precision_halves = False
        self.set_customize(customize)

    @property
    def precision_halves(self) -> bool | None:
        """Midea 40 device precision halves."""
        return self._precision_halves

    @staticmethod
    def _convert_to_midea_direction(direction: float | str | bool) -> int:
        """Deal value from user, if is valid, return it, else return 0xFF."""
        direction = int(direction)
        if direction in (DIRECTION_OSCILLATE, DIRECTION_STOP) or (
            DIRECTION_MIN_VALUE <= direction <= DIRECTION_MAX_VALUE
        ):
            return direction
        return DIRECTION_FF

    def _get_midea_direction(self) -> int:
        """Get direction byte by oscillation and direction."""
        oscillation: bool | None = self._attributes[DeviceAttributes.oscillation]
        if oscillation is True:
            return DIRECTION_OSCILLATE
        if oscillation is False:
            direction: int | None = self._attributes[DeviceAttributes.direction]
            return DIRECTION_STOP if direction is None else direction
        return DIRECTION_FF

    def build_query(self) -> list[MessageQuery]:
        """Midea x40 Device build query."""
        return [MessageQuery(self._message_protocol_version)]

    def process_message(self, msg: bytes) -> dict[str, Any]:
        """Midea x40 Device process message."""
        message = MessageX40Response(msg)
        _LOGGER.debug("[%s] Received: %s", self.device_id, message)
        new_status = {}
        self._fields = message.fields
        for status in self._attributes:
            if hasattr(message, str(status)):
                value = getattr(message, str(status))
                if (
                    self._precision_halves
                    and status == DeviceAttributes.current_temperature
                ):
                    value /= 2
                if status == DeviceAttributes.direction:
                    if value in (DIRECTION_STOP, DIRECTION_00, DIRECTION_FF):
                        # never be 0xFE and don't save 0xFF and 0x00
                        continue
                    if value == DIRECTION_OSCILLATE:
                        # clear the direction and mark oscillation as True
                        value = None
                        self._attributes[DeviceAttributes.oscillation] = True
                    else:
                        # value is 60~120
                        self._attributes[DeviceAttributes.oscillation] = False
                self._attributes[status] = value
                new_status[str(status)] = self._attributes[status]
        return new_status

    def set_attribute(self, attr: str, value: float | str | bool) -> None:
        """Midea x40 Device set attribute."""
        if attr in [
            DeviceAttributes.light,
            DeviceAttributes.fan_speed,
            DeviceAttributes.direction,
            DeviceAttributes.ventilation,
            DeviceAttributes.anion,
            DeviceAttributes.smelly_sensor,
        ]:
            message = MessageSet(self._message_protocol_version)
            message.fields = self._fields
            message.light = self._attributes[DeviceAttributes.light]
            message.ventilation = self._attributes[DeviceAttributes.ventilation]
            message.anion = self._attributes.get(DeviceAttributes.anion, False)
            message.smelly_sensor = self._attributes[DeviceAttributes.smelly_sensor]
            message.fan_speed = self._attributes[DeviceAttributes.fan_speed]
            message.direction = self._get_midea_direction()
            if attr == DeviceAttributes.direction:
                message.direction = self._convert_to_midea_direction(value)
            elif (
                attr == DeviceAttributes.ventilation
                and message.fan_speed == VENTILATION_FAN_SPEED
            ):
                message.fan_speed = 1
                message.ventilation = bool(value)
            else:
                setattr(message, str(attr), value)
            self.build_send(message)

    def set_customize(self, customize: str) -> None:
        """Midea 40 device set customize."""
        self._precision_halves = self._default_precision_halves
        if customize and len(customize) > 0:
            try:
                params = json.loads(customize)
                if params and "precision_halves" in params:
                    self._precision_halves = params.get("precision_halves")
            except Exception:
                _LOGGER.exception("[%s] Set customize error", self.device_id)
            self.update_all({"precision_halves": self._precision_halves})


class MideaAppliance(MideaX40Device):
    """Midea x40 appliance."""
