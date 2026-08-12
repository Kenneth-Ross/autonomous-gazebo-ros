from datetime import datetime, timezone

from my_gazebo_package_py.run_artifacts import (
    build_mcap_command, REQUIRED_TOPICS, RunArtifactError, RunArtifacts)
import pytest


STAMP = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def test_mcap_command_is_explicit_and_requires_core_topics(tmp_path):
    output = tmp_path / 'bag'
    command = build_mcap_command(output, REQUIRED_TOPICS)
    assert command[:7] == [
        'ros2', 'bag', 'record', '--storage', 'mcap', '--output', str(output)]
    assert command[7] == '--topics'
    assert '--all' not in command
    with pytest.raises(RunArtifactError):
        build_mcap_command(output, ['/clock'])
    with pytest.raises(RunArtifactError):
        RunArtifacts.prepare(tmp_path, 'empty', topics=())


def test_prepare_writes_manifest_before_motion(tmp_path):
    artifacts = RunArtifacts.prepare(
        tmp_path, 'fixed-route', metadata={'track': 'catalunya'},
        topics=REQUIRED_TOPICS, started_at=STAMP)
    manifest = artifacts.run_dir / 'run_manifest.json'
    assert manifest.is_file()
    payload = manifest.read_text()
    assert '"status": "PREPARED"' in payload
    assert '"track": "catalunya"' in payload
    assert (artifacts.run_dir / 'bag').is_dir()
    assert (artifacts.run_dir / 'recorder_heartbeat.json').is_file()
    assert (artifacts.run_dir / 'bag').is_dir()


def test_run_id_and_topic_validation_is_strict(tmp_path):
    with pytest.raises(RunArtifactError):
        RunArtifacts.prepare(tmp_path, '../escape', topics=REQUIRED_TOPICS)
    with pytest.raises(RunArtifactError):
        RunArtifacts.prepare(tmp_path, 'ok', topics=('/clock',) * len(REQUIRED_TOPICS))


def test_finalize_summary_is_atomic_and_reports_missing_bag(tmp_path):
    artifacts = RunArtifacts.prepare(tmp_path, 'run1', topics=REQUIRED_TOPICS, started_at=STAMP)
    summary = artifacts.finalize('ABORTED', {'reason': 'test'}, stopped_at=STAMP)
    assert summary['terminal_state'] == 'ABORTED'
    assert summary['bag_integrity']['valid'] is False
    assert (artifacts.run_dir / 'run_summary.json').is_file()
    assert '"reason": "test"' in (artifacts.run_dir / 'run_summary.json').read_text()


def test_bag_integrity_requires_metadata_and_segment(tmp_path):
    artifacts = RunArtifacts.prepare(
        tmp_path, 'run2', topics=REQUIRED_TOPICS, started_at=STAMP)
    assert artifacts.bag_integrity()['valid'] is False
    (artifacts.bag_dir / 'metadata.yaml').write_text('rosbag2_bagfile_information: {}\n')
    assert artifacts.bag_integrity()['valid'] is False
    (artifacts.bag_dir / 'segment_0.mcap').write_bytes(b'MCAP')
    assert artifacts.bag_integrity()['valid'] is True


def test_recorder_start_removes_empty_bag_placeholder(tmp_path):
    artifacts = RunArtifacts.prepare(
        tmp_path, 'recorder-start', topics=REQUIRED_TOPICS, started_at=STAMP)
    assert artifacts.bag_dir.is_dir()
    # Command construction remains explicit; fake executable exits immediately.
    from my_gazebo_package_py.run_artifacts import McapRecorderProcess
    recorder = McapRecorderProcess(artifacts)
    command = recorder.start(ros2='/bin/true')
    assert command[0] == '/bin/true'
    assert not artifacts.bag_dir.exists()
    summary = recorder.stop('ABORTED')
    assert summary['terminal_state'] == 'ABORTED'
    assert (artifacts.run_dir / 'recorder.log').is_file()
