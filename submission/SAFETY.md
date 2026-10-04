# Cơ chế an toàn khi thực thi lab

## Rủi ro phát hiện

Helper `reset()` gốc dùng shutil.rmtree; overwrite thay trạng thái bảng; MERGE/DELETE/RESTORE sửa trạng thái; NB6 VACUUM retention=0 xóa file lịch sử; orphan sweep dùng os.remove/Path.unlink. Catalog reset xóa SQLite và warehouse. Chạy chúng vào đường dẫn sai hoặc chạy cleanup đồng thời với writer có thể mất dữ liệu.

## Kiểm soát đã triển khai

1. `scripts/safe_lab.py` kiểm kê AST các lệnh nguy hiểm trước chạy. Danh sách nằm trong evidence/risk_inventory.json. Shell và dynamic execution thuộc danh sách cấm được chặn khi preflight, và subprocess/shell cũng bị chặn trong process chạy notebook.
2. Mỗi lần chạy tạo UUID mới dưới `_lakehouse/safe_runs/`, có marker do launcher tạo. Chỉ sinh dữ liệu giả ở đây; không dùng dữ liệu lakehouse ban đầu. Run riêng cho notebook, smoke và runner.
3. `lab_safety.install()` kiểm tra đường dẫn đã resolve, chặn traversal, đường dẫn ngoài root, root deletion, URL remote, symlink/junction và mục recovery/control files. Delta constructor/writer/mutator và các entry point catalog/path/reset của lab được bọc kiểm tra trước thao tác. Audit hook kiểm tra các thao tác xóa/rename ở Python.
4. Một process/kernel giữ khóa file OS cho mỗi run. Process thứ hai không được sử dụng chung run. Kernel của các notebook được chạy nối tiếp, mỗi kernel kết thúc trước kernel sau.
5. Trước overwrite/DELETE/MERGE/RESTORE/VACUUM thật hoặc xóa file/thư mục, sao lưu file/bảng trong `_recovery/`. Nếu sao lưu thất bại thì thao tác chưa được thực hiện. Copies được giữ trên máy, không commit vào Git.
6. VACUUM chỉ được phép trên bảng nằm dưới scratch. Trước thực thi, guard gọi dry-run, chuẩn hóa đường dẫn tương đối theo thư mục bảng và kiểm tra từng candidate. Số bytes dry-run vì vậy sử dụng đường dẫn đầy đủ có thật.
7. Sau thao tác có kiểm tra số dòng/metrics trong notebook; thêm kiểm tra Delta còn 100.000 dòng và Iceberg còn 2.000 dòng sau maintenance. SHA-256 toàn bộ file lakehouse có trước được so sánh trước/sau vòng chạy; xem original_data_integrity.json.

## Bằng chứng kiểm thử

Bộ tests/test_safety.py thử xóa sentinel ở ngoài vùng run, reset thư mục ngoài, path traversal, sibling có cùng prefix, URL remote, ghi/đọc Delta ngoài vùng và VACUUM Bronze. Chúng phải bị chặn; sentinel giữ nguyên. Test cũng thực hiện DELETE và VACUUM hợp lệ trên scratch, kiểm tra dữ liệu hiện tại và recovery. Test symlink chỉ chạy nếu tài khoản Windows có quyền tạo symlink; nếu thiếu quyền thì ghi SKIP, không khẳng định đã kiểm thử tình huống đó. Kết quả cụ thể nằm trong evidence/pytest.txt.

## Phạm vi và khôi phục

Đây là lớp bảo vệ cho các đường chạy mã lab đã rà soát, không phải OS sandbox đối với code thù địch. Python audit hooks không bao phủ mọi I/O native của Rust/Arrow; các API Delta và catalog dùng trong lab được kiểm tra ở điểm vào. Không dùng để chạy code lạ hoặc dữ liệu production. Sao lưu cùng đĩa chỉ hỗ trợ khôi phục thao tác lab, không bảo vệ khi hỏng đĩa.

Nếu cần khôi phục, dừng kernel/writer, xem audit để tìm backup, sao chép backup vào **một run mới** và kiểm tra đọc/schema/row count. Không tự động chép đè dữ liệu đang dùng. Iceberg có thể chứa URI tuyệt đối; cần khôi phục đồng bộ catalog/warehouse bằng thủ tục engine-aware, không sửa tay metadata và không giả định đổi thư mục là đủ. Recovery file rời của orphan/manifest chỉ là bằng chứng/bản sao trước xóa, không tương đương full backup toàn catalog.

Khi tự chạy lại, dùng `scripts/safe_lab.py` hoặc cell bootstrap trong notebook submission. Helper `_setup.py` của notebook lightweight và `verify_lite.py` cũng tự bật preflight/guard để bảo vệ khi chạy trực tiếp. Nếu kernel đã import helper cũ trước khi sửa, cần restart kernel trước khi chạy. Scripts sinh dữ liệu riêng lẻ và `make clean` không tự bật guard; dùng launcher cho việc sinh dữ liệu. Không chạy make clean: nó xóa cả venv và lakehouse. Chưa bật tự động cleanup recovery nhằm giữ bằng chứng và khả năng khôi phục.
