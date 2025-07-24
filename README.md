# TestOps System

Hệ thống TestOps để quản lý và tự động hóa quá trình testing với Docker.

## 📁 Cấu trúc dự án

```
autosys/
├── frontend/          # Frontend Dashboard (React)
├── backend/           # Backend API (Python/FastAPI)
├── database/          # Database migrations và schema
├── docker-compose.yml # Docker Compose configuration
├── start.sh          # Script khởi động hệ thống
└── README.md         # Tài liệu dự án
```

## 🚀 Tính năng chính

- **Test Management**: Quản lý test cases, test suites
- **Test Automation**: Framework tự động hóa test
- **Real-time Monitoring**: Theo dõi test execution
- **Analytics & Reporting**: Báo cáo và phân tích
- **Dashboard**: Giao diện quản lý trực quan
- **User Authentication**: Đăng nhập với JWT
- **Project Management**: Quản lý dự án với thông tin chi tiết

## 🛠️ Tech Stack

### Backend
- **Python/FastAPI**: API framework
- **PostgreSQL**: Database chính
- **SQLAlchemy**: ORM
- **JWT**: Authentication
- **Docker**: Containerization

### Frontend
- **HTML/CSS/JavaScript**: Giao diện web
- **Material Design**: UI components
- **Chart.js**: Biểu đồ và thống kê

### Database
- **PostgreSQL 15**: Database server
- **Docker Volume**: Persistent data storage

## 🚀 Quick Start với Docker

### Yêu cầu hệ thống
- Docker
- Docker Compose

### Triển khai hệ thống

#### 1. Khởi động lần đầu (hoặc sau khi thay đổi code)
```bash
# Build lại images và khởi động
docker-compose up --build -d
```

#### 2. Khởi động bình thường (sau lần đầu)
```bash
# Khởi động các services
docker-compose up -d
```

#### 3. Sử dụng script có sẵn
```bash
# Chạy script khởi động
./start.sh
cd database && ./setup.sh #khoi dong tat ca
```

### Kiểm tra hệ thống

#### 1. Kiểm tra trạng thái containers
```bash
docker-compose ps
```

#### 2. Kiểm tra kết nối database
```bash
curl http://localhost:8000/db-test
```

#### 3. Truy cập ứng dụng
- **Dashboard**: http://localhost:8000
- **Projects**: http://localhost:8000/projects
- **API Health**: http://localhost:8000/health
- **Database Test**: http://localhost:8000/db-test

### Quản lý hệ thống

#### Xem logs
```bash
# Xem logs tất cả services
docker-compose logs

# Xem logs backend
docker-compose logs backend

# Xem logs postgres
docker-compose logs postgres

# Xem logs real-time
docker-compose logs -f
```

#### Dừng hệ thống
```bash
# Dừng services
docker-compose down

# Dừng và xóa volumes (cẩn thận - sẽ mất data)
docker-compose down -v
```

#### Restart service
```bash
# Restart backend
docker-compose restart backend

# Restart postgres
docker-compose restart postgres
```

## 🗄️ Database Configuration

### PostgreSQL Container
- **Host**: localhost (hoặc postgres trong Docker network)
- **Port**: 5432
- **Database**: testops
- **User**: testops_user
- **Password**: testops_password

### Volume Mounts
- **Data Storage**: `postgres_data:/var/lib/postgresql/data` (Docker named volume)
- **Schema**: `./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql`
- **Initial Data**: `./database/init.sql:/docker-entrypoint-initdb.d/02-init.sql`

### Kiểm tra database
```bash
# Kết nối vào PostgreSQL container
docker exec -it testops_postgres psql -U testops_user -d testops

# Xem danh sách bảng
\dt

# Test query
SELECT * FROM projects;
```

## 🔐 Authentication

### Default User
- **Username**: admin
- **Password**: admin123

### Login Flow
1. Truy cập http://localhost:8000
2. Đăng nhập với thông tin trên
3. Sau khi đăng nhập thành công, thông tin user sẽ hiển thị ở góc trên bên phải

## 📊 API Endpoints

### Authentication
- `POST /api/auth/login` - Đăng nhập
- `POST /api/auth/logout` - Đăng xuất

### Projects
- `GET /api/projects` - Lấy danh sách projects
- `POST /api/projects` - Tạo project mới
- `GET /api/projects/{id}` - Lấy chi tiết project
- `PUT /api/projects/{id}` - Cập nhật project
- `DELETE /api/projects/{id}` - Xóa project

### Test Cases
- `GET /api/testcases` - Lấy danh sách test cases
- `POST /api/testcases` - Tạo test case mới

### Executions
- `GET /api/executions` - Lấy danh sách executions
- `POST /api/executions` - Tạo execution mới

## 🐛 Troubleshooting

### Port 8000 bị chiếm
```bash
# Tìm process đang sử dụng port 8000
lsof -i :8000

# Dừng process
kill <PID>

# Hoặc dừng tất cả process trên port 8000
fuser -k 8000/tcp
```

### Database connection failed
```bash
# Kiểm tra PostgreSQL container
docker-compose logs postgres

# Test kết nối database
docker exec testops_postgres psql -U testops_user -d testops -c "SELECT 1;"
```

### Backend không khởi động
```bash
# Xem logs backend
docker-compose logs backend

# Rebuild backend
docker-compose build backend
docker-compose up -d
```

## 📚 Documentation

- **Backend API**: Xem trong thư mục `backend/`
- **Database Schema**: Xem trong thư mục `database/`
- **Frontend**: Xem trong thư mục `frontend/`

## 🤝 Contributing

1. Fork the project
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License. 