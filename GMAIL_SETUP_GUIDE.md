# Hướng dẫn cấu hình Gmail cho TestOps

## Bước 1: Tạo App Password cho Gmail

### 1.1 Bật 2-Step Verification
1. Vào: https://myaccount.google.com/security
2. Đăng nhập bằng Gmail của bạn
3. Tìm **"2-Step Verification"** → Click **"Get Started"**
4. Làm theo hướng dẫn để bật 2-Step Verification

### 1.2 Tạo App Password
1. Vào: https://myaccount.google.com/apppasswords
2. Chọn **"Mail"** trong dropdown
3. Chọn **"Other (Custom name)"**
4. Đặt tên: **"TestOps Email Service"**
5. Click **"Generate"**
6. **Copy password 16 ký tự** (không có dấu cách)

## Bước 2: Cấu hình trong docker-compose.yml

Thay thế thông tin trong `docker-compose.yml`:

```yaml
environment:
  # ... other settings ...
  - EMAIL_SMTP_SERVER=smtp.gmail.com
  - EMAIL_SMTP_PORT=587
  - EMAIL_USERNAME=your-gmail@gmail.com
  - EMAIL_PASSWORD=your-16-char-app-password
  - EMAIL_FROM=TestOps <your-gmail@gmail.com>
```

**Ví dụ:**
```yaml
environment:
  # ... other settings ...
  - EMAIL_SMTP_SERVER=smtp.gmail.com
  - EMAIL_SMTP_PORT=587
  - EMAIL_USERNAME=testops@gmail.com
  - EMAIL_PASSWORD=abcd-efgh-ijkl-mnop
  - EMAIL_FROM=TestOps <testops@gmail.com>
```

## Bước 3: Restart và Test

### Restart backend:
```bash
docker-compose restart backend
```

### Test cấu hình:
```bash
curl -s "http://localhost:8000/api/email/config" | jq
```

### Test kết nối:
```bash
curl -s "http://localhost:8000/api/email/test-connection" | jq
```

### Test gửi email:
```bash
curl -X POST "http://localhost:8000/api/email/send-task-report" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "TASK-001",
    "task_name": "Test Task",
    "project_name": "Test Project",
    "result": "SUCCESS",
    "job_name": "GW040-NS",
    "build_number": "6",
    "recipients": ["test@example.com"],
    "duration": 30,
    "passed": 5,
    "total": 10
  }' | jq
```

## Lưu ý quan trọng

### ✅ Ưu điểm của Gmail:
- **Dễ cấu hình** - Chỉ cần App Password
- **Ổn định** - Gmail ít khi chặn SMTP
- **Bảo mật** - App Password có thể thu hồi
- **Miễn phí** - Không cần trả phí

### ⚠️ Lưu ý:
- **App Password** - Không phải password thường
- **2-Step Verification** - Phải bật trước khi tạo App Password
- **Quota** - Gmail có giới hạn gửi email/ngày
- **Spam** - Có thể bị đánh dấu spam nếu gửi nhiều

### 🔧 Troubleshooting:

#### Lỗi "Invalid credentials":
- Kiểm tra App Password có đúng 16 ký tự không
- Đảm bảo đã bật 2-Step Verification

#### Lỗi "Mailbox cannot be accessed":
- Kiểm tra Gmail có bị khóa không
- Thử đăng nhập Gmail trên web

#### Lỗi "Connection timeout":
- Kiểm tra firewall
- Thử port 465 với SSL thay vì 587 với TLS

## Cấu hình SSL (Nếu cần)

Nếu port 587 không hoạt động, thử port 465:

```yaml
environment:
  - EMAIL_SMTP_SERVER=smtp.gmail.com
  - EMAIL_SMTP_PORT=465
  - EMAIL_USERNAME=your-gmail@gmail.com
  - EMAIL_PASSWORD=your-app-password
  - EMAIL_FROM=TestOps <your-gmail@gmail.com>
```

Và cập nhật code trong `backend/routes/email.py`:

```python
# Thay đổi từ starttls() sang SSL
server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
server.login(self.username, self.password)
``` 