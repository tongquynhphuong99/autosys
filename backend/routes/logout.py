from fastapi import APIRouter

router = APIRouter()

@router.post("/logout")
def logout():
    """Logout endpoint (client should remove token)"""
    return {"message": "Logged out successfully"}
