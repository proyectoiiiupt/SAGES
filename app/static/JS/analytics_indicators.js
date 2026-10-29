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
        if (selParish) selParish.innerHTML = '<option value="">Todas las Parroquias</option>';
        if (selParish) selParish.disabled = true;

        if (!stateId) {
            selMuni.disabled = true;
            return;
        }

        fetch(`/analytics/api/geo/municipalities/${stateId}`)
            .then(res => res.json())
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
            .then(res => res.json())
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

    // Función de actualización expuesta para la siguiente tarea (AJAX)
    window.updateIndicatorsUI = function (newData) {
        if (!newData) return;
        const totalGenEl = document.getElementById('lbl-total-generadas');
        const totalAttEl = document.getElementById('lbl-total-atendidas');
        const tasaResEl = document.getElementById('lbl-tasa-resolucion');

        if (totalGenEl) totalGenEl.textContent = (newData.summary && newData.summary.total_generadas !== undefined) ? newData.summary.total_generadas : 0;
        if (totalAttEl) totalAttEl.textContent = (newData.summary && newData.summary.total_atendidas !== undefined) ? newData.summary.total_atendidas : 0;
        if (tasaResEl) tasaResEl.textContent = (newData.summary && newData.summary.tasa_resolucion !== undefined) ? newData.summary.tasa_resolucion : '0.0%';

        const newLabels = newData.labels || [];
        const newGen = newData.generadas || [];
        const newAtt = newData.atendidas || [];

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

    // 5. Botón de Acción: Calcular Indicadores (Integración con AJAX de filtros)
    const btnCalc = document.getElementById('btn-calculate-indicators');
    if (btnCalc) {
        btnCalc.addEventListener('click', function () {
            const originalContent = btnCalc.innerHTML;
            btnCalc.disabled = true;
            btnCalc.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon" style="width: 18px; height: 18px; animation: spin 1s linear infinite;">
                    <line x1="12" y1="2" x2="12" y2="6"></line>
                    <line x1="12" y1="18" x2="12" y2="22"></line>
                    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                    <line x1="2" y1="12" x2="6" y2="12"></line>
                    <line x1="18" y1="12" x2="22" y2="12"></line>
                    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
                </svg>
                <span>Calculando...</span>
            `;

            const stateVal = document.getElementById('sel-filter-state') ? document.getElementById('sel-filter-state').value : '';
            const muniVal = document.getElementById('sel-filter-municipality') ? document.getElementById('sel-filter-municipality').value : '';
            const parishVal = document.getElementById('sel-filter-parish') ? document.getElementById('sel-filter-parish').value : '';
            const scopeVal = document.getElementById('sel-filter-scope') ? document.getElementById('sel-filter-scope').value : '';
            const levelVal = document.getElementById('sel-filter-level') ? document.getElementById('sel-filter-level').value : '';
            const timeMode = document.querySelector('input[name="time_mode"]:checked') ? document.querySelector('input[name="time_mode"]:checked').value : 'month';
            const monthVal = document.getElementById('sel-filter-month') ? document.getElementById('sel-filter-month').value : '';
            const dateFrom = document.getElementById('input-date-from') ? document.getElementById('input-date-from').value : '';
            const dateTo = document.getElementById('input-date-to') ? document.getElementById('input-date-to').value : '';

            const payload = {
                state_id: stateVal,
                municipality_id: muniVal,
                parish_id: parishVal,
                institution_scope_id: scopeVal,
                educational_level_id: levelVal,
                time_mode: timeMode,
                month: monthVal,
                date_from: dateFrom,
                date_to: dateTo
            };

            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

            fetch('/analytics/api/indicators-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (res.ok) {
                    return res.json();
                } else if (res.status === 404) {
                    throw new Error('API_PENDING');
                } else {
                    throw new Error('SERVER_ERROR');
                }
            })
            .then(data => {
                window.updateIndicatorsUI(data);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Indicadores Actualizados',
                        text: 'Las curvas se han recalculado exitosamente.',
                        timer: 2000,
                        showConfirmButton: false
                    });
                }
            })
            .catch(err => {
                if (err.message === 'API_PENDING') {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'info',
                            title: 'Parámetros de Filtrado',
                            text: 'Los parámetros han sido capturados correctamente en la interfaz.',
                            confirmButtonColor: '#019577',
                            confirmButtonText: 'Aceptar'
                        });
                    }
                } else {
                    console.error("Error al calcular indicadores:", err);
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error de Comunicación',
                            text: 'Ocurrió un error al consultar el servicio de indicadores.',
                            confirmButtonColor: '#0f3669'
                        });
                    }
                }
            })
            .finally(() => {
                btnCalc.disabled = false;
                btnCalc.innerHTML = originalContent;
            });
        });
    }
});
