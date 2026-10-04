"""Read-only probe of live Jupyter kernels, plus an isolated .venv kernel check."""
from pathlib import Path
import json
import os
import sys
import time
import uuid
from queue import Empty
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from jupyter_client import KernelManager, BlockingKernelClient
from jupyter_core.paths import jupyter_runtime_dir

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / ".lab-runtime"
EXPECTED = (REPO / ".venv" / "Scripts" / "python.exe").resolve()
PROBE = '''import sys, json, importlib.metadata as m
print("KERNEL_PROBE=" + json.dumps({"executable":sys.executable, "prefix":sys.prefix,
    "python":sys.version.split()[0], "versions":{n:m.version(n) for n in
    ["deltalake","pyiceberg","duckdb","polars","ipykernel"]}}))
'''


def probe(client, timeout=10):
    client.start_channels()
    try:
        client.wait_for_ready(timeout=timeout)
        message_id = client.execute(PROBE, store_history=False, silent=False)
        output = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = client.get_iopub_msg(timeout=timeout)
            if message.get("parent_header", {}).get("msg_id") != message_id:
                continue
            if message["msg_type"] == "stream":
                output += message["content"]["text"]
            elif message["msg_type"] == "error":
                raise RuntimeError(message["content"].get("evalue"))
            elif message["msg_type"] == "status" and message["content"]["execution_state"] == "idle":
                break
        line = next(s for s in output.splitlines() if s.startswith("KERNEL_PROBE="))
        result = json.loads(line.split("=", 1)[1])
        result["correct_venv"] = Path(result["executable"]).resolve() == EXPECTED
        return result
    finally:
        client.stop_channels()


def main():
    dirs = {RUNTIME / "jupyter", Path(jupyter_runtime_dir()),
            Path.home() / "AppData/Roaming/jupyter/runtime",
            Path.home() / "AppData/Local/jupyter/runtime"}
    live = []
    local_http = build_opener(ProxyHandler({}))
    for directory in dirs:
        if not directory.exists():
            continue
        for server_file in directory.glob("jpserver-*.json"):
            try:
                info = json.loads(server_file.read_text(encoding="utf-8"))
                url = info["url"]
                if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
                    continue
                headers = {"Authorization": "token " + info.get("token", "")}
                with local_http.open(Request(url.rstrip("/") + "/api/sessions", headers=headers), timeout=3) as response:
                    sessions = json.load(response)
                for session in sessions:
                    kernel = session["kernel"]
                    entry = {"notebook": session.get("path"), "kernel_name": kernel["name"],
                             "state": kernel.get("execution_state")}
                    connection = directory / ("kernel-" + kernel["id"] + ".json")
                    if entry["state"] == "idle" and connection.exists():
                        client = BlockingKernelClient(connection_file=str(connection))
                        client.load_connection_file()
                        entry["probe"] = probe(client, timeout=5)
                    live.append(entry)
            except (OSError, ValueError, KeyError, RuntimeError, StopIteration, Empty) as error:
                # Do not include URLs, tokens or connection data in reports.
                live.append({"status": "live probe unavailable", "error_type": type(error).__name__})
    os.environ["JUPYTER_PATH"] = str(RUNTIME)
    probe_runtime = RUNTIME / ("kernel-probe-" + uuid.uuid4().hex)
    probe_runtime.mkdir(parents=True)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(probe_runtime)
    os.environ["JUPYTER_CONFIG_DIR"] = str(RUNTIME / "config")
    manager = KernelManager(kernel_name="lab-safe", connection_file=str(probe_runtime / "connection.json"))
    try:
        manager.start_kernel(cwd=str(REPO / "notebooks"), env=dict(os.environ,
            IPYTHONDIR=str(RUNTIME / "kernel-check"), PYTHONUTF8="1"))
        isolated = probe(manager.blocking_client())
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    assert isolated["correct_venv"], "Kernel uses a different Python environment"
    assert all(s.get("probe", {}).get("correct_venv", True) for s in live), "A live kernel uses a different environment"
    report = {"expected_python": str(EXPECTED), "live_sessions": live,
              "isolated_kernel": isolated, "passed": True}
    dest = REPO / "submission/evidence/kernel_check.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
