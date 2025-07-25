import os
import requests
import xml.etree.ElementTree as ET
from fastapi import APIRouter, HTTPException
from database import get_db, Cicd, Project
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import logging

router = APIRouter()

@router.get("/jenkins-jobs")
def get_jenkins_jobs():
    """Lấy danh sách Jenkins jobs hiện có"""
    try:
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        api_url = f"{JENKINS_URL}/api/json"
        session = requests.Session()
        # Lấy CSRF crumb nếu cần (nếu Jenkins bật bảo mật)
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        headers = {}
        try:
            crumb_response = session.get(crumb_url, timeout=10)
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
        except Exception:
            pass  # Nếu không lấy được crumb thì bỏ qua (Jenkins không bật CSRF)
        response = session.get(api_url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Jenkins API error: {response.text}")
        data = response.json()
        jobs = data.get('jobs', [])
        return {"jobs": [{"name": job["name"], "url": job["url"]} for job in jobs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách Jenkins jobs: {e}")

def get_next_available_cicd_id(db):
    """Tìm ID nhỏ nhất có sẵn để tái sử dụng"""
    try:
        # Lấy tất cả ID hiện có
        result = db.execute(text("SELECT id FROM cicd ORDER BY id"))
        existing_ids = [row[0] for row in result.fetchall()]
        
        if not existing_ids:
            return 1
        
        # Tìm ID nhỏ nhất có sẵn
        for i in range(1, max(existing_ids) + 2):
            if i not in existing_ids:
                return i
        
        return max(existing_ids) + 1
    except Exception as e:
        print(f"Error getting next available cicd ID: {e}")
        # Fallback: sử dụng sequence
        result = db.execute(text("SELECT nextval('cicd_id_seq')"))
        return result.fetchone()[0]

@router.post("/cicd")
def create_cicd(data: dict, db: Session = Depends(get_db)):
    required = ["cicd_name", "cicd_type", "jenkins_job", "project_id"]
    for f in required:
        if f not in data or not data[f]:
            raise HTTPException(status_code=400, detail=f"Missing field: {f}")
    project = db.query(Project).filter(Project.id == data["project_id"]).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Tìm ID nhỏ nhất có sẵn
    next_id = get_next_available_cicd_id(db)
    cicd_id = f"CICD-{next_id:03d}"
    
    new_cicd = Cicd(
        id=next_id,  # Sử dụng ID tùy chỉnh
        cicd_id=cicd_id,  # Lưu cicd_id vào database
        cicd_name=data["cicd_name"].strip(),
        cicd_type=data["cicd_type"].strip(),
        description=data.get("description", "").strip(),
        jenkins_job=data["jenkins_job"].strip(),
        project_id=data["project_id"],
        status="initialized"
    )
    db.add(new_cicd)
    db.commit()
    db.refresh(new_cicd)
    
    return {
        "message": "CI/CD pipeline created successfully",
                    "cicd": {
                "id": new_cicd.id,
                "cicd_id": new_cicd.cicd_id,
                "cicd_name": new_cicd.cicd_name,
            "cicd_type": new_cicd.cicd_type,
            "description": new_cicd.description,
            "jenkins_job": new_cicd.jenkins_job,
            "project_id": new_cicd.project_id,
            "status": new_cicd.status,
            "created_at": new_cicd.created_at.isoformat() if new_cicd.created_at else None
        }
    }

@router.get("/cicd")
def list_cicd(project_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Cicd, Project.name.label('project_name')).join(Project, Cicd.project_id == Project.id)
    # Nếu project_id là None hoặc 0 thì không lọc, trả về tất cả CI/CD task
    if project_id and int(project_id) > 0:
        q = q.filter(Cicd.project_id == project_id)
    results = q.order_by(Cicd.created_at.desc()).all()
    return {"cicd": [
        {
            "id": c.Cicd.id,
            "cicd_id": c.Cicd.cicd_id,
            "cicd_name": c.Cicd.cicd_name,
            "cicd_type": c.Cicd.cicd_type,
            "description": c.Cicd.description,
            "jenkins_job": c.Cicd.jenkins_job,
            "project_id": c.Cicd.project_id,
            "project_name": c.project_name,
            "status": c.Cicd.status,
            "created_at": c.Cicd.created_at.isoformat() if c.Cicd.created_at else None
        } for c in results
    ]}

@router.get("/cicd/{cicd_id}")
def get_cicd(cicd_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết của CI/CD task"""
    try:
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        
        # Lấy thông tin project
        project = db.query(Project).filter(Project.id == cicd_task.project_id).first()
        
        return {
            "cicd": {
                "id": cicd_task.id,
                "cicd_id": cicd_task.cicd_id,
                "cicd_name": cicd_task.cicd_name,
                "cicd_type": cicd_task.cicd_type,
                "description": cicd_task.description,
                "jenkins_job": cicd_task.jenkins_job,
                "project_id": cicd_task.project_id,
                "project_name": project.name if project else None,
                "status": cicd_task.status,
                "created_at": cicd_task.created_at.isoformat() if cicd_task.created_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thông tin CI/CD task: {str(e)}")

@router.put("/cicd/{cicd_id}")
def update_cicd(cicd_id: int, data: dict, db: Session = Depends(get_db)):
    """Cập nhật CI/CD task"""
    try:
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        
        # Kiểm tra các trường bắt buộc
        required_fields = ["cicd_name", "cicd_type", "jenkins_job"]
        for field in required_fields:
            if field not in data or not data[field]:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Lưu Jenkins job cũ để so sánh
        old_jenkins_job = cicd_task.jenkins_job
        
        # Cập nhật thông tin
        cicd_task.cicd_name = data["cicd_name"].strip()
        cicd_task.cicd_type = data["cicd_type"].strip()
        cicd_task.description = data.get("description", "").strip()
        cicd_task.jenkins_job = data["jenkins_job"].strip()
        
        # Nếu thay đổi Jenkins job, reset status về initialized
        if old_jenkins_job != cicd_task.jenkins_job:
            cicd_task.status = "initialized"
        
        db.commit()
        db.refresh(cicd_task)
        
        return {
            "message": f"Đã cập nhật CI/CD task '{cicd_task.cicd_name}'",
            "cicd": {
                "id": cicd_task.id,
                "cicd_id": f"CICD-{cicd_task.id:03d}",
                "cicd_name": cicd_task.cicd_name,
                "cicd_type": cicd_task.cicd_type,
                "description": cicd_task.description,
                "jenkins_job": cicd_task.jenkins_job,
                "project_id": cicd_task.project_id,
                "status": cicd_task.status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật CI/CD task: {str(e)}")

@router.delete("/cicd/{cicd_id}")
def delete_cicd(cicd_id: int, db: Session = Depends(get_db)):
    """Xóa task CI/CD - disable GitHub webhook triggers trước khi xóa"""
    try:
        # Tìm task CI/CD
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        
        # Lưu thông tin để trả về
        task_info = {
            "id": cicd_task.id,
            "cicd_id": f"CICD-{cicd_task.id:03d}",
            "cicd_name": cicd_task.cicd_name,
            "jenkins_job": cicd_task.jenkins_job
        }
        
        # Disable GitHub webhook triggers trước khi xóa (nếu có Jenkins job)
        jenkins_result = None
        if cicd_task.jenkins_job:
            try:
                jenkins_result = disable_jenkins_webhook_trigger(cicd_task.jenkins_job)
            except Exception as jenkins_error:
                # Log lỗi nhưng vẫn tiếp tục xóa task
                print(f"Warning: Không thể disable Jenkins triggers cho job '{cicd_task.jenkins_job}': {jenkins_error}")
                jenkins_result = {
                    "message": f"Không thể disable Jenkins triggers: {str(jenkins_error)}",
                    "job_name": cicd_task.jenkins_job
                }
        
        # Xóa task khỏi database
        db.delete(cicd_task)
        db.commit()
        
        # Tạo response message
        message = f"Đã xóa thành công task CI/CD '{task_info['cicd_name']}' (ID: {task_info['cicd_id']})"
        if jenkins_result:
            message += f"\n\nJenkins: {jenkins_result['message']}"
        
        return {
            "message": message,
            "deleted_task": task_info,
            "jenkins_action": "disabled_github_hook_trigger" if jenkins_result else "no_jenkins_job",
            "jenkins_result": jenkins_result
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi xóa task CI/CD: {str(e)}")

@router.post("/cicd/{cicd_id}/run")
def run_cicd_task(cicd_id: int, db: Session = Depends(get_db)):
    """Chạy task CI/CD - tự động cấu hình Jenkins trigger và webhook"""
    try:
        # Lấy thông tin CI/CD task
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        
        # Chỉ xử lý cho loại task "Test"
        if cicd_task.cicd_type != "Test":
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tự động cấu hình cho loại task 'Test'")
        
        # Lấy thông tin project để có repo URL
        project = db.query(Project).filter(Project.id == cicd_task.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Cập nhật status
        cicd_task.status = "configuring"
        db.commit()
        
        result = {
            "message": "Bắt đầu cấu hình tự động",
            "steps": []
        }
        
        # Bước 1: Cấu hình Jenkins job trigger
        try:
            jenkins_result = configure_jenkins_webhook_trigger(cicd_task.jenkins_job)
            result["steps"].append({
                "step": "Jenkins Configuration",
                "status": "success",
                "message": jenkins_result["message"]
            })
        except Exception as e:
            result["steps"].append({
                "step": "Jenkins Configuration", 
                "status": "error",
                "message": f"Lỗi cấu hình Jenkins: {str(e)}"
            })
            cicd_task.status = "error"
            db.commit()
            return result
        
        # Bước 2: Thêm webhook vào Git repo (nếu có repo URL)
        if project.repo_link:
            try:
                logging.warning(f"[Webhook] Đang thêm webhook cho repo: {project.repo_link}, job: {cicd_task.jenkins_job}")
                webhook_result = add_github_webhook_public(project.repo_link, cicd_task.jenkins_job)
                logging.warning(f"[Webhook] Kết quả: {webhook_result}")
                result["steps"].append({
                    "step": "GitHub Webhook",
                    "status": "success", 
                    "message": webhook_result["message"]
                })
            except Exception as e:
                logging.error(f"[Webhook] Lỗi khi thêm webhook: {e}")
                result["steps"].append({
                    "step": "GitHub Webhook",
                    "status": "warning",
                    "message": f"Không thể thêm webhook tự động: {str(e)}. Vui lòng thêm thủ công qua GitHub UI."
                })
        else:
            logging.warning(f"[Webhook] Bỏ qua thêm webhook - project chưa có repo URL")
            result["steps"].append({
                "step": "GitHub Webhook",
                "status": "info",
                "message": "Bỏ qua thêm webhook - project chưa có repo URL"
            })
        
        # Cập nhật status thành công
        cicd_task.status = "active"
        db.commit()
        
        result["message"] = "Cấu hình tự động hoàn tất"
        return result
        
    except Exception as e:
        logging.error(f"[Webhook] Lỗi tổng quát khi chạy task CI/CD: {e}")
        # Cập nhật status lỗi
        if cicd_task:
            cicd_task.status = "error"
            db.commit()
        raise HTTPException(status_code=500, detail=f"Lỗi chạy task CI/CD: {str(e)}")

@router.post("/cicd/{cicd_id}/stop")
def stop_cicd_task(cicd_id: int, db: Session = Depends(get_db)):
    """Dừng CI/CD task - disable GitHub hook trigger"""
    try:
        # Tìm CI/CD task
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        
        if not cicd_task.jenkins_job:
            raise HTTPException(status_code=400, detail="CI/CD task không có Jenkins job được cấu hình")
        
        # Disable GitHub hook trigger
        try:
            result = disable_jenkins_webhook_trigger(cicd_task.jenkins_job)
            
            # Cập nhật status thành deactive
            cicd_task.status = "deactive"
            db.commit()
            
            return {
                "message": f"Đã dừng CI/CD task '{cicd_task.cicd_name}'",
                "cicd_id": cicd_task.id,
                "cicd_name": cicd_task.cicd_name,
                "jenkins_job": cicd_task.jenkins_job,
                "action": "disabled_github_hook_trigger",
                "status": "deactive"
            }
            
        except Exception as jenkins_error:
            return {
                "message": f"Lỗi khi dừng Jenkins job: {str(jenkins_error)}",
                "cicd_id": cicd_task.id,
                "cicd_name": cicd_task.cicd_name,
                "jenkins_job": cicd_task.jenkins_job,
                "action": "failed_to_disable_trigger",
                "status": cicd_task.status,
                "error": str(jenkins_error)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi dừng task CI/CD: {str(e)}")

@router.get("/cicd/{cicd_id}/results")
def get_cicd_results(cicd_id: int, build_number: int = None, db: Session = Depends(get_db)):
    """Lấy kết quả test của CI/CD task"""
    try:
        from database import Report
        # Lấy thông tin CI/CD task
        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
        if not cicd_task:
            raise HTTPException(status_code=404, detail="CI/CD task not found")
        # Lấy project name
        project = db.query(Project).filter(Project.id == cicd_task.project_id).first()
        project_name = project.name if project else "Unknown"
        # Nếu không truyền build_number, tự động lấy build_number của report gần nhất thành công/thất bại
        if build_number is None:
            reports = db.query(Report).filter(Report.task_id == cicd_task.cicd_id).order_by(Report.created_at.desc()).all()
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
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        if build_number:
            build_url = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/{build_number}/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/{build_number}/ws"
            console_url = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/{build_number}/consoleText"
        else:
            build_url = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/lastBuild/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/lastBuild/ws"
            console_url = f"{JENKINS_URL}/job/{cicd_task.jenkins_job}/lastBuild/consoleText"
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
                    "cicd_task": {
                        "id": cicd_task.id,
                        "cicd_name": cicd_task.cicd_name,
                        "cicd_type": cicd_task.cicd_type,
                        "project_name": project_name,
                        "status": cicd_task.status,
                        "jenkins_job": cicd_task.jenkins_job,
                        "created_at": cicd_task.created_at.isoformat() if cicd_task.created_at else None
                    },
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
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Không thể lấy thông tin build từ Jenkins: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi kết nối Jenkins: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

def disable_jenkins_webhook_trigger(job_name: str):
    """Disable GitHub hook trigger for GITScm polling"""
    try:
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        JENKINS_USER = os.getenv("JENKINS_USER", "admin")
        JENKINS_TOKEN = os.getenv("JENKINS_TOKEN", "")
        
        # Lấy cấu hình hiện tại của job
        config_url = f"{JENKINS_URL}/job/{job_name}/config.xml"
        session = requests.Session()
        
        # Chỉ dùng auth nếu có token
        if JENKINS_TOKEN:
            session.auth = (JENKINS_USER, JENKINS_TOKEN)
        
        # Lấy CSRF crumb
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        headers = {}
        try:
            crumb_response = session.get(crumb_url, timeout=10)
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
        except Exception:
            pass
        
        # Lấy config XML hiện tại
        response = session.get(config_url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Không thể lấy cấu hình job: {response.status_code}")
        
        # Parse XML và disable GitHub hook trigger cho Pipeline job
        root = ET.fromstring(response.text)
        
        # Tìm PipelineTriggersJobProperty trong properties
        properties = root.find('.//properties')
        if properties is None:
            return {
                "message": f"Job '{job_name}' không có triggers được cấu hình",
                "job_name": job_name
            }
        
        # Tìm PipelineTriggersJobProperty
        pipeline_triggers_prop = properties.find('.//org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty')
        if pipeline_triggers_prop is None:
            return {
                "message": f"Job '{job_name}' không có Pipeline triggers được cấu hình",
                "job_name": job_name
            }
        
        # Tìm phần triggers trong PipelineTriggersJobProperty
        triggers = pipeline_triggers_prop.find('.//triggers')
        if triggers is None:
            return {
                "message": f"Job '{job_name}' không có triggers được cấu hình",
                "job_name": job_name
            }
        
        # Xóa tất cả triggers
        for trigger in triggers.findall('*'):
            triggers.remove(trigger)
        
        # Cập nhật config
        updated_config = ET.tostring(root, encoding='unicode')
        
        # Gửi config mới về Jenkins
        update_response = session.post(
            config_url,
            data=updated_config,
            headers={**headers, 'Content-Type': 'application/xml'},
            timeout=15
        )
        
        if update_response.status_code != 200:
            raise Exception(f"Không thể cập nhật cấu hình job: {update_response.status_code}")
        
        return {
            "message": f"Đã disable GitHub hook trigger for GITScm polling cho Pipeline job '{job_name}'",
            "job_name": job_name
        }
        
    except Exception as e:
        raise Exception(f"Lỗi disable Jenkins trigger: {str(e)}")

def configure_jenkins_webhook_trigger(job_name: str):
    """Cấu hình Jenkins Pipeline job để bật GitHub hook trigger for GITScm polling"""
    try:
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        JENKINS_USER = os.getenv("JENKINS_USER", "admin")
        JENKINS_TOKEN = os.getenv("JENKINS_TOKEN", "")
        
        # Lấy cấu hình hiện tại của job
        config_url = f"{JENKINS_URL}/job/{job_name}/config.xml"
        session = requests.Session()
        
        # Chỉ dùng auth nếu có token
        if JENKINS_TOKEN:
            session.auth = (JENKINS_USER, JENKINS_TOKEN)
        
        # Lấy CSRF crumb
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        headers = {}
        try:
            crumb_response = session.get(crumb_url, timeout=10)
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
        except Exception:
            pass
        
        # Lấy config XML hiện tại
        response = session.get(config_url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Không thể lấy cấu hình job: {response.status_code}")
        
        # Parse XML và thêm GitHub hook trigger cho Pipeline job
        root = ET.fromstring(response.text)
        
        # Tìm PipelineTriggersJobProperty trong properties
        properties = root.find('.//properties')
        if properties is None:
            properties = ET.SubElement(root, 'properties')
        
        # Tìm hoặc tạo PipelineTriggersJobProperty
        pipeline_triggers_prop = properties.find('.//org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty')
        if pipeline_triggers_prop is None:
            pipeline_triggers_prop = ET.SubElement(properties, 'org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty')
        
        # Tìm hoặc tạo phần triggers trong PipelineTriggersJobProperty
        triggers = pipeline_triggers_prop.find('.//triggers')
        if triggers is None:
            triggers = ET.SubElement(pipeline_triggers_prop, 'triggers')
        
        # Xóa tất cả triggers cũ để tránh xung đột
        for old_trigger in triggers.findall('*'):
            triggers.remove(old_trigger)
        
        # Thêm GitHub hook trigger for GITScm polling
        # Đây chính là trigger đúng từ Jenkins UI
        github_trigger = ET.SubElement(triggers, 'com.cloudbees.jenkins.GitHubPushTrigger')
        # Thêm plugin attribute và empty spec như Jenkins UI
        github_trigger.set('plugin', 'github@1.43.0')
        ET.SubElement(github_trigger, 'spec').text = ''
        
        # Cập nhật config
        updated_config = ET.tostring(root, encoding='unicode')
        
        # Gửi config mới về Jenkins
        update_response = session.post(
            config_url,
            data=updated_config,
            headers={**headers, 'Content-Type': 'application/xml'},
            timeout=15
        )
        
        if update_response.status_code != 200:
            raise Exception(f"Không thể cập nhật cấu hình job: {update_response.status_code}")
        
        return {
            "message": f"Đã bật GitHub hook trigger for GITScm polling cho Pipeline job '{job_name}'",
            "job_name": job_name
        }
        
    except Exception as e:
        raise Exception(f"Lỗi cấu hình Jenkins: {str(e)}")

def add_github_webhook_public(repo_url: str, job_name: str):
    """Thêm webhook vào GitHub repository với token"""
    try:
        ngrok_url = os.getenv("NGROK_URL")
        logging.warning(f"[Webhook] NGROK_URL đang dùng: {ngrok_url}")
        logging.warning(f"[Webhook] repo_url: {repo_url}, job_name: {job_name}")
        # Parse repo URL để lấy owner và repo name
        # Ví dụ: https://github.com/username/repo.git -> username/repo
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        if 'github.com' in repo_url:
            parts = repo_url.split('github.com/')
            if len(parts) != 2:
                raise Exception("URL repository không hợp lệ")
            repo_path = parts[1]
        else:
            raise Exception("Chỉ hỗ trợ GitHub repositories")
        
        # Sử dụng NGROK_URL từ environment variable
        # ngrok_url = os.getenv("NGROK_URL")
        # if not ngrok_url:
        #     raise Exception("NGROK_URL environment variable chưa được set. Vui lòng set NGROK_URL trong docker-compose.yml")
        
        webhook_url = f"{ngrok_url}/github-webhook/"
        
        # Tạo webhook payload
        webhook_data = {
            "name": "web",
            "active": True,
            "events": ["push"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "insecure_ssl": "0"
            }
        }
        
        # GitHub token
        github_token = "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"
        
        # Gọi GitHub API để tạo webhook với token
        github_api_url = f"https://api.github.com/repos/{repo_path}/hooks"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "Authorization": f"token {github_token}"
        }
        
        # Lấy danh sách webhook hiện có
        list_response = requests.get(github_api_url, headers=headers, timeout=15)
        if list_response.status_code == 200:
            existing_hooks = list_response.json()
            for hook in existing_hooks:
                url = hook.get('config', {}).get('url', '')
                # Nếu là webhook ngrok cũ (khác ngrok_url hiện tại), xóa đi
                if 'ngrok-free.app' in url and not url.startswith(ngrok_url):
                    hook_id = hook['id']
                    del_url = f"{github_api_url}/{hook_id}"
                    del_response = requests.delete(del_url, headers=headers, timeout=15)
                    logging.warning(f"[Webhook] Đã xóa webhook cũ: {url}, status: {del_response.status_code}")
        response = requests.post(
            github_api_url,
            json=webhook_data,
            headers=headers,
            timeout=15
        )
        logging.warning(f"[Webhook] GitHub API response: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201]:
            return {
                "message": f"Đã thêm webhook thành công cho repository {repo_path}",
                "webhook_url": webhook_url
            }
        elif response.status_code == 401:
            raise Exception("GitHub token không hợp lệ hoặc đã hết hạn.")
        elif response.status_code == 403:
            raise Exception("Không có quyền thêm webhook. Token có thể không có quyền admin.")
        elif response.status_code == 404:
            raise Exception("Repository không tồn tại hoặc không thể truy cập.")
        elif response.status_code == 422:
            # Webhook đã tồn tại, cập nhật webhook hiện có
            try:
                # Lấy danh sách webhooks hiện có
                list_response = requests.get(
                    github_api_url,
                    headers=headers,
                    timeout=15
                )
                
                if list_response.status_code == 200:
                    existing_hooks = list_response.json()
                    if existing_hooks:
                        # Cập nhật webhook đầu tiên
                        hook_id = existing_hooks[0]['id']
                        update_url = f"{github_api_url}/{hook_id}"
                        
                        update_response = requests.patch(
                            update_url,
                            json=webhook_data,
                            headers=headers,
                            timeout=15
                        )
                        
                        if update_response.status_code in [200, 201]:
                            return {
                                "message": f"Đã cập nhật webhook thành công cho repository {repo_path}",
                                "webhook_url": webhook_url
                            }
                        else:
                            raise Exception(f"Không thể cập nhật webhook: {update_response.status_code}")
                    else:
                        return {
                            "message": f"Webhook đã tồn tại cho repository {repo_path}",
                            "webhook_url": webhook_url
                        }
                else:
                    return {
                        "message": f"Webhook đã tồn tại cho repository {repo_path}",
                        "webhook_url": webhook_url
                    }
            except Exception as update_error:
                return {
                    "message": f"Webhook đã tồn tại cho repository {repo_path}",
                    "webhook_url": webhook_url
                }
        else:
            error_msg = response.json().get('message', 'Unknown error') if response.text else 'Unknown error'
            raise Exception(f"GitHub API error: {response.status_code} - {error_msg}")
            
    except Exception as e:
        logging.error(f"[Webhook] Lỗi thêm webhook GitHub: {str(e)}")
        raise Exception(f"Lỗi thêm webhook GitHub: {str(e)}")
