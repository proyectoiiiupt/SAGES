document.addEventListener('DOMContentLoaded', function () {
    // 1. Fecha dinámica en cabecera
    const dateEl = document.getElementById('current-wizard-date');
    if (dateEl) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateEl.textContent = formattedDate;
    }

    // 2. Elementos del Stepper
    const panel1 = document.getElementById('wizard-panel-1');
    const panel2 = document.getElementById('wizard-panel-2');
    const stepNav1 = document.getElementById('step-nav-1');
    const stepNav2 = document.getElementById('step-nav-2');

    const btnNext = document.getElementById('btn-next-step');
    const btnPrev = document.getElementById('btn-prev-step');
    const inputReportName = document.getElementById('report_name');

    // ── NAVEGACIÓN: PASO 1 -> PASO 2 ──
    if (btnNext) {
        btnNext.addEventListener('click', function () {
            const nameVal = inputReportName ? inputReportName.value.trim() : '';

            // Validación en cliente: Nombre obligatorio
            if (!nameVal || nameVal.length < 3) {
                Swal.fire({
                    title: 'Nombre requerido',
                    text: 'Debe ingresar un nombre descriptivo para el reporte (mínimo 3 caracteres).',
                    icon: 'warning',
                    confirmButtonColor: '#019577'
                }).then(() => {
                    if (inputReportName) inputReportName.focus();
                });
                return;
            }

            // Validación en cliente: Al menos una fuente de datos seleccionada
            const chkUser = document.getElementById('chk-include-user')?.checked;
            const chkReq = document.getElementById('chk-include-requests')?.checked;
            const chkMet = document.getElementById('chk-include-metrics')?.checked;

            if (!chkUser && !chkReq && !chkMet) {
                Swal.fire({
                    title: 'Fuentes de datos requeridas',
                    text: 'Debe seleccionar al menos una fuente de datos a incluir en el reporte.',
                    icon: 'warning',
                    confirmButtonColor: '#019577'
                });
                return;
            }

            // Transición visual al Paso 2
            panel1.style.display = 'none';
            panel1.classList.remove('active');

            panel2.style.display = 'block';
            panel2.classList.add('active');

            stepNav1.classList.remove('active');
            stepNav2.classList.add('active');
        });
    }

    // ── NAVEGACIÓN: PASO 2 -> PASO 1 ──
    if (btnPrev) {
        btnPrev.addEventListener('click', function () {
            panel2.style.display = 'none';
            panel2.classList.remove('active');

            panel1.style.display = 'block';
            panel1.classList.add('active');

            stepNav2.classList.remove('active');
            stepNav1.classList.add('active');
        });
    }

    // 3. Selección interactiva de Tarjetas de Formato (PDF, Excel, CSV)
    const formatCards = document.querySelectorAll('.format-card');
    formatCards.forEach(card => {
        card.addEventListener('click', function () {
            formatCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            const radio = this.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 4. Alternancia temporal en Barra Lateral (Mes vs Rango)
    const wRadioMonth = document.getElementById('w-radio-month');
    const wRadioRange = document.getElementById('w-radio-range');
    const wWrapMonth = document.getElementById('w-wrapper-month');
    const wWrapRange = document.getElementById('w-wrapper-range');

    if (wRadioMonth && wRadioRange) {
        wRadioMonth.addEventListener('change', function () {
            if (this.checked) {
                wWrapMonth.style.display = 'block';
                wWrapRange.style.display = 'none';
            }
        });
        wRadioRange.addEventListener('change', function () {
            if (this.checked) {
                wWrapMonth.style.display = 'none';
                wWrapRange.style.display = 'block';
            }
        });
    }

    // 5. Cascada territorial en Barra Lateral (si es Super Admin)
    const wState = document.getElementById('w-filter-state');
    const wMuni = document.getElementById('w-filter-municipality');
    const wParish = document.getElementById('w-filter-parish');

    if (wState && wMuni && wParish && wState.tagName === 'SELECT') {
        wState.addEventListener('change', function () {
            const stateId = this.value;
            wMuni.innerHTML = '<option value="">Todos los Municipios</option>';
            wParish.innerHTML = '<option value="">Todas las Parroquias</option>';
            wParish.disabled = true;

            if (!stateId) {
                wMuni.disabled = true;
                return;
            }

            fetch(`/analytics/api/geo/municipalities/${stateId}`)
                .then(r => r.json())
                .then(municipalities => {
                    municipalities.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.id;
                        opt.textContent = m.name;
                        wMuni.appendChild(opt);
                    });
                    wMuni.disabled = false;
                })
                .catch(err => console.error("Error al cargar municipios:", err));
        });

        wMuni.addEventListener('change', function () {
            const muniId = this.value;
            wParish.innerHTML = '<option value="">Todas las Parroquias</option>';

            if (!muniId) {
                wParish.disabled = true;
                return;
            }

            fetch(`/analytics/api/geo/parishes/${muniId}`)
                .then(r => r.json())
                .then(parishes => {
                    parishes.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p.id;
                        opt.textContent = p.name;
                        wParish.appendChild(opt);
                    });
                    wParish.disabled = false;
                })
                .catch(err => console.error("Error al cargar parroquias:", err));
        });
    }

    // ─────────────────────────────────────────────────────────────
    // 6. SUBMIT DEL WIZARD: DESCARGA DIRECTA O DESPACHO POR CORREO
    // ─────────────────────────────────────────────────────────────
    const btnSubmitWizard = document.getElementById('btn-submit-wizard');
    const formWizard = document.getElementById('form-report-wizard');

    if (btnSubmitWizard && formWizard) {
        btnSubmitWizard.addEventListener('click', function (e) {
            e.preventDefault();

            const reportName = document.getElementById('report_name')?.value.trim();
            if (!reportName) {
                Swal.fire({
                    title: 'Nombre requerido',
                    text: 'Por favor, regrese al Paso 1 y defina un nombre para el reporte.',
                    icon: 'warning',
                    confirmButtonColor: '#0f3669'
                });
                return;
            }

            const exportFormat = document.querySelector('input[name="export_format"]:checked')?.value || 'pdf';
            const deliveryMethod = document.querySelector('input[name="delivery_method"]:checked')?.value || 'local';

            // Crear FormData consolidando Wizard + Filtros Laterales
            const formData = new FormData(formWizard);

            // Inyectar filtros laterales activos
            formData.set('state_id', document.getElementById('w-filter-state')?.value || '');
            formData.set('municipality_id', document.getElementById('w-filter-municipality')?.value || '');
            formData.set('parish_id', document.getElementById('w-filter-parish')?.value || '');
            formData.set('institution_scope_id', document.getElementById('w-filter-scope')?.value || '');
            formData.set('educational_level_id', document.getElementById('w-filter-level')?.value || '');

            // Gestión temporal (Mes vs Rango)
            const isMonthMode = document.getElementById('w-radio-month')?.checked;
            formData.set('month', isMonthMode ? (document.getElementById('w-filter-month')?.value || '') : '');
            formData.set('date_from', isMonthMode ? '' : (document.getElementById('w-date-from')?.value || ''));
            formData.set('date_to', isMonthMode ? '' : (document.getElementById('w-date-to')?.value || ''));

            // Inyectar checkboxes de fuentes explícitamente
            formData.set('include_user_data', document.getElementById('chk-include-user')?.checked ? 'true' : 'false');
            formData.set('include_request_details', document.getElementById('chk-include-requests')?.checked ? 'true' : 'false');
            formData.set('include_metrics', document.getElementById('chk-include-metrics')?.checked ? 'true' : 'false');

            // ── CASO A: DESPACHO POR CORREO ELECTRÓNICO (AJAX) ──
            if (deliveryMethod === 'email') {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                    || document.querySelector('input[name="csrf_token"]')?.value;

                Swal.fire({
                    title: 'Generando y despachando...',
                    text: 'Compilando el documento y enviándolo a su buzón institucional.',
                    allowOutsideClick: false,
                    didOpen: () => { Swal.showLoading(); }
                });

                fetch('/analytics/export', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken || '' },
                    body: formData
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: '¡Reporte Enviado!',
                            text: data.message,
                            icon: 'success',
                            confirmButtonColor: '#019577'
                        });
                    } else {
                        Swal.fire({
                            title: 'Error de despacho',
                            text: data.message || 'No se pudo enviar el correo.',
                            icon: 'error',
                            confirmButtonColor: '#0f3669'
                        });
                    }
                })
                .catch(err => {
                    console.error("Error al despachar reporte:", err);
                    Swal.fire({
                        title: 'Error',
                        text: 'Fallo de comunicación con el servidor.',
                        icon: 'error',
                        confirmButtonColor: '#0f3669'
                    });
                });

            // ── CASO B: DESCARGA BINARIA LOCAL (FORM SUBMIT) ──
            } else {
                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'info',
                    title: 'Iniciando descarga del reporte...',
                    showConfirmButton: false,
                    timer: 3000
                });

                // Construcción de formulario temporal para submit nativo de descarga binaria
                const hiddenForm = document.createElement('form');
                hiddenForm.method = 'POST';
                hiddenForm.action = '/analytics/export';
                hiddenForm.style.display = 'none';

                for (let [key, val] of formData.entries()) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    input.value = val;
                    hiddenForm.appendChild(input);
                }

                // Inyectar CSRF token
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                    || document.querySelector('input[name="csrf_token"]')?.value;
                if (csrfToken && !hiddenForm.querySelector('input[name="csrf_token"]')) {
                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrf_token';
                    csrfInput.value = csrfToken;
                    hiddenForm.appendChild(csrfInput);
                }

                document.body.appendChild(hiddenForm);
                hiddenForm.submit();
                setTimeout(() => hiddenForm.remove(), 1000);
            }
        });
    }
});
