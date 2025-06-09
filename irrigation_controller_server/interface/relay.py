import asyncio
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Annotated

from fastapi import Depends
from more_itertools import quantify
from pymodbus import ModbusException
from pymodbus.client import AsyncModbusTcpClient

from irrigation_controller_server.config import Settings, get_settings


class RelayErrorKind(StrEnum):
    RequestFailed = "request_failed"
    TooManyActiveOutputs = "too_many_active_outputs"


class RelayError(Exception): ...


interface_lock = asyncio.Lock()


RelayState = tuple[bool, bool, bool, bool]


@asynccontextmanager
async def get_client(host: str, port: int, timeout: float):
    async with interface_lock:
        async with AsyncModbusTcpClient(
            host,
            port=port,
            timeout=timeout,
        ) as client:
            yield client


async def get_status(client: AsyncModbusTcpClient, slave: int) -> RelayState:
    try:
        response = await client.read_coils(0, count=8, slave=slave)
    except ModbusException as e:
        raise RelayError(RelayErrorKind.RequestFailed.value) from e

    r1, r2, r3, r4, *_ = response.bits
    return r1, r2, r3, r4


async def _set_output_unsafe(
    client: AsyncModbusTcpClient, slave: int, address: int, value: bool
):
    try:
        await client.write_coil(address, value, slave=slave)
    except ModbusException as e:
        raise RelayError(RelayErrorKind.RequestFailed.value) from e

    return None


async def set_output(
    client: AsyncModbusTcpClient, slave: int, address: int, value: bool
):
    if value is False:
        await _set_output_unsafe(client, slave=slave, address=address, value=value)
        return value

    current_state = await get_status(client, slave=slave)
    num_active_outputs = quantify(current_state, lambda s: s)
    if num_active_outputs != 0:
        raise RelayError(RelayErrorKind.TooManyActiveOutputs.value)

    await _set_output_unsafe(client, slave=slave, address=address, value=value)
    return value
