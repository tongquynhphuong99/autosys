from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from sqlalchemy import func
from database import SessionLocal, Project, Execution, TestCase, Report, Plan, Cicd

router = APIRouter()
 
@router.get("/dashboard")
def get_dashboard():
    """Lấy thống kê tổng quan cho dashboard"""
    try:
        db = SessionLocal()
        try:
            # Thống kê projects
            total_projects = db.query(Project).count()
            active_projects = db.query(Project).filter(Project.status == "active").count()
            
            # Thống kê test cases đã chạy (tổng hợp từ tất cả reports)
            total_testcases = db.query(func.sum(Report.total_tests)).scalar() or 0
            active_testcases = (db.query(func.sum(Report.passed_tests)).scalar() or 0) + (db.query(func.sum(Report.failed_tests)).scalar() or 0)
            
            # Thống kê test runs completed hôm nay (dựa trên reports thực tế)
            today = datetime.utcnow().date()
            
            # Đếm reports được tạo hôm nay (test runs thực tế)
            reports_today = db.query(Report).filter(
                func.date(Report.created_at) == today
            ).count()
            
            # Đếm executions được tạo hôm nay (để tham khảo)
            executions_today = db.query(Execution).filter(
                func.date(Execution.created_at) == today
            ).count()
            
            # Đếm plans được tạo hôm nay (để tham khảo)
            plans_today = db.query(Plan).filter(
                func.date(Plan.created_at) == today
            ).count()
            
            # Đếm CI/CD tasks được tạo hôm nay (để tham khảo)
            cicd_today = db.query(Cicd).filter(
                func.date(Cicd.created_at) == today
            ).count()
            
            # Tổng test runs completed hôm nay
            total_tasks_today = reports_today
            
            # Thống kê success rate từ report gần nhất
            latest_report = db.query(Report).order_by(Report.created_at.desc()).first()
            
            if latest_report:
                success_rate = round((latest_report.passed_tests / latest_report.total_tests * 100) if latest_report.total_tests > 0 else 0, 1)
            else:
                success_rate = 0
            
            return {
                "active_projects": active_projects,
                "total_projects": total_projects,
                "total_testcases": total_testcases,
                "active_testcases": active_testcases,
                "reports_today": reports_today,
                "executions_today": executions_today,
                "plans_today": plans_today,
                "cicd_today": cicd_today,
                "total_tasks_today": total_tasks_today,
                "success_rate": success_rate,
                "latest_report_id": latest_report.id if latest_report else None
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 