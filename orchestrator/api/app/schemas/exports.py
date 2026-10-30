from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExportFormat(str, Enum):
    XLSX = "xlsx"
    CSV = "csv"


class ExportPeriod(str, Enum):
    ALL = "all"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    CUSTOM = "custom"


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ExportFormat = ExportFormat.XLSX
    period: ExportPeriod = ExportPeriod.ALL
    date_from: date | None = None
    date_to: date | None = None
    columns: list[str] | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_period(self) -> "ExportRequest":
        if self.period == ExportPeriod.CUSTOM:
            if self.date_from is None or self.date_to is None:
                raise ValueError("custom period requires date_from and date_to")
            if self.date_from > self.date_to:
                raise ValueError("date_from must not be after date_to")
        elif self.date_from is not None or self.date_to is not None:
            raise ValueError("preset periods do not accept custom dates")
        return self


class ExportColumnRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    default_enabled: bool
    category: str
    type: str


class ExportSchemaRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancies: list[ExportColumnRead]
    applications: list[ExportColumnRead]
    formats: list[ExportFormat]
    periods: list[ExportPeriod]
