document.addEventListener('DOMContentLoaded', function () {
    // ==========================================
    // SIDEBAR TOGGLE & ANIMATION
    // ==========================================
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    // BREAKPOINT: debe coincidir con el @media (max-width: 992px) de layout.css
    const MOBILE_BREAKPOINT = 992;
    const userId = sidebar ? (sidebar.dataset.userId || '') : '';
    const collapseKey = userId ? 'sidebarCollapsed_' + userId : 'sidebarCollapsed';

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function () {
            if (window.innerWidth <= MOBILE_BREAKPOINT) {
                sidebar.classList.toggle('mobile-open');
            } else {
                sidebar.classList.toggle('collapsed');
                localStorage.setItem(collapseKey, sidebar.classList.contains('collapsed'));
            }
        });
    }

    const activeItem = document.querySelector('.sidebar-menu a.active');
    const indicator = document.getElementById('active-indicator');
    
    if (activeItem && indicator) {
        indicator.style.height = activeItem.offsetHeight + 'px';
        
        const isReload = (window.performance && performance.getEntriesByType('navigation')[0]?.type === 'reload')
                         || (window.performance && performance.navigation && performance.navigation.type === 1);
        const lastUser = sessionStorage.getItem('sidebarActiveUserId');
        const lastTop = sessionStorage.getItem('sidebarActiveTop');
        const currentTop = activeItem.offsetTop;

        // Solo animar si venimos de otra página con el MISMO usuario y NO es un refresco de página
        if (lastTop && lastUser === userId && !isReload && Math.abs(parseFloat(lastTop) - currentTop) > 1) {
            indicator.style.transition = 'none';
            indicator.style.transform = `translateY(${lastTop}px)`;
            void indicator.offsetWidth;
            indicator.style.transition = 'transform 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
        } else {
            indicator.style.transition = 'none';
        }
        
        indicator.style.transform = `translateY(${currentTop}px)`;
        sessionStorage.setItem('sidebarActiveTop', currentTop);
        sessionStorage.setItem('sidebarActiveUserId', userId);
        
        document.querySelectorAll('.sidebar-menu a').forEach(link => {
            link.addEventListener('click', function() {
                sessionStorage.setItem('sidebarActiveTop', currentTop);
                sessionStorage.setItem('sidebarActiveUserId', userId);
            });
        });
    } else if (indicator) {
        indicator.style.display = 'none';
        sessionStorage.removeItem('sidebarActiveTop');
        sessionStorage.removeItem('sidebarActiveUserId');
    }

    // ==========================================
    // TOPBAR AVATAR DROPDOWN
    // ==========================================
    const avatarBtn = document.getElementById('avatar-btn');
    const dropdownMenu = document.getElementById('avatar-dropdown');

    if (avatarBtn && dropdownMenu) {
        avatarBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const isVisible = dropdownMenu.style.display === 'block';
            dropdownMenu.style.display = isVisible ? 'none' : 'block';
        });

        document.addEventListener('click', function(e) {
            if (!avatarBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
                dropdownMenu.style.display = 'none';
            }
        });
    }

    // ==========================================
    // LOGOUT SWEETALERT
    // ==========================================
    const logoutBtns = [
        document.getElementById('btn-logout'), 
        document.getElementById('sidebar-btn-logout')
    ];
    
    logoutBtns.forEach(btn => {
        if (btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const logoutUrl = this.dataset.logoutUrl;
                Swal.fire({
                    title: '¿Cerrar sesión?',
                    text: '¿Estás seguro de que deseas cerrar tu sesión?',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#019577',
                    cancelButtonColor: '#6b7280',
                    confirmButtonText: 'Sí, cerrar sesión',
                    cancelButtonText: 'Cancelar'
                }).then(function(result) {
                    if (result.isConfirmed) {
                        sessionStorage.removeItem('sidebarActiveTop');
                        sessionStorage.removeItem('sidebarActiveUserId');
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = logoutUrl;
                        
                        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
                        if (csrfTokenMeta) {
                            const input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = 'csrf_token';
                            input.value = csrfTokenMeta.content;
                            form.appendChild(input);
                        }
                        
                        document.body.appendChild(form);
                        form.submit();
                    }
                });
            });
        }
    });

    // ==========================================
    // SIDEBAR ICONS TOOLTIPS (MODO COLAPSADO)
    // ==========================================
    let sidebarTooltip = document.getElementById('sidebar-tooltip');
    if (!sidebarTooltip) {
        sidebarTooltip = document.createElement('div');
        sidebarTooltip.id = 'sidebar-tooltip';
        sidebarTooltip.className = 'sidebar-tooltip';
        document.body.appendChild(sidebarTooltip);
    }

    const tooltipLinks = document.querySelectorAll('.sidebar-menu a[data-tooltip], .sidebar-footer a[data-tooltip]');

    tooltipLinks.forEach(link => {
        link.addEventListener('mouseenter', function () {
            // Solo mostrar tooltip cuando el sidebar está colapsado en pantallas desktop
            if (sidebar && sidebar.classList.contains('collapsed') && window.innerWidth > MOBILE_BREAKPOINT) {
                const text = this.getAttribute('data-tooltip');
                if (!text) return;

                sidebarTooltip.textContent = text;
                const rect = this.getBoundingClientRect();
                const tooltipHeight = sidebarTooltip.offsetHeight || 32;
                const topPos = rect.top + (rect.height / 2) - (tooltipHeight / 2);
                const leftPos = rect.right + 12;

                sidebarTooltip.style.top = `${topPos}px`;
                sidebarTooltip.style.left = `${leftPos}px`;
                sidebarTooltip.classList.add('visible');
            }
        });

        link.addEventListener('mouseleave', function () {
            if (sidebarTooltip) {
                sidebarTooltip.classList.remove('visible');
            }
        });

        link.addEventListener('click', function () {
            if (sidebarTooltip) {
                sidebarTooltip.classList.remove('visible');
            }
        });
    });

    const sidebarMenu = document.querySelector('.sidebar-menu');
    if (sidebarMenu) {
        sidebarMenu.addEventListener('scroll', function () {
            if (sidebarTooltip) {
                sidebarTooltip.classList.remove('visible');
            }
        });
    }

    // Retirar clase preload después del renderizado inicial para reactivar transiciones suaves en clicks
    requestAnimationFrame(function () {
        setTimeout(function () {
            document.body.classList.remove('preload');
        }, 50);
    });
});

// ==========================================
// PREVENCIÓN DE BFCACHE (BACK-FORWARD CACHE) EN VISTAS DEL SISTEMA
// ==========================================
window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
        window.location.reload();
    }
});
