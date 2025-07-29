import smtplib
import os
import requests
import msal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict
import logging

router = APIRouter()

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp-mail.outlook.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self.username = os.getenv("EMAIL_USERNAME", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.from_email = os.getenv("EMAIL_FROM", "")
        
        # Microsoft Graph API settings
        self.client_id = os.getenv("MS_CLIENT_ID", "")
        self.client_secret = os.getenv("MS_CLIENT_SECRET", "")
        self.tenant_id = os.getenv("MS_TENANT_ID", "")
        self.use_graph_api = bool(self.client_id and self.client_secret and self.tenant_id)
        
        # Debug: Print configuration
        print(f"[DEBUG] Email config - Server: {self.smtp_server}, Port: {self.smtp_port}")
        print(f"[DEBUG] Email config - Username: {self.username}")
        print(f"[DEBUG] Email config - Password: {'*' * len(self.password) if self.password else 'NOT SET'}")
        print(f"[DEBUG] Email config - From: {self.from_email}")
        print(f"[DEBUG] Graph API - Client ID: {self.client_id}")
        print(f"[DEBUG] Graph API - Tenant ID: {self.tenant_id}")
        print(f"[DEBUG] Use Graph API: {self.use_graph_api}")
        
        # Test configuration
        if not self.username or not self.password:
            print("[WARNING] Email credentials not configured. Email service will not work.")
    
    def test_connection(self) -> Dict:
        """Test SMTP connection"""
        try:
            if self.use_graph_api:
                return self._test_graph_api_connection()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.username, self.password)
                server.quit()
                return {"success": True, "message": "SMTP connection successful"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_graph_api_connection(self) -> Dict:
        """Test Microsoft Graph API connection"""
        try:
            # Get access token
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            scopes = ["https://graph.microsoft.com/.default"]
            
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=authority,
                client_credential=self.client_secret
            )
            
            result = app.acquire_token_for_client(scopes=scopes)
            
            if "access_token" in result:
                return {"success": True, "message": "Graph API connection successful"}
            else:
                return {"success": False, "error": f"Failed to get token: {result.get('error_description', 'Unknown error')}"}
                
        except Exception as e:
            return {"success": False, "error": f"Graph API error: {str(e)}"}
    
    def download_file_from_jenkins(self, jenkins_url: str, job_name: str, build_number: str, file_name: str) -> Optional[str]:
        """Download file from Jenkins and save locally"""
        try:
            file_url = f"{jenkins_url}/job/{job_name}/{build_number}/robot/report/{file_name}"
            print(f"[DEBUG] Downloading file: {file_url}")
            
            response = requests.get(file_url, timeout=30)
            if response.status_code == 200:
                # Save file temporarily
                temp_file_path = f"/tmp/{job_name}_{build_number}_{file_name}"
                with open(temp_file_path, 'wb') as f:
                    f.write(response.content)
                print(f"[DEBUG] File saved: {temp_file_path}")
                return temp_file_path
            else:
                print(f"[DEBUG] Failed to download {file_name}: {response.status_code}")
                return None
        except Exception as e:
            print(f"[DEBUG] Error downloading {file_name}: {e}")
            return None
    
    def send_task_report_email(self, task_data: Dict) -> Dict:
        """Gửi email report với attachments từ Jenkins"""
        try:
            # Validate required fields
            required_fields = ['task_id', 'task_name', 'project_name', 'result', 'job_name', 'build_number', 'recipients']
            for field in required_fields:
                if field not in task_data:
                    return {"success": False, "error": f"Missing required field: {field}"}
            
            # Test connection first
            connection_test = self.test_connection()
            if not connection_test["success"]:
                return connection_test
            
            # Download files from Jenkins
            jenkins_url = os.getenv("JENKINS_URL", "http://localhost:8080")
            job_name = task_data['job_name']
            build_number = task_data['build_number']
            
            files_to_download = ["output.xml", "report.html", "log.html"]
            downloaded_files = []
            
            for file_name in files_to_download:
                file_path = self.download_file_from_jenkins(jenkins_url, job_name, build_number, file_name)
                if file_path:
                    downloaded_files.append(file_path)
                else:
                    print(f"[WARNING] Could not download {file_name}")
            
            # Send email based on method
            if self.use_graph_api:
                return self._send_email_via_graph_api(task_data, downloaded_files)
            else:
                return self._send_email_via_smtp(task_data, downloaded_files)
            
        except Exception as e:
            print(f"[ERROR] Failed to send email: {e}")
            return {"success": False, "error": str(e)}
    
    def _send_email_via_smtp(self, task_data: Dict, downloaded_files: List[str]) -> Dict:
        """Send email via SMTP"""
        try:
            # Lấy thông tin team từ database nếu có
            from database import SessionLocal
            db = SessionLocal()
            try:
                # Tìm project để lấy thông tin team
                from database import Project
                project = db.query(Project).filter(Project.id == task_data.get('project_id')).first()
                
                if project:
                    task_data['project_manager'] = getattr(project, 'project_manager', 'Chưa cập nhật')
                    # Xử lý members array thành string
                    members = getattr(project, 'members', [])
                    if members and isinstance(members, list):
                        task_data['team_members'] = ', '.join(members)
                    else:
                        task_data['team_members'] = 'Chưa cập nhật'
                else:
                    task_data['project_manager'] = 'Chưa cập nhật'
                    task_data['team_members'] = 'Chưa cập nhật'
            except Exception as e:
                print(f"Lỗi khi lấy thông tin team: {e}")
                task_data['project_manager'] = 'Chưa cập nhật'
                task_data['team_members'] = 'Chưa cập nhật'
            finally:
                db.close()
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.from_email or self.username
            msg['To'] = ", ".join(task_data['recipients'])
            msg['Subject'] = f"[TestOps] Task {task_data['task_id']} - {task_data['result']}"
            
            # Create HTML body
            html_body = self.create_email_template(task_data)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            for file_path in downloaded_files:
                try:
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        msg.attach(part)
                    print(f"[DEBUG] Added attachment: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"[ERROR] Failed to attach {file_path}: {e}")
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            # Clean up temporary files
            for file_path in downloaded_files:
                try:
                    os.remove(file_path)
                except:
                    pass
            
            return {
                "success": True, 
                "message": f"Email sent successfully to {len(task_data['recipients'])} recipients",
                "attachments_count": len(downloaded_files)
            }
            
        except Exception as e:
            return {"success": False, "error": f"SMTP error: {str(e)}"}
    
    def _send_email_via_graph_api(self, task_data: Dict, downloaded_files: List[str]) -> Dict:
        """Send email via Microsoft Graph API"""
        try:
            # Lấy thông tin team từ database nếu có
            from database import SessionLocal
            db = SessionLocal()
            try:
                # Tìm project để lấy thông tin team
                from database import Project
                project = db.query(Project).filter(Project.id == task_data.get('project_id')).first()
                
                if project:
                    task_data['project_manager'] = getattr(project, 'project_manager', 'Chưa cập nhật')
                    # Xử lý members array thành string
                    members = getattr(project, 'members', [])
                    if members and isinstance(members, list):
                        task_data['team_members'] = ', '.join(members)
                    else:
                        task_data['team_members'] = 'Chưa cập nhật'
                else:
                    task_data['project_manager'] = 'Chưa cập nhật'
                    task_data['team_members'] = 'Chưa cập nhật'
            except Exception as e:
                print(f"Lỗi khi lấy thông tin team: {e}")
                task_data['project_manager'] = 'Chưa cập nhật'
                task_data['team_members'] = 'Chưa cập nhật'
            finally:
                db.close()
            
            # Get access token
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            scopes = ["https://graph.microsoft.com/.default"]
            
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=authority,
                client_credential=self.client_secret
            )
            
            result = app.acquire_token_for_client(scopes=scopes)
            
            if "access_token" not in result:
                return {"success": False, "error": f"Failed to get token: {result.get('error_description', 'Unknown error')}"}
            
            access_token = result["access_token"]
            
            # Prepare email data
            subject = f"[TestOps] Task {task_data['task_id']} - {task_data['result']}"
            html_body = self.create_email_template(task_data)
            
            # Create email message
            email_data = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": html_body
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": recipient}}
                        for recipient in task_data['recipients']
                    ]
                }
            }
            
            # Add attachments if any
            if downloaded_files:
                email_data["message"]["attachments"] = []
                for file_path in downloaded_files:
                    try:
                        with open(file_path, "rb") as f:
                            file_content = f.read()
                            import base64
                            encoded_content = base64.b64encode(file_content).decode('utf-8')
                            
                            attachment = {
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": os.path.basename(file_path),
                                "contentType": "application/octet-stream",
                                "contentBytes": encoded_content
                            }
                            email_data["message"]["attachments"].append(attachment)
                    except Exception as e:
                        print(f"[ERROR] Failed to prepare attachment {file_path}: {e}")
            
            # Send email via Graph API
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Use the sender's email address
            sender_email = self.username
            graph_url = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
            
            response = requests.post(graph_url, headers=headers, json=email_data)
            
            # Clean up temporary files
            for file_path in downloaded_files:
                try:
                    os.remove(file_path)
                except:
                    pass
            
            if response.status_code == 202:
                return {
                    "success": True,
                    "message": f"Email sent successfully to {len(task_data['recipients'])} recipients",
                    "attachments_count": len(downloaded_files)
                }
            else:
                return {
                    "success": False,
                    "error": f"Graph API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
                            return {"success": False, "error": f"Graph API error: {str(e)}"}
    

    
    def create_email_template(self, task_data: Dict) -> str:
        """Tạo HTML template cho email với thiết kế hiện đại"""
        # Tính toán kết quả dựa trên testcase
        total_tests = task_data.get('total', 0)
        passed_tests = task_data.get('passed', 0)
        failed_tests = total_tests - passed_tests
        
        # Logic kết quả: PASSED nếu tất cả testcase passed, FAILED nếu có bất kỳ testcase failed
        if total_tests == 0:
            result = "NO_TESTS"
            result_text = "Không có testcase"
            result_color = "#6c757d"
            result_icon = "⚠️"
        elif failed_tests == 0:
            result = "PASSED"
            result_text = "PASSED"
            result_color = "#28a745"
            result_icon = "✅"
        else:
            result = "FAILED"
            result_text = "FAILED"
            result_color = "#dc3545"
            result_icon = "❌"
        
        # Tính toán thông tin testcase
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Chuyển đổi múi giờ từ UTC sang UTC+7
        def convert_to_vietnam_time(utc_time_str):
            if utc_time_str == 'N/A':
                return 'N/A'
            try:
                from datetime import datetime, timedelta
                utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')
                vietnam_time = utc_time + timedelta(hours=7)
                return vietnam_time.strftime('%d/%m/%Y %H:%M:%S')
            except:
                return utc_time_str
        
        start_time_vn = convert_to_vietnam_time(task_data.get('start_time', 'N/A'))
        end_time_vn = convert_to_vietnam_time(task_data.get('end_time', 'N/A'))
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TestOps Task Report</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                
                .email-container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                    position: relative;
                }}
                
                .header::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="1" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }}
                
                .header h1 {{
                    font-size: 2.5em;
                    font-weight: 700;
                    margin-bottom: 10px;
                    position: relative;
                    z-index: 1;
                }}
                
                .header .status {{
                    font-size: 1.2em;
                    font-weight: 600;
                    opacity: 0.9;
                    position: relative;
                    z-index: 1;
                }}
                
                .status-badge {{
                    display: inline-block;
                    background: {result_color};
                    color: white;
                    padding: 8px 20px;
                    border-radius: 25px;
                    font-weight: 600;
                    font-size: 1.1em;
                    margin-top: 15px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                    position: relative;
                    z-index: 1;
                }}
                
                .content {{
                    padding: 40px 30px;
                }}
                
                .section {{
                    margin-bottom: 40px;
                }}
                
                .section-title {{
                    font-size: 1.4em;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                
                .info-card {{
                    background: #f8f9fa;
                    border-radius: 15px;
                    padding: 25px;
                    border-left: 5px solid #667eea;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                    transition: transform 0.3s ease;
                }}
                
                .info-card:hover {{
                    transform: translateY(-2px);
                }}
                
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 0;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .info-row:last-child {{
                    border-bottom: none;
                }}
                
                .info-label {{
                    font-weight: 600;
                    color: #555;
                    font-size: 0.95em;
                }}
                
                .info-value {{
                    font-weight: 500;
                    color: #333;
                    text-align: right;
                }}
                

                
                .stat-number {{
                    font-size: 2.5em;
                    font-weight: 700;
                    margin-bottom: 5px;
                }}
                
                .stat-label {{
                    font-size: 0.9em;
                    color: #666;
                    font-weight: 500;
                }}
                
                .passed {{ color: #28a745; }}
                .failed {{ color: #dc3545; }}
                .total {{ color: #6c757d; }}
                .rate {{ color: #667eea; }}
                

                
                .footer {{
                    background: #f8f9fa;
                    padding: 30px;
                    text-align: center;
                    border-top: 1px solid #e9ecef;
                }}
                
                .attachments {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin-top: 20px;
                    box-shadow: 0 3px 10px rgba(0,0,0,0.08);
                }}
                
                .attachment-list {{
                    list-style: none;
                    padding: 0;
                }}
                
                .attachment-list li {{
                    padding: 8px 0;
                    border-bottom: 1px solid #e9ecef;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                
                .attachment-list li:last-child {{
                    border-bottom: none;
                }}
                
                .attachment-icon {{
                    color: #667eea;
                    font-size: 1.2em;
                }}
                
                @media (max-width: 768px) {{
                    .info-grid {{
                        grid-template-columns: 1fr;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>📊 TestOps Report</h1>
                    <div class="status">{result_icon} {result_text}</div>
                    <div class="status-badge">{task_data['task_id']}</div>
                </div>
                
                <div class="content">
                    <div class="section">
                        <div class="section-title">📋 Thông tin Task</div>
                        <div class="info-grid">
                            <div class="info-card">
                                <div class="info-row">
                                    <span class="info-label">Tên Task:</span>
                                    <span class="info-value">{task_data['task_name']}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Dự án:</span>
                                    <span class="info-value">{task_data['project_name']}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Project Manager:</span>
                                    <span class="info-value">{task_data.get('project_manager', 'Chưa cập nhật')}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Team Members:</span>
                                    <span class="info-value">{task_data.get('team_members', 'Chưa cập nhật')}</span>
                                </div>
                            </div>
                            
                            <div class="info-card">
                                <div class="info-row">
                                    <span class="info-label">Jenkins Job:</span>
                                    <span class="info-value">{task_data['job_name']}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Build Number:</span>
                                    <span class="info-value">#{task_data['build_number']}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Thời gian bắt đầu:</span>
                                    <span class="info-value">{start_time_vn}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Thời gian kết thúc:</span>
                                    <span class="info-value">{end_time_vn}</span>
                                </div>
                            </div>
                            
                            <div class="info-card">
                                <div class="info-row">
                                    <span class="info-label">Thời gian chạy:</span>
                                    <span class="info-value">{task_data.get('duration', 'N/A')} giây</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Kết quả:</span>
                                    <span class="info-value" style="color: {result_color}; font-weight: bold;">{result_text}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Tổng số testcase:</span>
                                    <span class="info-value">{total_tests}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Testcase passed:</span>
                                    <span class="info-value" style="color: #28a745; font-weight: bold;">{passed_tests}</span>
                                </div>
                            </div>
                            
                            <div class="info-card">
                                <div class="info-row">
                                    <span class="info-label">Testcase failed:</span>
                                    <span class="info-value" style="color: #dc3545; font-weight: bold;">{failed_tests}</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Tỷ lệ passed:</span>
                                    <span class="info-value" style="color: #28a745; font-weight: bold;">{pass_rate:.1f}%</span>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">Tỷ lệ failed:</span>
                                    <span class="info-value" style="color: #dc3545; font-weight: bold;">{(100 - pass_rate):.1f}%</span>
                                </div>

                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">📎 File đính kèm</div>
                        <div class="attachments">
                            <ul class="attachment-list">
                                <li>
                                    <span class="attachment-icon">📄</span>
                                    <span>output.xml - Kết quả test chi tiết</span>
                                </li>
                                <li>
                                    <span class="attachment-icon">📊</span>
                                    <span>report.html - Báo cáo HTML</span>
                                </li>
                                <li>
                                    <span class="attachment-icon">📝</span>
                                    <span>log.html - Log chi tiết</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <div class="footer">
                    <p style="color: #666; font-size: 0.9em; margin-bottom: 10px;">
                        Email được gửi tự động từ TestOps System
                    </p>
                    <p style="color: #999; font-size: 0.8em;">
                        © 2025 TestOps - Automated Testing Platform
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

# API endpoints
@router.get("/test-connection")
async def test_email_connection():
    """Test email connection"""
    email_service = EmailService()
    return email_service.test_connection()

@router.post("/send-task-report")
async def send_task_report_email(task_data: Dict):
    """Gửi email report cho task"""
    email_service = EmailService()
    return email_service.send_task_report_email(task_data)

@router.get("/config")
async def get_email_config():
    """Lấy cấu hình email (không bao gồm password)"""
    return {
        "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp-mail.outlook.com"),
        "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
        "username": os.getenv("EMAIL_USERNAME", ""),
        "from_email": os.getenv("EMAIL_FROM", ""),
        "configured": bool(os.getenv("EMAIL_USERNAME") and os.getenv("EMAIL_PASSWORD")),
        "use_graph_api": bool(os.getenv("MS_CLIENT_ID") and os.getenv("MS_CLIENT_SECRET") and os.getenv("MS_TENANT_ID")),
        "client_id": os.getenv("MS_CLIENT_ID", ""),
        "tenant_id": os.getenv("MS_TENANT_ID", "")
    } 