# Jenkinsfile Guide - Luôn tạo Report cho SUCCESS và FAILURE

## Tổng quan

Jenkinsfile này được thiết kế để **luôn tạo report và gửi về backend** cho cả trường hợp SUCCESS và FAILURE, đảm bảo không bỏ lỡ bất kỳ kết quả test nào.

## Các tính năng chính

### 1. **Luôn tạo Report**
- ✅ Tạo report cho cả SUCCESS và FAILURE
- ✅ Tạo file `output.xml` tối thiểu nếu không có
- ✅ Archive tất cả kết quả (HTML, XML, logs)

### 2. **Webhook cho mọi trường hợp**
- ✅ Gửi webhook trong phần `always` (SUCCESS và FAILURE)
- ✅ Không gửi webhook cho ABORTED (theo yêu cầu)
- ✅ Bao gồm TASK_ID trong webhook

### 3. **Xử lý lỗi robust**
- ✅ Tiếp tục chạy ngay cả khi Robot tests fail
- ✅ Tạo report tối thiểu nếu không có `output.xml`
- ✅ Archive artifacts ngay cả khi có lỗi

## Cấu trúc Jenkinsfile

### Parameters
```groovy
parameters {
    string(name: 'TASK_ID', defaultValue: '', description: 'Task ID from TestOps')
    choice(name: 'TASK_TYPE', choices: ['execution', 'plan', 'cicd'], description: 'Type of task')
}
```

### Stages
1. **Setup**: Tạo thư mục và hiển thị thông tin
2. **Run Robot Tests**: Chạy tests với `|| true` để không dừng khi fail
3. **Generate Report**: Luôn tạo report, tạo `output.xml` tối thiểu nếu cần
4. **Archive Results**: Nén và archive tất cả kết quả

### Post Actions
- **always**: Gửi webhook cho mọi trường hợp
- **success**: Thông báo thành công
- **failure**: Thông báo thất bại nhưng vẫn có report
- **cleanup**: Dọn dẹp workspace

## Cách hoạt động

### 1. Khi job SUCCESS:
```
✅ Robot tests completed
✅ Report generation completed
✅ Results archived successfully
✅ Webhook sent successfully for result: SUCCESS
✅ Execution completed successfully
📊 Report generated and sent to backend
```

### 2. Khi job FAILURE:
```
⚠️ Robot tests failed, but continuing...
⚠️ No output.xml found, creating minimal report
✅ Report generation completed
✅ Results archived successfully
✅ Webhook sent successfully for result: FAILURE
❌ Execution failed
📊 Report still generated and sent to backend
```

## Webhook Data Structure

```json
{
  "name": "job-name",
  "build": {
    "number": 123,
    "result": "SUCCESS|FAILURE",
    "status": "FINISHED",
    "timestamp": 1640995200000,
    "duration": 60000,
    "parameters": {
      "TASK_ID": "TASK-001"
    }
  }
}
```

## Backend Processing

Backend sẽ nhận webhook và:
1. Parse thông tin job và build
2. Lấy file `output.xml` từ Jenkins
3. Parse thông tin test cases
4. Lưu report vào database
5. Cập nhật status của task

## Test Webhook

Sử dụng script test:
```bash
# Test SUCCESS
python test_webhook_simple.py test-job 10 SUCCESS TASK-001

# Test FAILURE
python test_webhook_simple.py test-job 11 FAILURE TASK-001
```

## Lưu ý quan trọng

### 1. **Luôn có Report**
- Ngay cả khi Robot tests fail hoàn toàn
- Tạo `output.xml` tối thiểu với 1 test case fail
- Archive tất cả artifacts

### 2. **Webhook cho SUCCESS và FAILURE**
- Gửi trong phần `always`
- Không gửi cho ABORTED
- Bao gồm đầy đủ thông tin build

### 3. **Robust Error Handling**
- `|| true` trong các lệnh shell
- Try-catch cho tất cả operations
- Tiếp tục chạy ngay cả khi có lỗi

### 4. **CI/CD Integration**
- Cập nhật defaultValue cho TASK_ID
- Archive artifacts cho Jenkins UI
- Log đầy đủ thông tin

## Troubleshooting

### 1. Webhook không được gửi
- Kiểm tra backend có đang chạy không
- Kiểm tra network connectivity
- Xem Jenkins console log

### 2. Report không được tạo
- Kiểm tra file `output.xml` có được tạo không
- Xem Jenkins workspace
- Kiểm tra Robot Framework logs

### 3. Backend không nhận được webhook
- Test với script `test_webhook_simple.py`
- Kiểm tra webhook URL
- Xem backend logs

## Kết luận

Jenkinsfile này đảm bảo:
- ✅ **Luôn có report** cho mọi trường hợp
- ✅ **Webhook được gửi** cho SUCCESS và FAILURE
- ✅ **Không bỏ lỡ** bất kỳ kết quả test nào
- ✅ **Robust** và **reliable** 