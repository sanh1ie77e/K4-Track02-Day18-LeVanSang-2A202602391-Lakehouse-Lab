# Reflection

Anti-pattern tôi chọn là coi vector index ngoài bảng là nguồn dữ liệu độc lập và chỉ đồng bộ upsert. Với hệ thống RAG dùng tài liệu người dùng, xóa document trong lakehouse nhưng bỏ qua delete event khiến index vẫn trả embedding cũ. NB7 tái hiện điều này: bảng không còn hit của dữ liệu đã xóa nhưng index cũ vẫn có hit.

Cách phòng tránh là dùng lakehouse làm nguồn chuẩn, coi index là dữ liệu dẫn xuất có thể dựng lại. Consumer phải xử lý insert, update và delete từ change feed, lưu checkpoint, retry idempotent và đối soát doc_id định kỳ. Khi xóa subject, cần kiểm tra cả bảng hiện tại, index, version cũ và backup theo chính sách retention. Pin version giúp tái lập training, nhưng không đồng nghĩa xóa hiện tại đã xóa mọi bản cũ.

AI hỗ trợ đọc code, xây guard an toàn, tự động thực thi và soạn bản giải thích/reflection; chi tiết trong [AI_USAGE.md](AI_USAGE.md). Đây là bản nháp cần người học rà soát trước khi nộp.
