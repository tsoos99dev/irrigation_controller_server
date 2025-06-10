from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated

from irrigation_controller_server.interface import relay
from irrigation_controller_server.config import Settings, get_settings
from irrigation_controller_server.interface.relay import RelayError
from irrigation_controller_server.models import ZoneType

router = APIRouter(prefix="/zone", tags=["zone"])


@router.get("/status", response_model=dict[ZoneType, bool])
async def status(
    settings: Annotated[Settings, Depends(get_settings)],
):
    relay_ids = {z.relay_id for z in settings.zones.values()}
    relay_states = {}
    for relay_id in relay_ids:
        relay_config = settings.relays.get(relay_id)
        if relay_config is None:
            raise HTTPException(status_code=404, detail="Invalid zone configuration")

        async with relay.get_client(
            relay_config.host, relay_config.port, relay_config.timeout
        ) as client:
            try:
                state = await relay.get_status(client, slave=relay_config.unit_id)
            except RelayError as e:
                return str(e)

        relay_states[relay_id] = state

    zone_statuses = {
        zone_type: relay_states[zone_config.relay_id][zone_config.relay_output]
        for zone_type, zone_config in settings.zones.items()
    }

    return zone_statuses


class OutputSetting(BaseModel):
    zone: ZoneType
    value: bool


@router.post("/set")
async def set_zone(
    zone_setting: OutputSetting,
    settings: Annotated[Settings, Depends(get_settings)],
):
    zone_config = settings.zones.get(zone_setting.zone)
    if zone_config is None:
        raise HTTPException(status_code=404, detail="No such zone")

    relay_config = settings.relays.get(zone_config.relay_id)
    if relay_config is None:
        raise HTTPException(status_code=404, detail="Invalid zone configuration")

    async with relay.get_client(
        relay_config.host, relay_config.port, relay_config.timeout
    ) as client:
        try:
            state = await relay.set_output(
                client,
                slave=relay_config.unit_id,
                address=zone_config.relay_output,
                value=zone_setting.value,
            )
        except RelayError as e:
            return str(e)

        return state
