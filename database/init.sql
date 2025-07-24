-- Initialize TestOps Database

-- Create database (run this as superuser)
-- CREATE DATABASE testops;

-- Connect to database
-- \c testops;

-- Create tables
\i schema.sql

-- Insert single user (password: testops123)
INSERT INTO users (username, password_hash, full_name) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.iK8i', 'TestOps Administrator');

-- Insert sample data
INSERT INTO projects (name, description, status, repo_link, project_manager, members) VALUES 
('E-commerce Website Testing', 'Kiểm thử toàn diện cho website thương mại điện tử', 'active', 'https://github.com/company/ecommerce-testing', 'Nguyễn Văn A', ARRAY['Trần Thị B', 'Lê Văn C', 'Phạm Thị D']),
('Mobile App Testing', 'Kiểm thử ứng dụng di động trên iOS và Android', 'active', 'https://gitlab.com/company/mobile-testing', 'Hoàng Văn E', ARRAY['Vũ Thị F', 'Đặng Văn G']),
('API Testing Project', 'Kiểm thử REST API và microservices', 'completed', 'https://bitbucket.org/company/api-testing', 'Bùi Thị H', ARRAY['Ngô Văn I', 'Lý Thị K', 'Trịnh Văn L']),
('Performance Testing', 'Kiểm thử hiệu năng và tải cho hệ thống', 'paused', 'https://github.com/company/performance-testing', 'Đỗ Văn M', ARRAY['Hồ Thị N']);

INSERT INTO testcases (name, description, project_id, priority) VALUES 
('Login Test', 'Test user login functionality', 1, 'high'),
('Registration Test', 'Test user registration', 1, 'high'),
('Search Test', 'Test search functionality', 1, 'medium'),
('API Health Check', 'Check API endpoints health', 3, 'high');

INSERT INTO executions (task_id, task_name, description, project_id, jenkins_job, status) VALUES 
('TASK001', 'Login Test Run 1', 'Kiểm thử chức năng đăng nhập người dùng', 1, 'login-test-job', 'completed'),
('TASK002', 'Registration Test Run 1', 'Kiểm thử chức năng đăng ký người dùng', 1, 'registration-test-job', 'completed'),
('TASK003', 'Search Test Run 1', 'Kiểm thử chức năng tìm kiếm', 1, 'search-test-job', 'completed');

INSERT INTO plans (name, description, project_id) VALUES 
('Daily Smoke Test', 'Run critical tests daily', 1),
('Weekly Regression', 'Full regression test weekly', 1),
('API Test Plan', 'API testing plan', 3);

INSERT INTO logs (level, message, source) VALUES 
('INFO', 'Application started', 'system'),
('INFO', 'Database connected', 'database'),
('WARNING', 'Test execution failed', 'testrunner'); 