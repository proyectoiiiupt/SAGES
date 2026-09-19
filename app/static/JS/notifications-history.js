document.addEventListener("DOMContentLoaded", function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Asynchronous read marking for history page
    document.querySelectorAll('.history-mark-read, .history-action-link').forEach(elem => {
        elem.addEventListener('click', function(e) {
            const notifId = this.getAttribute('data-notif-id');
            const isReadButton = this.classList.contains('history-mark-read');
            const isActionLink = this.classList.contains('history-action-link');
            
            // Si el usuario presiona Ctrl o rueda del ratón (nueva pestaña), dejamos que el navegador actúe natural
            const isNewTab = e.ctrlKey || e.metaKey || e.button === 1;
            
            if (isReadButton || (isActionLink && !isNewTab)) {
                e.preventDefault(); // Evitamos la navegación prematura
            }

            if (!notifId) return;

            const card = document.querySelector(`.notification-card[data-notif-id="${notifId}"]`);
            const isUnread = card && card.classList.contains('is-unread');
            
            if (isUnread) {
                fetch(`/notifications/api/${notifId}/read`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json'
                    }
                }).then(response => {
                    if (!response.ok || response.redirected) {
                        throw new Error('Sesión expirada o error de red');
                    }
                    return response.json();
                }).then(data => {
                    if (data && data.success) {
                        if (card) card.classList.remove('is-unread');
                        
                        if (isReadButton) {
                            this.disabled = true;
                            this.style.opacity = '0.5';
                            if (this.innerText.trim().toLowerCase().includes('marcar')) {
                                this.innerText = 'Leído';
                            }
                        }
                        
                        // Actualizar la campanita del Topbar
                        const badge = document.getElementById("notifications-badge");
                        if (badge) {
                            if (data.unread_count > 0) {
                                badge.innerText = data.unread_count > 99 ? '99+' : data.unread_count;
                                badge.style.display = 'block';
                            } else {
                                badge.style.display = 'none';
                            }
                        }
                    }
                    
                    // Si era un link, navegamos DESPUÉS de haber marcado como leído
                    if (isActionLink && !isNewTab) {
                        window.location.href = this.href;
                    }
                }).catch(err => {
                    console.error("Error marking as read", err);
                    // Incluso si falla, navegamos para no bloquear al usuario
                    if (isActionLink && !isNewTab) {
                        window.location.href = this.href;
                    }
                });
            } else {
                // Si la tarjeta ya estaba leída, simplemente navegamos
                if (isActionLink && !isNewTab) {
                    window.location.href = this.href;
                }
            }
        });
    });
    
    // Lógica del Modal Detalle
    const modal = document.getElementById("notificationDetailModal");
    const closeBtns = document.querySelectorAll(".close-modal-btn");
    
    if (modal) {
        closeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
        
        document.querySelectorAll('.trigger-modal').forEach(card => {
            card.addEventListener('click', function(e) {
                if (e.target.closest('a') || e.target.closest('button')) {
                    return;
                }
                
                const notifId = this.getAttribute('data-notif-id');
                const title = this.getAttribute('data-notif-title');
                const message = this.getAttribute('data-notif-message');
                const date = this.getAttribute('data-notif-date');
                
                document.getElementById('modalNotifTitle').innerText = title;
                document.getElementById('modalNotifMessage').innerText = message;
                
                let formattedDate = date;
                try {
                    let utcString = date;
                    if (utcString) {
                        utcString = utcString.replace(/Z+$/, '');
                        const hasOffset = utcString.includes('+') || utcString.lastIndexOf('-') > 10;
                        if (!hasOffset) {
                            utcString += 'Z';
                        }
                    }
                    
                    const parsed = new Date(utcString);
                    if (!isNaN(parsed.getTime())) {
                        formattedDate = new Intl.DateTimeFormat('es-VE', {
                            year: 'numeric', month: 'short', day: '2-digit',
                            hour: '2-digit', minute: '2-digit', hour12: true
                        }).format(parsed);
                    }
                } catch(e) {}
                document.getElementById('modalNotifDate').innerText = formattedDate;
                
                const extraContainer = document.getElementById('modalNotifExtra');
                extraContainer.innerHTML = '';
                try {
                    const extraStr = this.getAttribute('data-notif-extra');
                    const extra = extraStr && extraStr.trim() !== '' ? JSON.parse(extraStr) : {};
                    const isArray = Array.isArray(extra);
                    
                    if (extra && (Object.keys(extra).length > 0 || (isArray && extra.length > 0))) {
                        let html = '<h4>Detalles Adicionales</h4><ul style="list-style-type: none; padding: 0;">';
                        
                        if (isArray) {
                            for (const item of extra) {
                                if (Array.isArray(item) && item.length === 2) {
                                    html += `<li><strong>${item[0]}:</strong> ${item[1]}</li>`;
                                }
                            }
                        } else {
                            for (const [key, value] of Object.entries(extra)) {
                                html += `<li><strong>${key}:</strong> ${value}</li>`;
                            }
                        }
                        
                        html += '</ul>';
                        extraContainer.innerHTML = html;
                        extraContainer.style.display = 'block';
                    } else {
                        extraContainer.style.display = 'none';
                    }
                } catch (err) {
                    console.error("Error parsing extra_data", err);
                    extraContainer.style.display = 'none';
                }
                
                modal.style.display = 'flex';
                
                // Marcar como leída automáticamente al abrir (silenciosamente)
                const isUnread = this.classList.contains('is-unread');
                if (isUnread && notifId) {
                    fetch(`/notifications/api/${notifId}/read`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Content-Type': 'application/json'
                        }
                    }).then(res => res.json()).then(data => {
                        if (data && data.success) {
                            this.classList.remove('is-unread');
                            const readBtn = this.querySelector('.history-mark-read');
                            if (readBtn) {
                                readBtn.disabled = true;
                                readBtn.style.opacity = '0.5';
                                if (readBtn.innerText.trim().toLowerCase().includes('marcar')) {
                                    readBtn.innerText = 'Leído';
                                }
                            }
                            const badge = document.getElementById("notifications-badge");
                            if (badge) {
                                if (data.unread_count > 0) {
                                    badge.innerText = data.unread_count > 99 ? '99+' : data.unread_count;
                                    badge.style.display = 'block';
                                } else {
                                    badge.style.display = 'none';
                                }
                            }
                        }
                    }).catch(err => console.error("Error marking via modal", err));
                }
            });
        });
    }
});
