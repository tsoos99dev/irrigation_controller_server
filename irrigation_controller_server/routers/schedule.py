import json
import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict
from sqlalchemy_celery_beat import CrontabSchedule, PeriodicTask, SessionManager
from sqlalchemy import select, delete
from fastapi import APIRouter, HTTPException, Response, Depends
from starlette.status import HTTP_200_OK

from irrigation_controller_server.config import Settings, get_settings
from irrigation_controller_server.tasks import IRRIGATION_TASK, IrrigationConfig

router = APIRouter(prefix="/schedule", tags=["schedule"])


class ScheduleConfig(BaseModel):
    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"
    timezone: str = "UTC"


class TaskConfig(BaseModel):
    name: str
    schedule: ScheduleConfig
    parameters: IrrigationConfig


class PartialScheduleConfig(BaseModel):
    minute: str | None = None
    hour: str | None = None
    day_of_week: str | None = None
    day_of_month: str | None = None
    month_of_year: str | None = None
    timezone: str | None = None


class PartialTaskConfig(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    schedule: PartialScheduleConfig | None = None
    parameters: IrrigationConfig | None = Field(serialization_alias="kwargs")

    @field_serializer("parameters")
    def serialize_parameters(self, parameters: IrrigationConfig, _info):
        return parameters.model_dump_json()

    model_config = ConfigDict(serialize_by_alias=True)


class ScheduleConfigResponse(BaseModel):
    minute: str
    hour: str
    day_of_week: str
    day_of_month: str
    month_of_year: str
    timezone: str


class TaskConfigResponse(BaseModel):
    name: str
    enabled: bool
    schedule: ScheduleConfigResponse = Field(validation_alias="schedule_model")
    parameters: IrrigationConfig = Field(validation_alias="kwargs")
    last_run_at: datetime.datetime | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def load_json(cls, value: str) -> str:
        return json.loads(value)


@router.get("/", response_model=list[TaskConfigResponse])
async def list_schedule(settings: Annotated[Settings, Depends(get_settings)]):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    tasks = list(
        session.scalars(
            select(PeriodicTask).where(PeriodicTask.task == IRRIGATION_TASK)
        )
    )

    return tasks


@router.get("/{name}", response_model=TaskConfigResponse)
async def get_schedule(name: str, settings: Annotated[Settings, Depends(get_settings)]):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    task = session.execute(
        select(PeriodicTask).where(
            PeriodicTask.name == name, PeriodicTask.task == IRRIGATION_TASK
        )
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="No such task")

    return task


@router.post("/", response_model=TaskConfigResponse)
async def set_schedule(
    config: TaskConfig, settings: Annotated[Settings, Depends(get_settings)]
):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)

    schedule = CrontabSchedule(
        minute=config.schedule.minute,
        hour=config.schedule.hour,
        day_of_week=config.schedule.day_of_week,
        day_of_month=config.schedule.day_of_month,
        month_of_year=config.schedule.month_of_year,
        timezone=config.schedule.timezone,
    )

    session.add(schedule)
    session.commit()
    session.refresh(schedule)

    periodic_task = PeriodicTask(
        schedule_model=schedule,
        name=config.name,
        task=IRRIGATION_TASK,
        kwargs=config.parameters.model_dump_json(),
    )
    session.add(periodic_task)
    session.commit()

    return periodic_task


@router.patch("/{name}", response_model=TaskConfigResponse)
async def update_schedule(
    name: str,
    config: PartialTaskConfig,
    settings: Annotated[Settings, Depends(get_settings)],
):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)

    task = session.execute(
        select(PeriodicTask).where(
            PeriodicTask.name == name, PeriodicTask.task == IRRIGATION_TASK
        )
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="No such task")

    if config.schedule is not None:
        schedule = task.schedule_model
        schedule_update = config.schedule.model_dump(exclude_unset=True)
        for key, value in schedule_update.items():
            setattr(schedule, key, value)

    task_update = config.model_dump(exclude_unset=True, exclude={"schedule"})
    for key, value in task_update.items():
        setattr(task, key, value)

    session.commit()
    return task


@router.delete("/{name}")
async def delete_schedule(
    name: str, settings: Annotated[Settings, Depends(get_settings)]
):
    session_manager = SessionManager()
    session = session_manager.session_factory(settings.broker.beat_dburi)
    result = session.execute(
        delete(PeriodicTask).where(
            PeriodicTask.name == name, PeriodicTask.task == IRRIGATION_TASK
        )
    )
    session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="No such task")

    return Response(status_code=HTTP_200_OK)
