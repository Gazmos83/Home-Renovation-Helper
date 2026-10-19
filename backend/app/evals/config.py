"""`config/evals.yaml`: the judge, the per-run token ceiling and where files live."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, PositiveInt, ValidationError

from app.agent.models.registry import is_available, is_known
from app.config import REPO_ROOT, ConfigurationError

DEFAULT_EVAL_CONFIG: Final = Path(__file__).resolve().parents[2] / "config" / "evals.yaml"


class EvalConfigError(ConfigurationError):
    """The eval configuration is invalid. The message names the key or slug."""


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    judge: str
    token_ceiling: PositiveInt
    golden_set: Path
    report_dir: Path


def load_eval_config(path: Path = DEFAULT_EVAL_CONFIG) -> EvalConfig:
    """Read and check the eval configuration; paths come back absolute."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise EvalConfigError(f"eval config not found: {path}") from error
    except yaml.YAMLError as error:
        raise EvalConfigError(f"eval config is not valid YAML: {path}") from error
    try:
        config = EvalConfig.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        key = ".".join(str(part) for part in first["loc"]) or "(top level)"
        raise EvalConfigError(f"eval config key {key!r}: {first['msg']}") from error
    if not is_known(config.judge) or not is_available(config.judge):
        raise EvalConfigError(f"eval judge {config.judge!r} is not an available registry model")
    return config.model_copy(
        update={
            "golden_set": REPO_ROOT / config.golden_set,
            "report_dir": REPO_ROOT / config.report_dir,
        }
    )
