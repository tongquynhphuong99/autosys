from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import requests
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_, Integer, text
from sqlalchemy.orm import Session
from database import get_db, Project, Execution, TestCase, Report
from routes.log import log_backend_event

# Helper functions for webhook processing
def process_plan_webhook(plan, job_name, build_number, build_result, body, db):
    """Xử lý webhook cho plan task"""
    print(f"[DEBUG] Processing webhook for plan: {plan.plan_name}")
    
    # Lấy thông tin project
    project = db.query(Project).filter(Project.id == plan.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Lấy thông tin chi tiết từ Jenkins
    JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
    
    try:
        session = requests.Session()
        
        # Lấy file output.xml để parse thông tin test (chỉ khi không phải ABORTED)
        output_xml_url = f"{JENKINS_URL}/job/{job_name}/{build_number}/robot/report/output.xml"
        xml_response = session.get(output_xml_url, timeout=30) if build_result != "ABORTED" else None
        
        # Parse thông tin từ output.xml
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        start_time = None
        end_time = None
        duration_seconds = 0
        
        # Lấy thông tin thời gian từ webhook (fallback cho ABORTED)
        if body.get('build', {}).get('timestamp'):
            start_time = datetime.fromtimestamp(body['build']['timestamp'] / 1000)
        if body.get('build', {}).get('duration'):
            duration_seconds = body['build']['duration'] // 1000
            end_time = start_time + timedelta(seconds=duration_seconds) if start_time else None
        
        if xml_response and xml_response.status_code == 200:
            try:
                root = ET.fromstring(xml_response.text)
                
                # Lấy thông tin từ robot output.xml - sử dụng thống kê từ XML
                stats = root.find('.//statistics')
                if stats is not None:
                    total = stats.find('.//total')
                    if total is not None:
                        total_stat = total.find('.//stat')
                        if total_stat is not None:
                            passed_tests = int(total_stat.get('pass', 0))
                            failed_tests = int(total_stat.get('fail', 0))
                            skipped_tests = int(total_stat.get('skip', 0))
                            total_tests = passed_tests + failed_tests + skipped_tests
                
                # Lấy thông tin thời gian từ XML
                suite = root.find('.//suite')
                if suite is not None:
                    start_time_str = suite.get('starttime')
                    end_time_str = suite.get('endtime')
                    if start_time_str and end_time_str:
                        try:
                            start_time = datetime.strptime(start_time_str, '%Y%m%d %H:%M:%S.%f')
                            end_time = datetime.strptime(end_time_str, '%Y%m%d %H:%M:%S.%f')
                            duration_seconds = int((end_time - start_time).total_seconds())
                        except ValueError:
                            pass
            except ET.ParseError as e:
                print(f"[WARNING] Failed to parse output.xml: {e}")
        
        # Luôn tạo report mới cho mỗi lần chạy
        report = Report(
            task_id=plan.plan_id,
            execution_id=plan.id,
            project_id=project.id,
            build_number=build_number,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            duration_seconds=duration_seconds,
            start_time=start_time,
            end_time=end_time,
            status=build_result.lower() if build_result else 'completed'
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # Cập nhật status của plan theo kết quả thực tế
        if build_result == "ABORTED":
            plan.status = 'cancelled'
        elif build_result == "SUCCESS":
            plan.status = 'success'
        elif build_result == "FAILURE":
            plan.status = 'failed'
        db.commit()
        
        print(f"✅ Webhook: Đã lưu report cho plan '{plan.plan_name}' - Build #{build_number}")
        
        log_backend_event("INFO", f"Webhook: Saved report for plan '{plan.plan_name}' - Build #{build_number}", db)
        
        return {
            "message": f"Đã lưu report cho plan '{plan.plan_name}' thành công",
            "report_id": report.id,
            "plan_id": plan.id,
            "task_id": plan.plan_id,
            "project_name": project.name,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "duration_seconds": duration_seconds,
            "build_number": build_number,
            "status": report.status
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook: Lỗi kết nối Jenkins: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi kết nối Jenkins: {str(e)}"
        )

def process_execution_webhook(execution, job_name, build_number, build_result, body, db):
    """Xử lý webhook cho execution task"""
    print(f"[DEBUG] Processing webhook for execution: {execution.task_name}")
    
    # Lấy thông tin project
    project = db.query(Project).filter(Project.id == execution.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Lấy thông tin chi tiết từ Jenkins
    JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
    
    try:
        session = requests.Session()
        
        # Lấy file output.xml để parse thông tin test (chỉ khi không phải ABORTED)
        output_xml_url = f"{JENKINS_URL}/job/{job_name}/{build_number}/robot/report/output.xml"
        xml_response = session.get(output_xml_url, timeout=30) if build_result != "ABORTED" else None
        
        # Parse thông tin từ output.xml
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        start_time = None
        end_time = None
        duration_seconds = 0
        
        # Lấy thông tin thời gian từ webhook (fallback cho ABORTED)
        if body.get('build', {}).get('timestamp'):
            start_time = datetime.fromtimestamp(body['build']['timestamp'] / 1000)
        if body.get('build', {}).get('duration'):
            duration_seconds = body['build']['duration'] // 1000
            end_time = start_time + timedelta(seconds=duration_seconds) if start_time else None
        
        if xml_response and xml_response.status_code == 200:
            try:
                root = ET.fromstring(xml_response.text)
                
                # Lấy thông tin từ robot output.xml - sử dụng thống kê từ XML
                stats = root.find('.//statistics')
                if stats is not None:
                    total = stats.find('.//total')
                    if total is not None:
                        total_stat = total.find('.//stat')
                        if total_stat is not None:
                            passed_tests = int(total_stat.get('pass', 0))
                            failed_tests = int(total_stat.get('fail', 0))
                            skipped_tests = int(total_stat.get('skip', 0))
                            total_tests = passed_tests + failed_tests + skipped_tests
                
                # Lấy thông tin thời gian từ XML
                suite = root.find('.//suite')
                if suite is not None:
                    start_time_str = suite.get('starttime')
                    end_time_str = suite.get('endtime')
                    if start_time_str and end_time_str:
                        try:
                            start_time = datetime.strptime(start_time_str, '%Y%m%d %H:%M:%S.%f')
                            end_time = datetime.strptime(end_time_str, '%Y%m%d %H:%M:%S.%f')
                            duration_seconds = int((end_time - start_time).total_seconds())
                        except ValueError:
                            pass
            except ET.ParseError as e:
                print(f"[WARNING] Failed to parse output.xml: {e}")
        
        # Luôn tạo report mới cho mỗi lần chạy execution
        report = Report(
            task_id=execution.task_id,
            task_type='execution',
            project_id=project.id,
            project_name=project.name,
            jenkins_job=job_name,
            build_number=build_number,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            duration_seconds=duration_seconds,
            start_time=start_time,
            end_time=end_time,
            status=build_result.lower() if build_result else 'completed'
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # Cập nhật status của execution theo kết quả thực tế
        if build_result == "ABORTED":
            execution.status = 'cancelled'
        elif build_result == "SUCCESS":
            execution.status = 'success'
        elif build_result == "FAILURE":
            execution.status = 'failed'
        db.commit()
        
        print(f"✅ Webhook: Đã lưu report cho execution '{execution.task_name}' - Build #{build_number}")
        
        log_backend_event("INFO", f"Webhook: Saved report for execution '{execution.task_name}' - Build #{build_number}", db)
        
        return {
            "message": f"Đã lưu report cho execution '{execution.task_name}' thành công",
            "report_id": report.id,
            "execution_id": execution.id,
            "task_id": execution.task_id,
            "project_name": project.name,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "duration_seconds": duration_seconds,
            "build_number": build_number,
            "status": report.status
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook: Lỗi kết nối Jenkins: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi kết nối Jenkins: {str(e)}"
        )

def process_cicd_webhook(cicd, job_name, build_number, build_result, body, db):
    """Xử lý webhook cho CI/CD task"""
    print(f"[DEBUG] Processing webhook for CI/CD task: {cicd.cicd_name}")
    
    # Lấy thông tin project
    project = db.query(Project).filter(Project.id == cicd.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Lấy thông tin chi tiết từ Jenkins
    JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
    
    try:
        session = requests.Session()
        
        # Lấy file output.xml để parse thông tin test (chỉ khi không phải ABORTED)
        output_xml_url = f"{JENKINS_URL}/job/{job_name}/{build_number}/robot/report/output.xml"
        xml_response = session.get(output_xml_url, timeout=30) if build_result != "ABORTED" else None
        
        # Parse thông tin từ output.xml
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        start_time = None
        end_time = None
        duration_seconds = 0
        
        # Lấy thông tin thời gian từ webhook (fallback cho ABORTED)
        if body.get('build', {}).get('timestamp'):
            start_time = datetime.fromtimestamp(body['build']['timestamp'] / 1000)
        if body.get('build', {}).get('duration'):
            duration_seconds = body['build']['duration'] // 1000
            end_time = start_time + timedelta(seconds=duration_seconds) if start_time else None
        
        if xml_response and xml_response.status_code == 200:
            try:
                root = ET.fromstring(xml_response.text)
                
                # Lấy thông tin từ robot output.xml - sử dụng thống kê từ XML
                stats = root.find('.//statistics')
                if stats is not None:
                    total = stats.find('.//total')
                    if total is not None:
                        total_stat = total.find('.//stat')
                        if total_stat is not None:
                            passed_tests = int(total_stat.get('pass', 0))
                            failed_tests = int(total_stat.get('fail', 0))
                            skipped_tests = int(total_stat.get('skip', 0))
                            total_tests = passed_tests + failed_tests + skipped_tests
                
                # Lấy thông tin thời gian từ XML
                suite = root.find('.//suite')
                if suite is not None:
                    start_time_str = suite.get('starttime')
                    end_time_str = suite.get('endtime')
                    if start_time_str and end_time_str:
                        try:
                            start_time = datetime.strptime(start_time_str, '%Y%m%d %H:%M:%S.%f')
                            end_time = datetime.strptime(end_time_str, '%Y%m%d %H:%M:%S.%f')
                            duration_seconds = int((end_time - start_time).total_seconds())
                        except ValueError:
                            pass
            except ET.ParseError as e:
                print(f"[WARNING] Failed to parse output.xml: {e}")
        
        # Luôn tạo report mới cho mỗi lần chạy cicd
        report = Report(
            task_id=cicd.cicd_id,
            task_type='cicd',
            project_id=project.id,
            project_name=project.name,
            jenkins_job=job_name,
            build_number=build_number,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            duration_seconds=duration_seconds,
            start_time=start_time,
            end_time=end_time,
            status=build_result.lower() if build_result else 'completed'
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # Cập nhật status của CI/CD task theo kết quả thực tế
        if build_result == "ABORTED":
            cicd.status = 'cancelled'
        elif build_result == "SUCCESS":
            cicd.status = 'success'
        elif build_result == "FAILURE":
            cicd.status = 'failed'
        db.commit()
        
        print(f"✅ Webhook: Đã lưu report cho CI/CD '{cicd.cicd_name}' - Build #{build_number}")
        
        log_backend_event("INFO", f"Webhook: Saved report for CI/CD '{cicd.cicd_name}' - Build #{build_number}", db)
        
        return {
            "message": f"Đã lưu report cho CI/CD '{cicd.cicd_name}' thành công",
            "report_id": report.id,
            "cicd_id": cicd.id,
            "task_id": cicd.cicd_id,
            "project_name": project.name,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "duration_seconds": duration_seconds,
            "build_number": build_number,
            "status": report.status
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook: Lỗi kết nối Jenkins: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi kết nối Jenkins: {str(e)}"
        )

def log_backend_event(level, message, db):
    """Log event to database"""
    try:
        from database import Log
        log_entry = Log(level=level, message=message, source="backend")
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"[WARNING] Failed to log event: {e}")

router = APIRouter()
 
@router.get("/", response_class=HTMLResponse)
def get_reports_page():
    """Serve the reports page"""
    try:
        file_path = "static/reports.html"
        if open(file_path, 'r', encoding='utf-8').read():
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Reports page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading reports page: {str(e)}</h1>", status_code=500)

@router.get("/dashboard-stats")
def get_dashboard_stats():
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Plan, Cicd, TestCase
            from sqlalchemy import func
            from datetime import datetime, timedelta

            # Thống kê projects
            total_projects = db.query(Project).count()
            active_projects = db.query(Project).filter(Project.status == "active").count()

            # Thống kê executions
            total_executions = db.query(Execution).count()
            running_executions = db.query(Execution).filter(Execution.status == "running").count()
            success_executions = db.query(Execution).filter(Execution.status == "success").count()
            failed_executions = db.query(Execution).filter(Execution.status == "failed").count()
            cancelled_executions = db.query(Execution).filter(Execution.status == "cancelled").count()

            # Thống kê plans
            total_plans = db.query(Plan).count()
            running_plans = db.query(Plan).filter(Plan.status == "running").count()
            success_plans = db.query(Plan).filter(Plan.status == "success").count()
            failed_plans = db.query(Plan).filter(Plan.status == "failed").count()
            cancelled_plans = db.query(Plan).filter(Plan.status == "cancelled").count()

            # Thống kê CI/CD tasks
            total_cicd = db.query(Cicd).count()
            running_cicd = db.query(Cicd).filter(Cicd.status == "running").count()
            success_cicd = db.query(Cicd).filter(Cicd.status == "success").count()
            failed_cicd = db.query(Cicd).filter(Cicd.status == "failed").count()
            cancelled_cicd = db.query(Cicd).filter(Cicd.status == "cancelled").count()

            # Tổng hợp
            total_tasks = total_executions + total_plans + total_cicd
            running_tasks = running_executions + running_plans + running_cicd
            success_tasks = success_executions + success_plans + success_cicd
            failed_tasks = failed_executions + failed_plans + failed_cicd
            cancelled_tasks = cancelled_executions + cancelled_plans + cancelled_cicd

            # Thống kê test cases đã chạy (tổng hợp từ tất cả reports)
            total_testcases = db.query(func.sum(Report.total_tests)).scalar() or 0
            active_testcases = (db.query(func.sum(Report.passed_tests)).scalar() or 0) + (db.query(func.sum(Report.failed_tests)).scalar() or 0)

            # Thống kê tasks today (theo ngày hiện tại)
            today = datetime.utcnow().date()
            executions_today = db.query(Execution).filter(func.date(Execution.created_at) == today).count()
            plans_today = db.query(Plan).filter(func.date(Plan.created_at) == today).count()
            cicd_today = db.query(Cicd).filter(func.date(Cicd.created_at) == today).count()
            tasks_today = executions_today + plans_today + cicd_today

            # Success rate
            completed_tasks = total_tasks - running_tasks
            success_rate = (success_tasks / completed_tasks * 100) if completed_tasks > 0 else 0

            return {
                "projects": {
                    "total": total_projects,
                    "active": active_projects,
                    "inactive": total_projects - active_projects
                },
                "tasks": {
                    "total": total_tasks,
                    "total_executions": total_executions,
                    "total_plans": total_plans,
                    "total_cicd": total_cicd,
                    "running": running_tasks,
                    "success": success_tasks,
                    "success_executions": success_executions,
                    "success_plans": success_plans,
                    "success_cicd": success_cicd,
                    "failed": failed_tasks,
                    "cancelled": cancelled_tasks,
                    "today": tasks_today,
                    "success_rate": round(success_rate, 2)
                },
                "testcases": {
                    "total": total_testcases,
                    "active": active_testcases
                }
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/execution-trends")
def get_execution_trends(days: int = 30):
    """Lấy xu hướng tasks dựa trên số lần thực sự chạy Jenkins job (bao gồm executions, plans, CI/CD)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Plan, Cicd
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Lấy reports theo ngày (dựa trên thời gian thực sự chạy Jenkins job)
            # Bao gồm tất cả loại tasks: executions, plans, CI/CD
            daily_reports = db.query(
                func.date(Report.created_at).label('date'),
                func.count(Report.id).label('count'),
                func.sum(func.cast(1, Integer)).filter(Report.status == "success").label('success'),
                func.sum(func.cast(1, Integer)).filter(Report.status == "failure").label('failed'),
                func.sum(func.cast(1, Integer)).filter(Report.status == "aborted").label('cancelled')
            ).filter(
                Report.created_at >= start_date,
                Report.id.isnot(None)  # Chỉ đếm những job có build number
            ).group_by(
                func.date(Report.created_at)
            ).all()
            
            # Tạo dictionary để tổng hợp dữ liệu
            daily_data = {}
            
            # Thêm reports (số lần thực sự chạy Jenkins job)
            for day in daily_reports:
                date_str = str(day.date)
                if date_str not in daily_data:
                    daily_data[date_str] = {
                        'total': 0, 'success': 0, 'failed': 0, 'cancelled': 0
                    }
                daily_data[date_str]['total'] += day.count or 0
                daily_data[date_str]['success'] += day.success or 0
                daily_data[date_str]['failed'] += day.failed or 0
                daily_data[date_str]['cancelled'] += day.cancelled or 0
            
            # Tạo danh sách đầy đủ 30 ngày
            all_dates = []
            current_date = start_date
            while current_date <= end_date:
                all_dates.append(current_date.strftime('%Y-%m-%d'))
                current_date += timedelta(days=1)
            
            # Tạo response với đầy đủ 30 ngày
            result_data = []
            for date_str in all_dates:
                if date_str in daily_data:
                    # Có dữ liệu cho ngày này
                    result_data.append({
                        "date": date_str,
                        "total": daily_data[date_str]['total'],
                        "success": daily_data[date_str]['success'],
                        "failed": daily_data[date_str]['failed'],
                        "cancelled": daily_data[date_str]['cancelled']
                    })
                else:
                    # Không có dữ liệu cho ngày này
                    result_data.append({
                        "date": date_str,
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "cancelled": 0
                    })
            
            return {
                "period": f"Last {days} days",
                "data": result_data
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/project-performance")
def get_project_performance():
    """Lấy hiệu suất của các projects (bao gồm executions, plans và CI/CD)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Plan, Cicd
            
            # Lấy tất cả projects
            projects = db.query(Project).all()
            result = []
            
            for project in projects:
                # Thống kê executions cho project này
                execution_stats = db.query(
                    func.count(Execution.id).label('total_executions'),
                    func.sum(func.cast(1, Integer)).filter(Execution.status == "success").label('execution_success'),
                    func.sum(func.cast(1, Integer)).filter(Execution.status == "failed").label('execution_failed'),
                    func.sum(func.cast(1, Integer)).filter(Execution.status == "cancelled").label('execution_cancelled'),
                    func.sum(func.cast(1, Integer)).filter(Execution.status == "running").label('execution_running')
                ).filter(
                    Execution.project_id == project.id
                ).first()
                
                # Thống kê plans cho project này
                plan_stats = db.query(
                    func.count(Plan.id).label('total_plans'),
                    func.sum(func.cast(1, Integer)).filter(Plan.status == "success").label('plan_success'),
                    func.sum(func.cast(1, Integer)).filter(Plan.status == "failed").label('plan_failed'),
                    func.sum(func.cast(1, Integer)).filter(Plan.status == "cancelled").label('plan_cancelled'),
                    func.sum(func.cast(1, Integer)).filter(Plan.status == "running").label('plan_running')
                ).filter(
                    Plan.project_id == project.id
                ).first()
                
                # Thống kê CI/CD tasks cho project này
                cicd_stats = db.query(
                    func.count(Cicd.id).label('total_cicd'),
                    func.sum(func.cast(1, Integer)).filter(Cicd.status == "success").label('cicd_success'),
                    func.sum(func.cast(1, Integer)).filter(Cicd.status == "failed").label('cicd_failed'),
                    func.sum(func.cast(1, Integer)).filter(Cicd.status == "cancelled").label('cicd_cancelled'),
                    func.sum(func.cast(1, Integer)).filter(Cicd.status == "running").label('cicd_running')
                ).filter(
                    Cicd.project_id == project.id
                ).first()
                
                # Tổng hợp thống kê
                total_executions = execution_stats.total_executions or 0
                total_plans = plan_stats.total_plans or 0
                total_cicd = cicd_stats.total_cicd or 0
                total_tasks = total_executions + total_plans + total_cicd
                
                # Tổng hợp status
                total_success = (execution_stats.execution_success or 0) + (plan_stats.plan_success or 0) + (cicd_stats.cicd_success or 0)
                total_failed = (execution_stats.execution_failed or 0) + (plan_stats.plan_failed or 0) + (cicd_stats.cicd_failed or 0)
                total_cancelled = (execution_stats.execution_cancelled or 0) + (plan_stats.plan_cancelled or 0) + (cicd_stats.cicd_cancelled or 0)
                total_running = (execution_stats.execution_running or 0) + (plan_stats.plan_running or 0) + (cicd_stats.cicd_running or 0)
                
                # Tính success rate: success / (total - running) * 100
                # Loại trừ running vì chưa hoàn thành
                completed_total = total_tasks - total_running
                success_rate = (total_success / completed_total * 100) if completed_total > 0 else 0
                
                result.append({
                    "project_id": project.id,
                    "project_name": project.name,
                    "total_tasks": total_tasks,
                    "total_executions": total_executions,
                    "total_plans": total_plans,
                    "total_cicd": total_cicd,
                    "success": total_success,
                    "failed": total_failed,
                    "cancelled": total_cancelled,
                    "running": total_running,
                    "success_rate": round(success_rate, 2)
                })
            
            return {"projects": result}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/task-reports")
def get_task_reports(project_id: Optional[int] = None, status: Optional[str] = None):
    """Lấy danh sách report của các task (bao gồm cả executions, plans và CI/CD tasks)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Plan, Cicd
            
            result = []
            
            # Lấy executions
            query = db.query(Execution, Project.name.label('project_name'))
            
            if project_id:
                query = query.filter(Execution.project_id == project_id)
            if status:
                query = query.filter(Execution.status == status)
            
            executions = query.join(Project, Execution.project_id == Project.id).all()
            
            for exe, project_name in executions:
                # Lấy report gần nhất KHÔNG PHẢI cancelled/aborted
                from database import Report
                reports = db.query(Report).filter(Report.task_id == exe.task_id).order_by(Report.created_at.desc()).all()
                report = None
                if reports:
                    if reports[0].status in ["cancelled", "aborted"]:
                        for r in reports:
                            if r.status not in ["cancelled", "aborted"]:
                                report = r
                                break
                        if not report:
                            report = reports[0]
                    else:
                        report = reports[0]
                # Tạo report data cho execution
                report_data = {
                    "id": exe.id,
                    "task_id": exe.task_id,
                    "task_name": exe.task_name,
                    "project_name": project_name,
                    "status": exe.status,
                    "jenkins_job": exe.jenkins_job,
                    "created_at": exe.created_at.isoformat() if exe.created_at else None,
                    "report_url": f"/executions/{exe.id}/results",
                    "log_url": f"/jenkins/job/{exe.jenkins_job}/lastBuild/console" if exe.jenkins_job else None,
                    "last_run": report.created_at.isoformat() if report and report.created_at else None,
                    "build_number": report.build_number if report else None,
                    "test_results": {
                        "passed": report.passed_tests if report else 0,
                        "failed": report.failed_tests if report else 0,
                        "skipped": report.skipped_tests if report else 0
                    },
                    "type": "execution"
                }
                result.append(report_data)
            
            # Lấy plans
            plan_query = db.query(Plan, Project.name.label('project_name'))
            
            if project_id:
                plan_query = plan_query.filter(Plan.project_id == project_id)
            if status:
                plan_query = plan_query.filter(Plan.status == status)
            
            plans = plan_query.join(Project, Plan.project_id == Project.id).all()
            
            for plan, project_name in plans:
                from database import Report
                reports = db.query(Report).filter(Report.task_id == plan.plan_id).order_by(Report.created_at.desc()).all()
                report = None
                if reports:
                    if reports[0].status in ["cancelled", "aborted"]:
                        for r in reports:
                            if r.status not in ["cancelled", "aborted"]:
                                report = r
                                break
                        if not report:
                            report = reports[0]
                    else:
                        report = reports[0]
                report_data = {
                    "id": plan.id,
                    "task_id": plan.plan_id,
                    "task_name": plan.plan_name,
                    "project_name": project_name,
                    "status": plan.status,
                    "jenkins_job": plan.jenkins_job,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None,
                    "report_url": f"/plans/{plan.id}/results",  # API endpoint cho plans
                    "log_url": f"/jenkins/job/{plan.jenkins_job}/lastBuild/console" if plan.jenkins_job else None,
                    "last_run": report.created_at.isoformat() if report and report.created_at else None,
                    "build_number": report.build_number if report else None,
                    "test_results": {
                        "passed": report.passed_tests if report else 0,
                        "failed": report.failed_tests if report else 0,
                        "skipped": report.skipped_tests if report else 0
                    },
                    "type": "plan",  # Đánh dấu đây là plan
                    "schedule_time": plan.schedule_time  # Thêm thông tin cron schedule
                }
                result.append(report_data)
            
            # Lấy CI/CD tasks
            cicd_query = db.query(Cicd, Project.name.label('project_name'))
            
            if project_id:
                cicd_query = cicd_query.filter(Cicd.project_id == project_id)
            if status:
                cicd_query = cicd_query.filter(Cicd.status == status)
            
            cicd_tasks = cicd_query.join(Project, Cicd.project_id == Project.id).all()
            
            for cicd, project_name in cicd_tasks:
                from database import Report
                reports = db.query(Report).filter(Report.task_id == cicd.cicd_id).order_by(Report.created_at.desc()).all()
                report = None
                if reports:
                    if reports[0].status in ["cancelled", "aborted"]:
                        for r in reports:
                            if r.status not in ["cancelled", "aborted"]:
                                report = r
                                break
                        if not report:
                            report = reports[0]
                    else:
                        report = reports[0]
                report_data = {
                    "id": cicd.id,
                    "task_id": f"CICD-{cicd.id:03d}",
                    "task_name": cicd.cicd_name,
                    "project_name": project_name,
                    "status": cicd.status,
                    "jenkins_job": cicd.jenkins_job,
                    "created_at": cicd.created_at.isoformat() if cicd.created_at else None,
                    "report_url": f"/cicd/{cicd.id}/results",  # API endpoint cho CI/CD tasks
                    "log_url": f"/jenkins/job/{cicd.jenkins_job}/lastBuild/console" if cicd.jenkins_job else None,
                    "last_run": report.created_at.isoformat() if report and report.created_at else None,
                    "build_number": report.build_number if report else None,
                    "test_results": {
                        "passed": report.passed_tests if report else 0,
                        "failed": report.failed_tests if report else 0,
                        "skipped": report.skipped_tests if report else 0
                    },
                    "type": "cicd",  # Đánh dấu đây là CI/CD task
                    "cicd_type": cicd.cicd_type  # Thêm thông tin loại CI/CD
                }
                result.append(report_data)
            
            return {"reports": result, "count": len(result)}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/testcase-stats")
def get_testcase_stats():
    """Lấy thống kê test cases"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Thống kê test cases theo project
            testcase_stats = db.query(
                Project.name,
                func.count(TestCase.id).label('total_tests'),
                func.sum(func.cast(1, Integer)).filter(TestCase.status == "active").label('active'),
                func.sum(func.cast(1, Integer)).filter(TestCase.priority == "high").label('high_priority')
            ).outerjoin(
                TestCase, Project.id == TestCase.project_id
            ).group_by(
                Project.name
            ).all()
            
            result = []
            for stat in testcase_stats:
                result.append({
                    "project_name": stat.name,
                    "total_tests": stat.total_tests or 0,
                    "active": stat.active or 0,
                    "high_priority": stat.high_priority or 0
                })
            
            return {"testcases": result}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.get("/test")
def test_endpoint():
    """Test endpoint"""
    return {"message": "Reports router is working"}

@router.get("/test-parse-xml")
def test_parse_xml():
    """Test endpoint để kiểm tra logic parse XML"""
    try:
        import xml.etree.ElementTree as ET
        import requests
        
        # Lấy XML từ Jenkins
        JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
        output_xml_url = f"{JENKINS_URL}/job/GW040-NS/lastBuild/robot/report/output.xml"
        
        response = requests.get(output_xml_url, timeout=30)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            # Cách 1: Đếm thủ công
            manual_count = 0
            for test in root.findall('.//test'):
                manual_count += 1
            
            # Cách 2: Sử dụng thống kê
            stats_count = 0
            stats = root.find('.//statistics')
            if stats is not None:
                total = stats.find('.//total')
                if total is not None:
                    total_stat = total.find('.//stat')
                    if total_stat is not None:
                        pass_count = int(total_stat.get('pass', 0))
                        fail_count = int(total_stat.get('fail', 0))
                        skip_count = int(total_stat.get('skip', 0))
                        stats_count = pass_count + fail_count + skip_count
            
            return {
                "manual_count": manual_count,
                "stats_count": stats_count,
                "pass_count": int(total_stat.get('pass', 0)) if total_stat else 0,
                "fail_count": int(total_stat.get('fail', 0)) if total_stat else 0,
                "skip_count": int(total_stat.get('skip', 0)) if total_stat else 0
            }
        else:
            return {"error": f"Không thể lấy XML: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

@router.get("/list")
def get_reports_list():
    """Lấy danh sách tất cả reports từ database"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report, Execution, Plan, Cicd, Project
            
            # Lấy tất cả reports với thông tin execution, plan, CI/CD và project
            reports = db.query(Report).all()
            result = []
            
            for report in reports:
                # Lấy thông tin project
                project = db.query(Project).filter(Project.id == report.project_id).first()
                
                # Lấy thông tin task dựa trên task_id
                task_name = "N/A"
                if report.task_id.startswith("CICD-"):
                    # Lấy thông tin CI/CD task
                    cicd_id = int(report.task_id.split("-")[1])
                    cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
                    task_name = cicd_task.cicd_name if cicd_task else "N/A"
                elif report.task_id.startswith("PLAN-"):
                    # Lấy thông tin plan
                    plan = db.query(Plan).filter(Plan.plan_id == report.task_id).first()
                    task_name = plan.plan_name if plan else "N/A"
                else:
                    # Lấy thông tin execution (mặc định)
                    execution = db.query(Execution).filter(Execution.task_id == report.task_id).first()
                    task_name = execution.task_name if execution else "N/A"
                
                result.append({
                    "id": report.id,
                    "execution_id": report.execution_id,
                    "task_id": report.task_id,
                    "task_type": report.task_type,
                    "task_name": task_name,
                    "project_id": report.project_id,
                    "project_name": report.project_name,
                    "total_tests": report.total_tests,
                    "passed_tests": report.passed_tests,
                    "failed_tests": report.failed_tests,
                    "skipped_tests": report.skipped_tests,
                    "success_rate": round((report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0, 2),
                    "start_time": report.start_time.isoformat() if report.start_time else None,
                    "end_time": report.end_time.isoformat() if report.end_time else None,
                    "duration_seconds": report.duration_seconds,
                    "duration_formatted": f"{report.duration_seconds // 60}m {report.duration_seconds % 60}s" if report.duration_seconds else "N/A",
                    "build_number": report.build_number,
                    "jenkins_job": report.jenkins_job,
                    "status": report.status,
                    "created_at": report.created_at.isoformat() if report.created_at else None
                })
            
            return {
                "reports": result,
                "count": len(result)
            }
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error getting reports list: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/jenkins/save-report/{task_id}")
def save_jenkins_report(task_id: str):
    """Lưu kết quả report từ Jenkins vào database cho tất cả loại task (executions, plans, CI/CD)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Execution, Plan, Cicd, Project, Report
            
            # Xác định loại task dựa trên task_id format
            task_type = None
            task = None
            project = None
            
            if task_id.startswith('TASK'):
                # Execution task
                task = db.query(Execution).filter(Execution.task_id == task_id).first()
                if task:
                    task_type = 'execution'
                    project = db.query(Project).filter(Project.id == task.project_id).first()
            elif task_id.startswith('PLAN'):
                # Plan task
                task = db.query(Plan).filter(Plan.plan_id == task_id).first()
                if task:
                    task_type = 'plan'
                    project = db.query(Project).filter(Project.id == task.project_id).first()
            elif task_id.startswith('CICD'):
                # CI/CD task
                # Extract ID from CICD-001 format
                try:
                    cicd_id = int(task_id.split('-')[1])
                    task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
                    if task:
                        task_type = 'cicd'
                        project = db.query(Project).filter(Project.id == task.project_id).first()
                except (ValueError, IndexError):
                    pass
            
            if not task:
                raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
            
            if not task.jenkins_job:
                raise HTTPException(status_code=400, detail="Task không có Jenkins job được cấu hình")
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Cấu hình Jenkins
            JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
            
            # Lấy thông tin build cuối cùng
            last_build_url = f"{JENKINS_URL}/job/{task.jenkins_job}/lastBuild/api/json"
            
            print(f"[DEBUG] {task_type.title()} {task_id}: jenkins_job={task.jenkins_job}")
            print(f"[DEBUG] {task_type.title()} {task_id}: last_build_url={last_build_url}")
            
            try:
                session = requests.Session()
                response = session.get(last_build_url, timeout=30)
                
                if response.status_code == 200:
                    build_info = response.json()
                    build_number = build_info.get('number')
                    build_result = build_info.get('result')
                    building = build_info.get('building', False)
                    
                    print(f"[DEBUG] Build info: number={build_number}, result={build_result}, building={building}")
                    print(f"[DEBUG] Build URL: {build_info.get('url', 'N/A')}")
                    print(f"[DEBUG] Expected job: {task.jenkins_job}")
                    
                    if building:
                        raise HTTPException(status_code=400, detail="Jenkins job đang chạy, chưa có kết quả")
                    
                    # Lấy file output.xml để parse thông tin test
                    output_xml_url = f"{JENKINS_URL}/job/{task.jenkins_job}/lastBuild/robot/report/output.xml"
                    xml_response = session.get(output_xml_url, timeout=30)
                    
                    # Parse thông tin từ output.xml
                    total_tests = 0
                    passed_tests = 0
                    failed_tests = 0
                    skipped_tests = 0
                    start_time = None
                    end_time = None
                    duration_seconds = 0
                    
                    if xml_response.status_code == 200:
                        try:
                            root = ET.fromstring(xml_response.text)
                            
                            # Lấy thông tin từ robot output.xml - sử dụng thống kê từ XML
                            stats = root.find('.//statistics')
                            if stats is not None:
                                total = stats.find('.//total')
                                if total is not None:
                                    total_stat = total.find('.//stat')
                                    if total_stat is not None:
                                        passed_tests = int(total_stat.get('pass', 0))
                                        failed_tests = int(total_stat.get('fail', 0))
                                        skipped_tests = int(total_stat.get('skip', 0))
                                        total_tests = passed_tests + failed_tests + skipped_tests
                            
                            # Lấy thông tin thời gian
                            stats = root.find('.//statistics')
                            if stats is not None:
                                total = stats.find('.//total')
                                if total is not None:
                                    start_time_str = total.get('starttime')
                                    end_time_str = total.get('endtime')
                                    
                                    if start_time_str:
                                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                    if end_time_str:
                                        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                                    
                                    if start_time and end_time:
                                        duration_seconds = int((end_time - start_time).total_seconds())
                            
                        except ET.ParseError as e:
                            print(f"Error parsing XML: {e}")
                            # Fallback: sử dụng thông tin từ Jenkins build
                            if build_info.get('timestamp'):
                                start_time = datetime.fromtimestamp(build_info['timestamp'] / 1000)
                            if build_info.get('duration'):
                                duration_seconds = build_info['duration'] // 1000
                                end_time = start_time + timedelta(seconds=duration_seconds) if start_time else None
                    
                    # Fallback: nếu build_number là None, thử lấy từ body['build']['full_url'] hoặc từ job_name + lastBuild nếu cần.
                    if not build_number:
                        # Thử lấy từ build.full_url (nếu có dạng .../job/JOBNAME/123/)
                        full_url = body.get('build', {}).get('full_url')
                        if full_url:
                            import re
                            m = re.search(r'/job/[^/]+/(\d+)/', full_url)
                            if m:
                                build_number = int(m.group(1))
                        # Nếu vẫn không có, thử lấy từ Jenkins API (lastBuild)
                        if not build_number:
                            try:
                                JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
                                last_build_url = f"{JENKINS_URL}/job/{task.jenkins_job}/lastBuild/api/json"
                                session = requests.Session()
                                response = session.get(last_build_url, timeout=10)
                                if response.status_code == 200:
                                    build_info = response.json()
                                    build_number = build_info.get('number')
                            except Exception as e:
                                print(f"[WARNING] Fallback get build_number from Jenkins API failed: {e}")
                    
                    # Kiểm tra xem report đã tồn tại chưa
                    existing_report = db.query(Report).filter(
                        Report.task_id == task_id,
                        Report.id == build_number
                    ).first()
                    
                    print(f"[DEBUG] Checking existing report: task_id={task_id}, build_number={build_number}")
                    if existing_report:
                        print(f"[DEBUG] Found existing report: id={existing_report.id}, task_id={existing_report.task_id}, jenkins_job={existing_report.jenkins_job}")
                    else:
                        print(f"[DEBUG] No existing report found, will create new one")
                    
                    if existing_report:
                        # Cập nhật report hiện có
                        existing_report.total_tests = total_tests
                        existing_report.passed_tests = passed_tests
                        existing_report.failed_tests = failed_tests
                        existing_report.skipped_tests = skipped_tests
                        existing_report.start_time = start_time
                        existing_report.end_time = end_time
                        existing_report.duration_seconds = duration_seconds
                        existing_report.status = build_result.lower() if build_result else 'completed'
                        existing_report.created_at = datetime.utcnow()
                        
                        db.commit()
                        report = existing_report
                    else:
                        # Tạo report mới
                        print(f"[DEBUG] Creating new report: task_id={task_id}, jenkins_job={task.jenkins_job}")
                        print(f"[DEBUG] Report will be created with: task_id={task_id}, jenkins_job={task.jenkins_job}, build_number={build_number}")
                        
                        # Xác định execution_id dựa trên loại task
                        execution_id = None
                        if task_type == 'execution':
                            execution_id = task.id
                        elif task_type == 'plan':
                            execution_id = task.id
                        elif task_type == 'cicd':
                            execution_id = task.id
                        
                        new_report = Report(
                            execution_id=execution_id,
                            task_id=task_id,
                            project_id=task.project_id,
                            project_name=project.name,
                            total_tests=total_tests,
                            passed_tests=passed_tests,
                            failed_tests=failed_tests,
                            skipped_tests=skipped_tests,
                            start_time=start_time,
                            end_time=end_time,
                            duration_seconds=duration_seconds,
                            build_number=build_number,
                            jenkins_job=task.jenkins_job,
                            status=build_result.lower() if build_result else 'completed'
                        )
                        
                        db.add(new_report)
                        db.commit()
                        db.refresh(new_report)
                        report = new_report
                    
                    # Cập nhật status của task thành 'success' khi có report (dù pass hay fail)
                    task.status = 'success'
                    db.commit()
                    
                    # Xác định task name dựa trên loại task
                    task_name = None
                    if task_type == 'execution':
                        task_name = task.task_name
                    elif task_type == 'plan':
                        task_name = task.plan_name
                    elif task_type == 'cicd':
                        task_name = task.cicd_name
                    
                    return {
                        "message": f"Đã lưu report cho {task_type} '{task_name}' thành công",
                        "report_id": report.id,
                        "task_id": task_id,
                        "task_type": task_type,
                        "project_name": project.name,
                        "total_tests": total_tests,
                        "passed_tests": passed_tests,
                        "failed_tests": failed_tests,
                        "skipped_tests": skipped_tests,
                        "duration_seconds": duration_seconds,
                        "build_number": build_number,
                        "status": report.status
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
                
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error saving Jenkins report: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")




@router.get("/jenkins/file/{job_name}/{file_name}")
def get_jenkins_file(job_name: str, file_name: str):
    """Proxy để lấy file từ Jenkins robot report"""
    try:
        jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080")
        url = f"{jenkins_url}/job/{job_name}/lastBuild/robot/report/{file_name}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get('content-type', 'text/plain'),
                headers={
                    'Content-Disposition': f'attachment; filename=\"{file_name}\"'
                }
            )
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Không thể lấy file từ Jenkins: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi kết nối Jenkins: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi server: {str(e)}"
        )

@router.get("/jenkins/view/{job_name}/{build_number}/{file_name}")
def view_jenkins_file(job_name: str, build_number: str, file_name: str):
    """Proxy để xem file từ Jenkins robot report"""
    try:
        jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080")
        url = f"{jenkins_url}/job/{job_name}/{build_number}/robot/report/{file_name}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', 'text/plain')
            if 'html' in content_type:
                return HTMLResponse(content=response.text)
            else:
                return HTMLResponse(content=f"<pre>{response.text}</pre>")
        else:
            return HTMLResponse(
                content=f"<h1>Lỗi</h1><p>Không thể lấy file từ Jenkins: {response.status_code}</p>",
                status_code=response.status_code
            )
    except requests.exceptions.RequestException as e:
        return HTMLResponse(
            content=f"<h1>Lỗi</h1><p>Lỗi kết nối Jenkins: {str(e)}</p>",
            status_code=500
        )
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Lỗi</h1><p>Lỗi server: {str(e)}</p>",
            status_code=500
        ) 

@router.post("/jenkins/webhook")
async def jenkins_webhook(request: Request):
    """Webhook endpoint để nhận thông báo từ Jenkins khi job hoàn thành"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Plan, Execution, Project, Report, Cicd
            
            # Lấy request body
            body = await request.json()
            
            print(f"[DEBUG] Received Jenkins webhook: {body}")
            
            log_backend_event("INFO", f"Received Jenkins webhook: {body}", db)
            
            # Parse thông tin từ Jenkins webhook
            job_name = body.get('name')  # Tên job Jenkins
            build_number = body.get('build', {}).get('number')
            build_result = body.get('build', {}).get('result')
            build_status = body.get('build', {}).get('status')
            
            if not job_name or not build_number:
                raise HTTPException(status_code=400, detail="Missing required fields: name, build.number")
            
            print(f"[DEBUG] Processing webhook for job: {job_name}")
            
            # Tìm tất cả task có cùng jenkins_job name (KHÔNG ưu tiên, lấy hết)
            cicds = db.query(Cicd).filter(Cicd.jenkins_job == job_name).all()
            plans = db.query(Plan).filter(Plan.jenkins_job == job_name).all()
            executions = db.query(Execution).filter(Execution.jenkins_job == job_name).all()

            processed_tasks = []
            for cicd_task in cicds:
                processed_tasks.append(('cicd', cicd_task))
            for plan_task in plans:
                processed_tasks.append(('plan', plan_task))
            for exec_task in executions:
                processed_tasks.append(('execution', exec_task))
            
            results = []
            
            # Xử lý khi job hoàn thành (SUCCESS, FAILURE, ABORTED)
            if build_status == "FINISHED" and (build_result == "SUCCESS" or build_result == "FAILURE" or build_result == "ABORTED"):
                for task_type, task in processed_tasks:
                    try:
                        if task_type == 'plan':
                            result = process_plan_webhook(task, job_name, build_number, build_result, body, db)
                            results.append(result)
                        elif task_type == 'execution':
                            result = process_execution_webhook(task, job_name, build_number, build_result, body, db)
                            results.append(result)
                        elif task_type == 'cicd':
                            result = process_cicd_webhook(task, job_name, build_number, build_result, body, db)
                            results.append(result)
                    except Exception as e:
                        print(f"[ERROR] Failed to process {task_type} task: {e}")
                        results.append({"error": f"Failed to process {task_type} task: {str(e)}"})
                
                # Trả về kết quả của task đầu tiên (hoặc tất cả nếu cần)
                if results:
                    return results[0] if len(results) == 1 else {"message": f"Processed {len(results)} tasks", "results": results}
                else:
                    return {"message": "No tasks processed"}
            else:
                print(f"[DEBUG] Webhook: Job {job_name} chưa hoàn thành hoặc thất bại")
                return {"message": "Job chưa hoàn thành hoặc thất bại"}
                    
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Error processing Jenkins webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.get("/latest-test-results")
def get_latest_test_results():
    """Lấy thống kê kết quả test theo report mới nhất của mỗi task (hiển thị đủ tất cả task, kể cả chưa có report)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report, Execution, Plan, Cicd, Project
            from sqlalchemy import func
            # Lấy tất cả executions, plans, cicd
            executions = db.query(Execution).all()
            plans = db.query(Plan).all()
            cicds = db.query(Cicd).all()
            all_tasks = []
            for exe in executions:
                all_tasks.append({
                    "type": "execution",
                    "task_id": exe.task_id,
                    "task_name": exe.task_name,
                    "project_name": db.query(Project).filter(Project.id == exe.project_id).first().name if exe.project_id else None
                })
            for plan in plans:
                all_tasks.append({
                    "type": "plan",
                    "task_id": plan.plan_id,
                    "task_name": plan.plan_name,
                    "project_name": db.query(Project).filter(Project.id == plan.project_id).first().name if plan.project_id else None
                })
            for cicd in cicds:
                all_tasks.append({
                    "type": "cicd",
                    "task_id": cicd.cicd_id,
                    "task_name": cicd.cicd_name,
                    "project_name": db.query(Project).filter(Project.id == cicd.project_id).first().name if cicd.project_id else None
                })
            # Lấy report mới nhất cho từng task_id
            # Nếu report mới nhất bị cancelled/aborted thì lấy report gần nhất trước đó có status success/failed
            latest_reports_data = []
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0
            for task in all_tasks:
                # Lấy tất cả report của task, mới nhất trước
                reports = db.query(Report).filter(Report.task_id == task["task_id"]).order_by(Report.created_at.desc()).all()
                report = None
                if reports:
                    # Nếu report mới nhất bị cancelled/aborted thì tìm report gần nhất trước đó có status success/failed
                    if reports[0].status in ["cancelled", "aborted"]:
                        for r in reports:
                            if r.status not in ["cancelled", "aborted"]:
                                report = r
                                break
                        if not report:
                            report = reports[0]  # Nếu không có report thành công nào thì vẫn lấy report mới nhất
                    else:
                        report = reports[0]
                if report:
                    total_tests += report.total_tests
                    passed_tests += report.passed_tests
                    failed_tests += report.failed_tests
                    skipped_tests += report.skipped_tests
                    task_data = {
                        "id": report.id,
                        "task_info": {
                            "type": task["type"],
                            "task_id": task["task_id"],
                            "task_name": task["task_name"],
                            "project_name": task["project_name"]
                        },
                        "total_tests": report.total_tests,
                        "passed_tests": report.passed_tests,
                        "failed_tests": report.failed_tests,
                        "skipped_tests": report.skipped_tests,
                        "success_rate": round((report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0, 2),
                        "created_at": report.created_at.isoformat() if report.created_at else None,
                        "jenkins_job": report.jenkins_job,
                        "build_number": report.build_number,
                        "has_report": True
                    }
                else:
                    task_data = {
                        "id": None,
                        "task_info": {
                            "type": task["type"],
                            "task_id": task["task_id"],
                            "task_name": task["task_name"],
                            "project_name": task["project_name"]
                        },
                        "total_tests": 0,
                        "passed_tests": 0,
                        "failed_tests": 0,
                        "skipped_tests": 0,
                        "success_rate": 0,
                        "created_at": None,
                        "jenkins_job": None,
                        "build_number": None,
                        "has_report": False
                    }
                latest_reports_data.append(task_data)
            success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
            return {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "skipped_tests": skipped_tests,
                "success_rate": round(success_rate, 2),
                "latest_reports": latest_reports_data
            }
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error getting latest test results: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 

@router.get("/task-history/{task_id}")
def get_task_history(task_id: str):
    """Lấy lịch sử reports của một task để hiển thị xu hướng success rate"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report
            
            # Lấy tất cả reports của task, sắp xếp theo thời gian
            reports = db.query(Report).filter(
                Report.task_id == task_id
            ).order_by(Report.created_at.asc()).all()
            
            if not reports:
                return {
                    "task_id": task_id,
                    "history": [],
                    "message": f"Không có lịch sử reports cho task {task_id}"
                }
            
            history = []
            for report in reports:
                success_rate = (report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0
                history.append({
                    "report_id": report.id,
                    "build_number": report.build_number,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                    "success_rate": round(success_rate, 2),
                    "total_tests": report.total_tests,
                    "passed_tests": report.passed_tests,
                    "failed_tests": report.failed_tests,
                    "skipped_tests": report.skipped_tests,
                    "duration_seconds": report.duration_seconds,
                    "status": report.status
                })
            
            return {
                "task_id": task_id,
                "history": history,
                "count": len(history)
            }
            
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error getting task history: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.delete("/cleanup-task-reports/{task_id}")
def cleanup_task_reports(task_id: str):
    """Xóa tất cả reports cũ của một task để tạo lại với logic đúng"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report
            
            # Tìm và xóa tất cả reports của task
            reports_to_delete = db.query(Report).filter(Report.task_id == task_id).all()
            
            if not reports_to_delete:
                return {"message": f"Không tìm thấy reports nào cho task {task_id}"}
            
            deleted_count = len(reports_to_delete)
            report_ids = [r.id for r in reports_to_delete]
            
            # Xóa reports
            for report in reports_to_delete:
                db.delete(report)
            
            db.commit()
            
            return {
                "message": f"Đã xóa {deleted_count} reports cũ cho task {task_id}",
                "deleted_report_ids": report_ids,
                "task_id": task_id
            }
            
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error cleaning up task reports: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.delete("/reset-all-reports")
def reset_all_reports():
    """Xóa tất cả reports khỏi database"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report
            
            # Đếm số reports trước khi xóa
            total_reports = db.query(Report).count()
            
            if total_reports == 0:
                return {"message": "Không có reports nào để xóa"}
            
            # Xóa tất cả reports
            db.query(Report).delete()
            db.commit()
            
            # Reset sequence về 1
            db.execute(text("ALTER SEQUENCE reports_id_seq RESTART WITH 1"))
            db.commit()
            
            return {
                "message": f"Đã xóa thành công {total_reports} reports khỏi database và reset ID sequence",
                "deleted_count": total_reports
            }
            
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error resetting all reports: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.delete("/cleanup-orphaned-reports")
def cleanup_orphaned_reports():
    """Xóa tất cả reports của task CI/CD đã bị xóa khỏi database"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report, Cicd
            
            # Lấy tất cả task_id từ reports có task_type = 'cicd'
            cicd_reports = db.query(Report.task_id).filter(Report.task_type == 'cicd').distinct().all()
            
            orphaned_reports = []
            total_deleted = 0
            
            for (task_id,) in cicd_reports:
                # Kiểm tra xem task CI/CD có còn tồn tại không
                if task_id.startswith('CICD-'):
                    try:
                        # Extract ID từ CICD-001 format
                        cicd_id = int(task_id.split('-')[1])
                        cicd_task = db.query(Cicd).filter(Cicd.id == cicd_id).first()
                        
                        if not cicd_task:
                            # Task CI/CD đã bị xóa, xóa tất cả reports của task này
                            deleted_count = db.query(Report).filter(Report.task_id == task_id).delete()
                            orphaned_reports.append({
                                "task_id": task_id,
                                "deleted_count": deleted_count
                            })
                            total_deleted += deleted_count
                    except (ValueError, IndexError):
                        # Format không đúng, xóa reports này
                        deleted_count = db.query(Report).filter(Report.task_id == task_id).delete()
                        orphaned_reports.append({
                            "task_id": task_id,
                            "deleted_count": deleted_count,
                            "reason": "Invalid format"
                        })
                        total_deleted += deleted_count
            
            db.commit()
            
            return {
                "message": f"Đã xóa {total_deleted} reports của task CI/CD đã bị xóa",
                "total_deleted": total_deleted,
                "orphaned_reports": orphaned_reports
            }
            
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error cleaning up orphaned reports: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.get("/history-reports")
def get_history_reports(
    project_id: Optional[int] = None,
    task_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Lấy lịch sử reports với filter theo project, task type, và date range"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from database import Report, Project, Execution, Plan, Cicd
            
            # Base query
            query = db.query(Report)
            
            # Filter theo project
            if project_id:
                query = query.filter(Report.project_id == project_id)
            
            # Filter theo task type
            if task_type:
                if task_type == "executions":
                    query = query.filter(Report.task_id.like("EXEC-%"))
                elif task_type == "plans":
                    query = query.filter(Report.task_id.like("PLAN-%"))
                elif task_type == "cicd":
                    query = query.filter(Report.task_id.like("CICD-%"))
            
            # Filter theo date range
            if start_date:
                try:
                    start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Report.created_at >= start_datetime)
                except ValueError:
                    pass
            
            if end_date:
                try:
                    end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                    query = query.filter(Report.created_at < end_datetime)
                except ValueError:
                    pass
            
            # Sắp xếp theo thời gian mới nhất
            query = query.order_by(Report.created_at.desc())
            
            # Giới hạn số lượng
            query = query.limit(limit)
            
            reports = query.all()
            
            # Format kết quả
            history_data = []
            for report in reports:
                # Lấy thông tin project
                project = db.query(Project).filter(Project.id == report.project_id).first()
                
                # Xác định loại task và lấy thông tin task
                task_info = None
                task_name = "Unknown Task"
                
                if report.task_id.startswith("EXEC-"):
                    task_info = db.query(Execution).filter(Execution.task_id == report.task_id).first()
                    if task_info:
                        task_name = task_info.task_name
                elif report.task_id.startswith("PLAN-"):
                    task_info = db.query(Plan).filter(Plan.plan_id == report.task_id).first()
                    if task_info:
                        task_name = task_info.plan_name
                elif report.task_id.startswith("CICD-"):
                    task_info = db.query(Cicd).filter(Cicd.cicd_id == report.task_id).first()
                    if task_info:
                        task_name = task_info.cicd_name
                elif report.task_id.startswith("TASK-"):
                    # TASK-001 là execution task
                    task_info = db.query(Execution).filter(Execution.task_id == report.task_id).first()
                    if task_info:
                        task_name = task_info.task_name
                
                # Tính success rate
                success_rate = (report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0
                
                # Lấy Jenkins job name từ task info
                jenkins_job = "Unknown"
                if task_info:
                    if report.task_id.startswith("EXEC-") or report.task_id.startswith("TASK-"):
                        jenkins_job = task_info.jenkins_job or "Unknown"
                    elif report.task_id.startswith("PLAN-"):
                        jenkins_job = task_info.jenkins_job or "Unknown"
                    elif report.task_id.startswith("CICD-"):
                        jenkins_job = task_info.jenkins_job or "Unknown"
                
                history_data.append({
                    "report_id": report.id,
                    "task_id": report.task_id,
                    "task_name": task_name,
                    "project_name": project.name if project else "Unknown Project",
                    "project_id": report.project_id,
                    "jenkins_job": jenkins_job,
                    "build_number": report.build_number,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                    "start_time": report.start_time.isoformat() if report.start_time else None,
                    "end_time": report.end_time.isoformat() if report.end_time else None,
                    "duration_seconds": report.duration_seconds,
                    "total_tests": report.total_tests,
                    "passed_tests": report.passed_tests,
                    "failed_tests": report.failed_tests,
                    "skipped_tests": report.skipped_tests,
                    "success_rate": round(success_rate, 2),
                    "status": report.status,
                    "task_type": "executions" if report.task_id.startswith("EXEC-") or report.task_id.startswith("TASK-") else 
                                "plans" if report.task_id.startswith("PLAN-") else 
                                "cicd" if report.task_id.startswith("CICD-") else "unknown"
                })
            
            return {
                "history_reports": history_data,
                "total_count": len(history_data),
                "filters": {
                    "project_id": project_id,
                    "task_type": task_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit
                }
            }
            
        finally:
            db.close()
    except Exception as e:
        print(f"[DEBUG] Error getting history reports: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 