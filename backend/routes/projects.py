from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, Project as DBProject, TestCase, Execution, Report

router = APIRouter()

# Data models
class Project(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: str
    repo_link: str = ""
    project_manager: str = ""
    members: list = []
    test_cases_count: int = 0
    executions_count: int = 0
    success_rate: float = 0.0
    testcase_number: int = 0

class ProjectCreate(BaseModel):
    name: str
    description: str
    status: str = "active"
    repo_link: str = ""
    project_manager: str = ""
    members: list = []

class ProjectUpdate(BaseModel):
    name: str
    description: str
    status: str
    repo_link: str = ""
    project_manager: str = ""
    members: list = []

def get_next_available_id(db: Session) -> int:
    """Tìm ID nhỏ nhất có sẵn để tái sử dụng"""
    try:
        # Lấy tất cả ID hiện có
        result = db.execute(text("SELECT id FROM projects ORDER BY id"))
        existing_ids = [row[0] for row in result.fetchall()]
        
        if not existing_ids:
            return 1
        
        # Tìm ID nhỏ nhất có sẵn
        for i in range(1, max(existing_ids) + 2):
            if i not in existing_ids:
                return i
        
        return max(existing_ids) + 1
    except Exception as e:
        print(f"Error getting next available ID: {e}")
        # Fallback: sử dụng sequence
        result = db.execute(text("SELECT nextval('projects_id_seq')"))
        return result.fetchone()[0]



# Serve the projects HTML page
@router.get("/page", response_class=HTMLResponse)
def get_projects_page():
    """Serve the projects management page"""
    try:
        file_path = "static/projects.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Projects page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading projects page: {str(e)}</h1>", status_code=500)

# API endpoints
@router.get("/", response_model=List[Project])
def get_projects(db: Session = Depends(get_db)):
    """Get all projects from database"""
    try:
        db_projects = db.query(DBProject).all()
        projects = []
        
        for db_project in db_projects:
            # Members is already an array
            members = db_project.members or []
            
            # Count test cases for this project
            test_cases_count = db.query(TestCase).filter(TestCase.project_id == db_project.id).count()
            
            # Count executions for this project
            executions_count = db.query(Execution).filter(Execution.project_id == db_project.id).count()
            
            # Calculate success rate from reports
            reports = db.query(Report).filter(Report.project_id == db_project.id).all()
            total_runs = len(reports)
            successful_runs = len([r for r in reports if r.status == 'success'])
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
            
            project = {
                "id": db_project.id,
                "name": db_project.name,
                "description": db_project.description or "",
                "status": db_project.status,
                "created_at": db_project.created_at.strftime("%Y-%m-%d %H:%M:%S") if db_project.created_at else "",
                "repo_link": db_project.repo_link or "",
                "project_manager": db_project.project_manager or "",
                "members": members,
                "test_cases_count": test_cases_count,
                "executions_count": executions_count,
                "success_rate": round(success_rate, 2),
                "testcase_number": getattr(db_project, "testcase_number", 0)
            }
            projects.append(project)
        
        return projects
    except Exception as e:
        print(f"Error getting projects: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}", response_model=Project)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project by ID from database"""
    try:
        db_project = db.query(DBProject).filter(DBProject.id == project_id).first()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Members is already an array
        members = db_project.members or []
        
        # Count test cases for this project
        test_cases_count = db.query(TestCase).filter(TestCase.project_id == db_project.id).count()
        
        # Count executions for this project
        executions_count = db.query(Execution).filter(Execution.project_id == db_project.id).count()
        
        # Calculate success rate from reports
        reports = db.query(Report).filter(Report.project_id == db_project.id).all()
        total_runs = len(reports)
        successful_runs = len([r for r in reports if r.status == 'success'])
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
        
        return {
            "id": db_project.id,
            "name": db_project.name,
            "description": db_project.description or "",
            "status": db_project.status,
            "created_at": db_project.created_at.strftime("%Y-%m-%d %H:%M:%S") if db_project.created_at else "",
            "repo_link": db_project.repo_link or "",
            "project_manager": db_project.project_manager or "",
            "members": members,
            "test_cases_count": test_cases_count,
            "executions_count": executions_count,
            "success_rate": round(success_rate, 2),
            "testcase_number": getattr(db_project, "testcase_number", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=Project)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project in database with reused ID and create Jenkins job"""
    try:
        # Tìm ID nhỏ nhất có sẵn
        next_id = get_next_available_id(db)
        
        # Members is already a list, use directly
        members_array = project.members or []
        
        db_project = DBProject(
            id=next_id,  # Sử dụng ID tùy chỉnh
            name=project.name,
            description=project.description,
            status=project.status,
            repo_link=project.repo_link,
            project_manager=project.project_manager,
            members=members_array,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        
        return {
            "id": db_project.id,
            "name": db_project.name,
            "description": db_project.description or "",
            "status": db_project.status,
            "created_at": db_project.created_at.strftime("%Y-%m-%d %H:%M:%S") if db_project.created_at else "",
            "repo_link": db_project.repo_link or "",
            "project_manager": db_project.project_manager or "",
            "members": project.members,
            "test_cases_count": 0,  # New project has no test cases yet
            "executions_count": 0,   # New project has no executions yet
            "testcase_number": getattr(db_project, "testcase_number", 0)
        }
    except Exception as e:
        db.rollback()
        print(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{project_id}", response_model=Project)
def update_project(project_id: int, project: ProjectUpdate, db: Session = Depends(get_db)):
    """Update an existing project in database"""
    try:
        db_project = db.query(DBProject).filter(DBProject.id == project_id).first()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Members is already a list, use directly
        members_array = project.members or []
        
        # Update project fields
        db_project.name = project.name
        db_project.description = project.description
        db_project.status = project.status
        db_project.repo_link = project.repo_link
        db_project.project_manager = project.project_manager
        db_project.members = members_array
        db_project.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_project)
        
        # Count test cases and executions for updated project
        test_cases_count = db.query(TestCase).filter(TestCase.project_id == db_project.id).count()
        executions_count = db.query(Execution).filter(Execution.project_id == db_project.id).count()
        
        return {
            "id": db_project.id,
            "name": db_project.name,
            "description": db_project.description or "",
            "status": db_project.status,
            "created_at": db_project.created_at.strftime("%Y-%m-%d %H:%M:%S") if db_project.created_at else "",
            "repo_link": db_project.repo_link or "",
            "project_manager": db_project.project_manager or "",
            "members": project.members,
            "test_cases_count": test_cases_count,
            "executions_count": executions_count,
            "testcase_number": getattr(db_project, "testcase_number", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project from database"""
    try:
        db_project = db.query(DBProject).filter(DBProject.id == project_id).first()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_name = db_project.name
        db.delete(db_project)
        db.commit()
        
        return {"message": f"Project '{project_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 