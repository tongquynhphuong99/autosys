from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ARRAY, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - sử dụng cho Docker container
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://testops_user:testops_password@postgres:5432/testops")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

# Database models
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="active")
    repo_link = Column(String(500))
    project_manager = Column(String(100))
    members = Column(ARRAY(String))
    testcase_number = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    plans = relationship("Plan", back_populates="project")

class TestCase(Base):
    __tablename__ = "testcases"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    project_id = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Execution(Base):
    __tablename__ = "executions"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), nullable=False)
    task_name = Column(String(200), nullable=False)
    description = Column(Text)
    project_id = Column(Integer, nullable=False)
    jenkins_job = Column(String(200))
    status = Column(String(20), default="initialized")
    created_at = Column(DateTime, default=datetime.utcnow)

class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(50), nullable=False)
    plan_name = Column(String(200), nullable=False)
    description = Column(Text)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    jenkins_job = Column(String(200))
    schedule_time = Column(String(100), nullable=False)
    status = Column(String(20), default="initialized")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    project = relationship("Project", back_populates="plans")

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), nullable=False)  # ID của task (TASK001, PLAN001, CICD001)
    execution_id = Column(Integer, nullable=True)  # ID của execution hoặc plan (null cho CI/CD)
    cicd_id = Column(Integer, nullable=True)  # ID của CI/CD task (null cho executions và plans)
    project_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)
    total_tests = Column(Integer, default=0)
    passed_tests = Column(Integer, default=0)
    failed_tests = Column(Integer, default=0)
    skipped_tests = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Bổ sung các trường mới
    jenkins_job = Column(String(200))
    build_number = Column(Integer)
    project_name = Column(String(200))
    task_type = Column(String(20))

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    source = Column(String(50))  # 'backend', 'jenkins'
    created_at = Column(DateTime, default=datetime.utcnow)

class Cicd(Base):
    __tablename__ = "cicd"
    id = Column(Integer, primary_key=True, index=True)
    cicd_id = Column(String(50), nullable=False)
    cicd_name = Column(String(200), nullable=False)
    cicd_type = Column(String(50), nullable=False)
    description = Column(Text)
    jenkins_job = Column(String(200))
    project_id = Column(Integer, nullable=False)
    status = Column(String(20), default="initialized")
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), nullable=False)  # ID của task (TASK-001, PLAN-001, CICD-001)
    task_name = Column(String(200), nullable=False)  # Tên của task
    task_type = Column(String(20), nullable=False)  # Loại task (execution, plan, cicd)
    status = Column(String(20), nullable=False)  # Trạng thái (success, failure, aborted)
    project_name = Column(String(200))  # Tên project
    message = Column(Text, nullable=False)  # Nội dung thông báo
    is_read = Column(Boolean, default=False)  # Đã đọc chưa
    read_at = Column(DateTime)  # Thời gian đọc
    created_at = Column(DateTime, default=datetime.utcnow)  # Thời gian tạo

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)

# Get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test database connection
def test_connection():
    try:
        from sqlalchemy import text
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()  # Actually fetch the result
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False 