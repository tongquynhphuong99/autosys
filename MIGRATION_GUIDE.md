# 🔄 Hướng dẫn Migration từ Jenkinsfile cũ

## **Tổng quan**

Hướng dẫn này giúp bạn migrate từ Jenkinsfile cũ sang Jenkinsfile mới với TASK_ID parameter để xác định chính xác task cần xử lý.

## **So sánh Jenkinsfile cũ và mới**

### **Jenkinsfile cũ:**
```groovy
pipeline {
    agent {
        docker {
            image 'demopq/robot-python-sele-chor:phuongttq'
            args '-u root'
        }
    }
    stages {
        stage('Run Robot Tests') {
            steps {
                sh '''
                    mkdir -p results
                    robot --outputdir results Bases/Testcase/login.robot
                '''
            }
        }
        stage('Process Results') {
            steps {
                robot outputPath: 'results'
                sh '''
                    tar czf results.tar.gz -C results .
                '''
            }
        }
    }
    post {
        success {
            // Gửi webhook không có TASK_ID
        }
    }
}
```

### **Jenkinsfile mới:**
```groovy
pipeline {
    agent {
        docker {
            image 'demopq/robot-python-sele-chor:phuongttq'
            args '-u root'
        }
    }
    
    // Thêm TASK_ID parameter
    parameters {
        string(name: 'TASK_ID', defaultValue: '', description: 'Task ID from TestOps')
    }
    
    // Dynamic triggers
    triggers {
        cron(env.CRON_SCHEDULE ?: '')
        pollSCM(env.SCM_POLL ?: '')
    }
    
    stages {
        stage('Setup') {
            // Xác định task type từ TASK_ID
        }
        stage('Checkout') {
            when { expression { env.TASK_TYPE == 'cicd' } }
        }
        stage('Run Robot Tests') {
            // Logic cũ + dynamic stage name
        }
        stage('Process Results') {
            // Logic cũ
        }
        stage('Deploy') {
            when { expression { env.TASK_TYPE == 'cicd' } }
        }
    }
    post {
        always {
            // Gửi webhook với TASK_ID
        }
    }
}
```

## **Những thay đổi chính**

### **1. Thêm Parameters**
```groovy
parameters {
    string(name: 'TASK_ID', defaultValue: '', description: 'Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)')
}
```

### **2. Thêm Dynamic Triggers**
```groovy
triggers {
    cron(env.CRON_SCHEDULE ?: '')    // Cho PLAN tasks
    pollSCM(env.SCM_POLL ?: '')      // Cho CICD tasks
}
```

### **3. Thêm Setup Stage**
```groovy
stage('Setup') {
    steps {
        script {
            // Xác định task type từ TASK_ID
            if (params.TASK_ID.startsWith('TASK-')) {
                taskType = 'execution'
            } else if (params.TASK_ID.startsWith('PLAN-')) {
                taskType = 'plan'
            } else if (params.TASK_ID.startsWith('CICD-')) {
                taskType = 'cicd'
            }
            env.TASK_TYPE = taskType
        }
    }
}
```

### **4. Conditional Stages**
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

### **5. Enhanced Webhook**
```groovy
def webhookData = [
    name: env.JOB_NAME,
    build: [
        number: env.BUILD_NUMBER,
        result: currentBuild.result,
        status: currentBuild.currentResult,
        timestamp: currentBuild.startTimeInMillis,
        duration: currentBuild.duration,
        parameters: [
            TASK_ID: params.TASK_ID  // Thêm TASK_ID
        ]
    ]
]
```

## **Bước Migration**

### **Bước 1: Backup Jenkinsfile cũ**
```bash
cp Jenkinsfile Jenkinsfile.backup
```

### **Bước 2: Cập nhật Jenkinsfile**
1. Copy nội dung từ `Jenkinsfile-updated`
2. Paste vào Jenkins job configuration
3. Save changes

### **Bước 3: Cấu hình Parameters**
1. **Configure** → **General**
2. Tick **"This project is parameterized"**
3. **Add Parameter** → **String Parameter**
   - **Name:** `TASK_ID`
   - **Default Value:** (để trống)
   - **Description:** `Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)`

### **Bước 4: Cấu hình Environment Variables (Optional)**
1. **Build Environment** → **Inject environment variables**
2. Thêm variables:
   - **CRON_SCHEDULE:** `0 9 * * *` (cho PLAN tasks)
   - **SCM_POLL:** `* * * * *` (cho CICD tasks)

### **Bước 5: Test Migration**
1. **Test với Execution:**
   ```bash
   curl -X POST "http://jenkins:8080/job/your-job/buildWithParameters" \
     -d "TASK_ID=TASK-001"
   ```

2. **Test với Plan:**
   ```bash
   curl -X POST "http://jenkins:8080/job/your-job/buildWithParameters" \
     -d "TASK_ID=PLAN-001"
   ```

3. **Test với CI/CD:**
   ```bash
   curl -X POST "http://jenkins:8080/job/your-job/buildWithParameters" \
     -d "TASK_ID=CICD-001"
   ```

## **Backward Compatibility**

### **Nếu không có TASK_ID:**
- Backend sẽ fallback về tìm theo `jenkins_job` name
- Xử lý tất cả task có cùng job name
- Giữ backward compatibility

### **Nếu TASK_ID không hợp lệ:**
- Jenkins sẽ fail với error message
- User cần nhập TASK_ID đúng format

## **Testing Checklist**

### **✅ Pre-Migration:**
- [ ] Backup Jenkinsfile cũ
- [ ] Test Jenkinsfile cũ hoạt động bình thường
- [ ] Backup database

### **✅ Post-Migration:**
- [ ] Test với TASK_ID=TASK-001 (execution)
- [ ] Test với TASK_ID=PLAN-001 (plan)
- [ ] Test với TASK_ID=CICD-001 (cicd)
- [ ] Verify webhook được gửi với TASK_ID
- [ ] Verify report được tạo đúng trong backend
- [ ] Verify notification được tạo

### **✅ Error Handling:**
- [ ] Test với TASK_ID không hợp lệ
- [ ] Test với TASK_ID không tồn tại
- [ ] Test webhook failure

## **Rollback Plan**

### **Nếu có vấn đề:**
1. **Restore Jenkinsfile cũ:**
   ```bash
   cp Jenkinsfile.backup Jenkinsfile
   ```

2. **Remove Parameters:**
   - Untick "This project is parameterized"
   - Remove TASK_ID parameter

3. **Test lại:**
   - Verify job hoạt động bình thường
   - Verify webhook được gửi

## **Troubleshooting**

### **Jenkins job fail với TASK_ID:**
```
Error: Invalid TASK_ID format: INVALID-001. Must start with TASK-, PLAN-, or CICD-
```
**Giải pháp:** Kiểm tra format TASK_ID

### **Webhook không gửi:**
```
❌ Failed to send webhook: Connection refused
```
**Giải pháp:** Kiểm tra backend URL và network

### **Report không được tạo:**
```
Task not found for TASK_ID: TASK-001
```
**Giải pháp:** Kiểm tra task có tồn tại trong database không

## **Best Practices**

### **✅ Nên làm:**
- Test migration trên staging environment trước
- Monitor logs sau khi migration
- Train team members về TASK_ID usage
- Document TASK_ID format và usage

### **❌ Không nên:**
- Migrate production trực tiếp
- Bỏ qua testing
- Để trống TASK_ID parameter
- Sử dụng format TASK_ID không đúng

## **Support**

Nếu gặp vấn đề trong quá trình migration:
1. Kiểm tra Jenkins logs
2. Kiểm tra backend logs
3. Verify TASK_ID format
4. Contact development team 