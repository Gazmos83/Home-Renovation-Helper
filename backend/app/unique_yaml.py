"""YAML configuration that refuses a repeated key, so a duplicate entry is an error
rather than a silently kept last value."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import yaml


def load_unique(text: str, duplicate: Callable[[Any], Exception]) -> Any:
    """`yaml.safe_load(text)`, raising `duplicate(key)` for a key repeated in one mapping."""

    class _Loader(yaml.SafeLoader):
        pass

    def _no_duplicate_keys(loader: _Loader, node: yaml.MappingNode) -> dict:
        seen: set = set()
        for key_node, _value_node in node.value:
            key = loader.construct_object(key_node)
            if key in seen:
                raise duplicate(key)
            seen.add(key)
        return loader.construct_mapping(node)

    _Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)
    return yaml.load(text, Loader=_Loader)
