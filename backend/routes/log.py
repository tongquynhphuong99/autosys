from fastapi import APIRouter, Depends, HTTPException, Query, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging
import os

from database import get_db, Log

router = APIRouter()

# Configure logging for backend
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_backend_event(level: str, message: str, db: Session):
    """Log backend events to database"""
    try:
        log_entry = Log(
            level=level.upper(),
            message=message,
            source="backend",
            created_at=datetime.now(timezone.utc)
        )
        db.add(log_entry)
        db.commit()
        
        # Also log to file
        if level.upper() == "ERROR":
            logger.error(message)
        elif level.upper() == "WARNING":
            logger.warning(message)
        elif level.upper() == "DEBUG":
            logger.debug(message)
        else:
            logger.info(message)
            
    except Exception as e:
        logger.error(f"Failed to log to database: {e}")

@router.get("/")
def get_logs(
    db: Session = Depends(get_db),
    source: Optional[str] = Query(None, description="Filter by source: 'backend' or 'jenkins'"),
    level: Optional[str] = Query(None, description="Filter by level: 'INFO', 'WARNING', 'ERROR', 'DEBUG'"),
    limit: int = Query(100, description="Number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip")
):
    """Get logs with optional filtering"""
    try:
        query = db.query(Log)
        
        # Apply filters
        if source:
            query = query.filter(Log.source == source)
        if level:
            query = query.filter(Log.level == level.upper())
        
        # Order by most recent first
        query = query.order_by(desc(Log.created_at))
        
        # Apply pagination
        total = query.count()
        logs = query.offset(offset).limit(limit).all()
        
        # Convert to dict format
        log_list = []
        for log in logs:
            log_list.append({
                "id": log.id,
                "level": log.level,
                "message": log.message,
                "source": log.source,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "created_at_local": log.created_at.astimezone(timezone(timedelta(hours=7))).isoformat() if log.created_at else None
            })
        
        return {
            "logs": log_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        log_backend_event("ERROR", f"Failed to get logs: {str(e)}", db)
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@router.post("/backend")
def add_backend_log(
    level: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    """Add a backend system log"""
    try:
        if level.upper() not in ["INFO", "WARNING", "ERROR", "DEBUG"]:
            raise HTTPException(status_code=400, detail="Invalid log level")
        
        log_backend_event(level, message, db)
        
        return {"message": "Backend log added successfully"}
        
    except Exception as e:
        logger.error(f"Failed to add backend log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add backend log: {str(e)}")

@router.post("/jenkins")
def add_jenkins_log(
    level: str = Form(...),
    message: str = Form(...),
    job_name: Optional[str] = Form(None),
    build_number: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Add a Jenkins job log"""
    try:
        if level.upper() not in ["INFO", "WARNING", "ERROR", "DEBUG"]:
            raise HTTPException(status_code=400, detail="Invalid log level")
        
        # Enhance message with Jenkins context
        enhanced_message = message
        if job_name:
            enhanced_message = f"[{job_name}] {message}"
        if build_number:
            enhanced_message = f"[{job_name}#{build_number}] {message}"
        
        log_entry = Log(
            level=level.upper(),
            message=enhanced_message,
            source="jenkins",
            created_at=datetime.now(timezone.utc)
        )
        db.add(log_entry)
        db.commit()
        
        return {"message": "Jenkins log added successfully"}
        
    except Exception as e:
        logger.error(f"Failed to add Jenkins log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add Jenkins log: {str(e)}")

@router.get("/stats")
def get_log_stats(db: Session = Depends(get_db)):
    """Get log statistics"""
    try:
        # Total logs by source
        backend_count = db.query(Log).filter(Log.source == "backend").count()
        jenkins_count = db.query(Log).filter(Log.source == "jenkins").count()
        
        # Logs by level
        info_count = db.query(Log).filter(Log.level == "INFO").count()
        warning_count = db.query(Log).filter(Log.level == "WARNING").count()
        error_count = db.query(Log).filter(Log.level == "ERROR").count()
        debug_count = db.query(Log).filter(Log.level == "DEBUG").count()
        
        # Recent logs (last 24 hours)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_count = db.query(Log).filter(Log.created_at >= yesterday).count()
        
        return {
            "total_logs": backend_count + jenkins_count,
            "by_source": {
                "backend": backend_count,
                "jenkins": jenkins_count
            },
            "by_level": {
                "info": info_count,
                "warning": warning_count,
                "error": error_count,
                "debug": debug_count
            },
            "recent_24h": recent_count
        }
        
    except Exception as e:
        log_backend_event("ERROR", f"Failed to get log stats: {str(e)}", db)
        raise HTTPException(status_code=500, detail=f"Failed to get log stats: {str(e)}")

@router.delete("/")
def clear_logs(
    source: Optional[str] = Query(None, description="Clear logs by source"),
    older_than_days: Optional[int] = Query(None, description="Clear logs older than X days"),
    db: Session = Depends(get_db)
):
    """Clear logs with optional filtering"""
    try:
        query = db.query(Log)
        
        if source:
            query = query.filter(Log.source == source)
        
        if older_than_days:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            query = query.filter(Log.created_at < cutoff_date)
        
        deleted_count = query.count()
        query.delete()
        db.commit()
        
        log_backend_event("INFO", f"Cleared {deleted_count} logs", db)
        
        return {"message": f"Cleared {deleted_count} logs"}
        
    except Exception as e:
        log_backend_event("ERROR", f"Failed to clear logs: {str(e)}", db)
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {str(e)}")

# Initialize with some sample logs
@router.post("/init")
def initialize_sample_logs(db: Session = Depends(get_db)):
    """Initialize with sample logs for demonstration"""
    try:
        sample_logs = [
            {"level": "INFO", "message": "TestOps system started", "source": "backend"},
            {"level": "INFO", "message": "Database connection established", "source": "backend"},
            {"level": "INFO", "message": "Jenkins job 'TestTrigger' started", "source": "jenkins"},
            {"level": "INFO", "message": "Test execution completed successfully", "source": "jenkins"},
            {"level": "WARNING", "message": "High memory usage detected", "source": "backend"},
            {"level": "ERROR", "message": "Failed to connect to external service", "source": "backend"},
        ]
        
        for log_data in sample_logs:
            log_entry = Log(**log_data, created_at=datetime.utcnow())
            db.add(log_entry)
        
        db.commit()
        
        return {"message": "Sample logs initialized"}
        
    except Exception as e:
        logger.error(f"Failed to initialize sample logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize sample logs: {str(e)}")
