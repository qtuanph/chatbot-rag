# Chat API Stress Report

- User: `SSE01`
- Login URL: `http://localhost/api/bep/auth/login`
- Chat URL: `http://localhost/api/v1/public/v1/chat/completions`
- Concurrent workers: `10`
- Total requests: `30`
- Success: `30`
- Failed: `0`
- p50 latency: `4762.09 ms`
- p95 latency: `13437.07 ms`

## Results

### Case 1
- Question: Em mới vào, nếu em chỉ muốn đóng băng số liệu cũ để khỏi ai sửa nhầm thì em bấm khóa số liệu là xong hay vẫn phải backup trước ạ?
- Status: ok
- Latency: `12681.69 ms`

#### Answer

_No answer_

### Case 2
- Question: Nếu em lỡ nhập sai từ tuần trước thì em mở lại bằng cách SAO chép số liệu vào hay chỉ cần sửa ngày khóa số liệu thôi ạ?
- Status: ok
- Latency: `12053.14 ms`

#### Answer

_No answer_

### Case 3
- Question: Nhật ký người sử dụng có phải là nơi xem ai đã xóa hay sửa chứng từ cuối cùng không, hay nó chỉ ghi mỗi lần đăng nhập thôi ạ?
- Status: ok
- Latency: `12318.24 ms`

#### Answer

_No answer_

### Case 4
- Question: Em mới vào thì trong danh mục tài khoản em có cần tự tạo hết tài khoản trước không, hay phần mềm tự có sẵn rồi ạ?
- Status: ok
- Latency: `12843.77 ms`

#### Answer

_No answer_

### Case 5
- Question: Sang năm mới thì kết chuyển số dư cuối năm sang đầu năm sau có tự làm hết không, hay em phải nhập lại từng cái?
- Status: ok
- Latency: `11846.66 ms`

#### Answer

_No answer_

### Case 6
- Question: Trong kết chuyển tự động, có phải em bấm một lần là phần mềm tự hạch toán lãi lỗ hết đúng không ạ?
- Status: ok
- Latency: `11601.63 ms`

#### Answer

_No answer_

### Case 7
- Question: Em muốn thu tiền khách chuyển khoản thì em bấm phiếu thu tiền mặt hay giấy báo có, hay hai cái này thực ra là một?
- Status: ok
- Latency: `9235.96 ms`

#### Answer

_No answer_

### Case 8
- Question: Khi rút tiền từ ngân hàng về quỹ tiền mặt thì em chỉ nhập một chứng từ thôi được không, hay phải nhập cả giấy báo nợ lẫn phiếu thu?
- Status: ok
- Latency: `14162.22 ms`

#### Answer

_No answer_

### Case 9
- Question: Muốn xem hiện giờ còn bao nhiêu tiền ở quỹ, bao nhiêu tiền ở từng ngân hàng, và còn nợ vay bao nhiêu thì phải mở báo cáo nào trước ạ?
- Status: ok
- Latency: `10113.13 ms`

#### Answer

_No answer_

### Case 10
- Question: Em xuất hóa đơn bán hàng rồi thì hệ thống tự hiểu là khách còn nợ hay em phải bấm thêm chỗ nào để nó thành công nợ ạ?
- Status: ok
- Latency: `11413.37 ms`

#### Answer

_No answer_

### Case 11
- Question: Nếu khách chuyển khoản trước rồi mới mua hàng thì em nhập ở phiếu thu hay ở hóa đơn bán hàng để tiền đó không bị tính thu hai lần ạ?
- Status: ok
- Latency: `3412.44 ms`

#### Answer

_No answer_

### Case 12
- Question: Một khách có nhiều hóa đơn chưa trả, lúc khách thanh toán một cục thì phần mềm tự biết trừ vào hóa đơn nào trước hay em phải tự chọn từng hóa đơn ạ?
- Status: ok
- Latency: `3537.34 ms`

#### Answer

_No answer_

### Case 13
- Question: Em mua hàng rồi nhưng chưa có hóa đơn thì cứ nhập kho trước được không, hay phải treo ở kho tạm ạ?
- Status: ok
- Latency: `4047.56 ms`

#### Answer

_No answer_

### Case 14
- Question: Nếu em trả tiền nhà cung cấp trước rồi mà hàng về sau thì phần mềm có tự trừ công nợ luôn không, hay em phải bấm thêm chỗ nào nữa?
- Status: ok
- Latency: `8242.70 ms`

#### Answer

_No answer_

### Case 15
- Question: Bên em lỡ vừa là khách hàng vừa là nhà cung cấp của cùng một bên, thế mình trừ nợ qua lại luôn trong một bước được không?
- Status: ok
- Latency: `6756.98 ms`

#### Answer

_No answer_

### Case 16
- Question: Em muốn nhập một chứng từ mới thì phải bấm từ menu nào trước, em hay bị lạc ở 3 cấp menu?
- Status: ok
- Latency: `5965.06 ms`

#### Answer

_No answer_

### Case 17
- Question: Nếu em chỉ nhớ mang máng tên chức năng thì vào chứng từ bằng cách nào cho đúng?
- Status: ok
- Latency: `4995.87 ms`

#### Answer

_No answer_

### Case 18
- Question: Phím nào là để thêm mới, sửa, xóa chứng từ vậy ạ, em cứ sợ bấm nhầm?
- Status: ok
- Latency: `4186.31 ms`

#### Answer

_No answer_

### Case 19
- Question: Khi đang nhập chứng từ mà không nhớ mã khách hàng hay mã vật tư thì em bấm gì để tìm nhanh?
- Status: ok
- Latency: `4726.57 ms`

#### Answer

_No answer_

### Case 20
- Question: Cập nhật xong chứng từ rồi thì em phải chọn kiểu chuyển sổ nào trước khi lưu, hay cứ để mặc định?
- Status: ok
- Latency: `3950.28 ms`

#### Answer

_No answer_

### Case 21
- Question: Báo cáo em đang xem ra số khác hôm qua thì em phải bấm chỗ nào để nó tự tính lại vậy anh/chị?
- Status: ok
- Latency: `2990.41 ms`

#### Answer

_No answer_

### Case 22
- Question: Nếu em chỉ nhớ mang máng tên khách hàng hoặc số hóa đơn thì tra cứu ở đâu cho nhanh ạ?
- Status: ok
- Latency: `3891.40 ms`

#### Answer

_No answer_

### Case 23
- Question: Có cách nào lọc báo cáo để chỉ xem một kỳ, một khách hàng hoặc một loại chứng từ thôi không ạ?
- Status: ok
- Latency: `2945.61 ms`

#### Answer

_No answer_

### Case 24
- Question: Nếu em hỏi ngắn gọn là khóa sổ khác gì backup thì phần mềm có hướng dẫn đúng quy trình không ạ?
- Status: ok
- Latency: `2680.97 ms`

#### Answer

_No answer_

### Case 25
- Question: Nếu em hỏi thiếu ngữ cảnh kiểu công nợ này xem ở đâu thì hệ thống có tự đoán nhầm sang bán hàng hay mua hàng không?
- Status: ok
- Latency: `4425.43 ms`

#### Answer

_No answer_

### Case 26
- Question: Em muốn biết phần Quản trị hệ thống có các mục nào liên quan đến lưu trữ, bảo trì và quản lý người sử dụng?
- Status: ok
- Latency: `4797.61 ms`

#### Answer

_No answer_

### Case 27
- Question: Các mục con của phần 4.5 Quản lý và bảo trì số liệu là gì?
- Status: ok
- Latency: `4673.35 ms`

#### Answer

_No answer_

### Case 28
- Question: Muốn khai báo người sử dụng và phân quyền thì vào phần nào?
- Status: ok
- Latency: `3827.56 ms`

#### Answer

_No answer_

### Case 29
- Question: Muốn backup số liệu thì vào mục nào của Quản trị hệ thống?
- Status: ok
- Latency: `3428.17 ms`

#### Answer

_No answer_

### Case 30
- Question: Nếu chỉ muốn kiểm tra đồng bộ giữa các tệp thì trong tài liệu ghi ở đâu?
- Status: ok
- Latency: `3536.32 ms`

#### Answer

_No answer_
