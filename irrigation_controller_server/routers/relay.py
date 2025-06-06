from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymodbus.client import AsyncModbusTcpClient
from typing import Annotated

from irrigation_controller_server.interface import relay
from irrigation_controller_server.config import Settings, get_settings

router = APIRouter(prefix="/relay", tags=["relay"])


@router.get("/status")
async def status(
    client: Annotated[AsyncModbusTcpClient, Depends(relay.get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return await relay.get_status(client, slave=settings.relay_unit_id)


class OutputSetting(BaseModel):
    label: int
    value: bool


@router.post("/set-output")
async def set_output(
    output_settings: OutputSetting,
    client: Annotated[AsyncModbusTcpClient, Depends(relay.get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return await relay.set_output(
        client,
        slave=settings.relay_unit_id,
        address=output_settings.label,
        value=output_settings.value,
    )
