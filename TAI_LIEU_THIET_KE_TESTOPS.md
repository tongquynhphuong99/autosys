# 📋 TÀI LIỆU THIẾT KẾ HỆ THỐNG TESTOPS

## 📖 Mục lục
1. [Tổng quan hệ thống](#tổng-quan-hệ-thống)
2. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
3. [Cơ sở dữ liệu](#cơ-sở-dữ-liệu)
4. [API Design](#api-design)
5. [Frontend Design](#frontend-design)
6. [Tích hợp Jenkins](#tích-hợp-jenkins)
7. [Workflow hệ thống](#workflow-hệ-thống)
8. [Bảo mật](#bảo-mật)
9. [Deployment](#deployment)
10. [Monitoring & Logging](#monitoring--logging)

---

## 🎯 TỔNG QUAN HỆ THỐNG

### Mục tiêu
TestOps là hệ thống quản lý và tự động hóa quá trình testing tích hợp với Jenkins, cung cấp:
- Quản lý test cases và test suites
- Tự động hóa test execution với Robot Framework
- Real-time monitoring và reporting
- Analytics và dashboard trực quan
- Tích hợp CI/CD với Jenkins webhook
- Quản lý test plans với cron scheduling

### Tính năng chính
- ✅ **Test Management**: Quản lý projects, test cases, test plans
- ✅ **Test Automation**: Framework tự động hóa với Robot Framework
- ✅ **Real-time Monitoring**: Theo dõi test execution real-time qua webhook
- ✅ **Analytics & Reporting**: Báo cáo chi tiết và biểu đồ thống kê
- ✅ **Dashboard**: Giao diện quản lý trực quan với Chart.js
- ✅ **User Authentication**: Đăng nhập với JWT và bcrypt
- ✅ **Jenkins Integration**: Tích hợp webhook với Jenkins pipeline
- ✅ **Cron Scheduling**: Quản lý test plans với cron expressions
- ✅ **Docker Support**: Containerization với Docker Compose
- ✅ **Filtering & Search**: Lọc và tìm kiếm dữ liệu nâng cao

---

## 🏗️ KIẾN TRÚC HỆ THỐNG

### Kiến trúc tổng thể
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   (HTML/CSS/JS) │◄──►│   (FastAPI)     │◄──►│  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Jenkins       │    │   Docker        │    │   Logging       │
│   (CI/CD)       │    │   (Container)   │    │   (System)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Tech Stack

#### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0.23
- **Authentication**: JWT + bcrypt
- **Container**: Docker
- **Dependencies**: 
  - fastapi==0.104.1
  - uvicorn==0.24.0
  - pydantic==2.5.0
  - passlib[bcrypt]==1.7.4
  - psycopg2-binary==2.9.9
  - requests==2.31.0

#### Frontend
- **Framework**: HTML/CSS/JavaScript (Vanilla)
- **Charts**: Chart.js 4.4.0
- **UI**: Material Design inspired
- **Responsive**: Mobile-first design
- **Features**: 
  - Real-time filtering
  - Interactive charts
  - Modal dialogs
  - Form validation

#### DevOps
- **CI/CD**: Jenkins LTS với Docker support
- **Container**: Docker Compose 3.8
- **Test Framework**: Robot Framework
- **Monitoring**: Custom logging system
- **Health Checks**: Container health monitoring

---

## 🗄️ CƠ SỞ DỮ LIỆU

### Schema Design

#### 1. Bảng `users`
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. Bảng `projects`
```sql
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    repo_link TEXT,
    project_manager VARCHAR(100),
    members TEXT[], -- Array of member names
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3. Bảng `testcases`
```sql
CREATE TABLE testcases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active',
    priority VARCHAR(20) DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4. Bảng `executions`
```sql
CREATE TABLE executions (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL,
    task_name VARCHAR(200) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    jenkins_job VARCHAR(200),
    status VARCHAR(20) DEFAULT 'initialized',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 5. Bảng `plans`
```sql
CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(50) NOT NULL,
    plan_name VARCHAR(200) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    jenkins_job VARCHAR(200),
    schedule_time VARCHAR(100) NOT NULL, -- Cron expression
    status VARCHAR(20) DEFAULT 'initialized',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 6. Bảng `reports`
```sql
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL,
    task_id VARCHAR(50) NOT NULL,
    project_id INTEGER NOT NULL,
    project_name VARCHAR(100) NOT NULL,
    total_testcases INTEGER DEFAULT 0,
    passed_testcases INTEGER DEFAULT 0,
    failed_testcases INTEGER DEFAULT 0,
    skipped_testcases INTEGER DEFAULT 0,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER DEFAULT 0,
    jenkins_build_number INTEGER,
    jenkins_job VARCHAR(200),
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 7. Bảng `logs`
```sql
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR, DEBUG
    message TEXT NOT NULL,
    source VARCHAR(50), -- 'backend', 'jenkins'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Relationships
- **Project** → **TestCases** (1:N)
- **Project** → **Executions** (1:N)
- **Project** → **Plans** (1:N)
- **Execution** → **Reports** (1:N)
- **Plan** → **Reports** (1:N)

### Database Features
- **Connection Pooling**: SQLAlchemy connection pool
- **Health Checks**: Database connectivity monitoring
- **Migration Support**: Schema versioning
- **Data Validation**: SQLAlchemy model validation

---

## 🔌 API DESIGN

### Base URL
```
http://localhost:8000/api
```

### Authentication Endpoints
```
POST /api/auth/login     - Đăng nhập với JWT
GET  /api/auth/me        - Lấy thông tin user hiện tại
POST /api/auth/logout    - Đăng xuất
```

### Projects Endpoints
```
GET    /api/projects           - Lấy danh sách projects
POST   /api/projects           - Tạo project mới
GET    /api/projects/{id}      - Lấy chi tiết project
PUT    /api/projects/{id}      - Cập nhật project
DELETE /api/projects/{id}      - Xóa project
```

### Test Cases Endpoints
```
GET    /api/projects/{project_id}/testcases  - Lấy test cases của project
POST   /api/projects/{project_id}/testcases  - Tạo test case mới
GET    /api/projects/{project_id}/testcases/{id}  - Lấy chi tiết test case
PUT    /api/projects/{project_id}/testcases/{id}  - Cập nhật test case
DELETE /api/projects/{project_id}/testcases/{id}  - Xóa test case
```

### Executions Endpoints
```
GET    /api/executions         - Lấy danh sách executions
POST   /api/executions         - Tạo execution mới
GET    /api/executions/{id}    - Lấy chi tiết execution
PUT    /api/executions/{id}    - Cập nhật execution
DELETE /api/executions/{id}    - Xóa execution
```

### Plans Endpoints
```
GET    /api/plans              - Lấy danh sách plans
POST   /api/plans              - Tạo plan mới
GET    /api/plans/{id}         - Lấy chi tiết plan
PUT    /api/plans/{id}         - Cập nhật plan
DELETE /api/plans/{id}         - Xóa plan (clear cron schedule)
```

### Reports Endpoints
```
GET    /api/reports/dashboard-stats      - Thống kê dashboard
GET    /api/reports/execution-trends     - Xu hướng executions
GET    /api/reports/project-performance  - Hiệu suất projects
GET    /api/reports/task-reports         - Báo cáo tasks (với filtering)
GET    /api/reports/testcase-stats       - Thống kê test cases
GET    /api/reports/latest-test-results  - Kết quả test gần nhất
POST   /api/reports/jenkins/webhook      - Webhook từ Jenkins
GET    /api/reports/jenkins/file/{job_name}/{file_name}  - Lấy file từ Jenkins
GET    /api/reports/jenkins/view/{job_name}/{build_number}/{file_name}  - Xem file Jenkins
```

### Logs Endpoints
```
GET    /api/logs               - Lấy danh sách logs
POST   /api/logs               - Tạo log mới
```

### Dashboard Endpoints
```
GET    /api/dashboard-stats    - Thống kê tổng quan
```

### Response Format
```json
{
  "status": "success",
  "data": {
    // Response data
  },
  "message": "Operation completed successfully"
}
```

### Error Format
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description"
  }
}
```

---

## 🎨 FRONTEND DESIGN

### Architecture
- **Framework**: Vanilla HTML/CSS/JavaScript
- **Styling**: Custom CSS với Material Design inspiration
- **Charts**: Chart.js 4.4.0 cho biểu đồ và thống kê
- **Responsive**: Mobile-first responsive design
- **Features**: Real-time filtering, modal dialogs, form validation

### Pages Structure
```
/                    - Dashboard (Tổng quan)
/projects           - Projects Management
/tests              - Test Cases Management
/executions         - Executions Management
/plans              - Plans Management
/reports            - Reports & Analytics
/logs               - System Logs
/login              - Authentication
```

### Components

#### 1. Navigation
- Header với logo và menu navigation
- User info và logout button
- Active page highlighting

#### 2. Dashboard
- Stats cards (Projects, Tasks, Test Cases)
- Charts (Execution Trends, Project Performance)
- Recent activities
- Quick actions

#### 3. Data Tables
- Sortable columns
- Search functionality
- Pagination
- Action buttons (Edit, Delete, View)
- Real-time filtering

#### 4. Forms
- Modal dialogs
- Form validation
- File upload support
- Auto-save functionality

#### 5. Charts
- Line charts (trends)
- Bar charts (comparisons)
- Pie charts (distributions)
- Stacked bar charts (breakdowns)

#### 6. Filtering System
- Project filter dropdown
- Status filter dropdown
- Clear filter functionality
- Real-time results update

### UI/UX Principles
- **Consistency**: Uniform design language
- **Accessibility**: WCAG 2.1 compliance
- **Performance**: Fast loading times
- **Usability**: Intuitive navigation
- **Responsive**: Works on all devices

---

## 🔗 TÍCH HỢP JENKINS

### Architecture
```
Jenkins Job → Webhook → Backend API → Database
     ↓           ↓           ↓           ↓
Robot Tests → HTTP POST → FastAPI → PostgreSQL
```

### Webhook Configuration

#### Jenkinsfile Template
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
                // Phân tích kết quả Robot Framework
                robot outputPath: 'results'
                
                // Nén và chuẩn bị gửi report
                sh '''
                    tar czf results.tar.gz -C results .
                '''
            }
        }
        
        success {
            script {
                // Gửi webhook khi build thành công
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
            }
        }
    }
}
```

### Webhook Processing
1. **Receive**: Backend nhận webhook từ Jenkins
2. **Parse**: Parse thông tin job và build
3. **Identify**: Xác định job thuộc plan hay execution
4. **Fetch**: Lấy file `output.xml` từ Jenkins
5. **Process**: Parse test results từ XML
6. **Save**: Lưu report vào database
7. **Update**: Cập nhật status của plan/execution

### Cron Schedule Management
- **Add Schedule**: Thêm cron expression vào Jenkins job
- **Remove Schedule**: Xóa cron expression khỏi Jenkins job
- **Update Schedule**: Cập nhật cron expression
- **Status Tracking**: Theo dõi trạng thái plan

### Supported Job Statuses
- **SUCCESS**: Job hoàn thành thành công
- **FAILURE**: Job thất bại
- **ABORTED**: Job bị hủy
- **UNSTABLE**: Job không ổn định

---

## 🔄 WORKFLOW HỆ THỐNG

### 1. Project Management Workflow
```
Create Project → Add Test Cases → Create Plans/Executions → Monitor Results
```

### 2. Test Execution Workflow
```
Manual Execution:
Create Execution → Configure Jenkins Job → Run Tests → Receive Webhook → Save Report

Scheduled Execution:
Create Plan → Set Cron Schedule → Jenkins Cron → Run Tests → Receive Webhook → Save Report
```

### 3. Reporting Workflow
```
Jenkins Job → Webhook → Parse Results → Save Report → Update Dashboard → Generate Analytics
```

### 4. User Authentication Workflow
```
Login → JWT Token → API Access → Session Management → Logout
```

### 5. Plan Management Workflow
```
Create Plan → Set Cron Schedule → Jenkins Config Update → Monitor Execution → Clear Schedule (on delete)
```

### 6. Data Flow
```
Frontend → Backend API → Database
    ↓           ↓           ↓
User Input → Business Logic → Data Storage
    ↓           ↓           ↓
UI Update ← Response Data ← Query Results
```

---

## 🔒 BẢO MẬT

### Authentication
- **JWT Tokens**: Stateless authentication
- **Password Hashing**: bcrypt for password security
- **Session Management**: Token-based sessions
- **Access Control**: Role-based permissions

### API Security
- **CORS**: Cross-origin resource sharing configuration
- **Input Validation**: Request data validation với Pydantic
- **SQL Injection**: Parameterized queries với SQLAlchemy
- **Rate Limiting**: API rate limiting (future)

### Data Security
- **Encryption**: Database encryption at rest
- **Backup**: Regular database backups
- **Audit Logs**: User action logging
- **Data Privacy**: GDPR compliance considerations

### Infrastructure Security
- **Docker Security**: Container security best practices
- **Network Security**: Isolated Docker networks
- **Environment Variables**: Secure configuration management
- **SSL/TLS**: HTTPS encryption (production)

---

## 🚀 DEPLOYMENT

### Docker Compose Configuration
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: testops_postgres
    environment:
      POSTGRES_DB: testops
      POSTGRES_USER: testops_user
      POSTGRES_PASSWORD: testops_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./database/init.sql:/docker-entrypoint-initdb.d/02-init.sql
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U testops_user -d testops"]
      interval: 10s
      timeout: 5s
      retries: 5

  jenkins:
    build: ./jenkins
    container_name: testops_jenkins
    user: root
    environment:
      - JENKINS_OPTS=--httpPort=8080
      - JAVA_OPTS=-Djenkins.install.runSetupWizard=false
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - ./jenkins-data:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/login"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  backend:
    build: ./backend
    container_name: testops_backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://testops_user:testops_password@postgres:5432/testops
      - JENKINS_URL=http://jenkins:8080
      - JENKINS_USER=
      - JENKINS_TOKEN=
    depends_on:
      postgres:
        condition: service_healthy
      jenkins:
        condition: service_healthy
    volumes:
      - ./backend:/app
    restart: unless-stopped

volumes:
  postgres_data:
```

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://testops_user:testops_password@postgres:5432/testops

# Jenkins
JENKINS_URL=http://jenkins:8080
JENKINS_USER=admin
JENKINS_TOKEN=your_jenkins_token

# Security
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret

# Application
DEBUG=True
LOG_LEVEL=INFO
```

### Deployment Commands
```bash
# Development
docker-compose up --build -d

# Production
docker-compose -f docker-compose.prod.yml up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f
```

---

## 📊 MONITORING & LOGGING

### Logging System
- **Application Logs**: FastAPI application logs
- **Database Logs**: PostgreSQL query logs
- **Jenkins Logs**: CI/CD pipeline logs
- **System Logs**: Docker container logs

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: General information messages
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical system errors

### Monitoring Metrics
- **API Performance**: Response times, throughput
- **Database Performance**: Query times, connections
- **System Resources**: CPU, memory, disk usage
- **Application Health**: Health check endpoints

### Health Checks
```bash
# API Health
curl http://localhost:8000/health

# Database Health
curl http://localhost:8000/db-test

# Jenkins Health
curl http://localhost:8080/login
```

### Alerting
- **Error Thresholds**: Automatic alerts on errors
- **Performance Degradation**: Response time monitoring
- **Resource Usage**: System resource monitoring
- **Service Availability**: Service uptime monitoring

---

## 📈 PERFORMANCE & SCALABILITY

### Performance Optimization
- **Database Indexing**: Optimized database queries
- **Connection Pooling**: Database connection management
- **Caching**: Application-level caching (future)
- **CDN**: Static file delivery (production)

### Scalability Considerations
- **Horizontal Scaling**: Multiple backend instances
- **Load Balancing**: Nginx load balancer (production)
- **Database Scaling**: Read replicas, sharding
- **Microservices**: Service decomposition (future)

### Resource Requirements
- **Minimum**: 2GB RAM, 1 CPU core
- **Recommended**: 4GB RAM, 2 CPU cores
- **Production**: 8GB RAM, 4 CPU cores

---

## 🔧 MAINTENANCE & OPERATIONS

### Backup Strategy
- **Database Backups**: Daily automated backups
- **Configuration Backups**: Version-controlled configs
- **Log Archives**: Log rotation and archiving
- **Disaster Recovery**: Backup restoration procedures

### Update Procedures
- **Application Updates**: Rolling updates with zero downtime
- **Database Migrations**: Schema migration scripts
- **Security Updates**: Regular security patches
- **Dependency Updates**: Package dependency management

### Troubleshooting
- **Common Issues**: Known problems and solutions
- **Debug Procedures**: Step-by-step debugging guides
- **Support Documentation**: User and admin guides
- **Escalation Procedures**: Issue escalation workflows

---

## 🆕 TÍNH NĂNG MỚI VÀ CẢI TIẾN

### Tính năng đã triển khai
- ✅ **Real-time Filtering**: Lọc dữ liệu theo project và status
- ✅ **Cron Schedule Management**: Quản lý lịch chạy test với cron expressions
- ✅ **Jenkins Integration**: Tích hợp webhook real-time
- ✅ **Advanced Reporting**: Báo cáo chi tiết với biểu đồ tương tác
- ✅ **Plan Deletion Logic**: Xóa cron schedule khi xóa plan
- ✅ **Form Validation**: Validation toàn diện cho forms
- ✅ **Error Handling**: Xử lý lỗi nâng cao

### Cải tiến UI/UX
- ✅ **Responsive Design**: Giao diện thích ứng mobile
- ✅ **Interactive Charts**: Biểu đồ tương tác với Chart.js
- ✅ **Modal Dialogs**: Dialog boxes cho forms
- ✅ **Loading States**: Trạng thái loading cho UX tốt hơn
- ✅ **Error Messages**: Thông báo lỗi rõ ràng
- ✅ **Success Feedback**: Phản hồi thành công

### Performance Improvements
- ✅ **Database Optimization**: Connection pooling và indexing
- ✅ **API Response Time**: Tối ưu thời gian phản hồi API
- ✅ **Frontend Loading**: Tối ưu tải trang
- ✅ **Caching Strategy**: Chiến lược cache hiệu quả

---

## 📚 CONCLUSION

TestOps là hệ thống quản lý testing toàn diện với các tính năng:
- ✅ Quản lý projects và test cases
- ✅ Tự động hóa test execution với Robot Framework
- ✅ Real-time monitoring và reporting qua webhook
- ✅ Tích hợp Jenkins CI/CD với cron scheduling
- ✅ Dashboard trực quan với Chart.js
- ✅ Bảo mật và authentication với JWT
- ✅ Docker containerization với health checks
- ✅ Scalable architecture với connection pooling
- ✅ Advanced filtering và search capabilities
- ✅ Comprehensive error handling và logging

Hệ thống được thiết kế để dễ dàng mở rộng và bảo trì, với kiến trúc modular và documentation đầy đủ. Tích hợp Jenkins webhook cho phép real-time monitoring và reporting, trong khi cron scheduling cho phép tự động hóa test execution theo lịch trình.

---

**Tài liệu này được cập nhật từ phân tích code thực tế của dự án TestOps.**
**Phiên bản**: 2.0.0
**Ngày cập nhật**: 2025-01-20
**Tác giả**: AI Assistant 