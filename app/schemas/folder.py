from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, DirectoryPath, Field, StringConstraints, AfterValidator, field_validator
from app.core.config import settings
from pathlib import Path


def validate_dir(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(settings.allowed_root.resolve()):
        raise ValueError(f'{resolved} isn`t an allowed directory')
    return resolved


SafeDir = Annotated[DirectoryPath, AfterValidator(validate_dir)]
FolderName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class FolderBase(BaseModel):
    name: FolderName
    description: Description | None = None
    writable: bool = False


class FolderCreate(FolderBase):
    path: SafeDir


class FolderUpdate(BaseModel):
    name: FolderName | None = None
    description: Description | None = None
    writable: bool | None = None
    path: SafeDir | None = None

    # noinspection PyNestedDecorators
    @field_validator("name", "writable", "path", mode="before")
    @classmethod
    def validate_none_dir(cls, value: str) -> str:
        if value is None:
            raise ValueError("Value can't be null. Remove it or leave it unchanged")
        return value


class FolderResponse(FolderBase):
    id: int
    created_at: datetime
    path: Path
