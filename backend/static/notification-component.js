// Notification Component JavaScript
class NotificationComponent {
    constructor() {
        this.notifications = [];
        this.unreadCount = 0;
        this.isDropdownOpen = false;
        this.init();
    }

    init() {
        this.createNotificationHTML();
        this.bindEvents();
        this.loadNotifications();
        this.startAutoRefresh();
    }

    createNotificationHTML() {
        const notificationHTML = `
            <div class="notification-container">
                <button class="notification-bell" id="notificationBell">
                    🔔
                    <div class="notification-badge" id="notificationBadge" style="display: none;">0</div>
                </button>
                <div class="notification-dropdown" id="notificationDropdown">
                    <div class="notification-header">
                        <h3>🔔 Thông báo</h3>
                        <div class="notification-actions">
                            <button class="notification-btn" onclick="notificationComponent.markAllAsRead()">✓ Tất cả</button>
                            <button class="notification-btn" data-tooltip="Làm mới" onclick="notificationComponent.refreshNotifications()">🔄</button>
                            <button class="notification-btn" data-tooltip="Xóa tất cả" onclick="notificationComponent.clearAllNotifications()">🗑️</button>
                        </div>
                    </div>
                    <div class="notification-list" id="notificationList">
                        <div class="notification-loading">
                            <div class="notification-spinner"></div>
                            <p>Đang tải...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Tìm user-info và chèn notification bell vào đó
        const userInfo = document.querySelector('.user-info');
        if (userInfo) {
            // Chèn notification bell vào trước logout button
            const logoutBtn = userInfo.querySelector('.logout-btn');
            if (logoutBtn) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = notificationHTML;
                userInfo.insertBefore(tempDiv.firstElementChild, logoutBtn);
            } else {
                userInfo.insertAdjacentHTML('beforeend', notificationHTML);
            }
        } else {
            // Fallback: chèn vào body nếu không tìm thấy user-info
            document.body.insertAdjacentHTML('beforeend', notificationHTML);
        }
    }

    bindEvents() {
        const bell = document.getElementById('notificationBell');
        const dropdown = document.getElementById('notificationDropdown');
        
        // Toggle dropdown
        bell.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown();
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && !bell.contains(e.target)) {
                this.closeDropdown();
            }
        });
        
        // Close dropdown on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeDropdown();
            }
        });
    }

    toggleDropdown() {
        const dropdown = document.getElementById('notificationDropdown');
        this.isDropdownOpen = !this.isDropdownOpen;
        
        if (this.isDropdownOpen) {
            dropdown.classList.add('show');
            this.loadNotifications(); // Refresh when opening
        } else {
            dropdown.classList.remove('show');
        }
    }

    closeDropdown() {
        const dropdown = document.getElementById('notificationDropdown');
        dropdown.classList.remove('show');
        this.isDropdownOpen = false;
    }

    async loadNotifications() {
        try {
            const response = await fetch('/api/reports/notifications/list?limit=10');
            if (!response.ok) {
                if (response.status === 401) {
                    // Session hết hạn, chuyển về login mà không hiển thị lỗi
                    window.location.href = '/login';
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.notifications = data.notifications;
            this.unreadCount = data.unread_count;
            
            this.updateBadge();
            this.renderNotifications();
            
        } catch (error) {
            console.error('Error loading notifications:', error);
            // Chỉ hiển thị lỗi nếu không phải lỗi 401
            if (!error.message.includes('401')) {
                this.showError('Lỗi tải thông báo');
            }
        }
    }

    updateBadge() {
        const badge = document.getElementById('notificationBadge');
        if (this.unreadCount > 0) {
            badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }

    renderNotifications() {
        const list = document.getElementById('notificationList');
        
        if (this.notifications.length === 0) {
            list.innerHTML = `
                <div class="notification-empty">
                    <div class="icon">🔔</div>
                    <h4>Không có thông báo</h4>
                    <p>Tất cả thông báo đã được đọc</p>
                </div>
            `;
            return;
        }
        
        list.innerHTML = this.notifications.map(notification => `
            <div class="notification-item ${notification.is_read ? '' : 'unread'}" 
                 onclick="notificationComponent.markAsRead(${notification.id})">
                <div class="notification-content">
                    ${notification.message}
                </div>
                <div class="notification-meta">
                    <div>
                        <span class="notification-status ${notification.status}">
                            ${this.getStatusText(notification.status)}
                        </span>
                        <span>${notification.task_id}</span>
                    </div>
                    <div class="notification-time">
                        ${notification.time_ago}
                    </div>
                </div>
            </div>
        `).join('');
    }

    async markAsRead(notificationId) {
        try {
            const response = await fetch(`/api/reports/notifications/${notificationId}/read`, {
                method: 'PUT'
            });
            
            if (response.ok) {
                // Update local state
                const notification = this.notifications.find(n => n.id === notificationId);
                if (notification) {
                    notification.is_read = true;
                    this.unreadCount = Math.max(0, this.unreadCount - 1);
                    this.updateBadge();
                    this.renderNotifications();
                }
            } else {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error marking as read:', error);
            if (!error.message.includes('401')) {
                this.showError('Lỗi đánh dấu đã đọc');
            }
        }
    }

    async markAllAsRead() {
        try {
            const response = await fetch('/api/reports/notifications/read-all', {
                method: 'PUT'
            });
            
            if (response.ok) {
                // Update local state
                this.notifications.forEach(n => n.is_read = true);
                this.unreadCount = 0;
                this.updateBadge();
                this.renderNotifications();
                this.showSuccess('Đã đánh dấu tất cả đã đọc');
            } else {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error marking all as read:', error);
            if (!error.message.includes('401')) {
                this.showError('Lỗi đánh dấu đã đọc');
            }
        }
    }

    async clearAllNotifications() {
        if (!confirm('Bạn có chắc muốn xóa tất cả thông báo? Hành động này không thể hoàn tác.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/reports/notifications/clear-all', {
                method: 'DELETE'
            });
            
            if (response.ok) {
                const result = await response.json();
                // Update local state
                this.notifications = [];
                this.unreadCount = 0;
                this.updateBadge();
                this.renderNotifications();
                this.showSuccess(result.message || 'Đã xóa tất cả thông báo');
            } else {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error clearing all notifications:', error);
            if (!error.message.includes('401')) {
                this.showError('Lỗi xóa thông báo');
            }
        }
    }

    refreshNotifications() {
        this.loadNotifications();
    }

    startAutoRefresh() {
        // Auto refresh every 30 seconds
        setInterval(() => {
            this.loadNotifications();
        }, 30000);
    }

    getStatusText(status) {
        switch (status) {
            case 'success': return 'Thành công';
            case 'failure': return 'Thất bại';
            case 'aborted': return 'Bị hủy';
            default: return status;
        }
    }

    showSuccess(message) {
        // Simple success notification
        if (typeof alert !== 'undefined') {
            alert('✅ ' + message);
        }
    }

    showError(message) {
        // Simple error notification
        if (typeof alert !== 'undefined') {
            alert('❌ ' + message);
        }
    }

    // Public method to manually trigger notification check
    checkForNewNotifications() {
        this.loadNotifications();
    }
}

// Initialize notification component when DOM is loaded
let notificationComponent;
document.addEventListener('DOMContentLoaded', function() {
    notificationComponent = new NotificationComponent();
});

// Global function for external access
window.notificationComponent = notificationComponent; 