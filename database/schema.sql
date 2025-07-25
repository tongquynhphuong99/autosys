-- TestOps Database Schema (Complete & Updated)

-- Users table (single user system)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table (without jenkins_jobs)
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    repo_link TEXT,
    project_manager VARCHAR(100),
    members TEXT[], -- Array of member names
    testcase_number INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test cases table
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

-- Executions table (with task name and description)
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

-- Plans table
CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(50) NOT NULL,
    plan_name VARCHAR(200) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    jenkins_job VARCHAR(200),
    schedule_time VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'initialized',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CI/CD table (with cicd_id support)
CREATE TABLE cicd (
    id SERIAL PRIMARY KEY,
    cicd_id VARCHAR(50) NOT NULL, -- Unique identifier for CI/CD task
    cicd_name VARCHAR(200) NOT NULL,
    cicd_type VARCHAR(50) NOT NULL,
    description TEXT,
    jenkins_job VARCHAR(200),
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'initialized',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reports table (unified for all task types)
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL, -- ID của task (TASK001, PLAN001, CICD001) - dùng để phân biệt loại task
    execution_id INTEGER, -- ID của execution hoặc plan (null cho CI/CD)
    cicd_id INTEGER, -- ID của CI/CD task (null cho executions và plans)
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    total_tests INTEGER DEFAULT 0,
    passed_tests INTEGER DEFAULT 0,
    failed_tests INTEGER DEFAULT 0,
    skipped_tests INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    jenkins_job VARCHAR(200),
    build_number INTEGER,
    project_name VARCHAR(200),
    task_type VARCHAR(20)
);

-- Logs table
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for better performance
CREATE INDEX idx_plans_project_id ON plans(project_id);
CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plans_schedule_time ON plans(schedule_time);
CREATE INDEX idx_cicd_project_id ON cicd(project_id);
CREATE INDEX idx_reports_project_id ON reports(project_id);
CREATE INDEX idx_reports_task_id ON reports(task_id);
CREATE INDEX idx_reports_execution_id ON reports(execution_id);
CREATE INDEX idx_reports_cicd_id ON reports(cicd_id);

-- Notifications table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL, -- ID của task (TASK-001, PLAN-001, CICD-001)
    task_name VARCHAR(200) NOT NULL, -- Tên của task
    task_type VARCHAR(20) NOT NULL, -- Loại task (execution, plan, cicd)
    status VARCHAR(20) NOT NULL, -- Trạng thái (success, failure, aborted)
    project_name VARCHAR(200), -- Tên project
    message TEXT NOT NULL, -- Nội dung thông báo
    is_read BOOLEAN DEFAULT FALSE, -- Đã đọc chưa
    read_at TIMESTAMP, -- Thời gian đọc
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Thời gian tạo
);

-- Add indexes for better performance
CREATE INDEX idx_notifications_task_id ON notifications(task_id);
CREATE INDEX idx_notifications_task_type ON notifications(task_type);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- Add comments for documentation
COMMENT ON COLUMN cicd.cicd_id IS 'ID định danh duy nhất cho CI/CD task (format: CICD-001, CICD-002, ...)';
COMMENT ON COLUMN reports.task_id IS 'ID của task (TASK001, PLAN001, CICD001) - dùng để phân biệt loại task';
COMMENT ON COLUMN reports.execution_id IS 'ID của execution hoặc plan (null cho CI/CD)';
COMMENT ON COLUMN reports.cicd_id IS 'ID của CI/CD task (null cho executions và plans)';
COMMENT ON COLUMN notifications.task_id IS 'ID của task để tạo thông báo';
COMMENT ON COLUMN notifications.task_type IS 'Loại task (execution, plan, cicd)';
COMMENT ON COLUMN notifications.status IS 'Trạng thái kết quả (success, failure, aborted)'; 