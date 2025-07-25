from sqlalchemy import text
from sqlalchemy.orm import Session

def reset_report_sequence(db: Session):
    """
    Reset ID sequence của bảng reports để bắt đầu từ số nhỏ nhất còn lại trong database
    """
    try:
        # Tìm ID lớn nhất hiện tại trong bảng reports
        result = db.execute(text("SELECT MAX(id) FROM reports"))
        max_id = result.scalar()
        
        if max_id is None:
            # Nếu không có report nào, reset sequence về 1
            db.execute(text("ALTER SEQUENCE reports_id_seq RESTART WITH 1"))
        else:
            # Reset sequence về số tiếp theo sau ID lớn nhất
            db.execute(text(f"ALTER SEQUENCE reports_id_seq RESTART WITH {max_id + 1}"))
        
        db.commit()
        print(f"[DEBUG] Reset reports sequence to start from {max_id + 1 if max_id else 1}")
        
    except Exception as e:
        print(f"[DEBUG] Error resetting reports sequence: {e}")
        db.rollback()
        raise 