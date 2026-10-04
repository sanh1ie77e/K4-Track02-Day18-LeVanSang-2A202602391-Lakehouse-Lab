# Tiêu đề PR

[K4-Track02-Day18] LeVanSang - 2A202602391 - Lakehouse Lab

# Nội dung PR

Người nộp: Lê Văn Sang — MSSV 2A202602391.
Đường chạy: lightweight, Windows 11, Python 3.13.15.

Thực thi 8 notebook bằng Jupyter kernel của .venv trên máy, lưu output và bổ sung giải thích số đo. Chạy trong vùng dữ liệu giả riêng có preflight, kiểm tra đường dẫn, khóa process, recovery và audit. Giữ nguyên các ngưỡng/assertion gốc.

Kiểm tra: smoke 9/9; 24 tests gốc và 6 tests an toàn PASS, 1 test symlink SKIP do thiếu quyền Windows; runner 8/8. Đối chiếu SHA-256 xác nhận 206 file lakehouse ban đầu giữ nguyên.

- Notebook: submission/notebooks/
- Screenshots: submission/screenshots/
- Kết quả/giải thích: submission/RESULTS.md và Markdown cells trong notebook.
- Reflection: submission/REFLECTION.md
- Khai AI: submission/AI_USAGE.md
- Cơ chế an toàn: submission/SAFETY.md

Trước khi dùng mô tả này: người học tự đọc/chạy lại, sửa reflection theo hiểu biết cá nhân; thêm URL của các mục trên từ fork đã push và commit SHA thực tế. Bản này là mẫu PR, chưa được gửi lên GitHub.
