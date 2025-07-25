from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import logging

from routes.auth import router as auth_router, get_current_user
from routes.logout import router as logout_router
from routes.dashboard import router as dashboard_router
from routes.projects import router as projects_router
from routes.test import router as test_router
from routes.executions import router as executions_router
from routes.plans import router as plans_router
from routes.reports import router as reports_router
from routes.log import router as logs_router
from routes.cicd import router as cicd_router
from database import test_connection, create_tables

app = FastAPI(
    title="TestOps API",
    description="TestOps - Test Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files from backend/static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(logout_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
app.include_router(projects_router, prefix="/api/projects", tags=["Projects"])
app.include_router(test_router, prefix="/api/projects", tags=["Test"])
app.include_router(executions_router, prefix="/api/executions", tags=["Executions"])
app.include_router(plans_router, prefix="/api/plans", tags=["Plans"])
app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
app.include_router(logs_router, prefix="/api/logs", tags=["Logs"])
app.include_router(cicd_router, prefix="/api/cicd", tags=["CICD"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "TestOps API is running"}

@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the main dashboard page"""
    try:
        file_path = "static/dashboard.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Dashboard page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading dashboard: {str(e)}</h1>", status_code=500)

@app.get("/projects", response_class=HTMLResponse)
def projects_page():
    """Serve the projects page"""
    try:
        file_path = "static/projects.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Projects page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading projects: {str(e)}</h1>", status_code=500)

@app.get("/tests", response_class=HTMLResponse)
def tests_page():
    """Serve the tests page"""
    try:
        file_path = "static/tests.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Tests page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading tests: {str(e)}</h1>", status_code=500)

@app.get("/executions", response_class=HTMLResponse)
def executions_page():
    """Serve the executions page"""
    try:
        file_path = "static/executions.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Executions page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading executions: {str(e)}</h1>", status_code=500)

@app.get("/plans", response_class=HTMLResponse)
def plans_page():
    """Serve the plans page"""
    try:
        file_path = "static/plans.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Plans page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading plans: {str(e)}</h1>", status_code=500)


@app.get("/results", response_class=HTMLResponse)
def results_page():
    """Serve the results page"""
    try:
        file_path = "static/results.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Results page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading results: {str(e)}</h1>", status_code=500)

@app.get("/reports", response_class=HTMLResponse)
def reports_page():
    """Serve the reports page"""
    try:
        file_path = "static/reports.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Reports page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading reports: {str(e)}</h1>", status_code=500)

@app.get("/logs", response_class=HTMLResponse)
def logs_page():
    """Serve the logs page"""
    try:
        file_path = "static/log.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Logs page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading logs: {str(e)}</h1>", status_code=500)

@app.get("/cicd", response_class=HTMLResponse)
def cicd_page():
    """Serve the CI/CD page"""
    try:
        file_path = "static/cicd.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>CI/CD page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading CI/CD: {str(e)}</h1>", status_code=500)



@app.get("/login", response_class=HTMLResponse)
def login_page():
    """Serve the login page"""
    try:
        file_path = "static/login.html"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading login: {str(e)}</h1>", status_code=500)

@app.post("/github-webhook/")
async def github_webhook(request: Request):
    payload = await request.json()
    logging.warning(f"[GitHub Webhook] Nhận payload: {payload}")
    return {"status": "ok"}

@app.get("/db-test")
async def test_db():
    """Test database connection"""
    is_connected = test_connection()
    return {
        "database_connected": is_connected,
        "message": "Database connection test completed"
    }

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("🚀 Starting TestOps API...")
    
    # Test database connection
    if test_connection():
        # Create tables if they don't exist
        create_tables()
        print("✅ Database tables created/verified")
    else:
        print("⚠️ Database connection failed - some features may not work")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 
    # uvicorn main:app --host 0.0.0.0 --port 8000 --reload