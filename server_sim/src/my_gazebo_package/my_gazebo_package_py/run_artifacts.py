"""MCAP-first run artifact and recording contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile


RUN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
REQUIRED_TOPICS = (
    '/clock', '/tf', '/tf_static', '/odometry/filtered',
    '/racing/control_candidate', '/racing/local_path',
    '/racing/supervisor_status', '/car/control_request',
    '/racing/recorder/heartbeat',
)
OPTIONAL_TOPICS = (
    '/rtabmap/mapData', '/rtabmap/landmarks', '/edge/landmark_detections',
    '/racing/active_path', '/racing/candidate_path', '/racing/path_diagnostics',
    '/racing/fault', '/ground_truth/tf',
    '/edge/camera/rgb/image_raw/compressed',
    '/edge/camera/depth/image_raw/compressed', '/yolo/image_annotations',
)


class RunArtifactError(ValueError):
    """Raised when run metadata or finalization violates the contract."""


def utc_now():
    return datetime.now(timezone.utc)


def utc_name(stamp):
    return stamp.strftime('%Y%m%dT%H%M%SZ')


def _atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=path.parent,
            prefix=f'.{path.name}.', delete=False) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, path)


def _validate_run_id(run_id):
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise RunArtifactError('run_id must be 1-64 safe filename characters')


def _validate_topics(topics):
    values = tuple(topics)
    if not values or any(not isinstance(topic, str) or not topic.startswith('/')
                         for topic in values):
        raise RunArtifactError('MCAP topic allowlist must contain absolute topics')
    if any(topic not in values for topic in REQUIRED_TOPICS):
        missing = [topic for topic in REQUIRED_TOPICS if topic not in values]
        raise RunArtifactError(f'MCAP allowlist missing required topics: {missing}')
    if len(set(values)) != len(values):
        raise RunArtifactError('MCAP topic allowlist contains duplicates')
    return values


def build_mcap_command(output, topics, ros2='ros2'):
    """Build explicit rosbag2 MCAP command; never use ``--all`` implicitly."""
    values = _validate_topics(topics)
    return [ros2, 'bag', 'record', '--storage', 'mcap', '--output',
            str(output), '--topics', *values]


@dataclass
class RunArtifacts:
    """Own one run directory and atomically publish lifecycle JSON artifacts."""

    run_dir: Path
    run_id: str
    topics: tuple[str, ...]
    started_at: datetime

    @classmethod
    def prepare(cls, root, run_id, metadata=None, topics=None, started_at=None):
        _validate_run_id(run_id)
        stamp = started_at or utc_now()
        if stamp.tzinfo is None:
            raise RunArtifactError('started_at must be timezone-aware')
        selected_topics = _validate_topics(
            REQUIRED_TOPICS + OPTIONAL_TOPICS if topics is None else topics)
        root_path = Path(root)
        run_dir = root_path / f'run_{utc_name(stamp)}_{run_id}'
        if run_dir.exists():
            raise RunArtifactError(f'run artifact already exists: {run_dir}')
        (run_dir / 'bag').mkdir(parents=True)
        instance = cls(run_dir, run_id, selected_topics, stamp)
        payload = dict(metadata or {})
        payload.update({
            'run_id': run_id,
            'utc_start': stamp.astimezone(timezone.utc).isoformat(),
            'status': 'PREPARED',
            'topics': list(selected_topics),
            'bag_path': 'bag',
            'summary_path': 'run_summary.json',
            'manifest_path': 'run_manifest.json',
        })
        _atomic_json(run_dir / 'run_manifest.json', payload)
        instance.heartbeat('PREPARED', stamp)
        return instance

    @property
    def bag_dir(self):
        return self.run_dir / 'bag'

    def heartbeat(self, state, stamp=None):
        """Atomically update recorder heartbeat for supervisor freshness checks."""
        instant = stamp or utc_now()
        if instant.tzinfo is None:
            raise RunArtifactError('heartbeat stamp must be timezone-aware')
        _atomic_json(self.run_dir / 'recorder_heartbeat.json', {
            'run_id': self.run_id,
            'state': str(state),
            'utc': instant.astimezone(timezone.utc).isoformat(),
        })

    def bag_integrity(self):
        metadata = self.bag_dir / 'metadata.yaml'
        segments = sorted(self.bag_dir.glob('*.mcap'))
        return {
            'metadata_present': metadata.is_file(),
            'mcap_segments': [segment.name for segment in segments],
            'valid': metadata.is_file() and bool(segments),
        }

    def finalize(self, terminal_state, summary=None, stopped_at=None):
        if not terminal_state or terminal_state == 'RUNNING':
            raise RunArtifactError('terminal_state must be non-running')
        stamp = stopped_at or utc_now()
        if stamp.tzinfo is None:
            raise RunArtifactError('stopped_at must be timezone-aware')
        payload = dict(summary or {})
        payload.update({
            'run_id': self.run_id,
            'terminal_state': terminal_state,
            'utc_stop': stamp.astimezone(timezone.utc).isoformat(),
            'bag_integrity': self.bag_integrity(),
            'artifact_path': str(self.run_dir),
        })
        _atomic_json(self.run_dir / 'run_summary.json', payload)
        self.heartbeat(terminal_state, stamp)
        return payload


@dataclass
class McapRecorderProcess:
    """Own rosbag2 subprocess lifecycle without importing broken rosbag2_py."""

    artifacts: RunArtifacts
    process: subprocess.Popen | None = None
    log_stream: object | None = None

    def start(self, ros2='ros2'):
        if self.process is not None:
            raise RunArtifactError('MCAP recorder already started')
        if shutil.which(ros2) is None and os.path.sep not in ros2:
            raise RunArtifactError(f'ros2 executable not found: {ros2}')
        # rosbag2 requires output directory not to exist. Prepare creates an
        # empty bag placeholder for manifest consumers; remove only that known
        # empty directory immediately before recorder start.
        try:
            self.artifacts.bag_dir.rmdir()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise RunArtifactError(
                f'MCAP output directory is not empty: {self.artifacts.bag_dir}') from error
        command = build_mcap_command(self.artifacts.bag_dir,
                                     self.artifacts.topics, ros2=ros2)
        log_path = self.artifacts.run_dir / 'recorder.log'
        self.log_stream = log_path.open('w', encoding='utf-8')
        try:
            self.process = subprocess.Popen(
                command, stdout=self.log_stream, stderr=subprocess.STDOUT,
                text=True, start_new_session=True)
        except Exception:
            self.log_stream.close()
            self.log_stream = None
            raise
        self.artifacts.heartbeat('RECORDING')
        return command

    def stop(self, terminal_state='COMPLETE', timeout=10.0):
        if self.process is None:
            raise RunArtifactError('MCAP recorder was not started')
        process = self.process
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2.0)
        if self.log_stream is not None:
            self.log_stream.flush()
            self.log_stream.close()
            self.log_stream = None
        result = self.artifacts.finalize(
            terminal_state, {'recorder_returncode': process.returncode})
        self.process = None
        return result
