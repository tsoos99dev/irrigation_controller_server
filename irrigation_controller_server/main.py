from contextlib import asynccontextmanager

from fastapi import FastAPI
from irrigation_controller_server.routers import relay, schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(relay.router)
app.include_router(schedule.router)
