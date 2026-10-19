from __future__ import annotations

import pytest

from backend.config.plugins import (
    ACTIVITY_CLASSIFIER_ENV_VAR,
    HEADING_ESTIMATOR_ENV_VAR,
    PluginLoadError,
    activity_classifier_from_env,
    heading_estimator_from_env,
    load_plugin,
)
from backend.imu.activity import TiltActivityClassifier
from backend.imu.heading import GyroYawIntegrator


def test_load_plugin_builds_class_without_arguments() -> None:
    plugin = load_plugin("backend.imu.heading:GyroYawIntegrator")

    assert isinstance(plugin, GyroYawIntegrator)


def test_load_plugin_rejects_spec_without_separator() -> None:
    with pytest.raises(PluginLoadError):
        load_plugin("backend.imu.heading.GyroYawIntegrator")


def test_load_plugin_rejects_unknown_module() -> None:
    with pytest.raises(PluginLoadError):
        load_plugin("backend.imu.not_a_module:Thing")


def test_load_plugin_rejects_unknown_attribute() -> None:
    with pytest.raises(PluginLoadError):
        load_plugin("backend.imu.heading:NotAClass")


def test_load_plugin_reports_constructor_arity_problems() -> None:
    with pytest.raises(PluginLoadError):
        load_plugin("backend.imu.heading:wrap_to_pi")


def test_env_loaders_return_none_when_unset() -> None:
    assert heading_estimator_from_env(env={}) is None
    assert activity_classifier_from_env(env={}) is None
    assert heading_estimator_from_env(env={HEADING_ESTIMATOR_ENV_VAR: "   "}) is None


def test_env_loaders_build_configured_plugins() -> None:
    heading = heading_estimator_from_env(
        env={HEADING_ESTIMATOR_ENV_VAR: "backend.imu.heading:GyroYawIntegrator"}
    )
    classifier = activity_classifier_from_env(
        env={ACTIVITY_CLASSIFIER_ENV_VAR: "backend.imu.activity:TiltActivityClassifier"}
    )

    assert isinstance(heading, GyroYawIntegrator)
    assert isinstance(classifier, TiltActivityClassifier)
