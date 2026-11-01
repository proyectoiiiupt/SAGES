document.addEventListener('DOMContentLoaded', function () {
    // 1. Fecha dinámica en cabecera
    const dateEl = document.getElementById('current-indicators-date');
    if (dateEl) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateEl.textContent = formattedDate.replace(' de 20', ', 20');
    }

    // 2. Alternancia de selectores temporales (Mes vs Rango)
    const radioMonth = document.getElementById('radio-mode-month');
    const radioRange = document.getElementById('radio-mode-range');
    const wrapMonth = document.getElementById('wrapper-month-select');
    const wrapRange = document.getElementById('wrapper-range-select');

    if (radioMonth && radioRange && wrapMonth && wrapRange) {
        radioMonth.addEventListener('change', function () {
            if (this.checked) {
                wrapMonth.style.display = 'block';
                wrapRange.style.display = 'none';
            }
        });
        radioRange.addEventListener('change', function () {
            if (this.checked) {
                wrapMonth.style.display = 'none';
                wrapRange.style.display = 'block';
            }
        });
    }

    // 3. Cascada Geográfica Dinámica (Estado -> Municipio -> Parroquia)
    const selState = document.getElementById('sel-filter-state');
    const selMuni = document.getElementById('sel-filter-municipality');
    const selParish = document.getElementById('sel-filter-parish');

    function loadMunicipalities(stateId) {
        if (!selMuni) return;
        selMuni.innerHTML = '<option value="">Todos los Municipios</option>';
        if (selParish) {
            selParish.innerHTML = '<option value="">Todas las Parroquias</option>';
            selParish.disabled = true;
        }

        if (!stateId) {
            selMuni.disabled = true;
            return;
        }

        fetch(`/analytics/api/geo/municipalities/${stateId}`)
            .then(res => {
                if (!res.ok) throw new Error("Error en servidor");
                return res.json();
            })
            .then(municipalities => {
                municipalities.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    selMuni.appendChild(opt);
                });
                selMuni.disabled = false;
            })
            .catch(err => console.error("Error al cargar municipios:", err));
    }

    function loadParishes(municipalityId) {
        if (!selParish) return;
        selParish.innerHTML = '<option value="">Todas las Parroquias</option>';

        if (!municipalityId) {
            selParish.disabled = true;
            return;
        }

        fetch(`/analytics/api/geo/parishes/${municipalityId}`)
            .then(res => {
                if (!res.ok) throw new Error("Error en servidor");
                return res.json();
            })
            .then(parishes => {
                parishes.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name;
                    selParish.appendChild(opt);
                });
                selParish.disabled = false;
            })
            .catch(err => console.error("Error al cargar parroquias:", err));
    }

    if (selState) {
        selState.addEventListener('change', function () {
            loadMunicipalities(this.value);
        });

        // Si ya hay un estado preseleccionado (ej. Administrador Estadal)
        if (selState.value) {
            loadMunicipalities(selState.value);
        }
    }

    if (selMuni) {
        selMuni.addEventListener('change', function () {
            loadParishes(this.value);
        });
    }

    // 4. Extraer payload inicial
    const payloadEl = document.getElementById('indicators-initial-payload');
    if (!payloadEl) return;

    let initialData = {};
    try {
        initialData = JSON.parse(payloadEl.textContent);
    } catch (e) {
        console.error("Error al parsear datos de indicadores:", e);
        return;
    }

    let chartGen = null;
    let chartAtt = null;
    let chartComp = null;

    // Configuración base con estilo de métricas de mercado
    function buildTrendConfig(labels, dataPoints, labelText, lineColor, fillColor) {
        return {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: labelText,
                    data: dataPoints,
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                    borderWidth: 2.5,
                    tension: 0.4,             // Curvatura suave y continua
                    fill: true,                // Sombreado de área inferior
                    pointRadius: 3.5,
                    pointHoverRadius: 6,
                    pointBackgroundColor: lineColor,
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#ffffff',
                        bodyColor: '#cbd5e1',
                        padding: 8,
                        cornerRadius: 6
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b', font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f8fafc' },
                        ticks: { precision: 0, color: '#64748b', font: { size: 10 } }
                    }
                }
            }
        };
    }

    // Inicialización de los tres lienzos
    const ctxGen = document.getElementById('chartGeneratedLines');
    const ctxAtt = document.getElementById('chartAttendedLines');
    const ctxComp = document.getElementById('chartComparativeLines');

    const labels = initialData.labels || [];
    const dataGen = initialData.generadas || [];
    const dataAtt = initialData.atendidas || [];

    // Tarjeta 1: Solicitudes Generadas (Rojo)
    if (ctxGen) {
        chartGen = new Chart(
            ctxGen.getContext('2d'),
            buildTrendConfig(labels, dataGen, 'Generadas', '#dc2626', 'rgba(220, 38, 38, 0.08)')
        );
    }

    // Tarjeta 2: Solicitudes Atendidas (Verde)
    if (ctxAtt) {
        chartAtt = new Chart(
            ctxAtt.getContext('2d'),
            buildTrendConfig(labels, dataAtt, 'Atendidas', '#10b981', 'rgba(16, 185, 129, 0.10)')
        );
    }

    // Tarjeta 3: Comparativa Consolidada (Superposición)
    if (ctxComp) {
        chartComp = new Chart(ctxComp.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Solicitudes Generadas',
                        data: dataGen,
                        borderColor: '#dc2626',
                        backgroundColor: 'rgba(220, 38, 38, 0.06)',
                        borderWidth: 2.5,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#dc2626',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 1.5
                    },
                    {
                        label: 'Solicitudes Atendidas',
                        data: dataAtt,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.08)',
                        borderWidth: 2.5,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#10b981',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 1.5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        padding: 10,
                        cornerRadius: 8
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b', font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f1f5f9' },
                        ticks: { precision: 0, color: '#64748b', font: { size: 11 } }
                    }
                }
            }
        });
    }

    // Función de actualización expuesta para recálculo dinámico (AJAX)
    window.updateIndicatorsUI = function (newData) {
        if (!newData) return;
        // Soporte defensivo por si se recibe el objeto de respuesta completo { success: true, data: { ... } }
        const data = (newData.data && newData.success !== undefined) ? newData.data : newData;

        const totalGenEl = document.getElementById('lbl-total-generadas');
        const totalAttEl = document.getElementById('lbl-total-atendidas');
        const tasaResEl = document.getElementById('lbl-tasa-resolucion');

        if (totalGenEl) totalGenEl.textContent = (data.summary && data.summary.total_generadas !== undefined) ? data.summary.total_generadas : 0;
        if (totalAttEl) totalAttEl.textContent = (data.summary && data.summary.total_atendidas !== undefined) ? data.summary.total_atendidas : 0;
        if (tasaResEl) tasaResEl.textContent = (data.summary && data.summary.tasa_resolucion !== undefined) ? data.summary.tasa_resolucion : '0.0%';

        const newLabels = data.labels || [];
        const newGen = data.generadas || [];
        const newAtt = data.atendidas || [];

        if (chartGen) {
            chartGen.data.labels = newLabels;
            chartGen.data.datasets[0].data = newGen;
            chartGen.update();
        }
        if (chartAtt) {
            chartAtt.data.labels = newLabels;
            chartAtt.data.datasets[0].data = newAtt;
            chartAtt.update();
        }
        if (chartComp) {
            chartComp.data.labels = newLabels;
            chartComp.data.datasets[0].data = newGen;
            chartComp.data.datasets[1].data = newAtt;
            chartComp.update();
        }
    };

    // 5. Botón de Acción: Calcular Indicadores (Integración AJAX y Reactividad)
    const btnCalc = document.getElementById('btn-calculate-indicators');
    if (btnCalc) {
        btnCalc.addEventListener('click', function () {
            // 1. Obtener y validar la modalidad temporal
            const radioRange = document.getElementById('radio-mode-range');
            const timeMode = (radioRange && radioRange.checked) ? 'range' : 'month';

            const dateFromInput = document.getElementById('input-date-from');
            const dateToInput = document.getElementById('input-date-to');
            const dateFrom = dateFromInput ? dateFromInput.value.trim() : '';
            const dateTo = dateToInput ? dateToInput.value.trim() : '';

            // Validación en cliente para la modalidad de rango de fechas
            if (timeMode === 'range') {
                if (!dateFrom || !dateTo) {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Rango incompleto',
                            text: 'Debe especificar tanto la fecha "Desde" como la fecha "Hasta".',
                            confirmButtonColor: '#0f3669'
                        });
                    }
                    return;
                }
                if (dateFrom > dateTo) {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Rango cronológico inválido',
                            text: 'La fecha inicial (Desde) no puede ser posterior a la fecha final (Hasta).',
                            confirmButtonColor: '#0f3669'
                        });
                    }
                    return;
                }
            }

            // 2. Extraer valores de filtros territoriales e institucionales
            const stateVal = document.getElementById('sel-filter-state') ? document.getElementById('sel-filter-state').value : '';
            const muniVal = document.getElementById('sel-filter-municipality') ? document.getElementById('sel-filter-municipality').value : '';
            const parishVal = document.getElementById('sel-filter-parish') ? document.getElementById('sel-filter-parish').value : '';
            const scopeVal = document.getElementById('sel-filter-scope') ? document.getElementById('sel-filter-scope').value : '';
            const levelVal = document.getElementById('sel-filter-level') ? document.getElementById('sel-filter-level').value : '';
            const monthVal = document.getElementById('sel-filter-month') ? document.getElementById('sel-filter-month').value : '';

            const payload = {
                time_mode: timeMode,
                month: monthVal ? parseInt(monthVal, 10) : null,
                date_from: dateFrom || null,
                date_to: dateTo || null,
                state_id: stateVal ? parseInt(stateVal, 10) : null,
                municipality_id: muniVal ? parseInt(muniVal, 10) : null,
                parish_id: parishVal ? parseInt(parishVal, 10) : null,
                institution_scope_id: scopeVal ? parseInt(scopeVal, 10) : null,
                educational_level_id: levelVal ? parseInt(levelVal, 10) : null
            };

            // 3. Token CSRF desde meta tag
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

            // 4. Estado de carga visual en el botón
            const originalContent = btnCalc.innerHTML;
            btnCalc.disabled = true;
            btnCalc.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon" style="width: 18px; height: 18px; animation: spin 1s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="0.75"></path>
                </svg>
                <span>Calculando...</span>
            `;

            // 5. Envío fetch() al endpoint de indicadores
            fetch('/analytics/api/indicators-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) {
                    return res.json()
                        .then(errData => {
                            throw new Error(errData.message || `Error en el servidor (HTTP ${res.status})`);
                        })
                        .catch(err => {
                            if (err instanceof SyntaxError) {
                                throw new Error(`Error en el servidor (HTTP ${res.status})`);
                            }
                            throw err;
                        });
                }
                return res.json();
            })
            .then(response => {
                if (response.success && response.data) {
                    window.updateIndicatorsUI(response.data);

                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            toast: true,
                            position: 'top-end',
                            icon: 'success',
                            title: 'Métricas actualizadas',
                            showConfirmButton: false,
                            timer: 2000
                        });
                    }
                } else {
                    throw new Error(response.message || 'La respuesta no contiene datos válidos.');
                }
            })
            .catch(error => {
                console.error("Error al calcular indicadores:", error);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error de cálculo',
                        text: error.message || 'No se pudieron procesar los indicadores con los filtros seleccionados.',
                        confirmButtonColor: '#0f3669'
                    });
                }
            })
            .finally(() => {
                btnCalc.disabled = false;
                btnCalc.innerHTML = originalContent;
            });
        });
    }
// 6. Modal y Exportación Directa de Indicadores (Bloque 6)
    const btnOpenExport = document.getElementById('btn-export-from-indicators');
    const modalExport = document.getElementById('modal-export-indicators');
    const btnCloseExport = document.getElementById('btn-close-export-modal');
    const btnCancelExport = document.getElementById('btn-cancel-export-modal');
    const btnConfirmExport = document.getElementById('btn-confirm-export-indicators');

    function openExportModal() {
        if (!modalExport) return;
        // Sincronizar los KPIs visibles del modal con lo que está en pantalla
        const totalGen = document.getElementById('lbl-total-generadas')?.textContent || '0';
        const totalAtt = document.getElementById('lbl-total-atendidas')?.textContent || '0';
        const tasaRes = document.getElementById('lbl-tasa-resolucion')?.textContent || '0.0%';

        const modalGen = document.getElementById('modal-lbl-generadas');
        const modalAtt = document.getElementById('modal-lbl-atendidas');
        const modalRes = document.getElementById('modal-lbl-resolucion');

        if (modalGen) modalGen.textContent = totalGen.trim();
        if (modalAtt) modalAtt.textContent = totalAtt.trim();
        if (modalRes) modalRes.textContent = tasaRes.trim();

        modalExport.style.display = 'flex';
        modalExport.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeExportModal() {
        if (!modalExport) return;
        modalExport.style.display = 'none';
        modalExport.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    if (btnOpenExport) {
        btnOpenExport.addEventListener('click', function (e) {
            e.preventDefault();
            openExportModal();
        });
    }

    if (btnCloseExport) btnCloseExport.addEventListener('click', closeExportModal);
    if (btnCancelExport) btnCancelExport.addEventListener('click', closeExportModal);

    if (modalExport) {
        modalExport.addEventListener('click', function (e) {
            if (e.target === modalExport) closeExportModal();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modalExport.style.display === 'flex') {
                closeExportModal();
            }
        });
    }

    // Selección de formato de archivo en el modal
    const formatCards = modalExport ? modalExport.querySelectorAll('.format-card') : [];
    formatCards.forEach(card => {
        card.addEventListener('click', function () {
            formatCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');
            const radio = this.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // Confirmar y procesar la exportación
    if (btnConfirmExport) {
        btnConfirmExport.addEventListener('click', function () {
            // Recoger formato seleccionado
            const selectedRadio = modalExport ? modalExport.querySelector('input[name="modal_export_format"]:checked') : null;
            const exportFormat = selectedRadio ? selectedRadio.value : 'xlsx';

            // Recoger método de despacho
            const deliveryRadio = modalExport ? modalExport.querySelector('input[name="modal_delivery_method"]:checked') : null;
            const deliveryMethod = deliveryRadio ? deliveryRadio.value : 'local';

            // Recoger filtros activos de la consola
            const radioRange = document.getElementById('radio-mode-range');
            const timeMode = (radioRange && radioRange.checked) ? 'range' : 'month';
            const dateFromInput = document.getElementById('input-date-from');
            const dateToInput = document.getElementById('input-date-to');
            const dateFrom = dateFromInput ? dateFromInput.value.trim() : '';
            const dateTo = dateToInput ? dateToInput.value.trim() : '';

            const stateVal = document.getElementById('sel-filter-state') ? document.getElementById('sel-filter-state').value : '';
            const muniVal = document.getElementById('sel-filter-municipality') ? document.getElementById('sel-filter-municipality').value : '';
            const parishVal = document.getElementById('sel-filter-parish') ? document.getElementById('sel-filter-parish').value : '';
            const scopeVal = document.getElementById('sel-filter-scope') ? document.getElementById('sel-filter-scope').value : '';
            const levelVal = document.getElementById('sel-filter-level') ? document.getElementById('sel-filter-level').value : '';
            const monthVal = document.getElementById('sel-filter-month') ? document.getElementById('sel-filter-month').value : '';

            const payload = {
                export_format: exportFormat,
                delivery_method: deliveryMethod,
                time_mode: timeMode,
                month: monthVal ? parseInt(monthVal, 10) : null,
                date_from: dateFrom || null,
                date_to: dateTo || null,
                state_id: stateVal ? parseInt(stateVal, 10) : null,
                municipality_id: muniVal ? parseInt(muniVal, 10) : null,
                parish_id: parishVal ? parseInt(parishVal, 10) : null,
                institution_scope_id: scopeVal ? parseInt(scopeVal, 10) : null,
                educational_level_id: levelVal ? parseInt(levelVal, 10) : null
            };

            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

            // Estado de carga en el botón del modal
            const originalBtnContent = btnConfirmExport.innerHTML;
            btnConfirmExport.disabled = true;
            btnConfirmExport.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon" style="width: 16px; height: 16px; animation: spin 1s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="0.75"></path>
                </svg>
                <span>Generando...</span>
            `;

            fetch('/analytics/api/export-indicators', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(errData => {
                        throw new Error(errData.message || `Error del servidor (HTTP ${res.status})`);
                    });
                }

                // Si fue envío por correo, recibimos JSON con confirmación
                if (deliveryMethod === 'email') {
                    return res.json().then(data => {
                        closeExportModal();
                        if (typeof Swal !== 'undefined') {
                            Swal.fire({
                                icon: 'success',
                                title: 'Reporte Despachado',
                                text: data.message || 'El reporte ha sido enviado a su buzón de correo institucional.',
                                confirmButtonColor: '#019577'
                            });
                        }
                    });
                }

                // Si fue descarga local, procesamos el BLOB binario
                const disposition = res.headers.get('Content-Disposition') || '';
                let filename = `Indicadores_Gestion_${exportFormat}.${exportFormat}`;
                if (disposition.includes('filename=')) {
                    const parts = disposition.split('filename=');
                    if (parts.length > 1) {
                        filename = parts[1].split(';')[0].trim().replaceAll('"', '').replaceAll("'", '');
                    }
                }

                return res.blob().then(blob => {
                    const blobUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = blobUrl;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(blobUrl);
                    a.remove();

                    closeExportModal();

                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            toast: true,
                            position: 'top-end',
                            icon: 'success',
                            title: 'Descarga completada',
                            text: filename,
                            showConfirmButton: false,
                            timer: 2500
                        });
                    }
                });
            })
            .catch(err => {
                console.error("Error al exportar indicadores:", err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error de Exportación',
                        text: err.message || 'Ocurrió un error al compilar el reporte de indicadores.',
                        confirmButtonColor: '#0f3669'
                    });
                }
            })
            .finally(() => {
                btnConfirmExport.disabled = false;
                btnConfirmExport.innerHTML = originalBtnContent;
            });
        });
    }
});
