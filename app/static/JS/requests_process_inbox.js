/**
 * Archivo: requests_process_inbox.js
 * Descripción: Control del Modal de Reprogramación Técnica de Fecha (US-42 / SR-F-022)
 * Estilo y UX: Idéntico a la Agenda de Cita Formativa Corporativa (US-41)
 * Autor: SAGES - CORPOELEC
 */

document.addEventListener('DOMContentLoaded', function () {
    const rescheduleOverlay = document.getElementById('reschedule-gate-overlay');
    const rescheduleForm = document.getElementById('reschedule-gate-form');
    if (!rescheduleOverlay || !rescheduleForm) {
        return; // No se encuentra el modal en la vista actual
    }

    const openBtns = document.querySelectorAll('#btn-open-reschedule-modal, .ws-btn-reprogramar');
    const closeBtn = document.getElementById('reschedule-close-btn');
    const submitBtn = document.getElementById('reschedule-submit-btn');
    const submitBtnText = document.getElementById('reschedule-submit-btn-text');
    const dateInput = document.getElementById('reschedule-date');
    const selectedDateText = document.getElementById('reschedule-selected-date-text');
    const reasonSelect = document.getElementById('reschedule-reason-select');
    const justificationInput = document.getElementById('reschedule-justification');
    const charCounter = document.getElementById('reschedule-char-count');
    const charError = document.getElementById('reschedule-char-error');
    const charProgress = document.getElementById('reschedule-char-progress');

    const rescheduleGateModal = document.getElementById('reschedule-gate-modal');
    const rescheduleGridContainer = document.getElementById('reschedule-grid-container');
    const rescheduleSlaColumn = document.getElementById('reschedule-sla-column');

    const calGrid = document.getElementById('reschedule-cal-grid');
    const calMonthYear = document.getElementById('reschedule-cal-month-year');
    const btnPrev = document.getElementById('reschedule-cal-prev');
    const btnNext = document.getElementById('reschedule-cal-next');

    let busyDates = [];
    let currentCalendarDate = new Date();
    let selectedDateStr = null;
    let isSubmitting = false;

    const monthNames = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ];

    // =========================================================================
    // 1. Toast de Error Dentro del Modal (Consistente con UX SAGES)
    // =========================================================================
    function showModalError(msg) {
        let existing = document.getElementById('reschedule-modal-error-toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.id = 'reschedule-modal-error-toast';
        toast.className = 'sla-error-toast';
        toast.innerHTML = `
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>${msg}</span>
        `;
        if (rescheduleGateModal) {
            rescheduleGateModal.insertBefore(toast, rescheduleForm);
        }
        setTimeout(() => { if (toast.parentNode) toast.remove(); }, 5000);
    }

    // =========================================================================
    // 2. Control de Apertura y Cierre del Modal
    // =========================================================================
    function openModal() {
        rescheduleOverlay.classList.add('visible');
        rescheduleOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        // Consultar fechas ocupadas del facilitador para marcarlas en naranja
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

        // Cargar motivos oficiales si el select estuviese vacío
        if (reasonSelect && reasonSelect.options.length <= 1) {
            const reqId = document.getElementById('reschedule-request-id').value;
            fetch(`/requests/api/requests/${reqId}/delay-reasons`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.json())
            .then(data => {
                reasonSelect.innerHTML = '<option value="">-- Seleccione una razón --</option>';
                if (data.reasons) {
                    data.reasons.forEach(r => {
                        const opt = document.createElement('option');
                        opt.value = r.id;
                        opt.textContent = r.name;
                        reasonSelect.appendChild(opt);
                    });
                }
                validateSubmit();
            })
            .catch(err => console.error('Error al cargar motivos:', err));
        }
    }

    function closeModal() {
        if (isSubmitting) return;
        rescheduleOverlay.classList.remove('visible');
        rescheduleOverlay.style.display = 'none';
        document.body.style.overflow = '';
        resetForm();
    }

    function resetForm() {
        rescheduleForm.reset();
        selectedDateStr = null;
        if (dateInput) dateInput.value = '';
        if (selectedDateText) selectedDateText.textContent = 'Ninguna';

        if (rescheduleGateModal) rescheduleGateModal.classList.remove('sla-expanded');
        if (rescheduleGridContainer) rescheduleGridContainer.classList.remove('sla-active');
        if (rescheduleSlaColumn) rescheduleSlaColumn.style.display = 'none';

        if (charCounter) charCounter.textContent = '0';
        if (charError) {
            charError.hidden = false;
            charError.style.display = 'inline';
        }
        if (charProgress) {
            charProgress.style.width = '0%';
            charProgress.className = 'sla-char-progress progress-danger';
        }

        setSubmitButtonMode(false);
        if (submitBtn) submitBtn.disabled = true;
    }

    openBtns.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            openModal();
        });
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    // Cierre al presionar fuera del diálogo
    rescheduleOverlay.addEventListener('click', function (e) {
        if (e.target === rescheduleOverlay) {
            closeModal();
        }
    });

    // Cierre con la tecla Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && rescheduleOverlay.classList.contains('visible')) {
            closeModal();
        }
    });

    // =========================================================================
    // 3. Renderizado del Calendario Mensual Interactivo
    // =========================================================================
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
            renderCalendar();
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
            renderCalendar();
        });
    }

    function renderCalendar() {
        if (!calGrid) return;
        calGrid.innerHTML = '';

        const year = currentCalendarDate.getFullYear();
        const month = currentCalendarDate.getMonth();
        if (calMonthYear) {
            calMonthYear.textContent = `${monthNames[month]} ${year}`;
        }

        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();

        // Cabeceras de días: Dom a Sáb
        const dayHeaders = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
        dayHeaders.forEach(d => {
            const el = document.createElement('div');
            el.className = 'corp-calendar-day-header';
            el.textContent = d;
            calGrid.appendChild(el);
        });

        // Celdas vacías al inicio del mes
        for (let i = 0; i < firstDay; i++) {
            const empty = document.createElement('div');
            calGrid.appendChild(empty);
        }

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const maxDate = new Date(today);
        maxDate.setDate(maxDate.getDate() + 60); // Límite de horizonte 60 días

        for (let d = 1; d <= daysInMonth; d++) {
            const dateObj = new Date(year, month, d);
            dateObj.setHours(0, 0, 0, 0);
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

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
                dayEl.title = isWeekend ? 'Fines de semana no permitidos' : 'Fecha no permitida';
                dayEl.addEventListener('click', () => {
                    const msg = isWeekend 
                        ? 'Las jornadas formativas solo pueden programarse en días hábiles (de lunes a viernes).' 
                        : 'Fecha no permitida. Seleccione un día hábil futuro.';
                    showModalError(msg);
                });
            } else if (isBusy) {
                dayEl.classList.add('corp-day-busy');
                dayEl.title = 'Usted ya tiene agendamientos este día';
                dayEl.addEventListener('click', () => {
                    showModalError('Ya tiene una actividad formativa agendada para este día. Por favor seleccione otro día.');
                });
            } else {
                dayEl.classList.add('corp-day-available');
                if (isSelected) {
                    dayEl.classList.add('corp-day-selected');
                }

                dayEl.addEventListener('click', () => {
                    selectedDateStr = dateStr;
                    if (dateInput) dateInput.value = dateStr;
                    if (selectedDateText) {
                        selectedDateText.textContent = `${String(d).padStart(2, '0')}/${String(month + 1).padStart(2, '0')}/${year}`;
                    }
                    renderCalendar(); // Re-renderizar para marcar el círculo azul
                    expandSlaColumn();
                });
            }
            calGrid.appendChild(dayEl);
        }
    }

    // =========================================================================
    // 4. Activación de Columna de Justificación (Al seleccionar fecha)
    // =========================================================================
    function expandSlaColumn() {
        if (rescheduleGateModal) rescheduleGateModal.classList.add('sla-expanded');
        if (rescheduleGridContainer) rescheduleGridContainer.classList.add('sla-active');
        if (rescheduleSlaColumn) rescheduleSlaColumn.style.display = 'block';

        if (reasonSelect) reasonSelect.required = true;
        if (justificationInput) justificationInput.required = true;

        setSubmitButtonMode(true);
        validateSubmit();
    }

    function setSubmitButtonMode(isSla) {
        if (!submitBtnText || !submitBtn) return;
        if (isSla) {
            submitBtnText.textContent = 'Justificar y Confirmar Planificación';
            submitBtn.classList.add('btn-sla-mode');
        } else {
            submitBtnText.textContent = 'Confirmar Planificación';
            submitBtn.classList.remove('btn-sla-mode');
        }
    }

    // =========================================================================
    // 5. Validación Reactiva en Tiempo Real
    // =========================================================================
    function validateSubmit() {
        if (!submitBtn) return;
        const hasDate = Boolean(dateInput && dateInput.value);
        const hasReason = Boolean(reasonSelect && reasonSelect.value.trim() !== '');
        const hasJust = Boolean(justificationInput && justificationInput.value.trim().length >= 20);

        submitBtn.disabled = !(hasDate && hasReason && hasJust);
    }

    if (reasonSelect) {
        reasonSelect.addEventListener('change', validateSubmit);
    }

    if (justificationInput) {
        justificationInput.addEventListener('input', function () {
            const len = this.value.length;
            if (charCounter) charCounter.textContent = len;

            if (charProgress) {
                const pct = Math.min((len / 2000) * 100, 100);
                charProgress.style.width = pct + '%';
                charProgress.className = 'sla-char-progress ' + (len < 20 ? 'progress-danger' : 'progress-ok');
            }

            if (charError) {
                charError.hidden = len >= 20;
                charError.style.display = len >= 20 ? 'none' : 'inline';
            }

            validateSubmit();
        });
    }

    // =========================================================================
    // 6. Envío AJAX al Endpoint Transaccional de Reprogramación (POST)
    // =========================================================================
    rescheduleForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (isSubmitting) return;

        const dateVal = dateInput ? dateInput.value : '';
        const reasonVal = reasonSelect ? reasonSelect.value : '';
        const justVal = justificationInput ? justificationInput.value.trim() : '';

        if (!dateVal || !reasonVal || justVal.length < 20) {
            validateSubmit();
            return;
        }

        const requestId = document.getElementById('reschedule-request-id').value;
        const defaultUrl = `/requests/api/${requestId}/reschedule`;
        const postUrl = rescheduleForm.dataset.rescheduleUrl || defaultUrl;

        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfInput = rescheduleForm.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : (csrfInput ? csrfInput.value : '');

        // Activar estado de carga
        isSubmitting = true;
        submitBtn.disabled = true;
        if (submitBtnText) submitBtnText.textContent = 'Procesando Reprogramación...';

        const payload = {
            new_planned_for: dateVal,
            reason_id: parseInt(reasonVal, 10),
            justification: justVal
        };

        fetch(postUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            isSubmitting = false;

            if (status === 200 && body.success) {
                closeModal();

                const formattedDate = body.data && body.data.new_planned_for ? body.data.new_planned_for : dateVal;
                const rescheduledCount = body.data && typeof body.data.rescheduled_count !== 'undefined' ? body.data.rescheduled_count : 1;

                // Actualizar reactivamente los elementos en pantalla
                const wsDateEl = document.getElementById('ws-planned-date-display');
                if (wsDateEl) wsDateEl.textContent = formattedDate;

                const wsBadgeEl = document.getElementById('ws-rescheduled-count-badge');
                const wsCountNumEl = document.getElementById('ws-rescheduled-count-num');
                if (wsBadgeEl) wsBadgeEl.style.display = 'inline-block';
                if (wsCountNumEl) wsCountNumEl.textContent = rescheduledCount;

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Fecha Reprogramada con Éxito!',
                        html: `La jornada formativa ha sido fijada para el día <strong>${formattedDate}</strong>.<br><small class="text-muted">Se ha notificado al solicitante y registrado el descargo en la bitácora.</small>`,
                        confirmButtonColor: '#019577',
                        confirmButtonText: 'Aceptar'
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    alert(`Fecha reprogramada exitosamente para el ${formattedDate}.`);
                    window.location.reload();
                }
            } else {
                let errorMsg = body.message || 'Error al procesar la reprogramación.';
                if (body.errors) {
                    const errorList = Object.values(body.errors).flat().join('<br>');
                    errorMsg += `<br><small style="color: #ef4444;">${errorList}</small>`;
                }

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo reprogramar la jornada',
                        html: errorMsg,
                        confirmButtonColor: '#ef4444'
                    });
                } else {
                    alert(errorMsg.replace(/<[^>]+>/g, ' '));
                }

                submitBtn.disabled = false;
                setSubmitButtonMode(true);
            }
        })
        .catch(err => {
            isSubmitting = false;
            console.error('Error en fetch reprogramación:', err);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Conexión',
                    text: 'Ocurrió un fallo en la comunicación con el servidor. Verifique su red e intente nuevamente.',
                    confirmButtonColor: '#ef4444'
                });
            } else {
                alert('Error de conexión al reprogramar la jornada.');
            }
            submitBtn.disabled = false;
            setSubmitButtonMode(true);
        });
    });
});
