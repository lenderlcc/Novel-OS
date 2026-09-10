from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class DatabaseHealthResponse(HealthResponse):
    database: Literal["ok"] = "ok"


class ErrorDetail(BaseModel):
    location: list[str | int]
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
