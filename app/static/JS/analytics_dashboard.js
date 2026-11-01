document.addEventListener("DOMContentLoaded", function () {
    // 1. Mostrar la fecha actual en la cabecera
    const dateElement = document.getElementById('current-analytics-date');
    if (dateElement) {
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        // Capitalizar la primera letra
        let dateStr = new Date().toLocaleDateString('es-VE', options);
        dateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
        dateElement.textContent = dateStr;
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

    // 3. Configuración global de Chart.js
    Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
    Chart.defaults.color = "#64748b";
    Chart.defaults.scale.grid.color = "#f1f5f9";
    
    // ── GRÁFICO 1: DONUT (Estado de Solicitudes) ──
    const ctxDonut = document.getElementById('donutStatusChart');
    if (ctxDonut) {
        new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['Aprobadas', 'En Proceso', 'Pendientes'],
                datasets: [{
                    data: [
                        metrics.donut.aprobadas, 
                        metrics.donut.en_proceso, 
                        metrics.donut.pendientes
                    ],
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'], // Verde, Ámbar, Rojo
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%', // Grosor del donut
                plugins: {
                    legend: { display: false }, // Ocultamos la leyenda nativa porque hicimos una HTML custom
                    tooltip: {
                        callbacks: {
                            label: function(context) {
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

    // ── GRÁFICO 2: LÍNEAS (Evolución Temporal) ──
    const ctxLines = document.getElementById('lineEvolutionChart');
    if (ctxLines && metrics.lines.labels.length > 0) {
        new Chart(ctxLines, {
            type: 'line',
            data: {
                labels: metrics.lines.labels,
                datasets: [
                    {
                        label: 'Aprobadas',
                        data: metrics.lines.aprobadas,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        tension: 0.3, // Líneas curvas
                        fill: true
                    },
                    {
                        label: 'En Proceso',
                        data: metrics.lines.en_proceso,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Pendientes',
                        data: metrics.lines.pendientes,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
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
                        labels: { usePointStyle: true, boxWidth: 8 }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 } // Evita decimales en conteo de solicitudes
                    }
                }
            }
        });
    }

    // ── GRÁFICO 3: BARRAS HORIZONTALES (Top Temas Formativos) ──
    const ctxBars = document.getElementById('barTrainingsChart');
    if (ctxBars && metrics.bars.labels.length > 0) {
        new Chart(ctxBars, {
            type: 'bar',
            data: {
                labels: metrics.bars.labels,
                datasets: [{
                    label: 'Solicitudes',
                    data: metrics.bars.data,
                    backgroundColor: '#0ea5e9', // Azul claro distintivo
                    borderRadius: 6, // Bordes redondeados en las barras
                    barPercentage: 0.6
                }]
            },
            options: {
                indexAxis: 'y', // Convierte el gráfico a barras horizontales
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.parsed.x + ' solicitudes';
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
                            font: { size: 11 },
                            // Truncar textos muy largos
                            callback: function(value) {
                                let label = this.getLabelForValue(value);
                                return label.length > 35 ? label.substr(0, 35) + '...' : label;
                            }
                        }
                    }
                }
            }
        });
    }
});