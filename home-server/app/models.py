from datetime import datetime
from pydantic import BaseModel


class UserUtterance(BaseModel):
    type: str
    session_id: str
    text: str
    timestamp: datetime


class AssistantResponse(BaseModel):
    type: str = "assistant_response"
    session_id: str
    text: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    type: str = "error"
    message: str
