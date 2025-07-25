import requests
import os
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Plan, Project
from typing import List, Optional
from datetime import datetime
import json
import re

router = APIRouter()
 
@router.get("/")
def get_plans(db: Session = Depends(get_db)):
    """Get all plans"""
    try:
        plans = db.query(Plan).all()
        return {
            "plans": [
                {
                    "id": plan.id,
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "description": plan.description,
                    "project_id": plan.project_id,
                    "project_name": plan.project.name if plan.project else None,
                    "jenkins_job": plan.jenkins_job,
                    "schedule_time": plan.schedule_time,
                    "status": plan.status,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None
                }
                for plan in plans
            ],
            "count": len(plans)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/projects")
def get_projects_for_plans(db: Session = Depends(get_db)):
    """Get all projects for plans dropdown"""
    try:
        projects = db.query(Project).all()
        return {
            "projects": [
                {
                    "id": project.id,
                    "name": project.name
                }
                for project in projects
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/project/{project_id}")
def get_plans_by_project(project_id: int, db: Session = Depends(get_db)):
    """Get plans by project ID"""
    try:
        plans = db.query(Plan).filter(Plan.project_id == project_id).all()
        return {
            "plans": [
                {
                    "id": plan.id,
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "description": plan.description,
                    "project_id": plan.project_id,
                    "project_name": plan.project.name if plan.project else None,
                    "jenkins_job": plan.jenkins_job,
                    "schedule_time": plan.schedule_time,
                    "status": plan.status,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None
                }
                for plan in plans
            ],
            "count": len(plans)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/")
def create_plan(plan_data: dict, db: Session = Depends(get_db)):
    """Create a new plan"""
    try:
        # Validate required fields (except plan_id since it will be auto-generated)
        required_fields = ["plan_name", "jenkins_job", "schedule_time", "project_id"]
        for field in required_fields:
            if field not in plan_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
            if not plan_data[field] or (isinstance(plan_data[field], str) and not plan_data[field].strip()):
                raise HTTPException(status_code=400, detail=f"Field '{field}' cannot be empty")
        
        # Validate project_id is a valid integer
        try:
            project_id = int(plan_data["project_id"])
            if project_id <= 0:
                raise HTTPException(status_code=400, detail="Project ID must be a positive integer")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Project ID must be a valid integer")
        
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project with ID {project_id} not found")
        
        # Validate cron schedule format (basic validation)
        cron_schedule = plan_data["schedule_time"]
        if not cron_schedule or len(cron_schedule.split()) != 5:
            raise HTTPException(status_code=400, detail="Invalid cron schedule format. Expected: 'minute hour day month weekday'")
        
        # Find the smallest available ID
        existing_ids = [plan.id for plan in db.query(Plan.id).all()]
        if existing_ids:
            # Find the smallest missing ID
            existing_ids.sort()
            next_id = 1
            for existing_id in existing_ids:
                if existing_id == next_id:
                    next_id += 1
                else:
                    break
        else:
            next_id = 1
        
        # Create new plan with auto-generated ID
        new_plan = Plan(
            id=next_id,
            plan_id=plan_data.get("plan_id", f"PLAN-{next_id:03d}"),  # Auto-generate plan_id if not provided
            plan_name=plan_data["plan_name"].strip(),
            description=plan_data.get("description", "").strip(),
            project_id=project_id,
            jenkins_job=plan_data["jenkins_job"].strip(),
            schedule_time=cron_schedule,
            status="initialized"
        )
        
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        
        # Don't automatically update Jenkins config - wait for user to press "Run" button
        print(f"[DEBUG] Plan '{new_plan.plan_name}' created successfully, waiting for manual Run")
        
        return {
            "message": "Plan created successfully",
            "plan_id_db": new_plan.id,
            "plan_id": new_plan.plan_id,
            "plan_name": new_plan.plan_name,
            "description": new_plan.description,
            "project_id": new_plan.project_id,
            "project_name": project.name,
            "jenkins_job": new_plan.jenkins_job,
            "schedule_time": new_plan.schedule_time,
            "status": new_plan.status,
            "created_at": new_plan.created_at.isoformat() if new_plan.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{plan_id}")
def update_plan(plan_id: int, plan_data: dict, db: Session = Depends(get_db)):
    """Update an existing plan"""
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Check if project exists
        if "project_id" in plan_data:
            try:
                project_id = int(plan_data["project_id"])
                if project_id <= 0:
                    raise HTTPException(status_code=400, detail="Project ID must be a positive integer")
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise HTTPException(status_code=404, detail=f"Project with ID {project_id} not found")
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Project ID must be a valid integer")
        
        # Update fields (plan_id cannot be changed)
        if "plan_name" in plan_data:
            plan_name = plan_data["plan_name"].strip() if plan_data["plan_name"] else ""
            if not plan_name:
                raise HTTPException(status_code=400, detail="Plan name cannot be empty")
            plan.plan_name = plan_name
        if "description" in plan_data:
            plan.description = plan_data["description"].strip() if plan_data["description"] else ""
        if "project_id" in plan_data:
            plan.project_id = project_id
        if "jenkins_job" in plan_data:
            jenkins_job = plan_data["jenkins_job"].strip() if plan_data["jenkins_job"] else ""
            if not jenkins_job:
                raise HTTPException(status_code=400, detail="Jenkins job cannot be empty")
            plan.jenkins_job = jenkins_job
        if "schedule_time" in plan_data:
            cron_schedule = plan_data["schedule_time"]
            if not cron_schedule or len(cron_schedule.split()) != 5:
                raise HTTPException(status_code=400, detail="Invalid cron schedule format. Expected: 'minute hour day month weekday'")
            plan.schedule_time = cron_schedule
        
        db.commit()
        db.refresh(plan)
        
        # Get updated project name
        project = db.query(Project).filter(Project.id == plan.project_id).first()
        
        return {
            "message": "Plan updated successfully",
            "plan_id_db": plan.id,
            "plan_id": plan.plan_id,
            "plan_name": plan.plan_name,
            "description": plan.description,
            "project_id": plan.project_id,
            "project_name": project.name if project else None,
            "jenkins_job": plan.jenkins_job,
            "schedule_time": plan.schedule_time,
            "status": plan.status,
            "created_at": plan.created_at.isoformat() if plan.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    """Delete a plan và xóa luôn các report liên quan"""
    try:
        from database import Report
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        plan_name = plan.plan_name
        jenkins_job = plan.jenkins_job
        # Xóa các report liên quan
        reports_deleted = db.query(Report).filter(Report.task_id == plan.plan_id).delete()
        
        # Nếu plan có Jenkins job, xóa cron schedule
        if jenkins_job:
            try:
                # Jenkins configuration
                JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
                
                session = requests.Session()
                
                # Lấy CSRF crumb từ Jenkins
                crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
                crumb_response = session.get(crumb_url, timeout=30)
                
                headers = {}
                if crumb_response.status_code == 200:
                    crumb_data = crumb_response.json()
                    headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                    print(f"Got crumb: {crumb_data['crumb']}")
                
                # Kiểm tra xem job có tồn tại không
                job_url = f"{JENKINS_URL}/job/{jenkins_job}/api/json"
                job_response = session.get(job_url, headers=headers, timeout=30)
                
                if job_response.status_code == 200:
                    # Job tồn tại, xóa cron schedule
                    config_url = f"{JENKINS_URL}/job/{jenkins_job}/config.xml"
                    config_response = session.get(config_url, headers=headers, timeout=30)
                    
                    if config_response.status_code == 200:
                        current_config = config_response.text
                        
                        # Xóa cron schedule (đặt spec thành rỗng)
                        
                        if 'flow-definition' in current_config:  # Pipeline job
                            # Xóa tất cả spec tags (cả có nội dung và rỗng)
                            updated_config = re.sub(r'<spec>.*?</spec>', '', current_config)
                            updated_config = re.sub(r'<spec/>', '', updated_config)
                            # Xóa các dòng trống thừa
                            updated_config = re.sub(r'\n\s*\n\s*\n', '\n\n', updated_config)
                            print(f"[DEBUG] Removed all spec tags from PipelineTriggersJobProperty for job: {jenkins_job}")
                        else:
                            # Freestyle job - cập nhật cron schedule thành rỗng
                            spec_pattern = r'(<spec>).*?(</spec>)'
                            if re.search(spec_pattern, current_config):
                                updated_config = re.sub(spec_pattern, r'\1\2', current_config)
                                print(f"[DEBUG] Updated cron schedule to empty in Freestyle job: {jenkins_job}")
                            else:
                                updated_config = current_config
                                print(f"[DEBUG] No cron schedule found in Freestyle job: {jenkins_job}")
                        
                        # Gửi config đã cập nhật về Jenkins
                        update_response = session.post(config_url, headers=headers, data=updated_config, timeout=30)
                        
                        if update_response.status_code == 200:
                            print(f"[DEBUG] Successfully removed cron schedule from Jenkins job: {jenkins_job}")
                            # Xóa plan khỏi database sau khi xóa cron schedule thành công
                            db.delete(plan)
                            db.commit()
                            
                            return {
                                "message": f"Đã xóa plan '{plan_name}' thành công",
                                "plan_id": plan_id,
                                "plan_name": plan_name,
                                "jenkins_job": jenkins_job,
                                "action": "plan_deleted",
                                "cron_removed": True,
                                "reports_deleted": reports_deleted
                            }
                        else:
                            print(f"[DEBUG] Failed to remove cron schedule from Jenkins job: {jenkins_job} - HTTP {update_response.status_code}")
                            # Vẫn xóa plan khỏi database ngay cả khi không thể xóa cron schedule
                            db.delete(plan)
                            db.commit()
                            
                            return {
                                "message": f"Đã xóa plan '{plan_name}' (cron schedule có thể chưa được xóa)",
                                "plan_id": plan_id,
                                "plan_name": plan_name,
                                "jenkins_job": jenkins_job,
                                "action": "plan_deleted_with_cron_error",
                                "cron_removed": False,
                                "error": f"HTTP {update_response.status_code}: {update_response.text}",
                                "reports_deleted": reports_deleted
                            }
                    else:
                        print(f"[DEBUG] Failed to get config from Jenkins job: {jenkins_job} - HTTP {config_response.status_code}")
                        # Vẫn xóa plan khỏi database ngay cả khi không thể lấy config
                        db.delete(plan)
                        db.commit()
                        
                        return {
                            "message": f"Đã xóa plan '{plan_name}' (không thể lấy Jenkins config)",
                            "plan_id": plan_id,
                            "plan_name": plan_name,
                            "jenkins_job": jenkins_job,
                            "action": "plan_deleted_with_config_error",
                            "cron_removed": False,
                            "error": f"HTTP {config_response.status_code}: {config_response.text}",
                            "reports_deleted": reports_deleted
                        }
                else:
                    print(f"[DEBUG] Jenkins job not found: {jenkins_job}")
                    # Vẫn xóa plan khỏi database ngay cả khi Jenkins job không tồn tại
                    db.delete(plan)
                    db.commit()
                    
                    return {
                        "message": f"Đã xóa plan '{plan_name}' (Jenkins job không tồn tại)",
                        "plan_id": plan_id,
                        "plan_name": plan_name,
                        "jenkins_job": jenkins_job,
                        "action": "plan_deleted_job_not_found",
                        "cron_removed": False,
                        "error": "Job không tồn tại trong Jenkins",
                        "reports_deleted": reports_deleted
                    }
                    
            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Connection error when removing cron schedule from Jenkins job {jenkins_job}: {e}")
                # Vẫn xóa plan khỏi database ngay cả khi không thể kết nối Jenkins
                db.delete(plan)
                db.commit()
                
                return {
                    "message": f"Đã xóa plan '{plan_name}' (không thể kết nối Jenkins)",
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "jenkins_job": jenkins_job,
                    "action": "plan_deleted_connection_error",
                    "cron_removed": False,
                    "error": f"Connection error: {str(e)}",
                    "reports_deleted": reports_deleted
                }
            except Exception as e:
                print(f"[DEBUG] Error removing cron schedule from Jenkins job {jenkins_job}: {e}")
                # Vẫn xóa plan khỏi database ngay cả khi có lỗi
                db.delete(plan)
                db.commit()
                
                return {
                    "message": f"Đã xóa plan '{plan_name}' (có lỗi khi xóa cron schedule)",
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "jenkins_job": jenkins_job,
                    "action": "plan_deleted_with_error",
                    "cron_removed": False,
                    "error": f"Error: {str(e)}",
                    "reports_deleted": reports_deleted
                }
        else:
            # Plan không có Jenkins job, xóa khỏi database
            db.delete(plan)
            db.commit()
            
            return {
                "message": f"Đã xóa plan '{plan_name}' (không có Jenkins job)",
                "plan_id": plan_id,
                "plan_name": plan_name,
                "jenkins_job": None,
                "action": "plan_deleted_no_jenkins_job",
                "cron_removed": False,
                "reports_deleted": reports_deleted
            }
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def ensure_timer_trigger(xml, cron_schedule):
    import re
    trigger_block = f'''<org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>\n  <triggers>\n    <hudson.triggers.TimerTrigger><spec>{cron_schedule}</spec></hudson.triggers.TimerTrigger>\n  </triggers>\n</org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>\n'''
    # Xóa tất cả block PipelineTriggersJobProperty (dù nằm đâu)
    xml = re.sub(r'<org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>[\s\S]*?</org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>', '', xml)
    # Đảm bảo chỉ còn một <properties>...</properties> hoặc thay thế <properties/> nếu có
    if '<properties/>' in xml:
        xml = xml.replace('<properties/>', f'<properties>\n{trigger_block}</properties>')
    elif re.search(r'<properties>.*?</properties>', xml, re.DOTALL):
        # Xóa các dòng trống dư thừa trong <properties>
        xml = re.sub(r'<properties>\s*</properties>', '<properties></properties>', xml)
        # Chèn block vào trong <properties>
        xml = re.sub(r'(<properties>)(.*?)(</properties>)', lambda m: f"<properties>\n{trigger_block}{m.group(2).strip()}</properties>", xml, flags=re.DOTALL)
    else:
        # Nếu chưa có <properties>, thêm mới
        xml = re.sub(r'(</flow-definition>)', f'<properties>\n{trigger_block}</properties>\n\\1', xml)
    # Đảm bảo không còn block PipelineTriggersJobProperty dư thừa ngoài <properties>
    xml = re.sub(r'(<\/properties>)(\s*<org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>[\s\S]*?</org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>)', r'\1', xml)
    return xml

# Hàm dùng cho nút Dừng: truyền cron schedule rỗng

def remove_timer_trigger(xml):
    # Nếu có block TimerTrigger
    if '<hudson.triggers.TimerTrigger>' in xml:
        # Nếu có <spec>, xóa <spec> đi
        xml = re.sub(r'<hudson.triggers.TimerTrigger>\s*<spec>.*?</spec>\s*</hudson.triggers.TimerTrigger>', '', xml, flags=re.DOTALL)
        # Nếu còn block TimerTrigger rỗng, xóa luôn
        xml = re.sub(r'<hudson.triggers.TimerTrigger>\s*</hudson.triggers.TimerTrigger>', '', xml, flags=re.DOTALL)
    return xml

@router.post("/{plan_id}/run")
def run_plan(plan_id: int, db: Session = Depends(get_db)):
    """Send cron schedule parameter to Jenkins job"""
    try:
        print(f"[DEBUG] Starting run_plan for plan_id: {plan_id}")
        
        # Find the plan
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        if not plan.jenkins_job:
            raise HTTPException(status_code=400, detail="Plan không có Jenkins job được cấu hình")
        
        print(f"[DEBUG] Plan found: {plan.plan_name}, Jenkins job: {plan.jenkins_job}, Schedule: {plan.schedule_time}")
        
        # Jenkins configuration
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        
        # URL to update Jenkins job configuration
        jenkins_config_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/config.xml"
        
        try:
            session = requests.Session()
            
            # Get CSRF crumb from Jenkins
            crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
            crumb_response = session.get(crumb_url, timeout=30)
            
            headers = {}
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                print(f"Got crumb: {crumb_data['crumb']}")
            else:
                print(f"Failed to get crumb: {crumb_response.status_code} - {crumb_response.text}")
            
            # Get current job configuration
            config_response = session.get(jenkins_config_url, headers=headers, timeout=30)
            
            if config_response.status_code == 200:
                current_config = config_response.text
                print(f"[DEBUG] Current Jenkins config for '{plan.jenkins_job}': {current_config[:200]}...")
                
                # For Pipeline jobs, we need to add cron trigger to the config.xml
                # Check if it's a pipeline job
                if 'flow-definition' in current_config:
                    print(f"[DEBUG] This is a Pipeline job, ensuring TimerTrigger exists or is updated")
                    updated_config = ensure_timer_trigger(current_config, plan.schedule_time)
                    
                    # Add webhook URL for plan report with task_type and task_id
                    webhook_url = f"http://backend:8000/api/reports/jenkins/webhook"
                    
                    # Add post-build action to call webhook with task_type and task_id
                    # This is a simplified approach - in production you'd need proper XML manipulation
                    if '<publishers>' not in updated_config:
                        # Add publishers section if not exists
                        publishers_pattern = r'(<disabled>false</disabled>)'
                        publishers_section = f'''<disabled>false</disabled>
  <publishers>
    <hudson.plugins.http_request.HttpRequestPublisher plugin="http_request@1.16">
      <configName></configName>
      <validResponseCodes>200,201,202</validResponseCodes>
      <url>{webhook_url}</url>
      <ignoreSslErrors>false</ignoreSslErrors>
      <passBuildParameters>false</passBuildParameters>
      <passAllBuildParameters>false</passAllBuildParameters>
      <customHeaders/>
      <json>{{"name": "{plan.jenkins_job}", "build": {{"number": "${{BUILD_NUMBER}}", "result": "${{BUILD_RESULT}}", "status": "FINISHED"}}, "task_type": "plan", "task_id": "{plan.id}"}}</json>
      <timeout>30000</timeout>
      <consoleLogResponseBody>false</consoleLogResponseBody>
      <quiet>false</quiet>
      <authentication/>
    </hudson.plugins.http_request.HttpRequestPublisher>
  </publishers>'''
                        updated_config = re.sub(publishers_pattern, publishers_section, updated_config)
                    else:
                        # Update existing webhook URL in publishers section only
                        webhook_url_pattern = r'(<publishers>.*?<json>)(.*?)(</json>.*?</publishers>)'
                        if re.search(webhook_url_pattern, updated_config, re.DOTALL):
                            new_json = f'{{"name": "{plan.jenkins_job}", "build": {{"number": "${{BUILD_NUMBER}}", "result": "${{BUILD_RESULT}}", "status": "FINISHED"}}, "task_type": "plan", "task_id": "{plan.id}"}}'
                            updated_config = re.sub(webhook_url_pattern, f'\\1{new_json}\\3', updated_config, flags=re.DOTALL)
                            print(f"[DEBUG] Updated existing webhook JSON to include task_type and task_id")
                        else:
                            print(f"[DEBUG] No existing webhook JSON found in publishers section")
                    
                    print(f"[DEBUG] Updated config with triggers: {plan.schedule_time}")
                    print(f"[DEBUG] Added webhook: {webhook_url}")
                    print(f"[DEBUG] Final config preview: {updated_config[:500]}...")
                    print(f"[DEBUG] Sending config to Jenkins: {jenkins_config_url}")
                    
                    # Validate XML structure before sending
                    if '<properties>' in updated_config and '<org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>' in updated_config:
                        print(f"[DEBUG] XML structure validation: OK - properties and PipelineTriggersJobProperty found")
                    else:
                        print(f"[DEBUG] XML structure validation: WARNING - properties or PipelineTriggersJobProperty missing")
                        print(f"[DEBUG] Properties found: {'<properties>' in updated_config}")
                        print(f"[DEBUG] PipelineTriggersJobProperty found: {'<org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>' in updated_config}")
                    
                    # Send updated config back to Jenkins
                    update_response = session.post(
                        jenkins_config_url,
                        headers=headers,
                        data=updated_config,
                        timeout=30
                    )
                    
                    if update_response.status_code == 200:
                        print(f"[DEBUG] Successfully updated Jenkins job config with cron schedule: {plan.schedule_time}")
                        
                        # Update plan status to "configured"
                        plan.status = "configured"
                        db.commit()
                        
                        return {
                            "message": f"Đã cập nhật Build periodically của Jenkins job '{plan.jenkins_job}' với cron schedule '{plan.schedule_time}'",
                            "plan_id": plan.id,
                            "plan_name": plan.plan_name,
                            "jenkins_job": plan.jenkins_job,
                            "cron_schedule": plan.schedule_time,
                            "status": "configured",
                            "jenkins_response": "Build periodically updated successfully",
                            "parameters": {"CRON_SCHEDULE": plan.schedule_time, "PLAN_ID": str(plan.id)}
                        }
                    else:
                        # If update failed
                        plan.status = "failed"
                        db.commit()
                        
                        return {
                            "message": f"Lỗi khi cập nhật Build periodically của Jenkins job '{plan.jenkins_job}'",
                            "plan_id": plan.id,
                            "plan_name": plan.plan_name,
                            "jenkins_job": plan.jenkins_job,
                            "cron_schedule": plan.schedule_time,
                            "status": "failed",
                            "jenkins_response": f"HTTP {update_response.status_code}: {update_response.text}"
                        }
                else:
                    # For Freestyle jobs, try to update the config
                    
                    # Pattern to match cron schedule in Jenkins config
                    cron_pattern = r'<spec>(.*?)</spec>'
                    
                    if re.search(cron_pattern, current_config):
                        # Replace existing cron schedule
                        updated_config = re.sub(cron_pattern, f'<spec>{plan.schedule_time}</spec>', current_config)
                        print(f"[DEBUG] Updated cron schedule to: {plan.schedule_time}")
                    else:
                        # Add cron schedule if not exists
                        print(f"[DEBUG] No existing cron schedule found, would need to add to config")
                        updated_config = current_config
                    
                    # Send updated config back to Jenkins
                    update_response = session.post(
                        jenkins_config_url,
                        headers=headers,
                        data=updated_config,
                        timeout=30
                    )
                    
                    if update_response.status_code == 200:
                        print(f"[DEBUG] Successfully updated Jenkins job config with cron schedule: {plan.schedule_time}")
                        
                        # Update plan status to "configured"
                        plan.status = "configured"
                        db.commit()
                        
                        return {
                            "message": f"Đã cập nhật Build periodically của Jenkins job '{plan.jenkins_job}' với cron schedule '{plan.schedule_time}'",
                            "plan_id": plan.id,
                            "plan_name": plan.plan_name,
                            "jenkins_job": plan.jenkins_job,
                            "cron_schedule": plan.schedule_time,
                            "status": "configured",
                            "jenkins_response": "Build periodically updated successfully",
                            "parameters": {"CRON_SCHEDULE": plan.schedule_time, "PLAN_ID": str(plan.id)}
                        }
                    else:
                        # If update failed
                        plan.status = "failed"
                        db.commit()
                        
                        return {
                            "message": f"Lỗi khi cập nhật Build periodically của Jenkins job '{plan.jenkins_job}'",
                            "plan_id": plan.id,
                            "plan_name": plan.plan_name,
                            "jenkins_job": plan.jenkins_job,
                            "cron_schedule": plan.schedule_time,
                            "status": "failed",
                            "jenkins_response": f"HTTP {update_response.status_code}: {update_response.text}"
                        }
            else:
                # If Jenkins returns error
                plan.status = "failed"
                db.commit()
                
                return {
                    "message": f"Lỗi khi cấu hình Jenkins job '{plan.jenkins_job}'",
                    "plan_id": plan.id,
                    "plan_name": plan.plan_name,
                    "jenkins_job": plan.jenkins_job,
                    "cron_schedule": plan.schedule_time,
                    "status": "failed",
                    "jenkins_response": f"HTTP {config_response.status_code}: {config_response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            # If cannot connect to Jenkins
            plan.status = "failed"
            db.commit()
            
            return {
                "message": f"Không thể kết nối đến Jenkins server",
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "jenkins_job": plan.jenkins_job,
                "cron_schedule": plan.schedule_time,
                "status": "failed",
                "jenkins_response": f"Connection error: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error running plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/{plan_id}/status")
def check_plan_status(plan_id: int, db: Session = Depends(get_db)):
    """Check status of plan and update database"""
    try:
        # Find the plan
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        if not plan.jenkins_job:
            raise HTTPException(status_code=400, detail="Plan không có Jenkins job được cấu hình")
        
        # Jenkins configuration
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        
        # Get last build information
        last_build_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/lastBuild/api/json"
        
        try:
            session = requests.Session()
            response = session.get(last_build_url, timeout=30)
            
            if response.status_code == 200:
                build_info = response.json()
                build_result = build_info.get('result')
                building = build_info.get('building', False)
                
                print(f"[DEBUG] Jenkins build info for {plan.jenkins_job}: building={building}, result={build_result}")
                
                # Update status based on Jenkins result
                if building:
                    new_status = "running"
                elif build_result == "SUCCESS" or build_result == "FAILURE":
                    # Coi cả SUCCESS và FAILURE là success (vì FAILURE có thể do testcase failed)
                    new_status = "success"
                elif build_result == "ABORTED":
                    new_status = "cancelled"
                else:
                    new_status = "running"  # Running or no result yet
                
                print(f"[DEBUG] Current status: {plan.status}, New status: {new_status}")
                
                # Update database if status changed
                if plan.status != new_status:
                    plan.status = new_status
                    db.commit()
                    print(f"[DEBUG] Updated plan {plan_id} status from {plan.status} to {new_status}")
                    
                    # Nếu job hoàn thành, tự động lưu report (cả SUCCESS và FAILURE)
                    if new_status == "success" and (build_result == "SUCCESS" or build_result == "FAILURE"):
                        try:
                            # Gọi API để lưu report
                            report_url = f"http://localhost:8000/api/reports/jenkins/save-report/{plan.plan_id}"
                            report_response = requests.post(report_url, timeout=30)
                            if report_response.status_code == 200:
                                print(f"✅ Đã tự động lưu report cho plan {plan_id}")
                                # Thêm log khi plan hoàn thành
                                log_backend_event("INFO", f"Plan '{plan.plan_name}' (ID: {plan.plan_id}) completed with result: {build_result}", db)
                            else:
                                print(f"⚠️ Không thể lưu report cho plan {plan_id}: {report_response.status_code}")
                                log_backend_event("WARNING", f"Failed to save report for plan {plan_id}: HTTP {report_response.status_code}", db)
                        except Exception as e:
                            print(f"❌ Lỗi khi lưu report cho plan {plan_id}: {e}")
                            log_backend_event("ERROR", f"Error saving report for plan {plan_id}: {str(e)}", db)
                else:
                    print(f"[DEBUG] Status unchanged for plan {plan_id}")
                
                return {
                    "plan_id": plan.id,
                    "plan_name": plan.plan_name,
                    "jenkins_job": plan.jenkins_job,
                    "cron_schedule": plan.schedule_time,
                    "status": new_status,
                    "jenkins_building": building,
                    "jenkins_result": build_result,
                    "build_number": build_info.get('number'),
                    "build_url": build_info.get('url')
                }
            else:
                # If cannot get build info
                print(f"[DEBUG] Failed to get build info: HTTP {response.status_code}")
                return {
                    "plan_id": plan.id,
                    "plan_name": plan.plan_name,
                    "jenkins_job": plan.jenkins_job,
                    "cron_schedule": plan.schedule_time,
                    "status": plan.status,
                    "jenkins_building": False,
                    "jenkins_result": None,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Request exception: {e}")
            return {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "jenkins_job": plan.jenkins_job,
                "cron_schedule": plan.schedule_time,
                "status": plan.status,
                "jenkins_building": False,
                "jenkins_result": None,
                "error": f"Connection error: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error checking plan status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.post("/{plan_id}/stop")
def stop_plan(plan_id: int, db: Session = Depends(get_db)):
    """Dừng plan - xóa cron schedule hoặc dừng job đang chạy"""
    try:
        # Tìm plan
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        if not plan.jenkins_job:
            raise HTTPException(status_code=400, detail="Plan không có Jenkins job được cấu hình")
        
        # Jenkins configuration
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
                print(f"Got crumb: {crumb_data['crumb']}")
            
            # Kiểm tra xem job có tồn tại không
            job_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/api/json"
            job_response = session.get(job_url, headers=headers, timeout=30)
            
            if job_response.status_code == 404:
                return {"message": f"Jenkins job '{plan.jenkins_job}' không tồn tại", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "job_not_found", "status": plan.status, "error": "Job không tồn tại trong Jenkins"}
            if job_response.status_code != 200:
                return {"message": f"Không thể kiểm tra Jenkins job '{plan.jenkins_job}'", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "failed_to_check_job", "status": plan.status, "error": f"HTTP {job_response.status_code}: {job_response.text}"}
            
            # Kiểm tra xem job có đang chạy không
            last_build_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/lastBuild/api/json"
            build_response = session.get(last_build_url, timeout=30)
            job_was_running = False
            build_number = None
            if build_response.status_code == 200:
                build_info = build_response.json()
                building = build_info.get('building', False)
                build_number = build_info.get('number')
                if building:
                    # Dừng job đang chạy
                    print(f"[DEBUG] Job {plan.jenkins_job} đang chạy (build #{build_number}), dừng job...")
                    stop_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/{build_number}/stop"
                    stop_response = session.post(stop_url, headers=headers, timeout=30)
                    job_was_running = True
            # Luôn cập nhật cron schedule về rỗng
            config_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/config.xml"
            config_response = session.get(config_url, headers=headers, timeout=30)
            if config_response.status_code == 200:
                current_config = config_response.text
                if 'flow-definition' in current_config:
                    updated_config = remove_timer_trigger(current_config)
                else:
                    # Freestyle job - cập nhật cron schedule thành rỗng
                    spec_pattern = r'(<spec>).*?(</spec>)'
                    if re.search(spec_pattern, current_config):
                        updated_config = re.sub(spec_pattern, r'\1\2', current_config)
                    else:
                        updated_config = current_config
                update_response = session.post(config_url, headers=headers, data=updated_config, timeout=30)
                if update_response.status_code == 200:
                    plan.status = "cancelled"
                    db.commit()
                    return {"message": f"Đã dừng Build periodically của Jenkins job '{plan.jenkins_job}'", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "stopped_cron_schedule", "status": "cancelled", "job_was_running": job_was_running, "build_number": build_number}
                else:
                    return {"message": f"Lỗi khi dừng Build periodically của Jenkins job '{plan.jenkins_job}'", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "failed_to_stop_schedule", "status": plan.status, "error": f"HTTP {update_response.status_code}: {update_response.text}"}
            else:
                return {"message": f"Lỗi khi lấy config của Jenkins job '{plan.jenkins_job}'", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "failed_to_get_config", "status": plan.status, "error": f"HTTP {config_response.status_code}: {config_response.text}"}
        except requests.exceptions.RequestException as e:
            return {"message": f"Không thể kết nối đến Jenkins server", "plan_id": plan.id, "plan_name": plan.plan_name, "jenkins_job": plan.jenkins_job, "action": "connection_error", "status": plan.status, "error": f"Connection error: {str(e)}"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error stopping plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/{plan_id}/results")
def get_plan_results(plan_id: int, build_number: int = None, db: Session = Depends(get_db)):
    """Lấy kết quả và files từ Jenkins job của plan"""
    try:
        # Tìm plan
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if not plan.jenkins_job:
            raise HTTPException(status_code=400, detail="Plan không có Jenkins job được cấu hình")
        # Nếu không truyền build_number, tự động lấy build_number của report gần nhất thành công/thất bại
        if build_number is None:
            from database import Report
            reports = db.query(Report).filter(Report.task_id == plan.plan_id).order_by(Report.created_at.desc()).all()
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
            build_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/{build_number}/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{plan.jenkins_job}/{build_number}/ws"
            console_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/{build_number}/consoleText"
        else:
            build_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/lastBuild/api/json"
            ws_prefix = f"{JENKINS_URL}/job/{plan.jenkins_job}/lastBuild/ws"
            console_url = f"{JENKINS_URL}/job/{plan.jenkins_job}/lastBuild/consoleText"
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
                    "plan_id": plan.id,
                    "plan_name": plan.plan_name,
                    "jenkins_job": plan.jenkins_job,
                    "schedule_time": plan.schedule_time,
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
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error getting plan results: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 