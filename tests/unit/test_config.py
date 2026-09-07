import pytest
from pydantic import ValidationError

from hufiagents.config import Settings


def test_bounded_defaults():
    settings = Settings(_env_file=None)
    assert settings.max_concurrent_tasks == 2
    assert settings.model_timeout_seconds == 180
    with pytest.raises(ValidationError):
        Settings(max_concurrent_tasks=0, _env_file=None)
