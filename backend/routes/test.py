from fastapi import APIRouter, HTTPException
import requests
from requests.auth import HTTPBasicAuth
import re
from urllib.parse import urlparse
import os
from datetime import datetime, timedelta
import logging
from sqlalchemy import text

router = APIRouter()

def get_next_available_jenkins_job_id(db):
    """Tìm ID nhỏ nhất có sẵn để tái sử dụng cho Jenkins jobs"""
    try:
        # Lấy tất cả ID hiện có
        result = db.execute(text("SELECT id FROM jenkins_jobs ORDER BY id"))
        existing_ids = [row[0] for row in result.fetchall()]
        
        if not existing_ids:
            return 1
        
        # Tìm ID nhỏ nhất có sẵn
        for i in range(1, max(existing_ids) + 2):
            if i not in existing_ids:
                return i
        
        return max(existing_ids) + 1
    except Exception as e:
        print(f"Error getting next available Jenkins job ID: {e}")
        # Fallback: sử dụng sequence
        result = db.execute(text("SELECT nextval('jenkins_jobs_id_seq')"))
        return result.fetchone()[0]

def extract_github_info(repo_url):
    if 'github.com' not in repo_url:
        print(f"[DEBUG] repo_url không phải github: {repo_url}")
        return None, None
    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    parts = repo_url.split('github.com/')
    if len(parts) != 2:
        print(f"[DEBUG] repo_url không đúng định dạng: {repo_url}")
        return None, None
    path_parts = parts[1].split('/')
    if len(path_parts) < 2:
        print(f"[DEBUG] repo_url thiếu owner/repo: {repo_url}")
        return None, None
    owner = path_parts[0]
    repo = path_parts[1]
    print(f"[DEBUG] Extracted owner: {owner}, repo: {repo}")
    return owner, repo

def get_github_files(owner, repo, path=""):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        print(f"[DEBUG] Fetching GitHub API: {url}")
        response = requests.get(url, timeout=10)
        print(f"[DEBUG] GitHub API status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[DEBUG] GitHub API error: {response.text}")
            return None
    except Exception as e:
        print(f"[DEBUG] Error fetching GitHub files: {e}")
        return None

def find_robot_files(contents, owner, repo, base_path=""):
    robot_files = []
    if not isinstance(contents, list):
        print(f"[DEBUG] Contents không phải list: {contents}")
        return robot_files
    for item in contents:
        if item['type'] == 'file' and item['name'].endswith('.robot'):
            test_count = count_test_cases_in_file(item['download_url'])
            robot_files.append({
                'name': item['name'],
                'path': f"{base_path}/{item['name']}" if base_path else item['name'],
                'size': format_file_size(item['size']),
                'test_count': test_count,
                'download_url': item['download_url']
            })
        elif item['type'] == 'dir':
            sub_contents = get_github_files(owner, repo, f"{base_path}/{item['name']}" if base_path else item['name'])
            if sub_contents:
                robot_files.extend(find_robot_files(sub_contents, owner, repo, f"{base_path}/{item['name']}" if base_path else item['name']))
    return robot_files

def count_test_cases_in_file(download_url):
    """Mỗi file .robot được tính là 1 test case"""
    return 1

def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    else:
        return f"{size_bytes // (1024 * 1024)} MB"

@router.get("/{project_id}/robot-files")
async def get_robot_files(project_id: int):
    try:
        from database import SessionLocal
        db = SessionLocal()
        project = None
        repo_url = None
        project_name = None
        
        try:
            from database import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                print(f"[DEBUG] Không tìm thấy project id={project_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            
            repo_url = project.repo_link
            project_name = project.name
            print(f"[DEBUG] repo_url: {repo_url}")
            print(f"[DEBUG] project_name: {project_name}")
            
            if not repo_url:
                print(f"[DEBUG] Project không có repo_link")
                raise HTTPException(status_code=400, detail="Project does not have repository link")
        finally:
            db.close()
            
        owner, repo = extract_github_info(repo_url)
        if not owner or not repo:
            print(f"[DEBUG] Không extract được owner/repo từ {repo_url}")
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
            
        contents = get_github_files(owner, repo)
        if not contents:
            print(f"[DEBUG] Không lấy được contents từ GitHub repo {owner}/{repo}")
            raise HTTPException(status_code=404, detail="Repository not found or not accessible")
            
        robot_files = find_robot_files(contents, owner, repo)
        total_testcases = sum(file['test_count'] for file in robot_files)
        print(f"[DEBUG] Tổng số file .robot: {len(robot_files)}, tổng testcase: {total_testcases}")
        # Cập nhật testcase_number vào DB
        db = SessionLocal()
        try:
            from database import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.testcase_number = total_testcases
                db.commit()
        finally:
            db.close()
        
        return {
            "project_id": project_id,
            "project_name": project_name,
            "repo_url": repo_url,
            "robot_files": robot_files,
            "total_testcases": total_testcases,
            "files_count": len(robot_files)
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error processing robot files: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")



@router.get("/db/info")
async def get_database_info():
    """Lấy thông tin database - tương tự view_testcases.py"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Project, TestCase
            
            # Lấy danh sách projects
            projects = db.query(Project).all()
            projects_data = []
            for proj in projects:
                projects_data.append({
                    "id": proj.id,
                    "name": proj.name,
                    "repo_link": proj.repo_link,
                    "project_manager": proj.project_manager,
                    "members": proj.members,
                    "created_at": proj.created_at.isoformat() if proj.created_at else None
                })
            
            # Lấy danh sách testcases
            testcases = db.query(TestCase).all()
            testcases_data = []
            for tc in testcases:
                project = db.query(Project).filter(Project.id == tc.project_id).first()
                testcases_data.append({
                    "id": tc.id,
                    "name": tc.name,
                    "description": tc.description,
                    "project_id": tc.project_id,
                    "project_name": project.name if project else "Unknown",
                    "status": tc.status,
                    "priority": tc.priority,
                    "created_at": tc.created_at.isoformat() if tc.created_at else None,
                    "updated_at": tc.updated_at.isoformat() if tc.updated_at else None
                })
            
            return {
                "projects": {
                    "count": len(projects_data),
                    "data": projects_data
                },
                "testcases": {
                    "count": len(testcases_data),
                    "data": testcases_data
                }
            }
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error getting database info: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/{project_id}/sync-testcases")
async def sync_testcases_to_db(project_id: int):
    """Đồng bộ test cases từ robot files vào database"""
    try:
        from database import SessionLocal, TestCase
        db = SessionLocal()
        
        try:
            from database import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            repo_url = project.repo_link
            if not repo_url:
                raise HTTPException(status_code=400, detail="Project does not have repository link")
        finally:
            db.close()
            
        # Lấy robot files từ GitHub
        owner, repo = extract_github_info(repo_url)
        if not owner or not repo:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
            
        contents = get_github_files(owner, repo)
        if not contents:
            raise HTTPException(status_code=404, detail="Repository not found or not accessible")
            
        robot_files = find_robot_files(contents, owner, repo)
        
        # Xóa test cases cũ của project
        db = SessionLocal()
        try:
            db.query(TestCase).filter(TestCase.project_id == project_id).delete()
            
            # Thêm test cases mới
            created_count = 0
            for robot_file in robot_files:
                test_case = TestCase(
                    name=robot_file['name'],
                    description=f"Robot file: {robot_file['path']}",
                    project_id=project_id,
                    status="active",
                    priority="medium",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(test_case)
                created_count += 1
            
            db.commit()
            
            return {
                "message": f"Đã đồng bộ {created_count} test cases cho project {project.name}",
                "project_id": project_id,
                "project_name": project.name,
                "synced_testcases": created_count,
                "robot_files_count": len(robot_files)
            }
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error syncing testcases: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Test router is working"}

@router.post("/{project_id}/create-jenkins-job")
async def create_jenkins_job(project_id: int, job_data: dict):
    """Tạo Jenkins job cho project"""
    try:
        from database import SessionLocal, Project
        db = SessionLocal()
        
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            if not project.repo_link:
                raise HTTPException(status_code=400, detail="Project does not have repository link")
        finally:
            db.close()
        
        # Jenkins configuration
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        JENKINS_USER = os.getenv("JENKINS_USER", "admin")
        JENKINS_PASS = os.getenv("JENKINS_PASS", "admin")
        
        job_name = job_data.get("job_name")
        if not job_name:
            raise HTTPException(status_code=400, detail="Job name is required")
        
        # Kiểm tra kết nối Jenkins
        try:
            test_response = requests.get(f"{JENKINS_URL}/api/json", timeout=10)
            if test_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Jenkins không khả dụng: {test_response.status_code}")
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Không thể kết nối đến Jenkins: {str(e)}")
        
        # Tạo Jenkins Pipeline job config XML
        config_xml = f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job@1339.vd5a_957c2c31">
    <description>Auto-generated pipeline job for {project.name}</description>
    <keepDependencies>false</keepDependencies>
    <properties>
        <hudson.model.ParametersDefinitionProperty>
            <parameterDefinitions>
                <hudson.model.StringParameterDefinition>
                    <name>TASK_ID</name>
                    <description>Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)</description>
                    <defaultValue></defaultValue>
                    <trim>false</trim>
                </hudson.model.StringParameterDefinition>
            </parameterDefinitions>
        </hudson.model.ParametersDefinitionProperty>
    </properties>
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps@3863.vb_a_490d892b8">
        <scm class="hudson.plugins.git.GitSCM" plugin="git@5.0.0">
            <configVersion>2</configVersion>
            <userRemoteConfigs>
                <hudson.plugins.git.UserRemoteConfig>
                    <url>{project.repo_link}</url>
                </hudson.plugins.git.UserRemoteConfig>
            </userRemoteConfigs>
            <branches>
                <hudson.plugins.git.BranchSpec>
                    <name>*/main</name>
                </hudson.plugins.git.BranchSpec>
            </branches>
            <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
            <submoduleCfg class="empty-list"/>
            <extensions/>
        </scm>
        <scriptPath>Jenkinsfile</scriptPath>
        <lightweight>true</lightweight>
    </definition>
    <triggers/>
    <disabled>false</disabled>
</flow-definition>"""
        
        # Tạo Jenkins job
        session = requests.Session()
        
        # Get CSRF crumb với authentication
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        try:
            crumb_response = session.get(
                crumb_url, 
                auth=HTTPBasicAuth(JENKINS_USER, JENKINS_PASS),
                timeout=30
            )
            
            headers = {'Content-Type': 'application/xml'}
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
            elif crumb_response.status_code == 403:
                # Jenkins không yêu cầu CSRF, tiếp tục không có crumb
                headers = {'Content-Type': 'application/xml'}
            else:
                logging.warning(f"Không thể lấy CSRF crumb: {crumb_response.status_code}")
                headers = {'Content-Type': 'application/xml'}
        except Exception as e:
            logging.warning(f"Lỗi khi lấy CSRF crumb: {e}")
            headers = {'Content-Type': 'application/xml'}
        
        # Tạo job với authentication (nếu cần)
        create_job_url = f"{JENKINS_URL}/createItem?name={job_name}"
        try:
            # Thử với authentication trước
            response = session.post(
                create_job_url,
                data=config_xml,
                headers=headers,
                auth=HTTPBasicAuth(JENKINS_USER, JENKINS_PASS),
                timeout=30
            )
            
            # Nếu lỗi 401/403, thử không có authentication
            if response.status_code in [401, 403]:
                logging.info("Jenkins requires authentication, trying without auth...")
                response = session.post(
                    create_job_url,
                    data=config_xml,
                    headers=headers,
                    timeout=30
                )
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Lỗi kết nối Jenkins: {str(e)}")
        
        if response.status_code == 200:
            # Lưu Jenkins job vào database với ID tùy chỉnh
            try:
                from database import JenkinsJob, SessionLocal
                db = SessionLocal()
                try:
                    # Tìm ID nhỏ nhất có sẵn
                    next_id = get_next_available_jenkins_job_id(db)
                    
                    jenkins_job = JenkinsJob(
                        id=next_id,  # Sử dụng ID tùy chỉnh
                        name=job_name,
                        project_id=project_id,
                        project_name=project.name,
                        repository=project.repo_link,
                        status="active",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(jenkins_job)
                    db.commit()
                    print(f"[DEBUG] Đã lưu Jenkins job '{job_name}' vào database với ID {next_id}")
                except Exception as e:
                    db.rollback()
                    print(f"[DEBUG] Lỗi lưu Jenkins job vào database: {e}")
                finally:
                    db.close()
            except Exception as e:
                print(f"[DEBUG] Lỗi import JenkinsJob model: {e}")
            
            return {
                "message": f"Đã tạo Jenkins job '{job_name}' thành công",
                "job_name": job_name,
                "project_id": project_id,
                "project_name": project.name,
                "repo_url": project.repo_link
            }
        elif response.status_code == 400:
            # Job name đã tồn tại
            raise HTTPException(
                status_code=400, 
                detail=f"Jenkins job '{job_name}' đã tồn tại"
            )
        elif response.status_code == 403:
            # Không có quyền tạo job
            raise HTTPException(
                status_code=403, 
                detail="Không có quyền tạo Jenkins job. Vui lòng kiểm tra thông tin đăng nhập."
            )
        else:
            logging.error(f"Jenkins API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=500, 
                detail=f"Không thể tạo Jenkins job: {response.status_code} - {response.text}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error creating Jenkins job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/jenkins/jobs")
async def get_jenkins_jobs():
    """Lấy danh sách Jenkins jobs"""
    try:
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        JENKINS_USER = os.getenv("JENKINS_USER", "admin")
        JENKINS_PASS = os.getenv("JENKINS_PASS", "admin")
        
        api_url = f"{JENKINS_URL}/api/json"
        session = requests.Session()
        
        # Kiểm tra kết nối Jenkins
        try:
            # Thử với authentication trước
            response = session.get(
                api_url, 
                auth=HTTPBasicAuth(JENKINS_USER, JENKINS_PASS),
                timeout=15
            )
            
            # Nếu lỗi 401/403, thử không có authentication
            if response.status_code in [401, 403]:
                logging.info("Jenkins requires authentication, trying without auth...")
                response = session.get(api_url, timeout=15)
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Jenkins API error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Không thể kết nối đến Jenkins: {str(e)}")
        
        data = response.json()
        jobs = data.get('jobs', [])
        
        # Format jobs với thông tin chi tiết hơn
        formatted_jobs = []
        for job in jobs:
            job_info = {
                "name": job["name"],
                "url": job["url"],
                "status": job.get('color', 'unknown'),
                "last_build": None
            }
            
            # Lấy thông tin build cuối cùng nếu có
            if job.get('builds') and len(job['builds']) > 0:
                last_build = job['builds'][0]
                job_info["last_build"] = {
                    "number": last_build.get('number'),
                    "result": last_build.get('result'),
                    "timestamp": last_build.get('timestamp')
                }
            
            formatted_jobs.append(job_info)
        
        return {"jobs": formatted_jobs}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting Jenkins jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách Jenkins jobs: {e}")

@router.get("/jenkins/jobs/db")
async def get_jenkins_jobs_from_db():
    """Lấy danh sách Jenkins jobs từ database"""
    try:
        from database import SessionLocal, JenkinsJob
        db = SessionLocal()
        
        try:
            jenkins_jobs = db.query(JenkinsJob).order_by(JenkinsJob.created_at.desc()).all()
            
            jobs_data = []
            for job in jenkins_jobs:
                # Chuyển đổi múi giờ từ UTC sang UTC+7 (Việt Nam)
                created_at_vn = None
                updated_at_vn = None
                
                if job.created_at:
                    # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                    created_at_vn = job.created_at.replace(tzinfo=None) + timedelta(hours=7)
                
                if job.updated_at:
                    # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                    updated_at_vn = job.updated_at.replace(tzinfo=None) + timedelta(hours=7)
                
                # Lấy trạng thái thực từ Jenkins
                jenkins_status = "unknown"
                try:
                    JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
                    jenkins_api_url = f"{JENKINS_URL}/job/{job.name}/api/json"
                    
                    response = requests.get(jenkins_api_url, timeout=10)
                    
                    if response.status_code == 200:
                        jenkins_data = response.json()
                        
                        # Lấy trạng thái từ lastBuild
                        if jenkins_data.get('lastBuild'):
                            last_build_number = jenkins_data['lastBuild'].get('number')
                            
                            if last_build_number:
                                # Lấy result từ build cụ thể
                                build_api_url = f"{JENKINS_URL}/job/{job.name}/{last_build_number}/api/json"
                                
                                build_response = requests.get(build_api_url, timeout=10)
                                if build_response.status_code == 200:
                                    build_data = build_response.json()
                                    build_result = build_data.get('result')
                                    building = build_data.get('building', False)
                                    
                                    # Kiểm tra nếu job đang chạy
                                    if building:
                                        jenkins_status = 'building'
                                    elif build_result == 'SUCCESS':
                                        jenkins_status = 'blue'
                                    elif build_result == 'FAILURE':
                                        jenkins_status = 'red'
                                    elif build_result == 'UNSTABLE':
                                        jenkins_status = 'yellow'
                                    elif build_result == 'ABORTED':
                                        jenkins_status = 'grey'
                                    else:
                                        jenkins_status = 'notbuilt'
                                else:
                                    jenkins_status = 'unknown'
                            else:
                                jenkins_status = 'notbuilt'
                        else:
                            jenkins_status = 'notbuilt'
                    else:
                        jenkins_status = 'disabled'
                except Exception as e:
                    print(f"[DEBUG] Không thể lấy trạng thái Jenkins cho job {job.name}: {e}")
                    jenkins_status = 'unknown'
                
                jobs_data.append({
                    "id": job.id,
                    "name": job.name,
                    "project_id": job.project_id,
                    "project_name": job.project_name,
                    "repository": job.repository,
                    "status": jenkins_status,  # Sử dụng trạng thái từ Jenkins
                    "created_at": created_at_vn.isoformat() if created_at_vn else None,
                    "updated_at": updated_at_vn.isoformat() if updated_at_vn else None
                })
            
            return {
                "jobs": jobs_data,
                "total": len(jobs_data)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[DEBUG] Error getting Jenkins jobs from DB: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách Jenkins jobs từ database: {e}")

@router.delete("/jenkins/jobs/{job_name}")
async def delete_jenkins_job(job_name: str):
    """Xóa Jenkins job"""
    try:
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        JENKINS_USER = os.getenv("JENKINS_USER", "admin")
        JENKINS_PASS = os.getenv("JENKINS_PASS", "admin")
        
        print(f"[DEBUG] Bắt đầu xóa Jenkins job: {job_name}")
        
        # Sử dụng session để xóa job
        session = requests.Session()
        session.auth = HTTPBasicAuth(JENKINS_USER, JENKINS_PASS)
        
        # Lấy CSRF crumb với session
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        try:
            crumb_response = session.get(crumb_url, timeout=30)
            print(f"[DEBUG] CSRF crumb response status: {crumb_response.status_code}")
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                print(f"[DEBUG] Đã lấy CSRF crumb thành công: {crumb_data['crumbRequestField']} = {crumb_data['crumb']}")
            else:
                print(f"[DEBUG] Không thể lấy CSRF crumb: {crumb_response.status_code}")
        except Exception as e:
            print(f"[DEBUG] Lỗi lấy CSRF crumb: {e}")
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Xóa job từ Jenkins với session
        delete_url = f"{JENKINS_URL}/job/{job_name}/doDelete"
        print(f"[DEBUG] Gọi Jenkins API: {delete_url}")
        
        response = None
        try:
            # Thử với session và form data
            response = session.post(
                delete_url,
                headers=headers,
                timeout=30
            )
            print(f"[DEBUG] Jenkins delete response status: {response.status_code}")
            print(f"[DEBUG] Jenkins delete response text: {response.text[:200]}")
            
            # Nếu vẫn lỗi, thử với DELETE method
            if not response or response.status_code not in [200, 302]:
                print(f"[DEBUG] Thử với DELETE method...")
                delete_rest_url = f"{JENKINS_URL}/job/{job_name}"
                try:
                    delete_response = session.delete(
                        delete_rest_url,
                        timeout=30
                    )
                    print(f"[DEBUG] Jenkins DELETE method response status: {delete_response.status_code}")
                    print(f"[DEBUG] Jenkins DELETE method response text: {delete_response.text[:200]}")
                    response = delete_response
                except Exception as e:
                    print(f"[DEBUG] Lỗi DELETE method: {e}")
                    response = None
            
        except Exception as e:
            print(f"[DEBUG] Lỗi gọi Jenkins API: {e}")
            response = None
        
        # Xóa job từ database
        db_deleted = False
        try:
            from database import SessionLocal, JenkinsJob
            db = SessionLocal()
            try:
                db_job = db.query(JenkinsJob).filter(JenkinsJob.name == job_name).first()
                if db_job:
                    db.delete(db_job)
                    db.commit()
                    db_deleted = True
                    print(f"[DEBUG] Đã xóa Jenkins job '{job_name}' khỏi database")
                else:
                    print(f"[DEBUG] Không tìm thấy job '{job_name}' trong database")
            except Exception as e:
                db.rollback()
                print(f"[DEBUG] Lỗi xóa Jenkins job khỏi database: {e}")
            finally:
                db.close()
        except Exception as e:
            print(f"[DEBUG] Lỗi import JenkinsJob model: {e}")
        
        # Trả về kết quả
        if response and response.status_code in [200, 302]:
            return {"success": True, "message": f"Jenkins job '{job_name}' deleted successfully"}
        elif db_deleted:
            return {"success": True, "message": f"Jenkins job '{job_name}' deleted from database (Jenkins may be unavailable)"}
        else:
            error_msg = f"Không thể xóa Jenkins job: Jenkins status={response.status_code if response else 'N/A'}, DB deleted={db_deleted}"
            print(f"[DEBUG] {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Lỗi xóa Jenkins job: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/jenkins/jobs/by-project/{project_id}")
async def get_jenkins_jobs_by_project(project_id: int):
    """Lấy danh sách Jenkins jobs theo project_id từ database"""
    try:
        from database import SessionLocal, JenkinsJob
        db = SessionLocal()
        
        try:
            jenkins_jobs = db.query(JenkinsJob).filter(JenkinsJob.project_id == project_id).all()
            
            jobs_data = []
            for job in jenkins_jobs:
                # Chuyển đổi múi giờ từ UTC sang UTC+7 (Việt Nam)
                created_at_vn = None
                updated_at_vn = None
                
                if job.created_at:
                    # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                    created_at_vn = job.created_at.replace(tzinfo=None) + timedelta(hours=7)
                
                if job.updated_at:
                    # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                    updated_at_vn = job.updated_at.replace(tzinfo=None) + timedelta(hours=7)
                
                jobs_data.append({
                    "id": job.id,
                    "name": job.name,
                    "project_id": job.project_id,
                    "project_name": job.project_name,
                    "repository": job.repository,
                    "status": job.status,
                    "created_at": created_at_vn.isoformat() if created_at_vn else None,
                    "updated_at": updated_at_vn.isoformat() if updated_at_vn else None
                })
            
            return {
                "jobs": jobs_data,
                "total": len(jobs_data)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[DEBUG] Error getting Jenkins jobs by project: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách Jenkins jobs theo project: {e}")

@router.get("/jenkins/jobs/{job_name}/info")
async def get_jenkins_job_info(job_name: str):
    """Lấy thông tin chi tiết của Jenkins job từ database"""
    try:
        from database import SessionLocal, JenkinsJob
        db = SessionLocal()
        
        try:
            db_job = db.query(JenkinsJob).filter(JenkinsJob.name == job_name).first()
            if not db_job:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy job '{job_name}' trong database")
            
            # Chuyển đổi múi giờ từ UTC sang UTC+7 (Việt Nam)
            created_at_vn = None
            updated_at_vn = None
            
            if db_job.created_at:
                # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                created_at_vn = db_job.created_at.replace(tzinfo=None) + timedelta(hours=7)
            
            if db_job.updated_at:
                # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                updated_at_vn = db_job.updated_at.replace(tzinfo=None) + timedelta(hours=7)
            
            return {
                "id": db_job.id,
                "name": db_job.name,
                "project_id": db_job.project_id,
                "project_name": db_job.project_name,
                "repository": db_job.repository,
                "status": db_job.status,
                "created_at": created_at_vn.isoformat() if created_at_vn else None,
                "updated_at": updated_at_vn.isoformat() if updated_at_vn else None
            }
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error getting Jenkins job info: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thông tin Jenkins job: {e}")

@router.put("/jenkins/jobs/{job_name}")
async def update_jenkins_job(job_name: str, job_data: dict):
    """Cập nhật thông tin Jenkins job - cả Jenkins và database"""
    try:
        from database import SessionLocal, JenkinsJob, Project
        db = SessionLocal()
        
        try:
            # Tìm job trong database
            db_job = db.query(JenkinsJob).filter(JenkinsJob.name == job_name).first()
            if not db_job:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy job '{job_name}' trong database")
            
            # Lấy thông tin cập nhật
            new_name = job_data.get("name")
            new_project_id = job_data.get("project_id")
            
            if not new_name or not new_project_id:
                raise HTTPException(status_code=400, detail="Tên job và project_id là bắt buộc")
            
            # Kiểm tra project có tồn tại không
            project = db.query(Project).filter(Project.id == new_project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy project với ID {new_project_id}")
            
            # Kiểm tra xem tên mới đã tồn tại chưa (nếu khác tên cũ)
            if new_name != job_name:
                existing_job = db.query(JenkinsJob).filter(JenkinsJob.name == new_name).first()
                if existing_job:
                    raise HTTPException(status_code=400, detail=f"Job name '{new_name}' đã tồn tại")
            
            # Jenkins configuration
            JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
            JENKINS_USER = os.getenv("JENKINS_USER", "admin")
            JENKINS_PASS = os.getenv("JENKINS_PASS", "admin")
            
            print(f"[DEBUG] Bắt đầu cập nhật Jenkins job: {job_name} -> {new_name}")
            
            # Bước 1: Xóa job cũ khỏi Jenkins (nếu tồn tại)
            session = requests.Session()
            session.auth = HTTPBasicAuth(JENKINS_USER, JENKINS_PASS)
            
            # Lấy CSRF crumb cho xóa job
            crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
            try:
                crumb_response = session.get(crumb_url, timeout=30)
                delete_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                if crumb_response.status_code == 200:
                    crumb_data = crumb_response.json()
                    delete_headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                    print(f"[DEBUG] Đã lấy CSRF crumb cho xóa job thành công")
            except Exception as e:
                print(f"[DEBUG] Lỗi lấy CSRF crumb cho xóa job: {e}")
                delete_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            # Xóa job cũ
            delete_url = f"{JENKINS_URL}/job/{job_name}/doDelete"
            try:
                delete_response = session.post(delete_url, headers=delete_headers, timeout=30)
                print(f"[DEBUG] Xóa job cũ status: {delete_response.status_code}")
            except Exception as e:
                print(f"[DEBUG] Lỗi xóa job cũ: {e}")
            
            # Bước 2: Tạo job mới với thông tin cập nhật (sử dụng logic giống tạo job)
            config_xml = f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job@1339.vd5a_957c2c31">
    <description>Auto-generated pipeline job for {project.name}</description>
    <keepDependencies>false</keepDependencies>
    <properties>
        <hudson.model.ParametersDefinitionProperty>
            <parameterDefinitions>
                <hudson.model.StringParameterDefinition>
                    <name>TASK_ID</name>
                    <description>Task ID from TestOps (e.g., TASK-001, PLAN-001, CICD-001)</description>
                    <defaultValue></defaultValue>
                    <trim>false</trim>
                </hudson.model.StringParameterDefinition>
            </parameterDefinitions>
        </hudson.model.ParametersDefinitionProperty>
    </properties>
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps@3863.vb_a_490d892b8">
        <scm class="hudson.plugins.git.GitSCM" plugin="git@5.0.0">
            <configVersion>2</configVersion>
            <userRemoteConfigs>
                <hudson.plugins.git.UserRemoteConfig>
                    <url>{project.repo_link}</url>
                </hudson.plugins.git.UserRemoteConfig>
            </userRemoteConfigs>
            <branches>
                <hudson.plugins.git.BranchSpec>
                    <name>*/main</name>
                </hudson.plugins.git.BranchSpec>
            </branches>
            <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
            <submoduleCfg class="empty-list"/>
            <extensions/>
        </scm>
        <scriptPath>Jenkinsfile</scriptPath>
        <lightweight>true</lightweight>
    </definition>
    <triggers/>
    <disabled>false</disabled>
</flow-definition>"""
            
            # Tạo job mới với logic giống hệt tạo job
            create_job_url = f"{JENKINS_URL}/createItem?name={new_name}"
            
            # Get CSRF crumb cho tạo job (giống logic tạo job)
            try:
                crumb_response = session.get(crumb_url, timeout=30)
                headers = {'Content-Type': 'application/xml'}
                if crumb_response.status_code == 200:
                    crumb_data = crumb_response.json()
                    headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                elif crumb_response.status_code == 403:
                    # Jenkins không yêu cầu CSRF, tiếp tục không có crumb
                    headers = {'Content-Type': 'application/xml'}
                else:
                    logging.warning(f"Không thể lấy CSRF crumb: {crumb_response.status_code}")
                    headers = {'Content-Type': 'application/xml'}
            except Exception as e:
                logging.warning(f"Lỗi khi lấy CSRF crumb: {e}")
                headers = {'Content-Type': 'application/xml'}
            
            # Tạo job với authentication (giống logic tạo job)
            try:
                # Thử với authentication trước
                create_response = session.post(
                    create_job_url,
                    data=config_xml,
                    headers=headers,
                    auth=HTTPBasicAuth(JENKINS_USER, JENKINS_PASS),
                    timeout=30
                )
                
                # Nếu lỗi 401/403, thử không có authentication
                if create_response.status_code in [401, 403]:
                    logging.info("Jenkins requires authentication, trying without auth...")
                    create_response = session.post(
                        create_job_url,
                        data=config_xml,
                        headers=headers,
                        timeout=30
                    )
                    
            except requests.exceptions.RequestException as e:
                raise HTTPException(status_code=500, detail=f"Lỗi kết nối Jenkins: {str(e)}")
            
            print(f"[DEBUG] Tạo job mới status: {create_response.status_code}")
            
            if create_response.status_code != 200:
                print(f"[DEBUG] Lỗi tạo job mới: {create_response.text}")
                raise HTTPException(status_code=500, detail=f"Không thể tạo job mới trong Jenkins: {create_response.status_code}")
            
            # Bước 3: Cập nhật database
            db_job.name = new_name
            db_job.project_id = new_project_id
            db_job.project_name = project.name
            db_job.repository = project.repo_link
            db_job.updated_at = datetime.utcnow()
            
            db.commit()
            print(f"[DEBUG] Đã cập nhật job trong database")
            
            # Chuyển đổi múi giờ từ UTC sang UTC+7 (Việt Nam)
            updated_at_vn = None
            if db_job.updated_at:
                # Thêm 7 giờ để chuyển từ UTC sang UTC+7
                updated_at_vn = db_job.updated_at.replace(tzinfo=None) + timedelta(hours=7)
            
            return {
                "success": True,
                "message": f"Đã cập nhật Jenkins job '{job_name}' thành '{new_name}' thành công",
                "job": {
                    "id": db_job.id,
                    "name": db_job.name,
                    "project_id": db_job.project_id,
                    "project_name": db_job.project_name,
                    "repository": db_job.repository,
                    "status": db_job.status,
                    "updated_at": updated_at_vn.isoformat() if updated_at_vn else None
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"[DEBUG] Error updating Jenkins job: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi cập nhật Jenkins job: {e}")
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error updating Jenkins job: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật Jenkins job: {e}")