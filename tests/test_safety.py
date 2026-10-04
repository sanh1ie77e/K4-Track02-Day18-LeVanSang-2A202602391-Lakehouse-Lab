"""Regression checks for accidental destructive operations in safe lab mode."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lab_safety import checked, create_run, preflight


def test_root_and_parent_deletion_are_blocked(tmp_path):
    for p in (tmp_path, tmp_path.parent, tmp_path / ".." / "user-data"):
        with pytest.raises(PermissionError):
            checked(p, tmp_path)


def test_sibling_prefix_and_remote_targets_are_blocked(tmp_path):
    for p in (str(tmp_path) + "-other/file", "s3://bucket/table", "file://server/share"):
        with pytest.raises(PermissionError):
            checked(p, tmp_path)


def test_recovery_is_not_a_deletion_target(tmp_path):
    with pytest.raises(PermissionError):
        checked(tmp_path / "_recovery" / "backup", tmp_path)


def test_preflight_finds_real_dangerous_calls():
    calls = {r["call"] for r in preflight()}
    assert {"vacuum", "reset", "delete", "unlink", "expire_snapshots"} <= calls


def test_guard_blocks_real_file_and_native_delta_operations(tmp_path):
    root = create_run()
    sentinel = tmp_path / "valuable.txt"
    sentinel.write_text("KEEP ME", encoding="utf-8")
    script = '''
from pathlib import Path
import os, shutil
from lab_safety import install
install()
import lakehouse as lh
from deltalake import write_deltalake, DeltaTable
import pyarrow as pa
outside = Path(os.environ['SENTINEL'])
actions = [lambda: outside.unlink(), lambda: shutil.rmtree(outside.parent),
           lambda: lh.reset(outside.parent), lambda: lh.path('scratch', '../../outside'),
           lambda: write_deltalake(str(outside.parent / 'delta'), pa.table({'id':[1]})),
           lambda: DeltaTable(str(outside.parent / 'delta'))]
for action in actions:
    try: action()
    except PermissionError: pass
    else: raise AssertionError('unsafe operation was allowed')
p = lh.path('scratch', 'owned')
write_deltalake(p, pa.table({'id':[1,2]}))
DeltaTable(p).delete('id = 1')
assert DeltaTable(p).count() == 1
doomed = DeltaTable(p).vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)
assert doomed and all(Path(f).is_absolute() and Path(f).exists() for f in doomed)
DeltaTable(p).vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
assert DeltaTable(p).count() == 1
b = lh.path('bronze', 'protected')
write_deltalake(b, pa.table({'id':[1]}))
try: DeltaTable(b).vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
except PermissionError: pass
else: raise AssertionError('bronze vacuum allowed')
assert list((Path(os.environ['LAKEHOUSE_ROOT']) / '_recovery').iterdir())
print('blocked unsafe targets; permitted scratch mutation; recovery exists')
'''
    env = dict(os.environ, LAKEHOUSE_ROOT=str(root), SENTINEL=str(sentinel),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / "scripts"), PYTHONUTF8="1")
    proc = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert sentinel.read_text(encoding="utf-8") == "KEEP ME"


def test_symlink_escape_rejected_when_supported(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Windows account cannot create symbolic links")
    with pytest.raises(PermissionError):
        checked(link / "file", tmp_path)


def test_two_processes_cannot_share_a_run():
    root = create_run()
    env = dict(os.environ, LAKEHOUSE_ROOT=str(root),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / "scripts"), PYTHONUTF8="1")
    holder = subprocess.Popen([sys.executable, "-c",
        "from lab_safety import install; install(); print('READY',flush=True); input()"],
        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while True:
            line = holder.stdout.readline()
            if line.strip() == "READY":
                break
            if not line:
                raise AssertionError(holder.stderr.read())
        other = subprocess.run([sys.executable, "-c",
            "from lab_safety import install; install()"], env=env, capture_output=True, text=True)
        assert other.returncode != 0 and "Another process is using this run" in other.stderr
    finally:
        holder.communicate("\n", timeout=30)
