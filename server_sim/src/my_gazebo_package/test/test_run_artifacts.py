"""Configuration boundaries that must be rejected before starting rosbag2."""

from my_gazebo_package_py.run_artifacts import (
    REQUIRED_TOPICS, RunArtifactError, RunArtifacts)
import pytest


def test_run_id_and_topic_validation_is_strict(tmp_path):
    with pytest.raises(RunArtifactError):
        RunArtifacts.prepare(tmp_path, '../escape', topics=REQUIRED_TOPICS)
    with pytest.raises(RunArtifactError):
        RunArtifacts.prepare(tmp_path, 'ok', topics=('/clock',) * len(REQUIRED_TOPICS))
