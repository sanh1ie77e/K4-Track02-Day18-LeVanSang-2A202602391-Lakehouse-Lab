"""Safety checks for trusted lab code; not an OS sandbox for hostile code."""
from __future__ import annotations

import ast
import functools
import json
import inspect
import os
from pathlib import Path
import shutil
import sys
import uuid
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "_lakehouse" / "safe_runs"
MARKER = ".lab-owned.json"
_installed = None
_execution_lock = None


def local_path(value) -> Path:
    value = os.fsdecode(value)
    if value.startswith("file://"):
        tail = value[7:]
        # The lab helper emits file://D:\... on Windows; accept its local drive form.
        if os.name == "nt" and len(tail) >= 3 and tail[0].isalpha() and tail[1] == ":":
            value = unquote(tail)
        else:
            uri = urlsplit(value)
            if uri.netloc:
                raise PermissionError("Network file locations are forbidden")
            value = unquote(uri.path)
            if os.name == "nt" and len(value) > 2 and value[0] == "/" and value[2] == ":":
                value = value[1:]
    elif "://" in value:
        raise PermissionError("Remote storage is forbidden in safe lab mode")
    return Path(value).absolute()


def checked(value, root: Path, *, allow_root=False) -> Path:
    """Resolve containment AND reject links/junctions, including ancestors."""
    p = local_path(value)
    for part in (p, *p.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise PermissionError(f"Linked path is forbidden: {part}")
    p, root = p.resolve(), root.resolve()
    if not p.is_relative_to(root) or (p == root and not allow_root):
        raise PermissionError(f"Outside permitted lab target: {p}")
    if p.is_relative_to(root / "_recovery"):
        raise PermissionError("Recovery copies cannot be mutation targets")
    if p.name in {MARKER, "execution.lock", "safety_audit.jsonl"}:
        raise PermissionError("Safety control files cannot be mutation targets")
    return p


def create_run() -> Path:
    # Inspect ancestors before mkdir, so a pre-existing junction cannot redirect writes.
    checked(RUNS / "probe", REPO)
    root = RUNS / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    (root / MARKER).write_text(json.dumps({"purpose": "synthetic Day18 lab", "id": root.name}), encoding="utf-8")
    return root


def preflight() -> list[dict]:
    """Inventory dangerous calls; reject shell/dynamic execution in lab inputs."""
    rows = []
    targets = list((REPO / "notebooks").glob("*.py")) + [REPO / "scripts" / n for n in
              ("lakehouse.py", "generate_ai_data.py", "generate_data_lite.py", "verify_lite.py")]
    risky = {"reset", "reset_catalog", "rmtree", "remove", "unlink", "delete", "restore",
             "vacuum", "expire_snapshots", "write_deltalake", "compact", "z_order", "merge"}
    forbidden = {"eval", "exec", "system", "popen", "Popen"}
    for source in targets:
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in forbidden:
                raise PermissionError(f"Unreviewed dynamic/shell execution: {source.name}:{node.lineno}")
            if name in risky:
                rows.append({"file": str(source.relative_to(REPO)), "line": node.lineno,
                             "call": name, "control": "isolated root + runtime checks + recovery"})
    return rows


def install(root=None):
    global _installed, _execution_lock
    root = local_path(root or os.environ["LAKEHOUSE_ROOT"]).resolve()
    checked(root, RUNS)
    if not (root / MARKER).is_file():
        raise PermissionError("Run has no ownership marker")
    if _installed is not None:
        if _installed != root:
            raise PermissionError("Cannot change the guarded root in this process")
        return root
    # One process/kernel owns a run at a time, including during orphan sweeps.
    lock = (root / "execution.lock").open("a+b")
    lock.seek(0)
    if os.name == "nt":
        import msvcrt
        if (root / "execution.lock").stat().st_size == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            lock.close()
            raise PermissionError("Another process is using this run; start a new run") from error
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    _execution_lock = lock
    os.environ["LAKEHOUSE_ROOT"] = str(root)
    sys.dont_write_bytecode = True
    tmp = root / "tmp"
    tmp.mkdir(exist_ok=True)
    os.environ.update(TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp))
    import tempfile
    tempfile.tempdir = str(tmp)
    recovery = root / "_recovery"
    recovery.mkdir(exist_ok=True)
    log = root / "safety_audit.jsonl"
    busy = False

    def record(operation, target, decision="ALLOW", **details):
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"operation": operation, "target": str(target), "decision": decision,
                                **details}, ensure_ascii=False) + "\n")

    def validate(value, operation):
        try:
            return checked(value, root)
        except (PermissionError, TypeError, ValueError) as error:
            record(operation, value, "BLOCK", reason=str(error))
            raise PermissionError(str(error)) from error

    def backup(target, operation):
        nonlocal busy
        if not target.exists() or busy:
            return
        # Check descendants too: copytree must never follow a link to user data.
        if target.is_dir():
            for item in target.rglob("*"):
                checked(item, root)
        destination = recovery / (uuid.uuid4().hex + "-" + target.name)
        busy = True
        try:
            if target.is_dir():
                shutil.copytree(target, destination)
            else:
                shutil.copy2(target, destination)
            record(operation, target, backup=str(destination))
        finally:
            busy = False

    def audit(event, args):
        if event in {"os.remove", "os.rmdir", "shutil.rmtree"}:
            p = validate(args[0], event)
            backup(p, event)
        elif event == "os.rename":
            src, dst = validate(args[0], event), validate(args[1], event)
            backup(src, event)
            backup(dst, event)
        elif event == "subprocess.Popen" or event == "os.system":
            record(event, args[0], "BLOCK")
            raise PermissionError("Child processes/shells forbidden inside notebook execution")
        elif event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            p = local_path(args[0]).resolve()
            flags = args[2]
            writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            # Protect pre-existing lakehouse data against Python-level writes too.
            old_root = REPO / "_lakehouse"
            if writing and p.is_relative_to(old_root) and not p.is_relative_to(root):
                record("open-write", p, "BLOCK")
                raise PermissionError("Original lakehouse is read-only in safe mode")

    import deltalake
    import deltalake.writer as writer
    cls = deltalake.DeltaTable
    old_init = cls.__init__

    @functools.wraps(old_init)
    def guarded_init(self, table_uri, *args, **kwargs):
        validate(table_uri, "DeltaTable")
        return old_init(self, table_uri, *args, **kwargs)
    cls.__init__ = guarded_init
    old_write = deltalake.write_deltalake

    @functools.wraps(old_write)
    def guarded_write(table_or_uri, *args, **kwargs):
        uri = table_or_uri.table_uri if isinstance(table_or_uri, cls) else table_or_uri
        p = validate(uri, "write_deltalake")
        if str(kwargs.get("mode", "error")) == "overwrite":
            backup(p, "overwrite")
        record("write_deltalake", p, mode=str(kwargs.get("mode", "error")))
        return old_write(table_or_uri, *args, **kwargs)
    deltalake.write_deltalake = writer.write_deltalake = guarded_write
    for method in ("delete", "restore", "vacuum", "merge", "update", "repair"):
        original = getattr(cls, method)
        def wrap(original=original, method=method):
            @functools.wraps(original)
            def guarded(self, *args, **kwargs):
                p = validate(self.table_uri, method)
                bound = inspect.signature(original).bind(self, *args, **kwargs)
                bound.apply_defaults()
                options = bound.arguments
                def vacuum_path(candidate):
                    # deltalake 1.6 may return table-relative paths, not full URIs.
                    value = candidate if Path(candidate).is_absolute() or "://" in candidate else p / candidate
                    return str(validate(value, "vacuum-candidate"))
                if method == "vacuum":
                    if p.relative_to(root).parts[0] != "scratch":
                        raise PermissionError("VACUUM is only allowed on scratch tables")
                    if not options["dry_run"]:
                        candidates = original(self, retention_hours=options["retention_hours"],
                                              dry_run=True, enforce_retention_duration=options["enforce_retention_duration"])
                        for candidate in candidates:
                            vacuum_path(candidate)
                if method != "vacuum" or not options["dry_run"]:
                    backup(p, method)
                record(method, p)
                result = original(self, *args, **kwargs)
                return [vacuum_path(c) for c in result] if method == "vacuum" else result
            return guarded
        setattr(cls, method, wrap())
    import lakehouse as lh
    lh.ROOT, lh.ICEBERG_ROOT = root, root / "iceberg"
    old_path, old_reset, old_catalog_dir = lh.path, lh.reset, lh._catalog_dir

    def safe_path(layer, table):
        p = validate(root / layer / table, "path")
        return old_path(layer, table)
    def safe_reset(*paths):
        # Validate every target before mutating any of them.
        targets = [validate(p, "reset") for p in paths]
        for p in targets:
            backup(p, "reset")
        return old_reset(*map(str, targets))
    def safe_catalog_dir(name):
        if not name or Path(name).name != name or name in {".", ".."}:
            raise PermissionError("Catalog name must be a single component")
        return validate(old_catalog_dir(name), "catalog")
    lh.path, lh.reset, lh._catalog_dir = safe_path, safe_reset, safe_catalog_dir
    from pyiceberg.catalog.sql import SqlCatalog
    old_create, old_load = SqlCatalog.create_table, SqlCatalog.load_table
    def create(self, *args, **kwargs):
        validate(self.properties["warehouse"], "iceberg-warehouse")
        if kwargs.get("location"):
            validate(kwargs["location"], "iceberg-create")
        return old_create(self, *args, **kwargs)
    def load(self, *args, **kwargs):
        table = old_load(self, *args, **kwargs)
        validate(table.location(), "iceberg-load")
        validate(table.metadata_location, "iceberg-metadata")
        return table
    SqlCatalog.create_table, SqlCatalog.load_table = create, load
    sys.addaudithook(audit)
    _installed = root
    record("install", root)
    print(f"Safety guard active: {root}\nOriginal lakehouse is excluded; recovery and audit enabled.")
    return root


if __name__ == "__main__":
    import runpy
    # The notebook bootstrap imports lab_safety again; reuse this module and lock.
    sys.modules["lab_safety"] = sys.modules[__name__]
    install()
    target = Path(sys.argv[1]).resolve()
    if target.parent not in {REPO / "scripts", REPO / "notebooks"}:
        raise PermissionError("Only repository lab entry points are allowed")
    sys.path.insert(0, str(target.parent))
    sys.argv = sys.argv[1:]
    runpy.run_path(str(target), run_name="__main__")
