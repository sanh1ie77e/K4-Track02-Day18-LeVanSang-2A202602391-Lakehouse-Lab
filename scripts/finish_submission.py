"""Add explanations and review documents using saved, measured notebook outputs."""
from pathlib import Path
import html
import importlib.metadata as metadata
import json
import platform
import sys

import nbformat
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def explanations(m):
    a,b,c,d,e,f,g,h = [m[f"nb{i:02}"] for i in range(1,9)]
    return [
f'''## Giải thích kết quả trên máy này

Bảng có {a['commits']} commit JSON và {a['rows']} dòng. Output `BLOCKED` ở cell ghi `age='thirty'` là bằng chứng schema enforcement thực tế; cờ PASS hardcoded ở cell cuối không được dùng thay thế. Schema evolution được yêu cầu rõ bằng `schema_mode="merge"`, thêm `tier`; truy vấn có nhóm `premium` (1 dòng) và NULL (3 dòng cũ).

Enforcement kiểm tra dữ liệu ghi có phù hợp schema đã chốt hay không. Evolution cho phép thay đổi schema theo yêu cầu rõ ràng. Opt-in giúp tránh việc typo hoặc upstream vô tình thêm cột làm thay đổi hợp đồng dữ liệu. Commit chứa `protocol`, `metaData`, `add` và `commitInfo` tùy thao tác: schema/protocol, file mới và thống kê, operation/time/metrics là dấu vết giao dịch. File JSON mô tả lần ghi đã commit; lần ghi sai kiểu không tạo commit thành công. Các dòng cũ nhận `tier=NULL` vì không có giá trị trong dữ liệu ban đầu.
''',
f'''## Giải thích kết quả trên máy này

Trước tối ưu có {b['files_before']} file; sau compaction + Z-order còn {b['files_after']}. Median query giảm {b['before_ms']:.2f} → {b['after_ms']:.2f} ms, speedup {b['speedup']:.2f}×. Chỉ {b['candidate_files']}/{b['files_after']} file có min/max chứa user_id=4242, pruning ratio {b['pruning']:.1f}×. Đối chiếu rubric: ≥100 file ban đầu, số file giảm, và speedup ≥3× **hoặc** pruning ≥10×.

Compaction giảm số file và chi phí mở file; Z-order gom giá trị gần nhau để khoảng min/max hẹp hơn, giúp loại file không thể chứa giá trị tìm kiếm. Nếu gộp thành một file duy nhất thì không còn file nào khác để skip, nên lab dùng target 256 KiB. Pruning ratio ở đây là số file sau tối ưu / số file có khoảng chứa target, dựa trên metadata; không phải bộ đếm I/O thực tế. Benchmark gồm materialization có filter, không đo thời gian khởi tạo DeltaTable trước timer. Cache, SSD, CPU, antivirus và hoạt động nền làm thời gian biến động. Một lần thực nghiệm này không chứng minh cùng speedup ở production.
''',
f'''## Giải thích kết quả trên máy này

MERGE xử lý {c['merge_metrics']['num_source_rows']:,} dòng nguồn: update {c['merge_metrics']['num_target_rows_updated']:,}, insert {c['merge_metrics']['num_target_rows_inserted']:,}. Sau RESTORE, bảng có {c['restored_rows']:,} dòng, {c['bad_rows']} dòng `score < 0`; history gồm {c['versions']} version và có RESTORE tại version {c['current_version']}.

Time travel đọc trạng thái version cũ mà không đổi trạng thái hiện tại. RESTORE thay trạng thái hiện tại bằng tập file của version đích thông qua một commit mới. Không xóa lịch sử giúp các reader đã pin version tiếp tục có một lịch sử nhất quán và giữ audit trail của việc rollback. Khả năng đọc lại còn phụ thuộc file cũ chưa bị vacuum; time travel không thay thế backup khi mất storage.
''',
f'''## Giải thích kết quả trên máy này

Bronze {d['bronze']:,} → Silver {d['silver']:,} dòng; loại {d['dropped']:,} dòng. Gold có {d['dates']} ngày × {d['models']} model = {d['gold_rows']} dòng; đã assert đủ tổ hợp, p50 ≤ p95, cost > 0 và error_rate trong [0,1]. Tổng cost minh họa {d['cost_total']:.6f} USD; error_rate dao động {d['error_min']:.4f}–{d['error_max']:.4f}. Ba đường dẫn storage được ghi trong `LAB_METRICS_JSON`.

Dedup theo request_id ở Silver ngăn retry khiến dashboard đếm request và token nhiều lần. Query dùng ROW_NUMBER ORDER BY ts, giữ bản sớm nhất; với dữ liệu thật cần định nghĩa rõ retry/attempt nào phải được giữ và quy tắc khi timestamp bằng nhau. Dashboard đọc Gold vì tổng hợp theo ngày/model đã được tính sẵn, ổn định định nghĩa metric và giảm scan.

Error rate là trung bình indicator status khác 'ok', trên request sau dedup. Với dữ liệu giả có status đầy đủ thì phù hợp; NULL status sẽ rơi vào ELSE 0 nên cần chính sách riêng trong production. Cost = input_tokens × giá input/1e6 + output_tokens × giá output/1e6, rồi cộng theo nhóm. Giá trong notebook chỉ minh họa. INNER JOIN bảng giá có thể loại model chưa có giá; hiện đã kiểm tra đủ 3 model của generator. Comment nói loại malformed JSON nhưng query không có json_valid/TRY_CAST; dữ liệu giả hợp lệ, nên lần chạy này chưa chứng minh khả năng xử lý JSON hỏng.
''',
f'''## Giải thích kết quả trên máy này

Full scan chọn {e['full_files']} file; filter ngày trên cột ts chọn {e['filtered_files']} file, pruning {e['pruning']:.1f}×. Metadata {e['metadata_bytes']:,} bytes / data {e['data_bytes']:,} bytes = {e['metadata_data_ratio']*100:.2f}%. Rename giữ field ID={e['field_id']}; file sử dụng spec IDs {e['specs']}, đọc được {e['rows']:,} dòng.

Catalog đăng ký bảng và trỏ tới metadata JSON; snapshot trỏ manifest list; manifests mô tả data files và statistics. Hidden partitioning lưu transform day(ts), nên planner suy ra partition phù hợp từ filter trên ts; người dùng không phải thêm điều kiện ts_day. Field ID là định danh ổn định khi nhãn latency_ms đổi thành latency_millis; không cần rewrite file để rename. Mỗi data file gắn partition spec đã dùng lúc ghi, cho phép file layout cũ và mới cùng tồn tại. Spec mới chỉ áp dụng cho ghi mới.

Tỷ lệ ở notebook là metadata:data (mẫu số chỉ data bytes), không phải metadata/(metadata+data). Nó đếm file đang tồn tại trên đĩa ở thời điểm đo, có thể gồm metadata lịch sử. Catalog SQLite và scan planning chạy phía client; chưa đo remote planning, phân quyền hay catalog production. Các phép tính chi phí có sẵn là giả định minh họa, không phải hóa đơn thực tế.
''',
f'''## Giải thích kết quả trên máy này

Compaction {f['files_before']} → {f['files_compact']} file ({f['files_before']/f['files_compact']:.1f}× ít hơn). Sau clustering có thể skip {f['skip_rate']*100:.1f}% file theo min/max, còn {f['candidate_files']}/{f['files_cluster']} file ứng viên. Vacuum thu hồi {f['vacuum_bytes']:,} bytes; tìm/xóa {f['delta_orphans']} orphan Delta ({f['orphan_bytes']:,} bytes). Iceberg giảm {f['snapshots_before']} → {f['snapshots_after']} snapshots, rồi dọn {f['stranded_lists']} manifest lists ({f['iceberg_reclaimed']:,} bytes). Checkpoint và _last_checkpoint tồn tại. Bảng hiện tại vẫn đọc được {f['delta_rows']:,} dòng Delta và {f['iceberg_rows']:,} dòng Iceberg.

Compaction/clustering tạo file mới và tombstone file cũ; bytes vật lý có thể tăng trước vacuum. Trong engine/version đo ở lab, vacuum dựa trên tombstones nên không thấy file orphan chưa từng commit. Bộ tìm orphan dùng file trên đĩa trừ file live và age guard; chỉ an toàn trong vùng chạy độc quyền này sau vacuum. Nó không liệt kê mọi file của version lịch sử, nên không phải công cụ cleanup tổng quát bảo vệ mọi time-travel version.

PyIceberg expiry trong lần chạy này bỏ tham chiếu snapshots, không tự xóa các manifest lists cũ. Sweep mới thu hồi bytes vật lý; đây không phải kết luận cho mọi engine Iceberg. Retention quá ngắn có thể phá reader cũ hoặc training run đã pin. Retention=0 chỉ được guard cho phép ở scratch; có dry-run và recovery trước xóa. Guard khóa một process cho mỗi run, bảo vệ đường dẫn và sao lưu; nó không thay thế transaction coordinator của production.
''',
f'''## Giải thích kết quả trên máy này

Amplification {g['amplification']:.2f}×; float32 {g['f32_bytes']:,} bytes / int8 {g['int8_bytes']:,} bytes = {g['storage_ratio']:.2f}×. Với 100 query vectors, recall@10={g['recall']:.3f}, topic fidelity={g['topic_fidelity']:.3f}. Top-5 SQL search thuộc {g['top_topics']}, query topic={g['query_topic']}. Sau delete: in-table hits={g['table_hits']}, stale external index hits={g['stale_index_hits']}; CDF phát {g['cdf_deletes']} delete events.

Blob inline không gây scan blob nếu query chỉ lấy cột metadata nhờ column pruning. Random fetch có thể phải đọc một row group lớn; pointer cho phép lấy object riêng. Amplification trong lab tính từ footer row-group total_byte_size / kích thước một blob, là proxy dung lượng chưa nén, không đo số byte thực tế qua hệ điều hành/network. Không khẳng định mọi Parquet reader đều đọc toàn row group trong mọi trường hợp.

Quantization giảm độ chính xác số thực để giảm storage; thứ hạng vector gần nhau có thể đổi. Recall@10 đo overlap doc IDs với float32, topic fidelity đo phần kết quả cùng topic; cùng topic không bảo đảm relevance của từng tài liệu. Bộ query lấy ngay từ corpus và có self-match, không phải benchmark query độc lập hoặc tải model thật. External index là bản sao nên delete trong source chưa cập nhật nó. Index cần nhận delete/tombstone, insert và update (cả embedding mới và ID bị thay thế), với checkpoint, retry idempotent và đối soát để tránh mất sự kiện.
''',
f'''## Giải thích kết quả trên máy này

Silver có {h['agent_partitions']} agent_version partitions; Gold có {h['policies']} policies. Training run pin v{h['pinned_version']}: replay {h['pinned_steps']:,} steps khớp {h['recorded_steps']:,} steps đã ghi. 5 lần list_tables chỉ đọc catalog {h['catalog_reads']} lần. Call chưa xác nhận trả {h['confirmation']}; task đạt {h['task_status']}. Có 4 bucket minh họa và UNCLASSIFIED: loại {h['unclassified']} dòng, giữ {h['trainable']} dòng theo rule lab. Subject {h['subject_before']} → {h['subject_after']} dòng hiện tại, nhưng version cũ vẫn có {h['subject_old_version']} dòng.

Pin version xác định snapshot dataset của training run dù ingest tiếp tục; còn cần giữ file của version đó và lưu code/config để tái lập. DELETE tạo trạng thái hiện tại mới, không xóa vật lý file version cũ; retention, vacuum, backup và index ngoài bảng có vòng đời riêng.

MCP là lớp mô phỏng offline: confirmed do caller truyền, delete_rows là no-op, task dùng elapsed time thay background job, replay mới so số steps chứ chưa kiểm tra hash nội dung. Cache được đo ở list_tables, không phải tools/list. Cần xác thực/phân quyền độc lập, approval không cho caller tự đặt, audit và postcondition trước production. Bucket provenance là fixture: mapping CC-BY-4.0 thành public_domain sai về ngữ nghĩa giấy phép; user-owned + consent chưa chứng minh kiểm tra opt-out. Lọc UNCLASSIFIED không chứng minh quyền training hay tuân thủ. Không dùng mapping lab để ra quyết định trên dữ liệu thật.
'''
    ]


def main():
    m = json.loads((OUT / "evidence" / "metrics.json").read_text(encoding="utf-8"))
    if len(m) != 8:
        raise RuntimeError("All eight successful notebook metrics are required")
    prose = explanations(m)
    picks = {
        1: ["BLOCKED by schema", "COMMIT", "SCHEMA"],
        2: ["Files before OPTIMIZE", "Files after OPTIMIZE", "Z-order deliverable metrics"],
        3: ["MERGE 100K", "Rows with score<0", "Total versions:"],
        4: ["Bronze rows:", "Silver rows:", "FULL GOLD TABLE"],
        5: ["Catalog:", "Partition spec:", "Files to read, no filter", "data/", "Field IDs after", "Partition specs in use"],
        6: ["AFTER compaction", "Point query user_id", "AFTER vacuum", "Orphans found:", "Checkpoint written:", "before expiry", "Stranded manifest lists:", "after sweep"],
        7: ["inline parquet:", "On disk (Parquet", "recall@10", "Erased docs still", "CDF rows"],
        8: ["Silver:", "policy-v", "Replay at pinned", "Actual catalog round", "resultType:", "submit_scan", "Partitions on disk:", "Rows for user_007"]
    }
    for n, file in enumerate(sorted((OUT / "notebooks").glob("[0-9]*.ipynb")), 1):
        nb = nbformat.read(file, as_version=4)
        nb.cells = [c for c in nb.cells if c.get("metadata", {}).get("lab_explanation") is not True]
        cell = nbformat.v4.new_markdown_cell(prose[n-1])
        cell.metadata["lab_explanation"] = True
        nb.cells.append(cell)
        nbformat.write(nb, file)
        exported, _ = HTMLExporter().from_notebook_node(nb)
        (OUT / "evidence" / f"nb{n:02}.html").write_text(exported, encoding="utf-8")
        outputs = []
        for c in nb.cells:
            text = "".join(o.get("text", "") for o in c.get("outputs", []))
            if any(s in text for s in picks[n]):
                text = "\n".join(line for line in text.splitlines() if not line.startswith("LAB_METRICS_JSON="))
                outputs.append(text)
        table = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(round(v,6) if isinstance(v,float) else v))}</td></tr>" for k,v in m[f"nb{n:02}"].items() if k not in {"storage", "merge_metrics"})
        blocks = "".join("<pre>" + html.escape(t) + "</pre>" for t in outputs)
        if n == 4:
            cards = []
            for text in outputs:
                for line in text.splitlines():
                    values = [s.strip() for s in line.replace("┆", "│").split("│")[1:-1]]
                    if len(values) == 8 and values[0].startswith("2026-"):
                        date, model, p50, p95, tin, tout, error, cost = values
                        cards.append(f"<section><b>{html.escape(date)} · {html.escape(model)}</b><table><tr><th>p50 / p95 (ms)</th><td>{p50} / {p95}</td></tr><tr><th>cost_usd / error_rate</th><td>{cost} / {error}</td></tr></table></section>")
            assert len(cards) == m['nb04']['gold_rows'], "Gold evidence must show every row"
            blocks = f"<p>Bronze {m['nb04']['bronze']:,} → Silver {m['nb04']['silver']:,} dòng. Gold gồm các dòng dưới, trích nguyên giá trị từ output Polars đã lưu.</p>" + "".join(cards) + "<details><summary>Output đầy đủ có token totals</summary>" + blocks + "</details>"
        page = f'''<!doctype html><html lang="vi"><meta charset="utf-8"><title>NB{n:02} — Bằng chứng thực thi</title>
<style>body{{font:15px system-ui;margin:14px;color:#142536;background:#f4f7fb}}main{{max-width:1400px;margin:auto;background:white;padding:18px;border:1px solid #d1dbe7;border-radius:12px}}h1{{font-size:25px}}table{{border-collapse:collapse;width:100%;font-size:14px;table-layout:fixed}}th,td{{text-align:left;padding:6px;border-bottom:1px solid #dde4ed;overflow-wrap:anywhere}}th{{width:44%}}pre{{font:13px Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:12px;border-left:4px solid #326caa}}.note{{color:#526579}}</style>
<main><h1>NB{n:02} — {html.escape(file.stem)}</h1><p>LeVanSang · 2A202602391 · K4-Track02-Day18 · lightweight</p>
<p class="note">Bằng chứng trích từ output đã thực thi bằng Jupyter kernel của .venv. Số liệu không phải ví dụ. Có thể đối chiếu file .ipynb và metrics.json.</p>
<h2>Số đo trên máy</h2><table>{table}</table><h2>Output thực tế</h2>{blocks}</main></html>'''
        (OUT / "evidence" / f"nb{n:02}_evidence.html").write_text(page, encoding="utf-8")
        summary_page = page.split('<h2>Output thực tế</h2>')[0] + '</main></html>'
        summary_page = summary_page.replace('margin:14px', 'margin:6px').replace('padding:18px', 'padding:10px').replace('font-size:25px', 'font-size:18px').replace('padding:6px;', 'padding:4px;')
        summary_page = summary_page.replace('<p class="note">Bằng chứng trích từ output đã thực thi bằng Jupyter kernel của .venv. Số liệu không phải ví dụ. Có thể đối chiếu file .ipynb và metrics.json.</p>', '<p class="note">Số đo từ output .ipynb đã chạy thật trên máy.</p>')
        (OUT / "evidence" / f"nb{n:02}_summary.html").write_text(summary_page, encoding="utf-8")
        for j, text in enumerate(outputs):
            detail = page.split('<h2>Số đo trên máy</h2>')[0] + f'<h2>Output thực tế — phần {j+1}</h2><pre>' + html.escape(text) + '</pre></main></html>'
            (OUT / "evidence" / f"nb{n:02}_detail_{j:02}.html").write_text(detail, encoding="utf-8")
    versions = {name:metadata.version(name) for name in ["deltalake", "pyiceberg", "duckdb", "polars", "numpy", "pyarrow", "jupytext", "nbclient", "ipykernel"]}
    info = f'''# Thông tin bài nộp

- Họ tên: Lê Văn Sang (LeVanSang)
- MSSV: 2A202602391
- Mã bài: K4-Track02-Day18
- Đường chạy: lightweight cho đủ 8 notebook; không dùng Spark.
- Python: {platform.python_version()}
- Hệ điều hành: {platform.platform()}
- Thực thi: nbclient điều khiển Jupyter kernel từ .venv trên máy này, lưu output vào submission/notebooks. run_all.py là kiểm tra riêng, không được dùng làm bản notebook có output.
- Ngày thực thi: 04/10/2026 (Asia/Ho_Chi_Minh).
- Tên fork yêu cầu: K4-Track02-Day18-LeVanSang-2A202602391-Lakehouse-Lab.
- Trạng thái GitHub: cần kiểm tra tên fork và origin trước khi commit/push; chưa công bố hoặc nộp thay người học.

## Phiên bản thư viện

```json
{json.dumps(versions, indent=2)}
```

## Kiểm tra và bằng chứng

- Smoke: 9/9 (evidence/smoke.txt).
- Bộ gốc: đủ 24 tests đạt; kiểm thử an toàn bổ sung được ghi trong evidence/pytest.txt.
- Runner lightweight: 8/8 (evidence/run_all.txt).
- Notebook giữ output, câu trả lời và các kiểm tra rubric bổ sung NB1/NB2/NB4/NB6/NB8.
- evidence/original_data_integrity.json: SHA-256 dữ liệu lakehouse có trước, trước/sau lần chạy.
- evidence/risk_inventory.json và safety_audit.json: danh sách thao tác nguy hiểm và nhật ký.
- Screenshots: chụp trang bằng chứng từ output đã lưu, xem screenshots/.

## Chạy lại an toàn

Từ gốc repo: `.\\.venv\\Scripts\\python.exe scripts/safe_lab.py`, sau đó `.\\.venv\\Scripts\\python.exe scripts/finish_submission.py`.
Mỗi lần tạo vùng dữ liệu mới; không tái sử dụng dữ liệu gốc. Ảnh là bằng chứng của lần chụp hiện tại; nếu chạy lại, cần chụp lại để khớp số đo mới.
Mở notebook bài nộp trong Jupyter từ gốc repo hoặc một thư mục con và đọc/chạy cell bootstrap an toàn trước các cell khác. Không bỏ cell này.

Kernel `lab-safe` do launcher tạo cục bộ trong .lab-runtime. Để mở lại bằng PowerShell tại gốc repo:

```powershell
$env:JUPYTER_PATH = Join-Path (Get-Location) '.lab-runtime'
$env:IPYTHONDIR = Join-Path (Get-Location) '.lab-runtime/ipython'
.\\.venv\\Scripts\\python.exe -m jupyter lab --notebook-dir=submission/notebooks --no-browser
```

Chọn kernel **Day18 safe .venv**. Kiểm tra bộ bài mà không chạy lại dữ liệu: `.\\.venv\\Scripts\\python.exe scripts/verify_submission.py`.

Người học cần tự kiểm tra output, hiểu giải thích và thực thi lại trong Jupyter theo RULES/SUBMISSION trước khi chốt bài. Reflection và giải thích là bản hỗ trợ bằng AI, cần rà soát theo hiểu biết cá nhân.
'''
    (OUT / "INFO.md").write_text(info, encoding="utf-8")
    reflection = '''# Reflection

Anti-pattern tôi chọn là coi vector index ngoài bảng là nguồn dữ liệu độc lập và chỉ đồng bộ upsert. Với hệ thống RAG dùng tài liệu người dùng, xóa document trong lakehouse nhưng bỏ qua delete event khiến index vẫn trả embedding cũ. NB7 tái hiện điều này: bảng không còn hit của dữ liệu đã xóa nhưng index cũ vẫn có hit.

Cách phòng tránh là dùng lakehouse làm nguồn chuẩn, coi index là dữ liệu dẫn xuất có thể dựng lại. Consumer phải xử lý insert, update và delete từ change feed, lưu checkpoint, retry idempotent và đối soát doc_id định kỳ. Khi xóa subject, cần kiểm tra cả bảng hiện tại, index, version cũ và backup theo chính sách retention. Pin version giúp tái lập training, nhưng không đồng nghĩa xóa hiện tại đã xóa mọi bản cũ.

AI hỗ trợ đọc code, xây guard an toàn, tự động thực thi và soạn bản giải thích/reflection; chi tiết trong [AI_USAGE.md](AI_USAGE.md). Đây là bản nháp cần người học rà soát trước khi nộp.
'''
    (OUT / "REFLECTION.md").write_text(reflection, encoding="utf-8")
    (OUT / "AI_USAGE.md").write_text('''# Khai sử dụng AI

Sử dụng Codex để đọc đề/repo, rà thao tác nguy hiểm, viết scripts/lab_safety.py, scripts/safe_lab.py, scripts/finish_submission.py và tests/test_safety.py; tự động chạy notebook bằng Jupyter kernel .venv, thu số đo/output, bổ sung kiểm tra rubric, tạo bản nháp giải thích và reflection, chuẩn bị trang/ảnh bằng chứng.

Các số đo lấy từ lần thực thi thật trên máy, không tạo output giả, không bỏ assertion hoặc hạ ngưỡng gốc. Nội dung 8 notebook nguồn giữ nguyên; helper _setup.py và verify_lite.py tự bật guard, runner bổ sung chế độ chạy có guard. Phần thêm kiểm tra kết quả nằm trong notebook bài nộp.

Người học cung cấp họ tên/MSSV và đã chuẩn bị môi trường. Tại thời điểm tạo bộ file, AI đã thực thi thay mặt người dùng; không khẳng định người học đã tự chạy, tự chụp ảnh hay đã hoàn thành rà soát cá nhân. Người học cần đọc, hiểu, tự kiểm tra/chạy lại theo quy định lớp và chỉnh bản nháp phản ánh hiểu biết của mình trước khi gửi bài.
''', encoding="utf-8")
    summary = ["# Đối chiếu rubric", "", "Số liệu của lần thực thi được lưu trong evidence/metrics.json; thông tin an toàn trong SAFETY.md.", "", "| Notebook | Kết quả chính |", "|---|---|"]
    summary += [f"| NB{i:02} | `{json.dumps(m[f'nb{i:02}'], ensure_ascii=False)}` |" for i in range(1,9)]
    (OUT / "RESULTS.md").write_text("\n".join(summary)+"\n", encoding="utf-8")
    print("Saved explanations, INFO, AI disclosure, draft reflection and evidence pages.")


if __name__ == "__main__":
    main()
