# Thông tin bài nộp

- Họ tên: Lê Văn Sang (LeVanSang)
- MSSV: 2A202602391
- Mã bài: K4-Track02-Day18
- Đường chạy: lightweight cho đủ 8 notebook; không dùng Spark.
- Python: 3.13.15
- Hệ điều hành: Windows-11-10.0.26300-SP0
- Thực thi: nbclient điều khiển Jupyter kernel từ .venv trên máy này, lưu output vào submission/notebooks. run_all.py là kiểm tra riêng, không được dùng làm bản notebook có output.
- Ngày thực thi: 04/10/2026 (Asia/Ho_Chi_Minh).
- Tên fork yêu cầu: K4-Track02-Day18-LeVanSang-2A202602391-Lakehouse-Lab.
- Fork và origin đã kiểm tra: https://github.com/sanh1ie77e/K4-Track02-Day18-LeVanSang-2A202602391-Lakehouse-Lab.git. Việc gửi bài qua kênh lớp do người học thực hiện.

## Phiên bản thư viện

```json
{
  "deltalake": "1.6.6",
  "pyiceberg": "0.12.0",
  "duckdb": "1.5.6",
  "polars": "1.44.2",
  "numpy": "2.5.3",
  "pyarrow": "25.0.1",
  "jupytext": "1.19.5",
  "nbclient": "0.11.0",
  "ipykernel": "7.4.0"
}
```

## Kiểm tra và bằng chứng

- Smoke: 9/9 (evidence/smoke.txt).
- Bộ gốc: đủ 24 tests đạt; kiểm thử an toàn bổ sung được ghi trong evidence/pytest.txt.
- Runner lightweight: 8/8 (evidence/run_all.txt).
- Kernel: kiểm tra Python thực tế và phiên bản thư viện trong evidence/kernel_check.json.
- Notebook giữ output, câu trả lời và các kiểm tra rubric bổ sung NB1/NB2/NB4/NB6/NB8.
- evidence/original_data_integrity.json: SHA-256 dữ liệu lakehouse có trước, trước/sau lần chạy.
- evidence/risk_inventory.json và safety_audit.json: danh sách thao tác nguy hiểm và nhật ký.
- Screenshots: chụp trang bằng chứng từ output đã lưu, xem screenshots/.

## Chạy lại an toàn

Từ gốc repo: `.\.venv\Scripts\python.exe scripts/safe_lab.py`, sau đó `.\.venv\Scripts\python.exe scripts/finish_submission.py`.
Mỗi lần tạo vùng dữ liệu mới; không tái sử dụng dữ liệu gốc. Ảnh là bằng chứng của lần chụp hiện tại; nếu chạy lại, cần chụp lại để khớp số đo mới.
Mở notebook bài nộp trong Jupyter từ gốc repo hoặc một thư mục con và đọc/chạy cell bootstrap an toàn trước các cell khác. Không bỏ cell này.

Kernel `lab-safe` do launcher tạo cục bộ trong .lab-runtime. Để mở lại bằng PowerShell tại gốc repo:

```powershell
$env:JUPYTER_PATH = Join-Path (Get-Location) '.lab-runtime'
$env:IPYTHONDIR = Join-Path (Get-Location) '.lab-runtime/ipython'
.\.venv\Scripts\python.exe -m jupyter lab --notebook-dir=submission/notebooks --no-browser
```

Chọn kernel **Day18 safe .venv**. Kiểm tra bộ bài mà không chạy lại dữ liệu: `.\.venv\Scripts\python.exe scripts/verify_submission.py`.

Người học cần tự kiểm tra output, hiểu giải thích và thực thi lại trong Jupyter theo RULES/SUBMISSION trước khi chốt bài. Reflection và giải thích là bản hỗ trợ bằng AI, cần rà soát theo hiểu biết cá nhân.
