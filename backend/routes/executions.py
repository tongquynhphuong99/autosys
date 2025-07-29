import requests
import json
import os
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text
from database import SessionLocal, get_db
from database import Execution, Project
from routes.log import log_backend_event

router = APIRouter()

class ExecutionCreate(BaseModel):
    task_name: str
    description: Optional[str] = None
    jenkins_job: str
    project_id: int
    task_id: Optional[str] = None  # Cho phép chỉ định task_id
    email_recipients: Optional[str] = None  # Comma-separated email addresses

class ExecutionUpdate(BaseModel):
    task_name: str
    description: Optional[str] = None
    jenkins_job: str
    project_id: int
    email_recipients: Optional[str] = None  # Comma-separated email addresses

def get_next_available_execution_id(db):
    """Tìm ID nhỏ nhất có sẵn để tái sử dụng"""
    try:
        # Lấy tất cả ID hiện có
        result = db.execute(text("SELECT id FROM executions ORDER BY id"))
        existing_ids = [row[0] for row in result.fetchall()]
        
        if not existing_ids:
            return 1
        
        # Tìm ID nhỏ nhất có sẵn
        for i in range(1, max(existing_ids) + 2):
            if i not in existing_ids:
                return i
        
        return max(existing_ids) + 1
    except Exception as e:
        print(f"Error getting next available execution ID: {e}")
        # Fallback: sử dụng sequence
        result = db.execute(text("SELECT nextval('executions_id_seq')"))
        return result.fetchone()[0]

def get_next_available_task_id(db):
    """Tìm task_id nhỏ nhất có sẵn để tái sử dụng"""
    try:
        # Lấy tất cả task_id hiện có
        result = db.execute(text("SELECT task_id FROM executions WHERE task_id LIKE 'TASK-%' ORDER BY task_id"))
        existing_task_ids = [row[0] for row in result.fetchall()]
        
        if not existing_task_ids:
            return "TASK-001"
        
        # Tìm số lớn nhất hiện có
        max_number = 0
        for task_id in existing_task_ids:
            try:
                number = int(task_id.split('-')[1])
                max_number = max(max_number, number)
            except (IndexError, ValueError):
                continue
        
        # Tìm số nhỏ nhất có sẵn
        for i in range(1, max_number + 2):
            candidate_task_id = f"TASK-{i:03d}"
            if candidate_task_id not in existing_task_ids:
                return candidate_task_id
        
        return f"TASK-{(max_number + 1):03d}"
    except Exception as e:
        print(f"Error getting next available task ID: {e}")
        # Fallback: sử dụng timestamp
        import time
        return f"TASK-{int(time.time())}"

@router.get("/")
def get_executions(db: SessionLocal = Depends(get_db)):
    """Lấy tất cả executions"""
    try:
        executions = db.query(Execution).all()
        result = []
        for exe in executions:
            project = db.query(Project).filter(Project.id == exe.project_id).first()
            result.append({
                "id": exe.id,
                "task_id": exe.task_id,
                "task_name": exe.task_name,
                "description": exe.description,
                "project_id": exe.project_id,
                "project_name": project.name if project else "Unknown",
                "jenkins_job": exe.jenkins_job,
                "status": exe.status,
                "email_recipients": exe.email_recipients,
                "created_at": exe.created_at.isoformat() if exe.created_at else None
            })
        return {"executions": result, "count": len(result)}
    except Exception as e:
        print(f"[DEBUG] Error getting executions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/project/{project_id}")
def get_executions_by_project(project_id: int, db: SessionLocal = Depends(get_db)):
    """Lấy executions theo project"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        executions = db.query(Execution).filter(Execution.project_id == project_id).all()
        result = []
        for exe in executions:
            result.append({
                "id": exe.id,
                "task_id": exe.task_id,
                "task_name": exe.task_name,
                "description": exe.description,
                "project_id": exe.project_id,
                "project_name": project.name,
                "jenkins_job": exe.jenkins_job,
                "status": exe.status,
                "created_at": exe.created_at.isoformat() if exe.created_at else None
            })
        return {
            "project": {
                "id": project.id,
                "name": project.name
            },
            "executions": result,
            "count": len(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error getting executions by project: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/projects")
def get_projects(db: SessionLocal = Depends(get_db)):
    """Lấy danh sách projects cho dropdown"""
    try:
        projects = db.query(Project).all()
        result = []
        for proj in projects:
            result.append({
                "id": proj.id,
                "name": proj.name,
                "repo_link": proj.repo_link
            })
        return {"projects": result}
    except Exception as e:
        print(f"[DEBUG] Error getting projects: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/")
def create_execution(execution: ExecutionCreate, db: SessionLocal = Depends(get_db)):
    """Tạo execution task mới"""
    try:
        # Validate required fields
        if not execution.task_name or not execution.task_name.strip():
            raise HTTPException(status_code=400, detail="Task name cannot be empty")
        
        if not execution.jenkins_job or not execution.jenkins_job.strip():
            raise HTTPException(status_code=400, detail="Jenkins job cannot be empty")
        
        # Validate project_id
        if not execution.project_id or execution.project_id <= 0:
            raise HTTPException(status_code=400, detail="Project ID must be a positive integer")
        
        # Kiểm tra project tồn tại
        project = db.query(Project).filter(Project.id == execution.project_id).first()
        if not project:
            log_backend_event("ERROR", f"Project not found: {execution.project_id}", db)
            raise HTTPException(status_code=404, detail=f"Project with ID {execution.project_id} not found")
        
        # Tìm ID nhỏ nhất có sẵn
        next_id = get_next_available_execution_id(db)
        next_task_id = get_next_available_task_id(db)
        
        # Tạo execution mới
        new_execution = Execution(
            id=next_id,  # Sử dụng ID tùy chỉnh
            task_id=next_task_id,  # Tự động tạo task_id
            task_name=execution.task_name.strip(),
            description=execution.description.strip() if execution.description else "",
            jenkins_job=execution.jenkins_job.strip(),
            project_id=execution.project_id,
            email_recipients=execution.email_recipients.strip() if execution.email_recipients else None,
            status='initialized',
            created_at=datetime.utcnow()
        )
        
        db.add(new_execution)
        db.commit()
        db.refresh(new_execution)
        
        log_backend_event("INFO", f"Created execution task: {execution.task_name} (ID: {next_task_id})", db)
        
        return {
            "message": f"Đã tạo task '{execution.task_name}' thành công",
            "execution_id": new_execution.id,
            "task_id": next_task_id,
            "task_name": execution.task_name,
            "description": execution.description,
            "jenkins_job": execution.jenkins_job,
            "project_id": execution.project_id,
            "project_name": project.name,
            "status": "initialized",
            "created_at": new_execution.created_at.isoformat() if new_execution.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error creating execution: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.delete("/{execution_id}")
def delete_execution(execution_id: int, db: SessionLocal = Depends(get_db)):
    """Xóa execution task theo ID và xóa luôn các report liên quan"""
    try:
        from database import Report
        # Tìm execution cần xóa
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        task_name = execution.task_name
        # Xóa các report liên quan
        reports_deleted = db.query(Report).filter(Report.task_id == execution.task_id).delete()
        db.delete(execution)
        db.commit()
        return {
            "message": f"Đã xóa task '{task_name}' thành công và {reports_deleted} report liên quan",
            "execution_id": execution_id,
            "reports_deleted": reports_deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error deleting execution: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.put("/{execution_id}")
def update_execution(execution_id: int, execution: ExecutionUpdate, db: SessionLocal = Depends(get_db)):
    """Cập nhật execution task theo ID"""
    try:
        # Tìm execution cần cập nhật
        existing_execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not existing_execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Validate required fields
        if not execution.task_name or not execution.task_name.strip():
            raise HTTPException(status_code=400, detail="Task name cannot be empty")
        
        if not execution.jenkins_job or not execution.jenkins_job.strip():
            raise HTTPException(status_code=400, detail="Jenkins job cannot be empty")
        
        # Validate project_id
        if not execution.project_id or execution.project_id <= 0:
            raise HTTPException(status_code=400, detail="Project ID must be a positive integer")
        
        # Kiểm tra project tồn tại
        project = db.query(Project).filter(Project.id == execution.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project with ID {execution.project_id} not found")
        
        # Cập nhật thông tin (không cho phép thay đổi task_id)
        # existing_execution.task_id = execution.task_id  # Không thay đổi task_id
        existing_execution.task_name = execution.task_name.strip()
        existing_execution.description = execution.description.strip() if execution.description else ""
        existing_execution.jenkins_job = execution.jenkins_job.strip()
        existing_execution.project_id = execution.project_id
        existing_execution.email_recipients = execution.email_recipients.strip() if execution.email_recipients else None
        
        db.commit()
        db.refresh(existing_execution)
        
        return {
            "message": f"Đã cập nhật task '{execution.task_name}' thành công",
            "execution_id": existing_execution.id,
            "task_id": existing_execution.task_id,  # Giữ nguyên task_id cũ
            "task_name": execution.task_name,
            "description": execution.description,
            "jenkins_job": execution.jenkins_job,
            "project_id": execution.project_id,
            "project_name": project.name,
            "status": existing_execution.status,
            "created_at": existing_execution.created_at.isoformat() if existing_execution.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error updating execution: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/{execution_id}/run")
def run_jenkins_job(execution_id: int, db: SessionLocal = Depends(get_db)):
    """Chạy Jenkins job cho execution task"""
    try:
        # Tìm execution cần chạy
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            log_backend_event("ERROR", f"Execution not found: {execution_id}", db)
            raise HTTPException(status_code=404, detail="Execution not found")
        
        if not execution.jenkins_job:
            log_backend_event("ERROR", f"Execution {execution_id} has no Jenkins job configured", db)
            raise HTTPException(status_code=400, detail="Task không có Jenkins job được cấu hình")
        
        log_backend_event("INFO", f"Starting Jenkins job for execution {execution_id}: {execution.jenkins_job}", db)
        
        # Cấu hình Jenkins từ environment variables
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        
        # Kiểm tra xem Jenkins job có đang chạy không trước khi trigger
        last_build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
        
        try:
            session = requests.Session()
            build_check_response = session.get(last_build_url, timeout=30)
            
            if build_check_response.status_code == 200:
                build_info = build_check_response.json()
                building = build_info.get('building', False)
                
                if building:
                    # Nếu job đang chạy, vẫn cho phép trigger job mới (Jenkins sẽ xử lý queue)
                    print(f"[DEBUG] Jenkins job '{execution.jenkins_job}' đang chạy, nhưng vẫn cho phép trigger job mới")
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Could not check Jenkins job status: {e}")
            # Tiếp tục nếu không thể kiểm tra được
        
        # URL để trigger Jenkins job với parameters
        jenkins_build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/buildWithParameters"
        
        try:
            # Sử dụng session để lấy crumb và trigger job
            session = requests.Session()
            
            # Lấy CSRF crumb từ Jenkins (không cần xác thực vì Jenkins ở chế độ không bảo mật)
            crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
            crumb_response = session.get(crumb_url, timeout=30)
            
            headers = {}
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                print(f"Got crumb: {crumb_data['crumb']}")
            else:
                print(f"Failed to get crumb: {crumb_response.status_code} - {crumb_response.text}")
            
            # Gọi Jenkins API để trigger job với TASK_ID parameter
            data = {
                'TASK_ID': execution.task_id
            }
            
            response = session.post(
                jenkins_build_url,
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 201:
                # Lấy build number từ Jenkins response headers
                build_number = None
                if 'Location' in response.headers:
                    location = response.headers['Location']
                    # Extract build number from location header
                    if '/builds/' in location:
                        build_number = location.split('/builds/')[-1].split('/')[0]
                
                # Cập nhật trạng thái task thành "running"
                execution.status = "running"
                db.commit()
                
                log_backend_event("INFO", f"Jenkins job triggered successfully: {execution.jenkins_job} (Build: {build_number})", db)
                
                return {
                    "message": f"Đã khởi chạy Jenkins job '{execution.jenkins_job}' thành công",
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "status": "running",
                    "jenkins_response": "Job triggered successfully"
                }
            else:
                # Nếu Jenkins trả về lỗi
                execution.status = "failed"
                db.commit()
                
                log_backend_event("ERROR", f"Jenkins job failed: {execution.jenkins_job} - HTTP {response.status_code}: {response.text}", db)
                
                return {
                    "message": f"Lỗi khi chạy Jenkins job '{execution.jenkins_job}'",
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "status": "failed",
                    "jenkins_response": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            # Nếu không kết nối được Jenkins
            execution.status = "failed"
            db.commit()
            
            log_backend_event("ERROR", f"Jenkins connection failed: {execution.jenkins_job} - {str(e)}", db)
            
            return {
                "message": f"Không thể kết nối đến Jenkins server",
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "task_name": execution.task_name,
                "jenkins_job": execution.jenkins_job,
                "status": "failed",
                "jenkins_response": f"Connection error: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error running Jenkins job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.get("/{execution_id}/status")
def check_jenkins_status(execution_id: int, db: SessionLocal = Depends(get_db)):
    """Kiểm tra trạng thái Jenkins job và cập nhật database"""
    try:
        # Tìm execution
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        if not execution.jenkins_job:
            raise HTTPException(status_code=400, detail="Task không có Jenkins job được cấu hình")
        
        # Cấu hình Jenkins từ environment variables
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        
        # Nếu đã có build_number, dùng build_number này để lấy trạng thái build
        # build_number = execution.build_number # Xóa dòng này
        if True: # Luôn dùng lastBuild
            build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
        else:
            build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
        
        try:
            session = requests.Session()
            response = session.get(build_url, timeout=30)
            
            if response.status_code == 200:
                build_info = response.json()
                build_result = build_info.get('result')
                building = build_info.get('building', False)
                # Đơn giản hóa: chỉ dựa vào Jenkins API
                if execution.status == "cancelled":
                    new_status = "cancelled"
                else:
                    if building:
                        new_status = "running"
                    elif build_result == "SUCCESS" or build_result == "FAILURE":
                        new_status = "success"
                    elif build_result == "ABORTED":
                        new_status = "cancelled"
                    else:
                        new_status = "running"
                print(f"[DEBUG] Current status: {execution.status}, New status: {new_status}")
                if execution.status != new_status:
                    execution.status = new_status
                    db.commit()
                    print(f"[DEBUG] Updated execution {execution_id} status from {execution.status} to {new_status}")
                else:
                    print(f"[DEBUG] Status unchanged for execution {execution_id}")
                return {
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "status": new_status,
                    "jenkins_building": building,
                    "jenkins_result": build_result,
                    "build_number": build_info.get('number'),
                    "build_url": build_info.get('url')
                }
            else:
                # Nếu không lấy được thông tin build
                print(f"[DEBUG] Failed to get build info: HTTP {response.status_code}")
                return {
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "status": execution.status,
                    "jenkins_building": False,
                    "jenkins_result": None,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Request exception: {e}")
            return {
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "task_name": execution.task_name,
                "jenkins_job": execution.jenkins_job,
                "status": execution.status,
                "jenkins_building": False,
                "jenkins_result": None,
                "error": f"Connection error: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error checking Jenkins status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.put("/{execution_id}/force-update-status")
def force_update_execution_status(execution_id: int, db: SessionLocal = Depends(get_db)):
    """Force update status cho execution từ Jenkins"""
    try:
        # Tìm execution
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        if not execution.jenkins_job:
            raise HTTPException(status_code=400, detail="Execution không có Jenkins job được cấu hình")
        
        # Cấu hình Jenkins
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        
        # Lấy thông tin build cuối cùng
        last_build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
        
        try:
            session = requests.Session()
            response = session.get(last_build_url, timeout=30)
            
            if response.status_code == 200:
                build_info = response.json()
                build_number = build_info.get('number')
                build_result = build_info.get('result')
                building = build_info.get('building', False)
                
                if building:
                    raise HTTPException(status_code=400, detail="Jenkins job đang chạy")
                
                # Cập nhật status
                if build_result == "SUCCESS" or build_result == "FAILURE":
                    # Coi cả SUCCESS và FAILURE là success (vì FAILURE có thể do testcase failed)
                    execution.status = "success"
                elif build_result == "ABORTED":
                    execution.status = "cancelled"
                else:
                    execution.status = build_result.lower() if build_result else "unknown"
                
                db.commit()
                
                print(f"✅ Force update: Execution {execution.task_id} status = {execution.status}")
                
                return {
                    "message": f"Đã cập nhật status cho execution {execution.task_id}",
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "old_status": "unknown",
                    "new_status": execution.status,
                    "jenkins_result": build_result
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Không thể lấy thông tin build từ Jenkins: {response.text}"
                )
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi kết nối Jenkins: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error force updating execution status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/{execution_id}/results")
def get_jenkins_results(execution_id: int, build_number: int = None, db: SessionLocal = Depends(get_db)):
    """Lấy kết quả và files từ Jenkins job (ưu tiên build_number nếu có)"""
    try:
        # Tìm execution
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not execution.jenkins_job:
            raise HTTPException(status_code=400, detail="Task không có Jenkins job được cấu hình")
        # Nếu không truyền build_number, tự động lấy build_number của report gần nhất thành công/thất bại
        if build_number is None:
            from database import Report
            reports = db.query(Report).filter(Report.task_id == execution.task_id).order_by(Report.created_at.desc()).all()
            report = None
            if reports:
                if reports[0].status in ["cancelled", "aborted"]:
                    for r in reports:
                        if r.status in ["success", "failed", "failure"]:
                            report = r
                            break
                    if not report:
                        report = reports[0]
                else:
                    report = reports[0]
                build_number = report.build_number if report else None
        # Cấu hình Jenkins từ environment variables
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        # Nếu có build_number, lấy đúng build đó, không thì lấy lastBuild
        if build_number:
            build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/{build_number}/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{execution.jenkins_job}/{build_number}/ws"
            console_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/{build_number}/consoleText"
        else:
            build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/ws"
            console_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/consoleText"
        try:
            session = requests.Session()
            response = session.get(build_url, timeout=30)
            if response.status_code == 200:
                build_info = response.json()
                artifacts = build_info.get('artifacts', [])
                console_response = session.get(console_url, timeout=30)
                console_log = console_response.text if console_response.status_code == 200 else ""
                workspace_files = [
                    {"name": "log.html", "url": f"{ws_prefix}/log.html", "type": "file"},
                    {"name": "report.html", "url": f"{ws_prefix}/report.html", "type": "file"},
                    {"name": "output.xml", "url": f"{ws_prefix}/output.xml", "type": "file"}
                ]
                result_files = [
                    {"name": "report.html", "url": f"{ws_prefix}/report.html", "description": "Robot Framework Test Report"},
                    {"name": "log.html", "url": f"{ws_prefix}/log.html", "description": "Robot Framework Test Log"},
                    {"name": "output.xml", "url": f"{ws_prefix}/output.xml", "description": "Robot Framework Test Results XML"}
                ]
                return {
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "build_info": {
                        "number": build_info.get('number'),
                        "result": build_info.get('result'),
                        "duration": build_info.get('duration'),
                        "timestamp": build_info.get('timestamp'),
                        "url": build_info.get('url')
                    },
                    "artifacts": artifacts,
                    "result_files": result_files,
                    "workspace_files": workspace_files[:20],
                    "console_log": console_log[-5000:] if console_log else "",
                    "jenkins_url": JENKINS_URL
                }
            else:
                return {
                    "execution_id": execution.id,
                    "task_id": execution.task_id,
                    "task_name": execution.task_name,
                    "jenkins_job": execution.jenkins_job,
                    "error": f"Không thể lấy thông tin build: HTTP {response.status_code}",
                    "build_info": None,
                    "artifacts": [],
                    "result_files": [],
                    "workspace_files": [],
                    "console_log": ""
                }
        except requests.exceptions.RequestException as e:
            return {
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "task_name": execution.task_name,
                "jenkins_job": execution.jenkins_job,
                "error": f"Lỗi kết nối Jenkins: {str(e)}",
                "build_info": None,
                "artifacts": [],
                "result_files": [],
                "workspace_files": [],
                "console_log": ""
            }
    except Exception as e:
        return {
            "execution_id": execution_id,
            "error": f"Internal server error: {e}"
        }

@router.post("/{execution_id}/stop")
def stop_jenkins_job(execution_id: int, db: SessionLocal = Depends(get_db)):
    """Dừng job Jenkins đang chạy cho execution, giống logic stop_plan"""
    try:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        if not execution.jenkins_job:
            raise HTTPException(status_code=400, detail="Task không có Jenkins job được cấu hình")
        
        # Cấu hình Jenkins
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        try:
            session = requests.Session()
            # Lấy CSRF crumb từ Jenkins
            crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
            crumb_response = session.get(crumb_url, timeout=30)
            headers = {}
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
            # Kiểm tra xem job có đang chạy không
            last_build_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/api/json"
            build_response = session.get(last_build_url, timeout=30)
            if build_response.status_code == 200:
                build_info = build_response.json()
                building = build_info.get('building', False)
                # build_number = build_info.get('number') # Xóa dòng này
                if building:
                    # Dừng job đang chạy
                    stop_url = f"{JENKINS_URL}/job/{execution.jenkins_job}/lastBuild/stop" # Sửa URL để dừng lastBuild
                    stop_response = session.post(stop_url, headers=headers, timeout=30)
            # Cập nhật status execution thành cancelled
            execution.status = 'cancelled'
            db.commit()
            log_backend_event("INFO", f"Stopped Jenkins job for execution: {execution.task_name}", db)
            return {
                "message": f"Đã dừng job '{execution.task_name}' thành công",
                "execution_id": execution_id,
                "task_id": execution.task_id,
                "task_name": execution.task_name,
                "jenkins_job": execution.jenkins_job,
                "status": "cancelled"
            }
        except requests.exceptions.RequestException as e:
            return {"message": f"Không thể kết nối đến Jenkins server", "execution_id": execution_id, "task_id": execution.task_id, "task_name": execution.task_name, "jenkins_job": execution.jenkins_job, "status": execution.status, "error": f"Connection error: {str(e)}"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error stopping execution: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 