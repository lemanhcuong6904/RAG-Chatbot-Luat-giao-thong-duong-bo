# TÀI LIỆU MÔ TẢ THIẾT KẾ CHI TIẾT GIAO DIỆN "LUẬT GIAO THÔNG"

## 1. Tổng quan dự án
"Luật Giao Thông" là hệ thống trợ lý pháp lý AI chuyên sâu về Luật Giao thông đường bộ Việt Nam. Giao diện tập trung vào sự rõ ràng, trực quan và giảm bớt căng thẳng cho người dùng khi đối mặt với các quy định pháp luật phức tạp.

## 2. Ngôn ngữ thiết kế: Kinetic Juris Playful
Dựa trên hệ thống thiết kế `{{DATA:DESIGN_SYSTEM:DESIGN_SYSTEM_2}}`, giao diện Luật Giao Thông tuân theo phong cách thân thiện, rõ ràng và dễ sử dụng.

### 2.1. Hệ màu (Color Palette)
Hệ màu được lựa chọn để tạo cảm giác an tâm nhưng vẫn tràn đầy năng lượng:
- **Nền chính (Surface):** `#fff8ef` (Màu kem dịu mắt, tránh mỏi mắt khi đọc văn bản dài).
- **Màu nhấn thương hiệu (Primary):** `#ffd600` (Vàng nắng - biểu tượng của sự cảnh báo giao thông nhưng được làm tươi mới).
- **Màu hành động (Accent):** `#ff6d00` (Cam điện tử - dùng cho nút gửi, các hành động quan trọng).
- **Màu trạng thái (Semantic):**
  - Xanh Mint (`#b2ff59`): Cho các trạng thái "Đang hiệu lực" hoặc "Hợp lệ".
  - Đỏ San hô: Cho các mức phạt tiền hoặc cảnh báo vi phạm.
- **Đường nét (Outline):** Sử dụng các đường viền đen đậm (Black 2px) tạo hiệu ứng retro/comic hiện đại.

### 2.2. Typography
- **Font chữ chính:** `Plus Jakarta Sans`. Đây là bộ font không chân (sans-serif) hiện đại, có độ mở lớn, giúp văn bản luật trở nên dễ đọc và bớt nặng nề.
- **Cấu trúc phân cấp:**
  - **Tiêu đề lớn (Hero):** Italic, đậm, kích thước lớn để tạo sự chào đón.
  - **Văn bản pháp luật:** Kích thước font 15.5px, khoảng cách dòng (line-height) rộng (1.6 - 1.7) để tối ưu trải nghiệm đọc.

### 2.3. Hình khối và Hiệu ứng (Shapes & Shadows)
- **Roundness:** Bo tròn tối đa (`ROUND_FULL` cho nút, `18px+` cho card).
- **Shadow:** Sử dụng đổ bóng cứng (Hard Shadows) màu đen đặc trưng của phong cách Neo-brutalism, tạo cảm giác các thành phần giao diện nổi khối và có sức sống.

---

## 3. Cấu trúc các màn hình chính

### 3.1. Trang chủ (Landing Page) `{{DATA:SCREEN:SCREEN_12}}`
Màn hình đầu tiên tập trung vào việc kích thích người dùng đặt câu hỏi.
- **Hero Section:** Logo "Luật Giao Thông" nổi bật với icon đèn giao thông. Slogan "Tra cứu pháp luật giao thông chính xác, có căn cứ" được đặt chính giữa.
- **Gợi ý nhanh:** Các thẻ màu sắc (Vượt đèn đỏ, Nồng độ cồn, GPLX) giúp người dùng bắt đầu cuộc hội thoại chỉ với một lần chạm.
- **Smart Composer:** Khung nhập liệu nằm cố định phía dưới với tùy chọn chọn "Ngày áp dụng" để AI tra cứu đúng hiệu lực văn bản tại thời điểm đó.

### 3.2. Màn hình Trò chuyện (Chat Experience) `{{DATA:SCREEN:SCREEN_10}}`
Đây là nơi diễn ra tương tác chính giữa người dùng và AI.
- **Bong bóng chat:** Thiết kế dạng card bo tròn lớn. Tin nhắn AI luôn đi kèm icon trợ lý robot thân thiện.
- **Sanction Cards (Thẻ mức phạt):** Khi người dùng hỏi về mức phạt, AI không trả về một đoạn văn dài mà hiển thị dưới dạng các thẻ tóm tắt màu sắc:
    - Thẻ Cam: Phạt tiền (Ví dụ: 800K - 1 Củ).
    - Thẻ Vàng: Tước bằng (Ví dụ: 1 - 3 Tháng).
- **Bảng căn cứ pháp lý (Evidence Panel):** Nằm bên phải (Desktop) hoặc dạng Drawer (Mobile), hiển thị chính xác Điều, Khoản, Điểm được trích dẫn để người dùng đối soát.

### 3.3. Trang Văn bản pháp luật `{{DATA:SCREEN:SCREEN_4}}`
Dành cho người dùng muốn tra cứu gốc văn bản.
- Danh sách văn bản được trình bày dạng List Card. Mỗi card hiển thị rõ: Số hiệu thông tư/nghị định, Cơ quan ban hành, và quan trọng nhất là nhãn "Đang hiệu lực" màu xanh neon nổi bật.

### 3.4. Trang Hệ thống RAG (Developer Mode) `{{DATA:SCREEN:SCREEN_3}}`
Màn hình dành cho quản trị viên theo dõi hiệu suất của AI.
- Sử dụng các biểu tượng minh họa vui nhộn cho các pipeline kỹ thuật (BM25, Dense, Rerank).
- Khung "Runtime" hiển thị dữ liệu JSON thô nhưng được đặt trong một container phong cách máy tính thập niên 90 để giữ vững chủ đề "vui vẻ".

---

## 4. Các thành phần dùng chung (Shared Components)
Dựa trên `{{DATA:COMPONENTS:COMPONENTS_11}}`:
- **SideNavBar:** Thanh điều hướng bên trái với các icon Lucide trực quan (Home, Biển báo, Tra cứu phạt, Cẩm nang).
- **TopAppBar:** Thanh tiêu đề phía trên tích hợp tìm kiếm nhanh và thông báo.
- **Footer:** Chứa các thông tin về điều khoản và bản quyền, giữ phong cách tối giản.

---

## 5. Microcopy & Tương tác
- Ngôn ngữ sử dụng trong app gần gũi, sử dụng các từ ngữ GenZ nhẹ nhàng (ví dụ: "1 Củ" thay vì "1.000.000 VNĐ" trong các thẻ tóm tắt vui nhộn).
- Hiệu ứng tương tác: Khi di chuột hoặc nhấn vào các nút, chúng có hiệu ứng lún xuống hoặc thay đổi độ bóng để phản hồi người dùng một cách sinh động.
