document.addEventListener('DOMContentLoaded', function () {
    // ==========================================
    // SIDEBAR TOGGLE & ANIMATION
    // ==========================================
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    // BREAKPOINT: debe coincidir con el @media (max-width: 992px) de layout.css
    const MOBILE_BREAKPOINT = 992;

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function () {
            if (window.innerWidth <= MOBILE_BREAKPOINT) {
                sidebar.classList.toggle('mobile-open');
            } else {
                sidebar.classList.toggle('collapsed');
                localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
            }
        });
    }

    const activeItem = document.querySelector('.sidebar-menu a.active');
    const indicator = document.getElementById('active-indicator');
    
    if (activeItem && indicator) {
        indicator.style.height = activeItem.offsetHeight + 'px';
        
        const lastTop = sessionStorage.getItem('sidebarActiveTop');
        if (lastTop) {
            indicator.style.transition = 'none';
            indicator.style.transform = `translateY(${lastTop}px)`;
            void indicator.offsetWidth;
            indicator.style.transition = 'transform 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
        }
        
        const currentTop = activeItem.offsetTop;
        indicator.style.transform = `translateY(${currentTop}px)`;
        sessionStorage.setItem('sidebarActiveTop', currentTop);
        
        document.querySelectorAll('.sidebar-menu a').forEach(link => {
            link.addEventListener('click', function() {
                sessionStorage.setItem('sidebarActiveTop', currentTop);
            });
        });
    } else if (indicator) {
        indicator.style.display = 'none';
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
});
