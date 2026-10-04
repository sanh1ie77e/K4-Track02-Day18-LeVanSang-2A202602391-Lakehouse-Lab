"""Execute and save all eight notebooks with isolation and real evidence."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from lab_safety import REPO, create_run, preflight

OUT = REPO / "submission"

EXTRA = {
1: '''import json
for commit in _log:
    print("COMMIT", commit.name)
    print(commit.read_text(encoding="utf-8"))
print("SCHEMA", DeltaTable(table_path).schema())
assert DeltaTable(table_path).count() == 4
LAB_METRICS = dict(commits=len(_log), rows=DeltaTable(table_path).count(), tier_groups=tier_counts)
''',
2: '''assert files_before >= 100
LAB_METRICS = dict(files_before=files_before, files_after=files_after, before_ms=before*1000,
                  after_ms=after*1000, speedup=speedup, pruning=pruned_ratio, candidate_files=hits)
''',
3: '''LAB_METRICS = dict(versions=len(final_history), current_version=DeltaTable(table_path).version(),
                  restored_rows=DeltaTable(table_path).count(), bad_rows=bad_count,
                  merge_metrics=next(h.get("operationMetrics", {}) for h in final_history if "MERGE" in h["operation"]))
''',
4: '''print("FULL GOLD TABLE")
with pl.Config(tbl_rows=100, tbl_cols=10, tbl_width_chars=160):
    print(gold_df.sort(["date", "model"]))
assert n_dates >= 7 and n_models == 3 and gold_df.height == n_dates * n_models
assert gold_df.filter(pl.col("p50_latency_ms") > pl.col("p95_latency_ms")).height == 0
assert gold_df.filter((pl.col("cost_usd") <= 0) | pl.col("cost_usd").is_null()).height == 0
assert gold_df.filter((pl.col("error_rate") < 0) | (pl.col("error_rate") > 1) | pl.col("error_rate").is_null()).height == 0
LAB_METRICS = dict(bronze=bronze_n, silver=silver_n, dropped=bronze_n-silver_n, dates=n_dates,
                  models=n_models, gold_rows=gold_df.height, cost_total=float(gold_df["cost_usd"].sum()),
                  error_min=float(gold_df["error_rate"].min()), error_max=float(gold_df["error_rate"].max()),
                  storage=dict(bronze=BRONZE, silver=SILVER, gold=GOLD))
''',
5: '''LAB_METRICS = dict(full_files=files_all, filtered_files=files_one, pruning=PRUNE_RATIO,
                  metadata_bytes=meta_bytes, data_bytes=data_bytes, metadata_data_ratio=meta_bytes/max(data_bytes,1),
                  field_id=next(f.field_id for f in tbl.schema().fields if f.name == "latency_millis"),
                  specs=sorted(specs_in_use), rows=tbl.scan().to_arrow().num_rows)
''',
6: '''assert DeltaTable(TABLE).count() == N_BATCHES * ROWS_PER_BATCH
LAB_METRICS = dict(files_before=base["data files"], files_compact=after_compact["data files"],
                  files_cluster=total_files, candidate_files=after_cluster, skip_rate=1-after_cluster/max(total_files,1),
                  vacuum_bytes=before_vacuum-(after_vacuum["data bytes"]+after_vacuum["log bytes"]),
                  delta_orphans=len(found), orphan_bytes=reclaimed, snapshots_before=ice_before["snapshots"],
                  snapshots_after=ice_final["snapshots"], stranded_lists=len(stranded), iceberg_reclaimed=reclaimed_ice,
                  checkpoint=bool(ckpt), delta_rows=DeltaTable(TABLE).count(), iceberg_rows=ice.scan().to_arrow().num_rows)
''',
7: '''LAB_METRICS = dict(amplification=AMPLIFICATION, f32_bytes=du(F32), int8_bytes=du(I8),
                  storage_ratio=du(F32)/max(du(I8),1), recall=float(recall), topic_fidelity=float(topic_fidelity),
                  query_topic=query_topic, top_topics=top_topics, table_hits=in_hits, stale_index_hits=ex_hits,
                  cdf_deletes=len(deletes), docs=n, dim=dim)
''',
8: '''old_subject = DeltaTable(GOVERNED, version=corpus_version).to_pyarrow_table(filters=[("subject_id", "=", SUBJECT)]).num_rows
assert old_subject == before and after == 0
LAB_METRICS = dict(agent_partitions=2, policies=gold.num_rows, pinned_version=training_run["table_version"],
                  pinned_steps=pinned.count(), recorded_steps=training_run["n_steps_seen"],
                  catalog_reads=mcp.catalog_reads, confirmation=attempt["resultType"], task_status=st["status"],
                  partitions=parts, unclassified=unclassified, trainable=trainable,
                  subject_before=before, subject_after=after, subject_old_version=old_subject)
'''
}


def inventory_original():
    base = REPO / "_lakehouse"
    result = {}
    for p in base.rglob("*"):
        if p.is_relative_to(base / "safe_runs") or not p.is_file():
            continue
        if p.is_symlink():
            raise PermissionError(f"Cannot fingerprint a linked original file: {p}")
        result[str(p.relative_to(base))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def run_command(args, env, log):
    p = subprocess.run([sys.executable, *args], cwd=REPO, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    log.write_text(p.stdout + p.stderr, encoding="utf-8")
    print(p.stdout, flush=True)
    if p.returncode:
        raise RuntimeError(f"Command failed; see {log}:\n{p.stderr[-2000:]}")


def main():
    import jupytext
    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter
    before = inventory_original()
    rows = preflight()
    for sub in ("notebooks", "screenshots", "evidence"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    (OUT / "evidence" / "risk_inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    root = create_run()
    env = dict(os.environ, LAKEHOUSE_ROOT=str(root), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    checks_root = create_run()
    check_env = dict(env, LAKEHOUSE_ROOT=str(checks_root))
    run_command(["scripts/lab_safety.py", "scripts/verify_lite.py"], check_env, OUT / "evidence" / "smoke.txt")
    run_command(["-m", "pytest", "tests/test_lab18.py", "tests/test_safety.py", "-q",
                 "--basetemp=" + str(checks_root / "pytest")], check_env, OUT / "evidence" / "pytest.txt")
    # A local kernelspec ensures execution uses the user's .venv, not a global Python.
    runtime = REPO / ".lab-runtime"
    spec = runtime / "kernels" / "lab-safe"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "kernel.json").write_text(json.dumps({"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
           "display_name": "Day18 safe .venv", "language": "python"}), encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(runtime)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime / "jupyter")
    os.environ["JUPYTER_CONFIG_DIR"] = str(runtime / "config")
    env["IPYTHONDIR"] = str(runtime / "ipython")
    metrics = {}
    bootstrap = '''from pathlib import Path
import os, sys
_repo = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "scripts" / "lab_safety.py").is_file())
sys.path.insert(0, str(_repo / "scripts"))
sys.path.insert(0, str(_repo / "notebooks"))
from lab_safety import create_run, install
_safe_root = install(os.environ.get("LAKEHOUSE_ROOT") or create_run())
'''
    for n, source in enumerate(sorted((REPO / "notebooks").glob("[0-9]*.py")), 1):
        print(f"Executing NB{n}: {source.name}", flush=True)
        nb = jupytext.read(source)
        nb.cells.insert(0, nbformat.v4.new_markdown_cell("## Chạy an toàn\nDữ liệu giả chạy trong vùng riêng dưới `_lakehouse/safe_runs/`. Cell sau bật kiểm tra đường dẫn, sao lưu trước xóa và audit; không trỏ tới dữ liệu lakehouse có sẵn."))
        nb.cells.insert(1, nbformat.v4.new_code_cell(bootstrap))
        nb.cells.append(nbformat.v4.new_code_cell(EXTRA[n] + '\nprint("LAB_METRICS_JSON=" + json.dumps(LAB_METRICS, default=str))' if n in (1,2,5,8) else
            'import json\n' + EXTRA[n] + '\nprint("LAB_METRICS_JSON=" + json.dumps(LAB_METRICS, default=str))'))
        # json import is also required when the source did not import it.
        nb.cells[-1].source = "import json\n" + nb.cells[-1].source
        nb.metadata.kernelspec = {"name": "lab-safe", "display_name": "Day18 safe .venv", "language": "python"}
        client = NotebookClient(nb, timeout=600, kernel_name="lab-safe", resources={"metadata": {"path": str(REPO / "notebooks")}})
        start = time.perf_counter()
        try:
            client.execute(env=env)
        finally:
            nbformat.write(nb, OUT / "notebooks" / (source.stem + ".ipynb"))
        text_outputs = "\n".join(o.get("text", "") for c in nb.cells for o in c.get("outputs", []))
        line = next(s for s in text_outputs.splitlines() if s.startswith("LAB_METRICS_JSON="))
        metrics[f"nb{n:02}"] = json.loads(line.split("=", 1)[1])
        metrics[f"nb{n:02}"]["execution_seconds"] = time.perf_counter() - start
        (OUT / "evidence" / f"nb{n:02}_output.txt").write_text(text_outputs, encoding="utf-8")
        body, _ = HTMLExporter().from_notebook_node(nb)
        (OUT / "evidence" / f"nb{n:02}.html").write_text(body, encoding="utf-8")
        (OUT / "evidence" / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"NB{n} saved with real outputs ({metrics[f'nb{n:02}']['execution_seconds']:.1f}s)", flush=True)
    # Official script runner uses another fresh root; its children are guarded too.
    runner_root = create_run()
    runner_env = dict(env, LAKEHOUSE_ROOT=str(runner_root), LAB_SAFE_MODE="1")
    run_command(["scripts/run_all.py"], runner_env, OUT / "evidence" / "run_all.txt")
    after = inventory_original()
    preservation = {"original_file_count": len(before), "unchanged": before == after,
                    "changed": sorted(k for k in before if before[k] != after.get(k)),
                    "added": sorted(set(after) - set(before)), "before": before, "after": after}
    (OUT / "evidence" / "original_data_integrity.json").write_text(json.dumps(preservation, indent=2), encoding="utf-8")
    assert before == after, "Original data changed; inspect original_data_integrity.json"
    audits = []
    for run in (root, checks_root, runner_root):
        audits.extend(json.loads(s) for s in (run / "safety_audit.jsonl").read_text(encoding="utf-8").splitlines())
    (OUT / "evidence" / "safety_audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "evidence" / "run_environment.json").write_text(json.dumps({"data_root": str(root), "python": sys.version,
        "executable": sys.executable, "original_files_unchanged": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("All 8 notebooks saved; original lakehouse hashes unchanged.")


if __name__ == "__main__":
    main()
