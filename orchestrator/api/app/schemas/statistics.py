from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict


class StatisticsPeriod(str, Enum):
    TODAY = "today"
    DAYS_7 = "7d"
    DAYS_14 = "14d"
    DAYS_30 = "30d"
    ALL = "all"
    CUSTOM = "custom"


class VacancyStatisticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: StatisticsPeriod
    date_from: date | None
    date_to: date | None
    found: int
    reviewed: int
    applications: int
    responses: int
    interviews: int
    rejections: int
    active_processes: int
    offers: int
    legacy_without_date: int
