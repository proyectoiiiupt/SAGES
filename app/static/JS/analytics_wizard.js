document.addEventListener('DOMContentLoaded', function () {
    // 2. Elementos del Stepper
    const panel1 = document.getElementById('wizard-panel-1');
    const panel2 = document.getElementById('wizard-panel-2');
    const stepNav1 = document.getElementById('step-nav-1');
    const stepNav2 = document.getElementById('step-nav-2');

    const btnNext = document.getElementById('btn-next-step');
    const btnPrev = document.getElementById('btn-prev-step');
    const inputReportName = document.getElementById('report_name');
    const selectReportType = document.getElementById('report_type');

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

            // Validación en cliente: Tipo de reporte obligatorio
            const reportTypeVal = selectReportType ? selectReportType.value.trim() : '';
            if (!reportTypeVal) {
                Swal.fire({
                    title: 'Tipo de reporte requerido',
                    text: 'Debe seleccionar el tipo de reporte a realizar antes de continuar.',
                    icon: 'warning',
                    confirmButtonColor: '#019577'
                }).then(() => {
                    if (selectReportType) selectReportType.focus();
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

    // 5. Cascada territorial en Barra Lateral (Super Admin no bloqueante y State Admin bloqueado)
    const wState = document.getElementById('w-filter-state');
    const wMuni = document.getElementById('w-filter-municipality');
    const wParish = document.getElementById('w-filter-parish');

    function loadWizardParishes(muniId, preselectedParishId = '') {
        if (!wParish) return;
        wParish.innerHTML = '<option value="">Todas las Parroquias</option>';

        if (!muniId) {
            wParish.disabled = true;
            return;
        }

        fetch(`/analytics/api/geo/parishes/${muniId}`)
            .then(r => {
                if (!r.ok) throw new Error("Error en servidor");
                return r.json();
            })
            .then(parishes => {
                parishes.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name;
                    if (preselectedParishId && String(p.id) === String(preselectedParishId)) {
                        opt.selected = true;
                    }
                    wParish.appendChild(opt);
                });
                wParish.disabled = false;
            })
            .catch(err => console.error("Error al cargar parroquias:", err));
    }

    function loadWizardMunicipalities(stateId, preselectedMuniId = '', preselectedParishId = '') {
        if (!wMuni) return;
        wMuni.innerHTML = '<option value="">Todos los Municipios</option>';
        if (wParish) {
            wParish.innerHTML = '<option value="">Todas las Parroquias</option>';
            wParish.disabled = true;
        }

        if (!stateId) {
            wMuni.disabled = true;
            return;
        }

        fetch(`/analytics/api/geo/municipalities/${stateId}`)
            .then(r => {
                if (!r.ok) throw new Error("Error en servidor");
                return r.json();
            })
            .then(municipalities => {
                let hasPreselectedMuni = false;
                municipalities.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    if (preselectedMuniId && String(m.id) === String(preselectedMuniId)) {
                        opt.selected = true;
                        hasPreselectedMuni = true;
                    }
                    wMuni.appendChild(opt);
                });
                wMuni.disabled = false;

                if (hasPreselectedMuni) {
                    loadWizardParishes(preselectedMuniId, preselectedParishId);
                }
            })
            .catch(err => console.error("Error al cargar municipios:", err));
    }

    if (wState && wMuni && wParish) {
        if (wState.tagName === 'SELECT') {
            wState.addEventListener('change', function () {
                loadWizardMunicipalities(this.value);
            });
        }

        wMuni.addEventListener('change', function () {
            loadWizardParishes(this.value);
        });

        // Precargar municipios si ya existe un estado preseleccionado (Sede de Super Admin, query param o State Admin)
        if (wState.value) {
            loadWizardMunicipalities(
                wState.value,
                wMuni.dataset.preselected || '',
                wParish.dataset.preselected || ''
            );
        }
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

            const reportType = selectReportType ? selectReportType.value.trim() : '';
            if (!reportType) {
                Swal.fire({
                    title: 'Tipo de reporte requerido',
                    text: 'Por favor, regrese al Paso 1 y seleccione el tipo de reporte a realizar.',
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
            formData.set('institution_type_id', document.getElementById('w-filter-type')?.value || '');
            formData.set('institution_dependency_id', document.getElementById('w-filter-dependency')?.value || '');
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
                        }).then(() => {
                            window.location.reload();
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

            // ── CASO B: DESCARGA BINARIA LOCAL (FETCH BLOB + ÉXITO + RECARGA) ──
            } else {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                    || document.querySelector('input[name="csrf_token"]')?.value;

                Swal.fire({
                    title: 'Generando reporte...',
                    text: 'Preparando el archivo para descarga.',
                    allowOutsideClick: false,
                    didOpen: () => { Swal.showLoading(); }
                });

                fetch('/analytics/export', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken || '' },
                    body: formData
                })
                .then(async response => {
                    if (!response.ok) {
                        let errMsg = 'No se pudo generar el reporte.';
                        try {
                            const errJson = await response.json();
                            if (errJson && errJson.message) errMsg = errJson.message;
                        } catch (_) {}
                        throw new Error(errMsg);
                    }
                    const disposition = response.headers.get('Content-Disposition') || '';
                    const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
                    const filename = match ? decodeURIComponent(match[1]) : 'reporte_sages';
                    const blob = await response.blob();
                    return { blob, filename };
                })
                .then(({ blob, filename }) => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);

                    Swal.fire({
                        title: '¡Reporte Exportado!',
                        text: 'El archivo se ha generado y descargado correctamente.',
                        icon: 'success',
                        confirmButtonColor: '#019577'
                    }).then(() => {
                        window.location.reload();
                    });
                })
                .catch(err => {
                    console.error("Error al exportar reporte:", err);
                    Swal.fire({
                        title: 'Error de exportación',
                        text: err.message || 'Ocurrió un error al generar el reporte.',
                        icon: 'error',
                        confirmButtonColor: '#0f3669'
                    });
                });
            }
        });
    }
});
