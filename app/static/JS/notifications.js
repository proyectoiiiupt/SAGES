document.addEventListener("DOMContentLoaded", function () {
    const bellBtn = document.getElementById("bell-btn");
    const dropdown = document.getElementById("notifications-dropdown");
    const badge = document.getElementById("notifications-badge");
    const notifList = document.getElementById("notifications-list");
    const markAllReadBtn = document.getElementById("mark-all-read-btn");
    
    // CSRF Token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    let pollingInterval = 15000; // 15 seconds
    let pollingTimer = null;
    let previousUnreadCount = null;

    // Smart Polling
    function fetchUnreadCount() {
        if (document.hidden) return; // Do not poll if page is hidden

        fetch('/notifications/api/unread-count')
            .then(response => {
                // Si la sesión expiró y redirige al login, o da error 401/403
                if (!response.ok || response.redirected) {
                    stopPolling();
                    throw new Error('Sesión expirada o no autorizada');
                }
                return response.json();
            })
            .then(data => {
                if (data.unread_count > 0) {
                    badge.innerText = data.unread_count > 99 ? '99+' : data.unread_count;
                    badge.style.display = 'block';
                    
                    if (previousUnreadCount !== null && data.unread_count > previousUnreadCount) {
                        if (bellBtn) {
                            bellBtn.classList.remove('ring-animation');
                            void bellBtn.offsetWidth; // Trigger reflow para reiniciar animación
                            bellBtn.classList.add('ring-animation');
                            
                            // Remover la clase tras 1 segundo para apagar el brillo
                            setTimeout(() => {
                                bellBtn.classList.remove('ring-animation');
                            }, 1000);
                        }
                        
                        if (dropdown && dropdown.classList.contains("show")) {
                            loadDropdownNotifications();
                        }
                    }
                } else {
                    badge.style.display = 'none';
                }
                
                previousUnreadCount = data.unread_count;
            })
            .catch(err => console.error('Error fetching unread count:', err));
    }

    function startPolling() {
        fetchUnreadCount();
        pollingTimer = setInterval(fetchUnreadCount, pollingInterval);
    }

    function stopPolling() {
        clearInterval(pollingTimer);
    }

    // Page Visibility API
    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });

    // Start on load
    startPolling();

    // Toggle Dropdown
    if (bellBtn) {
        bellBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            const isShowing = dropdown.classList.contains("show");
            
            // Cierra otros dropdowns si existen (como el del avatar)
            document.querySelectorAll('.avatar-dropdown-menu, .notifications-dropdown').forEach(d => {
                if (d !== dropdown) d.classList.remove('show');
            });

            if (!isShowing) {
                dropdown.classList.add("show");
                loadDropdownNotifications();
            } else {
                dropdown.classList.remove("show");
            }
        });
    }

    // Close on click outside
    document.addEventListener("click", function (e) {
        if (dropdown && bellBtn && !dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
            dropdown.classList.remove("show");
        }
    });

    // Load Dropdown content
    function loadDropdownNotifications() {
        notifList.innerHTML = '<div class="notifications-empty">Cargando...</div>';
        
        fetch('/notifications/api/dropdown?limit=3')
            .then(response => {
                if (!response.ok || response.redirected) throw new Error('Network response not ok');
                return response.json();
            })
            .then(data => {
                const notifications = data.notifications;
                if (notifications.length === 0) {
                    notifList.innerHTML = '<div class="notifications-empty">No hay notificaciones recientes</div>';
                    return;
                }

                notifList.innerHTML = '';
                notifications.forEach(notif => {
                    const item = document.createElement("div");
                    item.className = `notification-item ${!notif.is_read ? 'unread' : ''}`;
                    item.onclick = () => handleNotificationClick(notif);
                    
                    const iconSvg = getIconSvg(notif.type);
                    
                    item.innerHTML = `
                        <div class="notif-icon ${notif.type}">${iconSvg}</div>
                        <div class="notif-content">
                            <h5 class="notif-title">${notif.title}</h5>
                            <p class="notif-message">${notif.message}</p>
                            <span class="notif-time">${formatTimeAgo(notif.created_at)}</span>
                        </div>
                        ${!notif.is_read ? '<div class="notif-dot"></div>' : ''}
                    `;
                    notifList.appendChild(item);
                });
            })
            .catch(err => {
                console.error('Error loading notifications:', err);
                notifList.innerHTML = '<div class="notifications-empty">Error al cargar notificaciones</div>';
            });
    }

    function handleNotificationClick(notif) {
        const targetUrl = notif.redirect_url ? notif.redirect_url : '/notifications/history';

        if (!notif.is_read) {
            fetch(`/notifications/api/${notif.id}/read`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            }).then(() => {
                window.location.href = targetUrl;
            }).catch(err => {
                console.error('Error al marcar como leída:', err);
                window.location.href = targetUrl;
            });
        } else {
            window.location.href = targetUrl;
        }
    }

    if (markAllReadBtn) {
        markAllReadBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            fetch('/notifications/api/mark-all-read', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            }).then(response => {
                if (response.ok && !response.redirected) return response.json();
                throw new Error('Failed to mark all read');
            }).then(data => {
                  if (data && data.success) {
                      updateBadgeCount(0);
                      loadDropdownNotifications();
                  }
              }).catch(err => console.error('Error:', err));
        });
    }

    function updateBadgeCount(count) {
        if (count > 0) {
            badge.innerText = count > 99 ? '99+' : count;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }

    function formatTimeAgo(isoDateStr) {
        if (!isoDateStr.endsWith('Z') && !isoDateStr.includes('+')) {
            isoDateStr += 'Z';
        }
        const date = new Date(isoDateStr);
        const now = new Date();
        const diffSeconds = Math.floor((now - date) / 1000);
        
        if (diffSeconds < 60) return "Hace un momento";
        const diffMinutes = Math.floor(diffSeconds / 60);
        if (diffMinutes < 60) return `Hace ${diffMinutes} min`;
        const diffHours = Math.floor(diffMinutes / 60);
        if (diffHours < 24) return `Hace ${diffHours} h`;
        const diffDays = Math.floor(diffHours / 24);
        if (diffDays === 1) return "Ayer";
        if (diffDays < 7) return `Hace ${diffDays} días`;
        
        return date.toLocaleDateString();
    }

    function getIconSvg(type) {
        switch(type) {
            case 'INFO':
                return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
            case 'SUCCESS':
                return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
            case 'WARNING':
                return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
            case 'DANGER':
                return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
            default:
                return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>';
        }
    }
});
