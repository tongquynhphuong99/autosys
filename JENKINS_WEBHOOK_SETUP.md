# Hướng dẫn cấu hình Jenkins Webhook tự động

## 1. Cấu hình biến môi trường

Tạo file `.env` trong thư mục `backend/` với các biến sau:

```bash
# Jenkins Configuration
JENKINS_URL=http://localhost:8080
JENKINS_USER=admin
JENKINS_TOKEN=your-jenkins-api-token  # Tùy chọn - nếu Jenkins không cần auth
```

### Cách lấy Jenkins API Token (nếu cần):
1. Đăng nhập vào Jenkins
2. Vào **Manage Jenkins** → **Manage Users**
3. Click vào user của bạn
4. Vào **Configure** → **API Token** → **Add new Token**
5. Copy token và lưu vào biến `JENKINS_TOKEN`

**Lưu ý**: Nếu Jenkins không yêu cầu authentication, có thể bỏ trống `JENKINS_TOKEN`

## 2. Cách sử dụng chức năng tự động

### Khi nhấn button "Chạy" task CI/CD:

Hệ thống sẽ tự động:

1. **Cấu hình Jenkins trigger**: Bật "GitHub hook trigger for GITScm polling" trong Jenkins job
2. **Thêm webhook vào GitHub** (nếu project có repo URL): Tự động thêm webhook vào repository từ thông tin project

**Lưu ý**: 
- Không cần nhập thông tin thủ công
- Hệ thống lấy repo URL từ bảng project
- Chỉ hỗ trợ repository public (không cần GitHub token)

## 3. Kiểm tra hoạt động

### Sau khi cấu hình thành công:

1. **Kiểm tra Jenkins job**:
   - Vào job → **Configure** → **Build Triggers**
   - Đảm bảo đã tick **GitHub hook trigger for GITScm polling**

2. **Kiểm tra GitHub webhook** (nếu project có repo URL):
   - Vào repository → **Settings** → **Webhooks**
   - Xem webhook đã được tạo chưa

3. **Test thử**:
   - Push một thay đổi nhỏ lên repository
   - Kiểm tra Jenkins job có tự động chạy không

## 4. Troubleshooting

### Lỗi cấu hình Jenkins:
- Kiểm tra `JENKINS_URL`, `JENKINS_USER`, `JENKINS_TOKEN` có đúng không
- Đảm bảo Jenkins user có quyền **Job/Configure** và **Job/Build**

### Lỗi thêm GitHub webhook:
- Đảm bảo repository là public
- Đảm bảo URL repository đúng format
- Kiểm tra Jenkins có thể truy cập từ internet không (nếu dùng ngrok)

### Lỗi webhook không trigger:
- Kiểm tra Jenkins URL có public không
- Nếu dùng ngrok, đảm bảo URL ngrok đúng và còn hoạt động
- Kiểm tra GitHub webhook delivery logs

## 5. Lưu ý quan trọng

- **Bảo mật**: Không commit file `.env` lên Git
- **Ngrok**: URL ngrok thay đổi mỗi lần restart (trừ bản trả phí)
- **Repository**: Chỉ hỗ trợ repository public (không cần GitHub token)
- **Jenkins plugins**: Đảm bảo đã cài đặt GitHub plugin trong Jenkins
- **Project setup**: Đảm bảo project đã có repo_link trong database

## 6. Các plugin Jenkins cần thiết

Đảm bảo Jenkins đã cài đặt các plugin sau:
- GitHub plugin
- GitHub API plugin
- Git plugin
- Pipeline plugin (nếu dùng Jenkinsfile) 