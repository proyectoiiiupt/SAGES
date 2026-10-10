    document.addEventListener("DOMContentLoaded", function () {

        // ── Banner: Inicializar fecha actual ──────────────────────────────────
        const dateElement = document.getElementById('current-date-display');
        if (dateElement) {
            dateElement.setAttribute('data-utc', new Date().toISOString());
            dateElement.classList.add('local-datetime');
            dateElement.setAttribute('data-format', 'full-date');
            if (typeof formatAllLocalTimes === 'function') {
                formatAllLocalTimes();
            }
        }

        // ── Asignación (Atender Solicitud - US-40) ────────────────────────────
        const claimBtn = document.getElementById('btn-claim-request');
        if (claimBtn) {
            claimBtn.addEventListener('click', function () {
                const reqId = this.getAttribute('data-request-id');
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

                Swal.fire({
                    title: '¿Confirmar Asignación?',
                    text: "Estás a punto de tomar esta solicitud para su procesamiento. Serás el operador responsable.",
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#019577',
                    cancelButtonColor: '#e74c3c',
                    confirmButtonText: 'Sí, atender solicitud',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        Swal.fire({
                            title: 'Procesando...',
                            html: 'Registrando la asignación y notificando al solicitante.',
                            allowOutsideClick: false,
                            didOpen: () => { Swal.showLoading(); }
                        });

                        fetch(`/requests/api/requests/${reqId}/claim-and-attend`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRFToken': csrfToken
                            }
                        })
                            .then(response => response.json().then(data => ({ status: response.status, body: data })))
                            .then(({ status, body }) => {
                                if (status === 200 && body.success) {
                                    Swal.fire({
                                        title: '¡Solicitud Asignada!',
                                        text: body.message,
                                        icon: 'success',
                                        confirmButtonColor: '#019577',
                                        timer: 2000,
                                        timerProgressBar: true
                                    }).then(() => {
                                        window.location.reload();
                                    });
                                } else if (status === 409) {
                                    Swal.fire({
                                        title: 'Asignación Conflictiva',
                                        text: body.message || 'Esta solicitud ya fue asumida por otro operador.',
                                        icon: 'warning',
                                        confirmButtonColor: '#f39c12'
                                    }).then(() => {
                                        window.location.reload();
                                    });
                                } else {
                                    Swal.fire({
                                        title: 'Error',
                                        text: body.message || 'Ocurrió un error al procesar la asignación.',
                                        icon: 'error',
                                        confirmButtonColor: '#e74c3c'
                                    });
                                }
                            })
                            .catch(error => {
                                Swal.fire({
                                    title: 'Error de Red',
                                    text: 'No se pudo conectar con el servidor. Intente nuevamente.',
                                    icon: 'error',
                                    confirmButtonColor: '#e74c3c'
                                });
                            });
                    }
                });
            });
        }

        // ── SLA Gate Modal ────────────────────────────────────────────────────
        const overlay = document.getElementById('sla-gate-overlay');
        const openBtn = document.getElementById('btn-open-sla-gate');
        const form = document.getElementById('sla-gate-form');
        const reasonSel = document.getElementById('sla-reason-select');
        const textarea = document.getElementById('sla-justification');
        const submitBtn = document.getElementById('sla-submit-btn');
        const charCount = document.getElementById('sla-char-count');
        const charProg = document.getElementById('sla-char-progress');
        const charErr = document.getElementById('sla-char-error');
        const reasonErr = document.getElementById('sla-reason-error');
        const requestId = document.getElementById('sla-request-id');

        const MIN_CHARS = 20;
        const MAX_CHARS = 2000;

        // Si el overlay existe, el bloqueo está activo: mostrar inmediatamente
        if (overlay) {
            // Mostrar el overlay al cargar la página automáticamente
            showSlaGate();
        }

        // Botón secundario "Justificar Retraso" también abre el modal
        if (openBtn) {
            openBtn.addEventListener('click', showSlaGate);
        }

        function showSlaGate() {
            if (!overlay) return;
            overlay.classList.add('visible');
            document.body.style.overflow = 'hidden';
            loadReasons();
            if (textarea) textarea.focus();
        }

        // Prevenir cierre por clic en overlay (es bloqueante)
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    // Sacudir el modal para indicar que no se puede cerrar
                    const modal = document.getElementById('sla-gate-modal');
                    if (modal) {
                        modal.classList.add('sla-shake');
                        setTimeout(() => modal.classList.remove('sla-shake'), 500);
                    }
                }
            });
        }

        // Prevenir cierre con tecla Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay && overlay.classList.contains('visible')) {
                e.preventDefault();
                const modal = document.getElementById('sla-gate-modal');
                if (modal) {
                    modal.classList.add('sla-shake');
                    setTimeout(() => modal.classList.remove('sla-shake'), 500);
                }
            }
        });

        // Cargar catálogo de razones desde la API
        function loadReasons() {
            if (!reasonSel || !requestId) return;
            const reqId = requestId.value;

            fetch(`/requests/api/requests/${reqId}/delay-reasons`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(r => r.json())
                .then(data => {
                    reasonSel.innerHTML = '<option value="">-- Seleccione una razón --</option>';
                    if (data.reasons && data.reasons.length > 0) {
                        data.reasons.forEach(r => {
                            const opt = document.createElement('option');
                            opt.value = r.id;
                            opt.textContent = r.name;
                            reasonSel.appendChild(opt);
                        });
                    } else {
                        reasonSel.innerHTML = '<option value="">No hay razones disponibles</option>';
                    }
                })
                .catch(() => {
                    reasonSel.innerHTML = '<option value="">Error al cargar razones. Recargue la página.</option>';
                });
        }

        // Contador de caracteres y barra de progreso
        if (textarea) {
            textarea.addEventListener('input', function () {
                const len = textarea.value.length;
                if (charCount) charCount.textContent = len;

                // Barra de progreso
                if (charProg) {
                    const pct = Math.min((len / MAX_CHARS) * 100, 100);
                    charProg.style.width = pct + '%';
                    // Color según mínimo cumplido
                    if (len < MIN_CHARS) {
                        charProg.className = 'sla-char-progress progress-danger';
                    } else if (len < 100) {
                        charProg.className = 'sla-char-progress progress-warning';
                    } else {
                        charProg.className = 'sla-char-progress progress-ok';
                    }
                }

                // Mostrar/ocultar error de caracteres
                if (charErr) {
                    charErr.hidden = len >= MIN_CHARS;
                }

                updateSubmitState();
            });
        }

        if (reasonSel) {
            reasonSel.addEventListener('change', function () {
                if (reasonErr) reasonErr.hidden = !!reasonSel.value;
                updateSubmitState();
            });
        }

        function updateSubmitState() {
            if (!submitBtn) return;
            const hasReason = reasonSel && reasonSel.value !== '';
            const hasText = textarea && textarea.value.trim().length >= MIN_CHARS;
            submitBtn.disabled = !(hasReason && hasText);
        }

        // Envío del formulario
        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();

                let valid = true;

                if (!reasonSel || !reasonSel.value) {
                    if (reasonErr) reasonErr.hidden = false;
                    valid = false;
                }
                if (!textarea || textarea.value.trim().length < MIN_CHARS) {
                    if (charErr) charErr.hidden = false;
                    valid = false;
                }
                if (!valid) return;

                // Estado de carga
                submitBtn.disabled = true;
                submitBtn.innerHTML = `
                <svg class="sla-spinner" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                Registrando descargo...
            `;

                const reqId = requestId.value;
                const payload = {
                    reason_id: parseInt(reasonSel.value),
                    justification: textarea.value.trim()
                };

                // Obtener el token CSRF del meta tag si existe
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

                fetch(`/requests/api/requests/${reqId}/justify-delay`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(payload)
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            // Éxito: cerrar modal y recargar para habilitar operatividad
                            overlay.classList.remove('visible');
                            document.body.style.overflow = '';

                            // Mostrar feedback visual antes de recargar
                            showSuccessBanner(data.message);
                            setTimeout(() => window.location.reload(), 1800);
                        } else {
                            // Error: restaurar botón y mostrar mensaje
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <polyline points="22 4 12 14.01 9 11.01"/>
                        </svg>
                        Registrar Descargo y Desbloquear
                    `;
                            showModalError(data.message || 'Error al procesar la solicitud.');
                        }
                    })
                    .catch(() => {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    Registrar Descargo y Desbloquear
                `;
                        showModalError('Error de red. Verifique su conexión e intente nuevamente.');
                    });
            });
        }

        // Notificación de error dentro del modal
        function showModalError(msg) {
            let existing = document.getElementById('sla-modal-error-toast');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.id = 'sla-modal-error-toast';
            toast.className = 'sla-error-toast';
            toast.innerHTML = `
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>${msg}</span>
        `;
            const modal = document.getElementById('sla-gate-modal');
            if (modal) modal.insertBefore(toast, modal.querySelector('#sla-gate-form'));
            setTimeout(() => { if (toast.parentNode) toast.remove(); }, 4000);
        }

        // Notificación de éxito (fuera del modal)
        function showSuccessBanner(msg) {
            const banner = document.createElement('div');
            banner.className = 'sla-success-banner';
            banner.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            <span>${msg}</span>
        `;
            document.body.appendChild(banner);
            setTimeout(() => requestAnimationFrame(() => banner.classList.add('visible')), 50);
        }

    });
