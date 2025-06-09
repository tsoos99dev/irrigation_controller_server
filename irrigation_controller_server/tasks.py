import asyncio
import logging
import datetime

import pydantic
from celery import Celery, chain
from pydantic import BaseModel, field_serializer, TypeAdapter

from irrigation_controller_server.config import get_settings
from irrigation_controller_server.interface import relay
from irrigation_controller_server.models import ZoneType

settings = get_settings()
app = Celery("tasks")
app.config_from_object(settings.celery_conf)

IRRIGATION_TASK = "irrigation_controller_server.tasks.irrigate"

# Time to wait while switching zones
ZONE_START_DELAY = 3


logger = logging.getLogger(__name__)


class IrrigationTaskError(Exception):
    pass


class ZoneConfig(BaseModel):
    name: ZoneType
    duration: datetime.timedelta

    @field_serializer("duration")
    def serialize_duration(self, duration: datetime.timedelta):
        timedelta_adapter = TypeAdapter(datetime.timedelta)
        return timedelta_adapter.dump_json(duration).replace(b'"', b"")


class IrrigationConfig(BaseModel):
    zones: list[ZoneConfig]


async def start_zone_action(config: ZoneConfig):
    settings = get_settings()

    zone_config = settings.zones.get(config.name)
    if zone_config is None:
        return

    relay_config = settings.relays.get(zone_config.relay_id)
    if relay_config is None:
        return

    async with relay.get_client(
        relay_config.host, relay_config.port, relay_config.timeout
    ) as client:
        return await relay.set_output(
            client,
            slave=relay_config.unit_id,
            address=zone_config.relay_output,
            value=True,
        )


async def stop_zone_action(config: ZoneConfig):
    settings = get_settings()

    zone_config = settings.zones.get(config.name)
    if zone_config is None:
        return

    relay_config = settings.relays.get(zone_config.relay_id)
    if relay_config is None:
        return

    async with relay.get_client(
        relay_config.host, relay_config.port, relay_config.timeout
    ) as client:
        return await relay.set_output(
            client,
            slave=relay_config.unit_id,
            address=zone_config.relay_output,
            value=False,
        )


@app.task
def start_zone(*args, **kwargs):
    config = ZoneConfig.model_validate(kwargs)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_zone_action(config))


@app.task
def stop_zone(*args, **kwargs):
    config = ZoneConfig.model_validate(kwargs)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(stop_zone_action(config))


@app.task(bind=True)
def irrigate_zone(self, **kwargs):
    config = ZoneConfig.model_validate(kwargs)

    workflow = chain(
        start_zone.si(**config.model_dump()),
        stop_zone.signature(
            kwargs=config.model_dump(),
            countdown=config.duration.total_seconds(),
            immutable=True,
        ),
    )
    return self.replace(workflow)


@app.task(bind=True, name=IRRIGATION_TASK)
def irrigate(self, *args, **kwargs):
    try:
        config = IrrigationConfig.model_validate(kwargs)
    except pydantic.ValidationError as e:
        raise IrrigationTaskError("Invalid config") from e

    if len(config.zones) == 0:
        return None

    workflow = chain(
        irrigate_zone.signature(
            kwargs=zone.model_dump(),
            countdown=None if i == 0 else ZONE_START_DELAY,
            immutable=True,
        )
        for i, zone in enumerate(config.zones)
    )

    return self.replace(workflow)
