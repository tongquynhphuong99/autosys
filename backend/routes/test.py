from fastapi import APIRouter, HTTPException
import requests
import re
from urllib.parse import urlparse
import os
from datetime import datetime

router = APIRouter()

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