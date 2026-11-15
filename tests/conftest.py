import pytest
from dataclasses import dataclass, field
from pathlib import Path
from fastapi.testclient import TestClient


@dataclass
class SandboxData:
    tmp: Path
    allowed_root: Path = field(init=False)
    photos: Path = field(init=False)
    docs: Path = field(init=False)
    a_file: Path = field(init=False)
    root_evil: Path = field(init=False)

    def __post_init__(self) -> None:
        self.allowed_root = self.tmp / "root"
        self.photos = self.allowed_root / "photos"
        self.docs = self.allowed_root / "docs"
        self.a_file = self.allowed_root / "a_file.txt"
        self.root_evil = self.tmp / "root_evil"

    def build(self) -> None:
        self.photos.mkdir(parents=True, exist_ok=True)
        self.docs.mkdir(parents=True, exist_ok=True)
        self.a_file.write_text("dummy content", encoding="utf-8")
        self.root_evil.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def sandbox(tmp_path_factory) -> SandboxData:
    tmp_dir = tmp_path_factory.mktemp("fileapi_test_")

    sandbox_data = SandboxData(tmp=tmp_dir)
    sandbox_data.build()

    env_vars = {
        "APP_NAME": "FastFile",
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "DATABASE_URL": "postgresql://user:password@localhost:5432/files",
        "ALLOWED_ROOT": str(sandbox_data.allowed_root),
    }

    with pytest.MonkeyPatch.context() as mp:
        for key, value in env_vars.items():
            mp.setenv(key, value)

        yield sandbox_data


@pytest.fixture
def client(sandbox):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store(sandbox):
    import app.routers.folders as folders_module

    folders_module.folders_dict.clear()
    folders_module.id_counter = 1
