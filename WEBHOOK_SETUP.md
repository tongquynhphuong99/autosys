# Hướng dẫn cấu hình Webhook cho Jenkins

## Tổng quan
Webhook cho phép Jenkins tự động gửi thông báo đến backend khi job hoàn thành, giúp lưu report real-time mà không cần polling.

## Cấu hình Jenkins Webhook

### 1. Cài đặt Plugin (nếu chưa có)
- Vào **Manage Jenkins** > **Manage Plugins**
- Tìm và cài đặt plugin **"HTTP Request Plugin"**

### 2. Cấu hình cho Pipeline Jobs

Với Pipeline jobs, bạn cần thêm webhook vào Jenkinsfile:

#### Cách 1: Thêm vào Jenkinsfile hiện tại
Thêm đoạn code sau vào phần `post` của Jenkinsfile:

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
    }

    post {
        always {
            script {
                // ✅ Phân tích kết quả Robot Framework
                robot outputPath: 'results'

                // ✅ Nén và chuẩn bị gửi report
                sh '''
                    tar czf results.tar.gz -C results .
                '''
            }
        }
        
        success {
            script {
                // ✅ Gửi webhook khi build thành công
                def webhookUrl = 'http://localhost:8000/api/reports/jenkins/webhook'
                def payload = [
                    name: env.JOB_NAME,
                    build: [
                        number: env.BUILD_NUMBER,
                        result: currentBuild.result,
                        status: 'FINISHED',
                        timestamp: currentBuild.startTimeInMillis,
                        duration: currentBuild.duration
                    ]
                ]
                
                // Gửi HTTP request đến webhook
                httpRequest(
                    url: webhookUrl,
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    requestBody: groovy.json.JsonOutput.toJson(payload),
                    validResponseCodes: '200,201,202'
                )
                
                echo "✅ Webhook sent to backend for job: ${env.JOB_NAME}"
            }
        }
        
        failure {
            script {
                echo "❌ Build failed, skipping webhook"
            }
        }
    }
}
```

#### Cách 2: Chỉ thêm phần webhook vào Jenkinsfile hiện tại
Nếu bạn không muốn thay đổi nhiều, chỉ cần thêm phần `success` vào `post`:

```groovy
    post {
        always {
            script {
                // ✅ Phân tích kết quả Robot Framework
                robot outputPath: 'results'

                // ✅ Nén và chuẩn bị gửi report
                sh '''
                    tar czf results.tar.gz -C results .
                '''
            }
        }
        
        success {
            script {
                // ✅ Gửi webhook khi build thành công
                def webhookUrl = 'http://localhost:8000/api/reports/jenkins/webhook'
                def payload = [
                    name: env.JOB_NAME,
                    build: [
                        number: env.BUILD_NUMBER,
                        result: currentBuild.result,
                        status: 'FINISHED',
                        timestamp: currentBuild.startTimeInMillis,
                        duration: currentBuild.duration
                    ]
                ]
                
                httpRequest(
                    url: webhookUrl,
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    requestBody: groovy.json.JsonOutput.toJson(payload),
                    validResponseCodes: '200,201,202'
                )
                
                echo "✅ Webhook sent to backend for job: ${env.JOB_NAME}"
            }
        }
    }
```

### 3. Cấu hình cho Freestyle Jobs (nếu có)

#### Cách 1: Sử dụng HTTP Request Plugin
1. Vào job Jenkins > **Configure**
2. Cuộn xuống phần **Post-build Actions**
3. Chọn **"HTTP Request"**
4. Cấu hình:
   - **URL**: `http://localhost:8000/api/reports/jenkins/webhook`
   - **HTTP Mode**: `POST`
   - **Content Type**: `application/json`
   - **Request Body**:
   ```json
   {
     "name": "${JOB_NAME}",
     "build": {
       "number": ${BUILD_NUMBER},
       "result": "${BUILD_RESULT}",
       "status": "FINISHED",
       "timestamp": ${BUILD_TIMESTAMP},
       "duration": ${BUILD_DURATION}
     }
   }
   ```
5. Chọn **"Only when build succeeds"** (chỉ gửi khi build thành công)

### 4. Test Webhook

Sử dụng script test:
```bash
# Test với job GW040-NS, build #5
python test_webhook.py GW040-NS 5 SUCCESS FINISHED

# Test với job khác
python test_webhook.py RobotTest 10 SUCCESS FINISHED
```

## Cách hoạt động

### 1. Khi job Jenkins hoàn thành:
- Jenkins gửi POST request đến webhook endpoint
- Backend nhận thông tin job và build

### 2. Backend xử lý:
- Kiểm tra job thuộc plan hay execution
- Lấy file `output.xml` từ Jenkins
- Parse thông tin test cases
- Lưu report vào database
- Cập nhật status của plan/execution

### 3. Ưu điểm:
- ✅ Real-time: Report được lưu ngay khi job hoàn thành
- ✅ Không cần polling: Tiết kiệm tài nguyên
- ✅ Đáng tin cậy: Không bỏ lỡ report
- ✅ Tự động: Không cần can thiệp thủ công

## Troubleshooting

### 1. Webhook không hoạt động:
- Kiểm tra URL webhook có đúng không
- Kiểm tra backend có đang chạy không
- Kiểm tra network connectivity
- Kiểm tra Jenkins có thể reach backend không

### 2. Report không được lưu:
- Kiểm tra job name có khớp với plan/execution không
- Kiểm tra file `output.xml` có tồn tại không
- Xem log backend để debug
- Kiểm tra Jenkins console log để xem webhook có được gửi không

### 3. Lỗi kết nối:
- Kiểm tra firewall
- Thử test với script `test_webhook.py`
- Kiểm tra Jenkins có quyền gửi HTTP request không

### 4. Lỗi trong Jenkinsfile:
- Kiểm tra syntax của Jenkinsfile
- Kiểm tra plugin HTTP Request đã được cài đặt chưa
- Xem Jenkins console log để debug

## Lưu ý

- Webhook chỉ gửi khi job **hoàn thành thành công** (SUCCESS)
- Backend sẽ tự động phân biệt job thuộc plan hay execution
- Report được lưu vào cùng bảng `reports` với execution
- Với Pipeline, webhook được gửi từ Jenkinsfile, không cần cấu hình UI
- Đảm bảo Jenkins có thể reach được backend URL 