from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
Priority = Literal["low","medium","high"]
Status = Literal["open","done"]
class TaskCreate(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    notes: str = Field(default="",max_length=5000)
    due_at: datetime | None = None
    priority: Priority = "medium"
    project: str | None = None
    @field_validator("title")
    @classmethod
    def clean(cls,v):
        if not v.strip(): raise ValueError("empty title")
        return v.strip()
    @field_validator("due_at")
    @classmethod
    def aware(cls,v):
        if v is not None and v.tzinfo is None: raise ValueError("timezone required")
        return v
class TaskPatch(BaseModel):
    title: str | None = Field(default=None,min_length=1,max_length=200)
    notes: str | None = None
    due_at: datetime | None = None
    priority: Priority | None = None
    project: str | None = None
    status: Status | None = None
    @field_validator("due_at")
    @classmethod
    def aware(cls,v):
        if v is not None and v.tzinfo is None: raise ValueError("timezone required")
        return v
