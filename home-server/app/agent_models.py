from datetime import datetime
from pydantic import BaseModel, Field


class AgentSessionCreateRequest(BaseModel):
    label: str | None = None


class AgentSessionResponse(BaseModel):
    session_id: str
    label: str
    root_path: str
    created_at: datetime


class AgentPathRequest(BaseModel):
    path: str = Field(default=".")


class AgentTreeEntry(BaseModel):
    path: str
    is_dir: bool
    size: int | None = None


class AgentReadFileRequest(BaseModel):
    path: str


class AgentWriteFileRequest(BaseModel):
    path: str
    content: str
    overwrite: bool = True


class AgentAppendFileRequest(BaseModel):
    path: str
    content: str


class AgentMovePathRequest(BaseModel):
    source_path: str
    destination_path: str


class AgentDeletePathRequest(BaseModel):
    path: str
    recursive: bool = False


class AgentRunGoalRequest(BaseModel):
    goal: str
    max_steps: int = 8


class AgentOperationResult(BaseModel):
    ok: bool
    message: str
    data: dict | None = None
