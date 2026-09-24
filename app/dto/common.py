from pydantic import BaseModel


class ErrorDetailOut(BaseModel):
    code: str
    message: str
    field_id: str | None = None


class ErrorBodyOut(BaseModel):
    code: str
    message: str
    details: list[ErrorDetailOut]


class ErrorResponseOut(BaseModel):
    error: ErrorBodyOut
