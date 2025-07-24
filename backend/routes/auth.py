from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import bcrypt
import os
import base64
import json
from datetime import datetime, timedelta

router = APIRouter()
security = HTTPBearer()

# JWT Configuration
SECRET_KEY = "testops-secret-key-2024"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Sample user data (in real app, this would come from database)
USER_DATA = {
    "admin": {
        "id": 1,
        "username": "admin",
        "full_name": "Admin",
        "password_hash": "$2b$12$4D8xh9S2DDQL929c5yppauWjUSVloXgl3ZrkQ5.gqTaRPq64ANXSu"  # testops123
    }
}

# Data models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserInfo(BaseModel):
    id: int
    username: str
    full_name: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def authenticate_user(username: str, password: str):
    """Authenticate user with username and password"""
    print(f"Attempting login for username: {username}")
    
    if username not in USER_DATA:
        print(f"Username {username} not found in USER_DATA")
        return None
    
    user = USER_DATA[username]
    print(f"User found: {user['username']}")
    
    is_valid = verify_password(password, user["password_hash"])
    print(f"Password verification result: {is_valid}")
    
    if not is_valid:
        print("Password verification failed")
        return None
    
    print("Authentication successful")
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create simple token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire.isoformat()})
    token_data = json.dumps(to_encode)
    encoded_token = base64.b64encode(token_data.encode()).decode()
    return encoded_token

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from token"""
    try:
        token = credentials.credentials
        token_data = base64.b64decode(token).decode()
        payload = json.loads(token_data)
        
        # Check expiration
        exp_str = payload.get("exp")
        if exp_str:
            exp_time = datetime.fromisoformat(exp_str)
            if datetime.utcnow() > exp_time:
                raise HTTPException(status_code=401, detail="Token expired")
        
        username: str = payload.get("sub")
        if username is None or username not in USER_DATA:
            raise HTTPException(status_code=401, detail="Invalid token")
        return USER_DATA[username]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# Serve login page
@router.get("/login", response_class=HTMLResponse)
def get_login_page():
    """Serve the login page"""
    try:
        file_path = "../frontend/public/login.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading login page: {str(e)}</h1>", status_code=500)

# Login endpoint
@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest):
    """Authenticate user and return JWT token"""
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"]
        }
    }

# Get current user info
@router.get("/me", response_model=UserInfo)
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"]
    }

# Logout endpoint (client-side token removal)
@router.post("/logout")
def logout():
    """Logout endpoint (client should remove token)"""
    return {"message": "Logged out successfully"}

# Check if user is authenticated
@router.get("/check")
def check_auth(current_user: dict = Depends(get_current_user)):
    """Check if user is authenticated"""
    return {"authenticated": True, "user": current_user} 