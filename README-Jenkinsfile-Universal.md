# 🔧 Jenkinsfile Universal - Hướng dẫn sử dụng

## **Tổng quan**

`Jenkinsfile-universal` là một Jenkinsfile chung có thể sử dụng cho cả 3 loại task trong TestOps:
- **Execution Tasks** (TASK-001, TASK-002, ...)
- **Plan Tasks** (PLAN-001, PLAN-002, ...)
- **CI/CD Tasks** (CICD-001, CICD-002, ...)

## **Ưu điểm**

### **✅ Lợi ích:**
- **1 file duy nhất** cho tất cả loại task
- **Tự động xác định** task type từ TASK_ID
- **Dễ maintain** và update
- **Consistent behavior** across all task types
- **Reduced complexity** trong Jenkins setup

### **❌ Nhược điểm:**
- **Phức tạp hơn** so với file riêng biệt
- **Cần hiểu logic** conditional stages
- **Harder to customize** cho từng loại task

## **Cách hoạt động**

### **1. Tự động xác định Task Type**
```groovy
// Xác định task type từ TASK_ID
if (params.TASK_ID.startsWith('TASK-')) {
    taskType = 'execution'
} else if (params.TASK_ID.startsWith('PLAN-')) {
    taskType = 'plan'
} else if (params.TASK_ID.startsWith('CICD-')) {
    taskType = 'cicd'
}
```

### **2. Conditional Stages**
```groovy
stage('Checkout') {
    when {
        expression { env.TASK_TYPE == 'cicd' }
    }
    steps {
        checkout scm
    }
}

stage('Deploy') {
    when {
        allOf(
            expression { env.TASK_TYPE == 'cicd' },
            expression { currentBuild.result == 'SUCCESS' }
        )
    }
    steps {
        // Deploy steps
    }
}
```

### **3. Dynamic Triggers**
```groovy
triggers {
    // Cron schedule cho PLAN tasks
    cron(env.CRON_SCHEDULE ?: '')
    // SCM polling cho CICD tasks
    pollSCM(env.SCM_POLL ?: '')
}
```

## **Cấu hình**

### **Bước 1: Tạo Jenkins Job**
1. **New Item** → **Pipeline**
2. Đặt tên job (e.g., `testops-universal`)

### **Bước 2: Cấu hình Parameters**
1. **Configure** → **General**
2. Tick **"This project is parameterized"**
3. **Add Parameter** → **String Parameter**
   - **Name:** `TASK_ID`
   - **Default Value:** (để trống)
   - **Description:** `Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)`

### **Bước 3: Cấu hình Pipeline**
1. **Pipeline** section
2. **Definition:** Pipeline script from SCM
3. **Script Path:** `Jenkinsfile-universal`

### **Bước 4: Cấu hình Environment Variables (Optional)**
1. **Build Environment** → **Inject environment variables**
2. Thêm variables:
   - **CRON_SCHEDULE:** `0 9 * * *` (cho PLAN tasks)
   - **SCM_POLL:** `* * * * *` (cho CICD tasks)

## **Sử dụng**

### **Execution Task:**
```bash
# Trigger với TASK_ID
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=TASK-001"
```

### **Plan Task:**
```bash
# Trigger với TASK_ID
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=PLAN-001"
```

### **CI/CD Task:**
```bash
# Trigger với TASK_ID
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=CICD-001"
```

## **Stages Flow**

### **Execution Tasks:**
```
Setup → Run Tests → Send Webhook
```

### **Plan Tasks:**
```
Setup → Run Tests → Send Webhook
```

### **CI/CD Tasks:**
```
Setup → Checkout → Run Tests → Deploy → Send Webhook
```

## **Environment Variables**

### **Tự động set:**
- **TASK_TYPE:** `execution`, `plan`, hoặc `cicd`
- **TASK_PREFIX:** `TASK`, `PLAN`, hoặc `CICD`

### **Cần cấu hình:**
- **CRON_SCHEDULE:** Cron schedule cho PLAN tasks
- **SCM_POLL:** SCM polling cho CICD tasks

## **Customization**

### **Thêm stages mới:**
```groovy
stage('Custom Stage') {
    when {
        expression { env.TASK_TYPE == 'execution' }
    }
    steps {
        echo "Custom stage for execution only"
    }
}
```

### **Thêm conditions:**
```groovy
stage('Conditional Stage') {
    when {
        allOf(
            expression { env.TASK_TYPE == 'cicd' },
            expression { env.BRANCH_NAME == 'main' }
        )
    }
    steps {
        echo "Only for CI/CD on main branch"
    }
}
```

## **Troubleshooting**

### **TASK_ID không hợp lệ:**
```
Error: Invalid TASK_ID format: INVALID-001. Must start with TASK-, PLAN-, or CICD-
```
**Giải pháp:** Kiểm tra format TASK_ID

### **Stage không chạy:**
```
Stage 'Checkout' skipped due to when conditional
```
**Giải pháp:** Kiểm tra TASK_TYPE và conditions

### **Webhook không gửi:**
```
❌ Failed to send webhook: Connection refused
```
**Giải pháp:** Kiểm tra backend URL và network

## **Best Practices**

### **✅ Nên làm:**
- Luôn sử dụng TASK_ID khi trigger job
- Test với từng loại task type
- Monitor logs để debug issues
- Backup Jenkinsfile trước khi modify

### **❌ Không nên:**
- Để trống TASK_ID parameter
- Sử dụng format TASK_ID không đúng
- Bỏ qua testing sau khi cấu hình

## **Migration từ Jenkinsfile riêng biệt**

### **Bước 1: Backup**
```bash
cp Jenkinsfile-execution Jenkinsfile-execution.backup
cp Jenkinsfile-plan Jenkinsfile-plan.backup
cp Jenkinsfile-cicd Jenkinsfile-cicd.backup
```

### **Bước 2: Update Jobs**
1. Cập nhật từng job sử dụng `Jenkinsfile-universal`
2. Test với TASK_ID tương ứng
3. Verify webhook và reports

### **Bước 3: Cleanup**
1. Xóa Jenkinsfile riêng biệt cũ
2. Update documentation
3. Train team members

## **Examples**

### **Test với curl:**
```bash
# Test execution
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=TASK-001"

# Test plan
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=PLAN-001"

# Test cicd
curl -X POST "http://jenkins:8080/job/testops-universal/buildWithParameters" \
  -d "TASK_ID=CICD-001"
```

### **Test với Jenkins CLI:**
```bash
# Test execution
java -jar jenkins-cli.jar -s http://jenkins:8080 build testops-universal -p TASK_ID=TASK-001

# Test plan
java -jar jenkins-cli.jar -s http://jenkins:8080 build testops-universal -p TASK_ID=PLAN-001

# Test cicd
java -jar jenkins-cli.jar -s http://jenkins:8080 build testops-universal -p TASK_ID=CICD-001
``` 