from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy_celery_beat import CrontabSchedule, PeriodicTask, SessionManager
from sqlalchemy import select, delete
from fastapi import APIRouter, HTTPException, Response, Depends
from starlette.status import HTTP_200_OK

from irrigation_controller_server.config import Settings, get_settings

router = APIRouter(prefix="/schedule", tags=["schedule"])


class ScheduleConfig(BaseModel):
    name: str
    task: str
    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"
    timezone: str = "UTC"
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)


@router.get("/")
async def list_schedule(settings: Annotated[Settings, Depends(get_settings)]):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    return list(session.scalars(select(PeriodicTask)))


@router.get("/{name}")
async def get_schedule(name: str, settings: Annotated[Settings, Depends(get_settings)]):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    schedule = session.execute(
        select(PeriodicTask).where(PeriodicTask.name == name)
    ).scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="No such schedule")

    return schedule


@router.post("/")
async def set_schedule(
    config: ScheduleConfig, settings: Annotated[Settings, Depends(get_settings)]
):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)

    task = f"irrigation_controller_server.tasks.{config.task}"

    schedule = CrontabSchedule(
        minute=config.minute,
        hour=config.hour,
        day_of_week=config.day_of_week,
        day_of_month=config.day_of_month,
        month_of_year=config.month_of_year,
        timezone=config.timezone,
    )

    session.add(schedule)
    session.commit()
    session.refresh(schedule)

    periodic_task = PeriodicTask(
        schedule_model=schedule,
        name=config.name,
        task=task,
        args=config.args,
        kwargs=config.kwargs,
    )
    session.add(periodic_task)
    session.commit()

    return Response(status_code=HTTP_200_OK)


@router.delete("/{name}")
async def delete_schedule(
    name: str, settings: Annotated[Settings, Depends(get_settings)]
):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    result = session.execute(delete(PeriodicTask).where(PeriodicTask.name == name))
    session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="No such schedule")

    return Response(status_code=HTTP_200_OK)
