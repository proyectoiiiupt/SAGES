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
        function showModalError(msg, modalId = 'sla-gate-modal', formId = 'sla-gate-form') {
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
            const modal = document.getElementById(modalId);
            if (modal) {
                const form = modal.querySelector('#' + formId) || modal.children[0];
                modal.insertBefore(toast, form);
            }
            setTimeout(() => { if (toast.parentNode) toast.remove(); }, 5000);
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

        // ── Modal de Planificación  ────────────────────────────────────
        const planOpenBtn = document.getElementById('btn-open-plan-modal');
        const planOverlay = document.getElementById('plan-gate-overlay');
        const planCloseBtn = document.getElementById('plan-close-btn');
        const planForm = document.getElementById('plan-gate-form');
        const planDate = document.getElementById('plan-date');
        const planDateErr = document.getElementById('plan-date-error');
        const planDeadline = document.getElementById('plan-execution-deadline');
        const planSlaWarning = document.getElementById('plan-sla-warning');
        const planReasonGroup = document.getElementById('plan-reason-group');
        const planJustGroup = document.getElementById('plan-justification-group');
        const planReason = document.getElementById('plan-reason-select');
        const planJust = document.getElementById('plan-justification');
        const planSubmitBtn = document.getElementById('plan-submit-btn');

        const planGateModal = document.getElementById('plan-gate-modal');
        const planGridContainer = document.getElementById('plan-grid-container');
        const planSlaColumn = document.getElementById('plan-sla-column');

        if (planOpenBtn && planOverlay) {
            let busyDates = [];
            let currentCalendarDate = new Date();
            let selectedDateStr = null;

            planOpenBtn.addEventListener('click', function() {
                planOverlay.classList.add('visible');
                document.body.style.overflow = 'hidden';
                
                // Fetch busy dates
                fetch('/requests/api/requests/me/busy-dates', {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success && data.busy_dates) {
                        busyDates = data.busy_dates;
                    }
                    renderCalendar();
                })
                .catch(() => renderCalendar());
            });
            
            planCloseBtn.addEventListener('click', function() {
                planOverlay.classList.remove('visible');
                document.body.style.overflow = '';
                planForm.reset();
                planDate.value = '';
                document.getElementById('corp-selected-date-text').textContent = 'Ninguna';
                selectedDateStr = null;
                planSlaWarning.style.display = 'none';
                planReasonGroup.style.display = 'none';
                planJustGroup.style.display = 'none';
                if(planGateModal) planGateModal.classList.remove('sla-expanded');
                if(planGridContainer) planGridContainer.classList.remove('sla-active');
                if(planSlaColumn) planSlaColumn.style.display = 'none';
                
                const charCount = document.getElementById('plan-char-count');
                if (charCount) charCount.textContent = '0';
                const charErr = document.getElementById('plan-char-error');
                if (charErr) { charErr.hidden = false; charErr.style.display = 'inline'; }
                const prog = document.getElementById('plan-char-progress');
                if (prog) { prog.style.width = '0%'; prog.className = 'sla-char-progress progress-danger'; }
                
                setSubmitButtonMode(false);
                planSubmitBtn.disabled = true;
                if(planReason) planReason.required = false;
                if(planJust) planJust.required = false;
            });

            // Lógica del Calendario Custom
            const calGrid = document.getElementById('corp-cal-grid');
            const calMonthYear = document.getElementById('corp-cal-month-year');
            const btnPrev = document.getElementById('corp-cal-prev');
            const btnNext = document.getElementById('corp-cal-next');
            
            const monthNames = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
            
            if(btnPrev) btnPrev.addEventListener('click', () => { currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1); renderCalendar(); });
            if(btnNext) btnNext.addEventListener('click', () => { currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1); renderCalendar(); });

            function renderCalendar() {
                if(!calGrid) return;
                calGrid.innerHTML = '';
                
                const year = currentCalendarDate.getFullYear();
                const month = currentCalendarDate.getMonth();
                calMonthYear.textContent = `${monthNames[month]} ${year}`;
                
                const firstDay = new Date(year, month, 1).getDay();
                const daysInMonth = new Date(year, month + 1, 0).getDate();
                
                const dayHeaders = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
                dayHeaders.forEach(d => {
                    const el = document.createElement('div');
                    el.className = 'corp-calendar-day-header';
                    el.textContent = d;
                    calGrid.appendChild(el);
                });
                
                for (let i = 0; i < firstDay; i++) {
                    const empty = document.createElement('div');
                    calGrid.appendChild(empty);
                }
                
                const today = new Date();
                today.setHours(0,0,0,0);
                const maxDate = new Date(today);
                maxDate.setDate(maxDate.getDate() + 30);
                
                for (let d = 1; d <= daysInMonth; d++) {
                    const dateObj = new Date(year, month, d);
                    dateObj.setHours(0,0,0,0);
                    const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
                    
                    const dayEl = document.createElement('div');
                    dayEl.className = 'corp-calendar-day';
                    dayEl.textContent = d;
                    
                    const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
                    const isPast = dateObj <= today;
                    const isTooFar = dateObj > maxDate;
                    const isBusy = busyDates.includes(dateStr);
                    const isSelected = selectedDateStr === dateStr;
                    
                    if (isPast || isTooFar || isWeekend) {
                        dayEl.classList.add('corp-day-disabled');
                        dayEl.title = 'No permitido';
                        dayEl.addEventListener('click', () => showModalError('Fecha no permitida. Seleccione un día hábil futuro dentro de los próximos 30 días.', 'plan-gate-modal', 'plan-gate-form'));
                    } else if (isBusy) {
                        dayEl.classList.add('corp-day-busy');
                        dayEl.title = 'Usted ya tiene agendamientos este día';
                        dayEl.addEventListener('click', () => showModalError('Ya tiene una solicitud agendada para este día. Por favor elija otro.', 'plan-gate-modal', 'plan-gate-form'));
                    } else {
                        dayEl.classList.add('corp-day-available');
                        if (isSelected) dayEl.classList.add('corp-day-selected');
                        
                        dayEl.addEventListener('click', () => {
                            selectedDateStr = dateStr;
                            planDate.value = dateStr; // hidden input
                            document.getElementById('corp-selected-date-text').textContent = `${String(d).padStart(2,'0')}/${String(month+1).padStart(2,'0')}/${year}`;
                            renderCalendar(); // re-render to highlight
                            validateDateLogic(dateObj);
                        });
                    }
                    calGrid.appendChild(dayEl);
                }
            }

            function setSubmitButtonMode(isSla) {
                const textEl = document.getElementById('plan-submit-btn-text');
                if (isSla) {
                    if (textEl) textEl.textContent = 'Justificar y Confirmar Planificación';
                    if (planSubmitBtn) planSubmitBtn.classList.add('btn-sla-mode');
                } else {
                    if (textEl) textEl.textContent = 'Confirmar Planificación';
                    if (planSubmitBtn) planSubmitBtn.classList.remove('btn-sla-mode');
                }
            }
            
            function validateDateLogic(selectedObj) {
                // Evaluar ANS
                if (planDeadline && planDeadline.value) {
                    const deadline = new Date(planDeadline.value);
                    deadline.setHours(0,0,0,0); // ensure midnight for accurate comparison
                    if (selectedObj > deadline) {
                        if(planGateModal) planGateModal.classList.add('sla-expanded');
                        if(planGridContainer) planGridContainer.classList.add('sla-active');
                        if(planSlaColumn) planSlaColumn.style.display = 'block';
                        planSlaWarning.style.display = 'block';
                        planReasonGroup.style.display = 'block';
                        planJustGroup.style.display = 'block';
                        if(planReason) planReason.required = true;
                        if(planJust) planJust.required = true;
                        setSubmitButtonMode(true);
                        
                        // Cargar razones si está vacío
                        if (planReason && planReason.options.length <= 1) {
                            const reqId = document.getElementById('plan-request-id').value;
                            fetch(`/requests/api/requests/${reqId}/delay-reasons`, {
                                headers: { 'X-Requested-With': 'XMLHttpRequest' }
                            })
                            .then(r => r.json())
                            .then(data => {
                                planReason.innerHTML = '<option value="">-- Seleccione una razón --</option>';
                                if (data.reasons) {
                                    data.reasons.forEach(r => {
                                        const opt = document.createElement('option');
                                        opt.value = r.id;
                                        opt.textContent = r.name;
                                        planReason.appendChild(opt);
                                    });
                                }
                                validatePlanSubmit();
                            });
                        }
                    } else {
                        if(planGateModal) planGateModal.classList.remove('sla-expanded');
                        if(planGridContainer) planGridContainer.classList.remove('sla-active');
                        if(planSlaColumn) planSlaColumn.style.display = 'none';
                        planSlaWarning.style.display = 'none';
                        planReasonGroup.style.display = 'none';
                        planJustGroup.style.display = 'none';
                        if(planReason) planReason.required = false;
                        if(planJust) planJust.required = false;
                        setSubmitButtonMode(false);
                    }
                } else {
                    setSubmitButtonMode(false);
                }
                validatePlanSubmit();
            }
            
            if (planReason) planReason.addEventListener('change', validatePlanSubmit);
            if (planJust) {
                planJust.addEventListener('input', function() {
                    const len = this.value.length;
                    const charCount = document.getElementById('plan-char-count');
                    if (charCount) charCount.textContent = len;

                    const prog = document.getElementById('plan-char-progress');
                    if (prog) {
                        const pct = Math.min((len / 2000) * 100, 100);
                        prog.style.width = pct + '%';
                        prog.className = 'sla-char-progress ' + (len < 20 ? 'progress-danger' : 'progress-ok');
                    }

                    const charErr = document.getElementById('plan-char-error');
                    if (charErr) {
                        charErr.hidden = len >= 20;
                        charErr.style.display = len >= 20 ? 'none' : 'inline';
                    }

                    validatePlanSubmit();
                });
            }
            
            function validatePlanSubmit() {
                if (!planSubmitBtn) return;
                const isSlaActive = planSlaColumn && planSlaColumn.style.display === 'block';
                if (isSlaActive) {
                    const hasReason = Boolean(planReason && planReason.value.trim() !== '');
                    const hasJust = Boolean(planJust && planJust.value.trim().length >= 20);
                    const hasDate = Boolean(planDate && planDate.value);
                    planSubmitBtn.disabled = !(hasReason && hasJust && hasDate);
                } else {
                    planSubmitBtn.disabled = !(planDate && planDate.value);
                }
            }
            
            planForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData(this);
                const reqId = document.getElementById('plan-request-id').value;
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
                const isSlaActive = planSlaColumn && planSlaColumn.style.display === 'block';

                function restoreSubmitButton() {
                    planSubmitBtn.disabled = false;
                    planSubmitBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <span id="plan-submit-btn-text">${isSlaActive ? 'Justificar y Confirmar Planificación' : 'Confirmar Planificación'}</span>`;
                }
                
                planSubmitBtn.disabled = true;
                planSubmitBtn.innerHTML = `
                <svg class="sla-spinner" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg> Procesando...`;
                
                fetch(`/requests/api/requests/${reqId}/plan-training`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                })
                .then(r => r.json().then(data => ({ status: r.status, body: data })))
                .then(({ status, body }) => {
                    if (status === 200 && body.success) {
                        planOverlay.classList.remove('visible');
                        showSuccessBanner(body.message);
                        setTimeout(() => window.location.reload(), 1500);
                    } else if (status === 400 && body.errors) {
                        restoreSubmitButton();
                        let errStr = "Revise el formulario:<br>";
                        for (let key in body.errors) {
                            errStr += `- ${body.errors[key].join(', ')}<br>`;
                        }
                        showModalError(errStr, 'plan-gate-modal', 'plan-gate-form');
                    } else {
                        restoreSubmitButton();
                        showModalError(body.message || "Error interno al planificar.", 'plan-gate-modal', 'plan-gate-form');
                    }
                })
                .catch(() => {
                    restoreSubmitButton();
                    showModalError('Error de red. Intente de nuevo.', 'plan-gate-modal', 'plan-gate-form');
                });
            });
        }

    });
