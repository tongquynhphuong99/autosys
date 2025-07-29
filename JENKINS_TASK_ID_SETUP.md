# 🚀 Hướng dẫn cấu hình Jenkins với TASK_ID Parameter

## **Tổng quan**

Hệ thống TestOps hiện tại sử dụng **TASK_ID parameter** để xác định chính xác task cần xử lý khi Jenkins gửi webhook về backend.

## **1. Cấu hình Jenkins Job**

### **Bước 1: Vào Jenkins Job**
1. Mở Jenkins Dashboard
2. Chọn job cần cấu hình
3. Click **"Configure"**

### **Bước 2: Thêm Parameters**
1. Trong section **"General"**
2. Tick **"This project is parameterized"**
3. Click **"Add Parameter"** → **"String Parameter"**
4. Cấu hình:
   - **Name:** `TASK_ID`
   - **Default Value:** (để trống)
   - **Description:** `Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)`

### **Bước 3: Cập nhật Jenkinsfile**
1. **Option 1: Sử dụng Jenkinsfile chung (Khuyến nghị)**
   - Copy nội dung từ `Jenkinsfile-universal`
   - Paste vào **"Pipeline"** section của job
   - Jenkinsfile này tự động xác định task type từ TASK_ID

2. **Option 2: Sử dụng Jenkinsfile riêng biệt**
   - Copy nội dung từ file tương ứng:
     - **Execution:** `Jenkinsfile-execution`
     - **Plan:** `Jenkinsfile-plan`
     - **CI/CD:** `Jenkinsfile-cicd`
   - Paste vào **"Pipeline"** section của job

## **2. Cấu hình theo loại Task**

### **Universal Jenkinsfile (Khuyến nghị)**
- **Jenkinsfile:** `Jenkinsfile-universal`
- **Tự động xác định** task type từ TASK_ID
- **Hỗ trợ tất cả** loại task trong 1 file

### **Execution Tasks**
- **TASK_ID Format:** `TASK-001`, `TASK-002`, ...
- **Trigger:** Manual hoặc từ TestOps UI
- **Jenkinsfile:** `Jenkinsfile-execution` (nếu dùng riêng biệt)

### **Plan Tasks**
- **TASK_ID Format:** `PLAN-001`, `PLAN-002`, ...
- **Trigger:** Cron schedule
- **Environment Variable:** `CRON_SCHEDULE` (e.g., `0 9 * * *`)
- **Jenkinsfile:** `Jenkinsfile-plan` (nếu dùng riêng biệt)

### **CI/CD Tasks**
- **TASK_ID Format:** `CICD-001`, `CICD-002`, ...
- **Trigger:** SCM polling hoặc GitHub webhook
- **Environment Variable:** `SCM_POLL` (e.g., `* * * * *`)
- **Jenkinsfile:** `Jenkinsfile-cicd` (nếu dùng riêng biệt)

## **3. Cách hoạt động**

### **Khi tạo task trong TestOps:**
1. Backend tạo task với `task_id` (e.g., `TASK-001`)
2. Lưu `jenkins_job` name vào database
3. Hiển thị thông tin cho user

### **Khi chạy Jenkins job:**
1. User nhập `TASK_ID` khi trigger job
2. Jenkins chạy với parameter `TASK_ID`
3. Sau khi hoàn thành, gửi webhook với `TASK_ID`

### **Backend xử lý webhook:**
1. Nhận webhook từ Jenkins
2. Lấy `TASK_ID` từ parameters
3. Xác định task type từ format:
   - `TASK-` → execution
   - `PLAN-` → plan
   - `CICD-` → cicd
4. Tìm task trong database
5. Xử lý report và tạo notification

## **4. Fallback Mechanism**

### **Nếu không có TASK_ID:**
1. Backend fallback về tìm theo `jenkins_job` name
2. Xử lý tất cả task có cùng job name
3. Giữ backward compatibility

### **Nếu TASK_ID không hợp lệ:**
1. Backend log warning
2. Fallback về tìm theo job name
3. Tiếp tục xử lý bình thường

## **5. Testing**

### **Test với Execution:**
1. Tạo execution task trong TestOps
2. Copy `task_id` (e.g., `TASK-001`)
3. Trigger Jenkins job với parameter `TASK_ID=TASK-001`
4. Kiểm tra webhook được gửi đúng

### **Test với Plan:**
1. Tạo plan task với cron schedule
2. Copy `plan_id` (e.g., `PLAN-001`)
3. Trigger Jenkins job với parameter `TASK_ID=PLAN-001`
4. Kiểm tra report được tạo đúng

### **Test với CI/CD:**
1. Tạo CI/CD task
2. Copy `cicd_id` (e.g., `CICD-001`)
3. Trigger Jenkins job với parameter `TASK_ID=CICD-001`
4. Kiểm tra webhook và report

## **6. Troubleshooting**

### **Webhook không được gửi:**
1. Kiểm tra Jenkins job có parameter `TASK_ID` không
2. Kiểm tra Jenkinsfile có gửi webhook không
3. Kiểm tra network connectivity

### **Task không được tìm thấy:**
1. Kiểm tra `TASK_ID` format có đúng không
2. Kiểm tra task có tồn tại trong database không
3. Kiểm tra log backend

### **Report không được tạo:**
1. Kiểm tra Jenkins job có chạy Robot Framework không
2. Kiểm tra `output.xml` có được tạo không
3. Kiểm tra webhook data có đúng format không

## **7. Best Practices**

### **✅ Nên làm:**
- Luôn sử dụng `TASK_ID` khi trigger job
- Kiểm tra format `TASK_ID` trước khi chạy
- Test webhook sau khi cấu hình
- Monitor logs để debug issues

### **❌ Không nên:**
- Để trống `TASK_ID` parameter
- Sử dụng format `TASK_ID` không đúng
- Bỏ qua testing sau khi cấu hình

## **8. Migration từ hệ thống cũ**

### **Bước 1: Backup**
- Backup tất cả Jenkins jobs
- Backup database

### **Bước 2: Update từng job**
- Thêm parameter `TASK_ID`
- Update Jenkinsfile
- Test job

### **Bước 3: Deploy backend**
- Deploy backend code mới
- Test webhook processing

### **Bước 4: Monitor**
- Monitor logs
- Kiểm tra reports được tạo đúng
- Fix issues nếu có

## **9. Environment Variables**

### **Backend URL:**
- **Development:** `http://localhost:8000`
- **Production:** `http://your-domain.com`

### **Cron Schedule Examples:**
- **Daily 9 AM:** `0 9 * * *`
- **Every 2 hours:** `0 */2 * * *`
- **Weekdays only:** `0 9 * * 1-5`

### **SCM Poll Examples:**
- **Every minute:** `* * * * *`
- **Every 5 minutes:** `*/5 * * * *`
- **Every hour:** `0 * * * *`

### **Universal Jenkinsfile Variables:**
- **CRON_SCHEDULE:** Cron schedule cho PLAN tasks
- **SCM_POLL:** SCM polling cho CICD tasks
- **TASK_TYPE:** Tự động set từ TASK_ID (execution/plan/cicd)

## **10. Support**

Nếu gặp vấn đề:
1. Kiểm tra Jenkins logs
2. Kiểm tra backend logs
3. Kiểm tra database
4. Contact development team 