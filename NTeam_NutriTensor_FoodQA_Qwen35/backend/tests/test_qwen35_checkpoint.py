"""Qwen3.5 capability regression: inspect local config without downloading weights."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nutritensor.inference.transformers import TransformersProvider


@pytest.mark.parametrize("vision_config,expected", [({"hidden_size": 1024}, True), (None, False)])
def test_qwen35_capability_is_derived_from_checkpoint_config(tmp_path: Path, vision_config, expected):
    config = {"model_type": "qwen3_5"}
    if vision_config is not None:
        config["vision_config"] = vision_config
    (tmp_path / "config.json").write_text(json.dumps(config))
    provider = TransformersProvider(SimpleNamespace(model_path=str(tmp_path), quantization="nf4", context_tokens=4096, max_new_tokens=384))
    assert provider.capabilities().vision is expected
    assert provider._model_type == "qwen3_5"


def test_qwen3_legacy_is_not_vision(tmp_path: Path):
    (tmp_path / "config.json").write_text(json.dumps({"model_type": "qwen3"}))
    provider = TransformersProvider(SimpleNamespace(model_path=str(tmp_path), quantization="nf4", context_tokens=4096, max_new_tokens=384))
    assert provider.capabilities().vision is False
