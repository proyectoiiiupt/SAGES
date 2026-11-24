document.addEventListener("DOMContentLoaded", function () {
    // 1. Mostrar la fecha actual en la cabecera (time-formatter.js / es-VE)
    const dateElement = document.getElementById('current-analytics-date');
    if (dateElement) {
        if (typeof formatCurrentDate === 'function') {
            formatCurrentDate(dateElement, 'full-date');
        } else {
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            let dateStr = new Date().toLocaleDateString('es-VE', options);
            dateElement.textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
        }
    }

    // 2. Leer el payload de datos inyectado de forma segura desde Flask
    const payloadElement = document.getElementById('analytics-data-payload');
    if (!payloadElement) {
        console.error("No se encontró el bloque de datos JSON de analíticas.");
        return;
    }

    let metrics;
    try {
        metrics = JSON.parse(payloadElement.textContent);
    } catch (e) {
        console.error("Error al parsear el JSON de analíticas:", e);
        return;
    }

    // 3. Configuración tipográfica y de colores globales de Chart.js
    Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
    Chart.defaults.color = "#64748b";
    Chart.defaults.scale.grid.color = "#f1f5f9";
    
    // Objeto para almacenar las instancias de Chart.js y redimensionarlas
    const charts = {};

    // ── GRÁFICO 1: AREA CHART (Volumen Global de Solicitudes) ──
    const ctxArea = document.getElementById('areaChart');
    if (ctxArea) {
        const areaLabels = (metrics.area && metrics.area.labels && metrics.area.labels.length > 0)
            ? metrics.area.labels
            : (metrics.lines && metrics.lines.labels ? metrics.lines.labels : []);
            
        const areaData = (metrics.area && metrics.area.data && metrics.area.data.length > 0)
            ? metrics.area.data
            : ((metrics.lines && metrics.lines.aprobadas) ? metrics.lines.aprobadas.map((v, i) => v + (metrics.lines.en_proceso[i] || 0) + (metrics.lines.pendientes[i] || 0)) : []);

        charts.area = new Chart(ctxArea, {
            type: 'line',
            data: {
                labels: areaLabels,
                datasets: [{
                    label: 'Volumen Total',
                    data: areaData,
                    borderColor: '#1c3d73',
                    backgroundColor: 'rgba(28, 61, 115, 0.18)',
                    borderWidth: 2.5,
                    pointBackgroundColor: '#1c3d73',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 1.5,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true,
                    tension: 0.35
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: { usePointStyle: true, boxWidth: 8, font: { size: 11, weight: 600 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return ' ' + context.parsed.y + ' solicitudes totales';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // ── GRÁFICO 2: DONUT CHART (Distribución por Estatus Operativo) ──
    const ctxDonut = document.getElementById('donutChart');
    if (ctxDonut && metrics.donut) {
        charts.donut = new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['Aprobadas', 'En Proceso', 'Pendientes'],
                datasets: [{
                    data: [
                        metrics.donut.aprobadas || 0, 
                        metrics.donut.en_proceso || 0, 
                        metrics.donut.pendientes || 0
                    ],
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderWidth: 2,
                    borderColor: '#ffffff',
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '68%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            padding: 14,
                            font: { size: 12, weight: 600 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                let label = context.label || '';
                                if (label) label += ': ';
                                label += context.parsed + ' solicitudes';
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }

    // ── GRÁFICO 3: LINE CHART (Evolución Temporal por Estatus) ──
    const ctxLines = document.getElementById('lineChart');
    if (ctxLines && metrics.lines && metrics.lines.labels && metrics.lines.labels.length > 0) {
        charts.line = new Chart(ctxLines, {
            type: 'line',
            data: {
                labels: metrics.lines.labels,
                datasets: [
                    {
                        label: 'Aprobadas',
                        data: metrics.lines.aprobadas || [],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        fill: false
                    },
                    {
                        label: 'En Proceso',
                        data: metrics.lines.en_proceso || [],
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        fill: false
                    },
                    {
                        label: 'Pendientes',
                        data: metrics.lines.pendientes || [],
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { usePointStyle: true, boxWidth: 8, font: { size: 11, weight: 600 } }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // ── GRÁFICO 4: BAR CHART (Formaciones UREE Más Demandadas) ──
    const ctxBars = document.getElementById('barChart');
    if (ctxBars && metrics.bars && metrics.bars.labels && metrics.bars.labels.length > 0) {
        charts.bar = new Chart(ctxBars, {
            type: 'bar',
            data: {
                labels: metrics.bars.labels,
                datasets: [{
                    label: 'Solicitudes',
                    data: metrics.bars.data,
                    backgroundColor: '#007865',
                    borderRadius: 6,
                    barPercentage: 0.65
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return ' ' + context.parsed.x + ' solicitudes';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { size: 11, weight: 500 },
                            callback: function (value) {
                                let label = this.getLabelForValue(value);
                                return label.length > 32 ? label.substr(0, 32) + '...' : label;
                            }
                        }
                    }
                }
            }
        });
    }

    // ── 5. MODO ENFOQUE AMPLIADO Y MINIMIZACIÓN DE TARJETAS ──
    const container = document.getElementById('charts-dashboard-container');
    const allCards = container ? container.querySelectorAll('.adminlte-chart-card') : [];

    // Iconos SVG para los estados de maximizar / restaurar
    const iconExpandSvg = '<svg class="icon-maximize" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>';
    const iconRestoreSvg = '<svg class="icon-maximize" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="10" y1="14" x2="3" y2="21"></line></svg>';

    // Función para redimensionar todos los gráficos después de transiciones
    function resizeAllCharts() {
        setTimeout(function () {
            Object.values(charts).forEach(function (c) {
                if (c && typeof c.resize === 'function') {
                    c.resize();
                }
            });
        }, 120);
    }

    // A) MODO ENFOQUE / AMPLIAR TARJETA
    function toggleFocusCard(targetCard) {
        if (!container) return;

        const isCurrentlyFocused = targetCard.classList.contains('card-focused');

        if (isCurrentlyFocused) {
            // SALIR DEL MODO ENFOQUE: Restaurar cuadrícula 2x2
            container.classList.remove('focus-mode-active');
            allCards.forEach(function (c) {
                c.classList.remove('card-focused', 'card-minimized-focus');
                const btnMax = c.querySelector('[data-lte-toggle="card-maximize"]');
                if (btnMax) {
                    btnMax.innerHTML = iconExpandSvg;
                    btnMax.setAttribute('title', 'Ampliar pantalla completa');
                }
                // Si la tarjeta no estaba colapsada manualmente, asegurarse que su body se vea
                if (!c.classList.contains('collapsed-card')) {
                    const cb = c.querySelector('.card-body');
                    if (cb) cb.style.display = 'block';
                }
            });
        } else {
            // ENTRAR AL MODO ENFOQUE con targetCard
            container.classList.add('focus-mode-active');
            allCards.forEach(function (c) {
                const btnMax = c.querySelector('[data-lte-toggle="card-maximize"]');
                if (c === targetCard) {
                    c.classList.add('card-focused');
                    c.classList.remove('card-minimized-focus', 'collapsed-card');
                    const cb = c.querySelector('.card-body');
                    if (cb) cb.style.display = 'block';
                    if (btnMax) {
                        btnMax.innerHTML = iconRestoreSvg;
                        btnMax.setAttribute('title', 'Restaurar cuadrícula (2x2)');
                    }
                } else {
                    c.classList.remove('card-focused');
                    c.classList.add('card-minimized-focus');
                    const cb = c.querySelector('.card-body');
                    if (cb) cb.style.display = 'none';
                    if (btnMax) {
                        btnMax.innerHTML = iconExpandSvg;
                        btnMax.setAttribute('title', 'Cambiar enfoque a este gráfico');
                    }
                }
            });

            // Desplazar suavemente hacia la tarjeta enfocada
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        resizeAllCharts();
    }

    // Eventos para el botón de maximizar / enfocar
    document.querySelectorAll('[data-lte-toggle="card-maximize"]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const card = this.closest('.adminlte-chart-card');
            if (card) toggleFocusCard(card);
        });
    });

    // Si una tarjeta está en estado minimizado dentro del modo enfoque, hacer clic en su cabecera la enfoca
    allCards.forEach(function (card) {
        const header = card.querySelector('.card-header');
        if (header) {
            header.addEventListener('click', function (e) {
                // Solo si el clic no vino de los botones internos de herramientas
                if (e.target.closest('.card-tools')) return;
                if (container && container.classList.contains('focus-mode-active') && card.classList.contains('card-minimized-focus')) {
                    toggleFocusCard(card);
                }
            });
        }
    });
});
