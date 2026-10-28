from __future__ import annotations

import os
from collections.abc import Mapping
from importlib import import_module
from typing import Any

HEADING_ESTIMATOR_ENV_VAR = "E014_HEADING_ESTIMATOR"
ACTIVITY_CLASSIFIER_ENV_VAR = "E014_ACTIVITY_CLASSIFIER"


class PluginLoadError(RuntimeError):
    """Raised when a configured plugin path cannot be resolved or built."""


def load_plugin(spec: str) -> Any:
    """Build an object from a ``module.path:AttributeName`` spec.

    The attribute is called with no arguments when it is callable, so both a
    class with a zero-argument constructor and a factory function work. An
    already-constructed module-level instance is returned as-is.
    """
    if ":" not in spec:
        raise PluginLoadError(
            f"plugin spec {spec!r} must look like 'package.module:AttributeName'"
        )

    module_path, _, attribute_name = spec.partition(":")
    module_path = module_path.strip()
    attribute_name = attribute_name.strip()
    if not module_path or not attribute_name:
        raise PluginLoadError(
            f"plugin spec {spec!r} must look like 'package.module:AttributeName'"
        )

    try:
        module = import_module(module_path)
    except ImportError as exc:
        raise PluginLoadError(f"cannot import module {module_path!r}: {exc}") from exc

    try:
        attribute = getattr(module, attribute_name)
    except AttributeError as exc:
        raise PluginLoadError(
            f"module {module_path!r} has no attribute {attribute_name!r}"
        ) from exc

    if not callable(attribute):
        return attribute

    try:
        return attribute()
    except TypeError as exc:
        raise PluginLoadError(
            f"{spec!r} could not be constructed without arguments: {exc}"
        ) from exc


def load_plugin_from_env(
    env_var: str,
    env: Mapping[str, str] | None = None,
) -> Any | None:
    """Return the configured plugin instance, or None when the var is unset."""
    environ = os.environ if env is None else env
    spec = environ.get(env_var)
    if spec is None or not spec.strip():
        return None
    return load_plugin(spec.strip())


def heading_estimator_from_env(env: Mapping[str, str] | None = None) -> Any | None:
    return load_plugin_from_env(HEADING_ESTIMATOR_ENV_VAR, env)


def activity_classifier_from_env(env: Mapping[str, str] | None = None) -> Any | None:
    return load_plugin_from_env(ACTIVITY_CLASSIFIER_ENV_VAR, env)
