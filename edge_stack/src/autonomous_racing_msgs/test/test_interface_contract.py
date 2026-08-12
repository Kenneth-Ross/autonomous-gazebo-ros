from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_required_interface_files_and_constants_exist():
    required = {
        'msg/ConeEstimate.msg': ('PROVISIONAL=0', 'PERSISTENT=1', 'QUARANTINED=2'),
        'msg/ConeMap.msg': ('map_revision', 'localization_confidence', 'ConeEstimate[] cones'),
        'msg/RacingPathPoint.msg': ('TRUSTED=0', 'DEGRADED=1', 'UNSAFE=2'),
        'msg/RacingPath.msg': ('ROLLING=0', 'GLOBAL=1', 'revision', 'closed_loop'),
        'msg/ControlCandidate.msg': ('path_revision', 'fault_reason'),
        'msg/SupervisorStatus.msg': ('PREPARING=1', 'READY=2', 'RACING=4', 'stop_reason'),
        'msg/RecorderHeartbeat.msg': ('RECORDING=2', 'bag_healthy'),
        'srv/PrepareRun.srv': ('run_id_hint', 'track_name', 'seed'),
        'srv/StartRun.srv': ('bool start',),
        'srv/AbortRun.srv': ('string reason',),
    }
    for relative, needles in required.items():
        content = (ROOT / relative).read_text()
        for needle in needles:
            assert needle in content, (relative, needle)


def test_no_duplicate_interface_source_is_checked_in():
    assert not (ROOT / 'COPYING_INTERFACE_DEFINITIONS_HERE').exists()
