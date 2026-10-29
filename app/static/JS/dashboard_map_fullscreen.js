/**
 * ============================================================================
 * MOTOR VECTORIAL DEL MAPA GEOGRÁFICO NACIONAL - VISTA AMPLIADA
 * ============================================================================
 */

(function () {
    'use strict';

    // Elementos del DOM
    const mapWrapper = document.getElementById('map-fullscreen-svg-wrapper');
    const loadingOverlay = document.getElementById('map-fullscreen-loading');
    const tooltipEl = document.getElementById('map-floating-tooltip');
    const filterChips = document.querySelectorAll('.map-chip');
    const detailPanel = document.getElementById('map-detail-panel');

    if (!mapWrapper || !detailPanel) return;

    // Estado del mapa
    let geojsonData = null;
    let statesMetrics = {};
    let nationalSummary = {};
    let activeFilter = 'all';
    let selectedStateId = null;

    // Canvas SVG
    const VIEW_WIDTH = 800;
    const VIEW_HEIGHT = 600;
    const PADDING = 25;

    /**
     * Inicialización de la vista ampliada
     */
    async function initFullscreenMap() {
        try {
            const [geoResp, apiResp] = await Promise.all([
                fetch('/static/maps/venezuela_states.geojson'),
                fetch('/dashboard/api/map/states')
            ]);

            if (!geoResp.ok) throw new Error(`Error GeoJSON: ${geoResp.status}`);
            if (!apiResp.ok) throw new Error(`Error API: ${apiResp.status}`);

            geojsonData = await geoResp.json();
            const apiData = await apiResp.json();

            if (!apiData.success) throw new Error(apiData.error || 'Respuesta inválida');

            statesMetrics = {};
            (apiData.states || []).forEach(st => {
                statesMetrics[st.state_id] = st;
            });

            nationalSummary = apiData.summary || {};

            // Actualizar contadores de chips
            updateChipCounters();

            // Formatear fecha actual en banner institucional
            const dateEl = document.getElementById('current-date');
            if (dateEl) {
                const options = { day: 'numeric', month: 'long', year: 'numeric' };
                const today = new Date();
                const formattedDate = today.toLocaleDateString('es-ES', options);
                dateEl.textContent = formattedDate.replace(' de 20', ', 20');
            }

            // Renderizar SVG del mapa
            renderSvgMap();

            // Ocultar carga
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }

            // Registrar eventos de chips
            initChipListeners();

            // Detectar si hay un state_id en los query params (ej: /dashboard/mapa?state_id=24)
            const urlParams = new URLSearchParams(window.location.search);
            const queryStateId = parseInt(urlParams.get('state_id'), 10);

            if (queryStateId && statesMetrics[queryStateId]) {
                selectState(queryStateId);
            } else {
                // Auto-seleccionar el estado con mayor número de solicitudes, si existe alguno con demanda
                let maxStateId = null;
                let maxTotal = 0;
                Object.values(statesMetrics).forEach(st => {
                    if (st.total > maxTotal) {
                        maxTotal = st.total;
                        maxStateId = st.state_id;
                    }
                });
                if (maxStateId) {
                    selectState(maxStateId);
                }
            }

        } catch (error) {
            console.error('Error inicializando vista ampliada del mapa SAGES:', error);
            if (loadingOverlay) {
                loadingOverlay.innerHTML = `
                    <div style="color: #ef4444; font-size: 0.9rem; text-align: center; padding: 2rem;">
                        <svg viewBox="0 0 24 24" width="36" height="36" stroke="currentColor" stroke-width="2" fill="none" style="margin-bottom: 8px;">
                            <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        <div>No se pudo cargar la vista del mapa geográfico.</div>
                    </div>`;
            }
        }
    }

    /**
     * Actualiza contadores de la barra de chips
     */
    function updateChipCounters() {
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val !== undefined ? val : 0;
        };

        setVal('chip-total-all', nationalSummary.total || 0);
        setVal('chip-total-red', nationalSummary.red_new || 0);
        setVal('chip-total-yellow', nationalSummary.yellow_in_progress || 0);
        setVal('chip-total-green', nationalSummary.green_completed || 0);
    }

    /**
     * Proyector de coordenadas geográficas
     */
    function createProjector(features) {
        let minLon = 180, maxLon = -180;
        let minLat = 90, maxLat = -90;

        features.forEach(f => {
            const geom = f.geometry || {};
            const type = geom.type;
            const coords = geom.coordinates || [];
            const rings = type === 'Polygon' ? coords : coords.flat(1);

            rings.forEach(ring => {
                ring.forEach(([lon, lat]) => {
                    if (lon < minLon) minLon = lon;
                    if (lon > maxLon) maxLon = lon;
                    if (lat < minLat) minLat = lat;
                    if (lat > maxLat) maxLat = lat;
                });
            });
        });

        const lonSpan = maxLon - minLon || 1;
        const latSpan = maxLat - minLat || 1;
        const availW = VIEW_WIDTH - (PADDING * 2);
        const availH = VIEW_HEIGHT - (PADDING * 2);

        return function project(lon, lat) {
            const x = PADDING + ((lon - minLon) / lonSpan) * availW;
            const y = PADDING + ((maxLat - lat) / latSpan) * availH;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        };
    }

    /**
     * Geometría GeoJSON a path SVG "d"
     */
    function geometryToPathD(geom, project) {
        if (!geom || !geom.coordinates) return '';
        const type = geom.type;
        const coords = geom.coordinates;
        let d = '';

        if (type === 'Polygon') {
            coords.forEach(ring => {
                if (ring.length > 0) {
                    const pts = ring.map(([lon, lat]) => project(lon, lat));
                    d += `M ${pts.join(' L ')} Z `;
                }
            });
        } else if (type === 'MultiPolygon') {
            coords.forEach(poly => {
                poly.forEach(ring => {
                    if (ring.length > 0) {
                        const pts = ring.map(([lon, lat]) => project(lon, lat));
                        d += `M ${pts.join(' L ')} Z `;
                    }
                });
            });
        }
        return d;
    }

    // Variables de Zoom y Pan (Amplitud y Movimiento)
    let currentScale = 1;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;
    let hasDragged = false;
    let zoomGroup = null;

    function applyTransform() {
        if (zoomGroup) {
            zoomGroup.setAttribute('transform', `translate(${panX.toFixed(2)}, ${panY.toFixed(2)}) scale(${currentScale.toFixed(3)})`);
        }
    }

    function zoom(factor, centerX, centerY) {
        const prevScale = currentScale;
        currentScale = Math.min(Math.max(currentScale * factor, 1), 7);

        if (currentScale === 1) {
            panX = 0;
            panY = 0;
        } else {
            const ratio = currentScale / prevScale;
            panX = centerX - (centerX - panX) * ratio;
            panY = centerY - (centerY - panY) * ratio;
        }
        applyTransform();
    }

    function resetZoom() {
        currentScale = 1;
        panX = 0;
        panY = 0;
        applyTransform();
    }

    /**
     * Renderizado SVG de los 26 estados con soporte de Zoom y Pan
     */
    function renderSvgMap() {
        if (!geojsonData || !geojsonData.features) return;

        const features = geojsonData.features;
        const project = createProjector(features);

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('id', 'fullscreen-venezuela-svg');
        svg.setAttribute('viewBox', `0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`);
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.setAttribute('fill-rule', 'evenodd');

        // Grupo contenedor para Zoom y Pan
        zoomGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        zoomGroup.setAttribute('id', 'fs-map-zoom-group');

        features.forEach(feat => {
            const props = feat.properties || {};
            const stateId = props.db_id;
            const stateCode = props.state_code;
            const stateName = props.name;

            const pathD = geometryToPathD(feat.geometry, project);
            if (!pathD) return;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('id', `fs-state-${stateId}`);
            path.setAttribute('data-state-id', stateId);
            path.setAttribute('data-state-code', stateCode);
            path.setAttribute('data-name', stateName);
            path.setAttribute('d', pathD);

            const m = statesMetrics[stateId] || {
                red_new: 0,
                yellow_in_progress: 0,
                green_completed: 0,
                gray_closed: 0,
                total: 0,
                predominant_color: 'gray'
            };

            const colorClass = getColorClassForState(m, activeFilter);
            path.setAttribute('class', `state-polygon ${colorClass}`);

            path.addEventListener('mouseenter', (e) => onStateMouseEnter(e, stateId, stateName, m));
            path.addEventListener('mousemove', onStateMouseMove);
            path.addEventListener('mouseleave', onStateMouseLeave);
            path.addEventListener('click', () => {
                if (hasDragged) return;
                selectState(stateId);
            });

            zoomGroup.appendChild(path);
        });

        svg.appendChild(zoomGroup);

        mapWrapper.innerHTML = '';
        mapWrapper.appendChild(svg);

        // Inicializar eventos de Zoom & Pan
        initFullscreenZoomAndPanEvents();
    }

    /**
     * Registra eventos de rueda del ratón y arrastre (Pan) en la vista ampliada
     */
    function initFullscreenZoomAndPanEvents() {
        mapWrapper.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = mapWrapper.getBoundingClientRect();
            const cursorX = ((e.clientX - rect.left) / rect.width) * VIEW_WIDTH;
            const cursorY = ((e.clientY - rect.top) / rect.height) * VIEW_HEIGHT;

            const factor = e.deltaY < 0 ? 1.25 : 0.8;
            zoom(factor, cursorX, cursorY);
        }, { passive: false });

        mapWrapper.addEventListener('mousedown', (e) => {
            if (e.button !== 0 || e.target.closest('.map-zoom-controls')) return;
            isPanning = true;
            hasDragged = false;
            startX = e.clientX;
            startY = e.clientY;
            mapWrapper.classList.add('is-panning');
        });

        window.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasDragged = true;
            }

            const rect = mapWrapper.getBoundingClientRect();
            const scaleX = VIEW_WIDTH / rect.width;
            const scaleY = VIEW_HEIGHT / rect.height;

            panX += dx * scaleX;
            panY += dy * scaleY;

            startX = e.clientX;
            startY = e.clientY;
            applyTransform();
        });

        window.addEventListener('mouseup', () => {
            if (isPanning) {
                isPanning = false;
                mapWrapper.classList.remove('is-panning');
            }
        });

        const btnIn = document.getElementById('fs-btn-zoom-in');
        const btnOut = document.getElementById('fs-btn-zoom-out');
        const btnReset = document.getElementById('fs-btn-zoom-reset');

        if (btnIn) btnIn.onclick = () => zoom(1.3, VIEW_WIDTH / 2, VIEW_HEIGHT / 2);
        if (btnOut) btnOut.onclick = () => zoom(0.77, VIEW_WIDTH / 2, VIEW_HEIGHT / 2);
        if (btnReset) btnReset.onclick = () => resetZoom();
    }

    /**
     * Clase de color según el semáforo
     */
    function getColorClassForState(metric, filter) {
        if (!metric) return 'status-neutral';

        if (filter === 'all') {
            switch (metric.predominant_color) {
                case 'red': return 'status-red';
                case 'yellow': return 'status-yellow';
                case 'green': return 'status-green';
                default: return 'status-neutral';
            }
        }

        if (filter === 'red') {
            return metric.red_new > 0 ? 'status-red' : 'state-dimmed';
        }

        if (filter === 'yellow') {
            return metric.yellow_in_progress > 0 ? 'status-yellow' : 'state-dimmed';
        }

        if (filter === 'green') {
            return metric.green_completed > 0 ? 'status-green' : 'state-dimmed';
        }

        return 'status-neutral';
    }

    /**
     * Selección interactiva de un estado
     */
    async function selectState(stateId) {
        selectedStateId = stateId;

        // Actualizar clase .selected en polígonos
        const paths = mapWrapper.querySelectorAll('.state-polygon');
        paths.forEach(p => {
            const sId = parseInt(p.getAttribute('data-state-id'), 10);
            if (sId === stateId) {
                p.classList.add('selected');
            } else {
                p.classList.remove('selected');
            }
        });

        // Actualizar URL sin recargar
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('state_id', stateId);
        window.history.replaceState(null, '', currentUrl.toString());

        // Mostrar indicador de carga en el panel
        detailPanel.innerHTML = `
            <div class="map-loading-overlay" style="position: relative; min-height: 350px;">
                <div class="map-spinner"></div>
                <span>Consultando demanda de ${statesMetrics[stateId] ? statesMetrics[stateId].name : 'Estado'}...</span>
            </div>
        `;

        try {
            const resp = await fetch(`/dashboard/api/map/state-details/${stateId}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const json = await resp.json();
            if (!json.success || !json.data) throw new Error(json.error || 'Sin datos');

            renderDetailPanel(json.data);

        } catch (err) {
            console.error('Error al cargar detalle del estado:', err);
            detailPanel.innerHTML = `
                <div class="detail-empty-state">
                    <svg class="detail-empty-icon" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none">
                        <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                    <p class="detail-empty-text">No se pudo cargar la información para este estado.</p>
                </div>
            `;
        }
    }

    /**
     * Renderiza el contenido completo del panel lateral de demanda
     */
    function renderDetailPanel(data) {
        const state = data.state || {};
        const breakdown = data.breakdown || {};
        const topTrainings = data.top_trainings || [];
        const recentRequests = data.recent_requests || [];

        // Generar lista de Top Formaciones
        let trainingsHtml = '';
        if (topTrainings.length > 0) {
            trainingsHtml = `
                <div class="trainings-list">
                    ${topTrainings.map((t, idx) => `
                        <div class="training-item">
                            <span class="training-rank">${idx + 1}</span>
                            <span class="training-name" title="${t.name}">${t.name}</span>
                            <span class="training-count-badge">${t.count} sol.</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            trainingsHtml = `<p style="font-size: 0.78rem; color: #94a3b8; font-style: italic; margin: 0;">Sin formaciones solicitadas aún en este estado.</p>`;
        }

        // Generar lista de Solicitudes Recientes
        let requestsHtml = '';
        if (recentRequests.length > 0) {
            requestsHtml = `
                <div class="recent-requests-list">
                    ${recentRequests.map(r => {
                        let badgeClass = 'badge-gray';
                        if (r.status_code === 'STAT-003') badgeClass = 'badge-red';
                        else if (['STAT-004', 'STAT-005', 'STAT-006'].includes(r.status_code)) badgeClass = 'badge-yellow';
                        else if (r.status_code === 'STAT-007') badgeClass = 'badge-green';

                        return `
                            <a href="/requests/${r.id}/detail" class="recent-req-card" title="Ver expediente">
                                <div class="recent-req-top">
                                    <span class="recent-req-code">${r.request_code}</span>
                                    <span class="recent-req-badge ${badgeClass}">${r.status_name}</span>
                                </div>
                                <div class="recent-req-inst">${r.institution_name || 'Institución no especificada'}</div>
                                <div class="recent-req-meta">
                                    <span>${r.training_name || ''}</span>
                                    <span>${r.created_at}</span>
                                </div>
                            </a>
                        `;
                    }).join('')}
                </div>
            `;
        } else {
            requestsHtml = `<p style="font-size: 0.78rem; color: #94a3b8; font-style: italic; margin: 0;">No registra solicitudes recientes.</p>`;
        }

        detailPanel.innerHTML = `
            <div class="map-detail-header">
                <h3 class="detail-state-name">${state.name}</h3>
                <span class="detail-state-code">${state.state_code}</span>
            </div>

            <div class="map-detail-body">
                <!-- Métricas Cuantitativas -->
                <div class="detail-metrics-grid">
                    <div class="stat-metric-card border-red">
                        <span class="stat-metric-label">Nuevas</span>
                        <span class="stat-metric-value" style="color: #b91c1c;">${breakdown.red_new || 0}</span>
                    </div>
                    <div class="stat-metric-card border-yellow">
                        <span class="stat-metric-label">En Trámite</span>
                        <span class="stat-metric-value" style="color: #b45309;">${breakdown.yellow_in_progress || 0}</span>
                    </div>
                    <div class="stat-metric-card border-green">
                        <span class="stat-metric-label">Completadas</span>
                        <span class="stat-metric-value" style="color: #15803d;">${breakdown.green_completed || 0}</span>
                    </div>
                    <div class="stat-metric-card border-total">
                        <span class="stat-metric-label">Total Demanda</span>
                        <span class="stat-metric-value">${breakdown.total || 0}</span>
                    </div>
                </div>

                <!-- Tasa de Resolución -->
                <div class="resolution-box">
                    <div class="resolution-header">
                        <span>Tasa de Resolución</span>
                        <span style="color: #059669;">${breakdown.resolution_rate || 0}%</span>
                    </div>
                    <div class="resolution-progress-bg">
                        <div class="resolution-progress-fill" style="width: ${breakdown.resolution_rate || 0}%;"></div>
                    </div>
                </div>

                <!-- Top 3 Formaciones -->
                <div>
                    <h4 class="detail-section-title">
                        <svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                            <path d="M6 12v5c3 3 9 3 12 0v-5"></path>
                        </svg>
                        Top Formaciones Más Solicitadas
                    </h4>
                    ${trainingsHtml}
                </div>

                <!-- Solicitudes Recientes -->
                <div>
                    <h4 class="detail-section-title">
                        <svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        Últimas Solicitudes Registradas
                    </h4>
                    ${requestsHtml}
                </div>
            </div>
        `;
    }

    /**
     * Aplica filtro de chips
     */
    function applyFilter(filterKey) {
        activeFilter = filterKey;

        filterChips.forEach(chip => {
            if (chip.getAttribute('data-filter') === filterKey) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });

        const paths = mapWrapper.querySelectorAll('.state-polygon');
        paths.forEach(p => {
            const sId = parseInt(p.getAttribute('data-state-id'), 10);
            const m = statesMetrics[sId];
            const isSel = p.classList.contains('selected');
            p.className.baseVal = `state-polygon ${getColorClassForState(m, activeFilter)}${isSel ? ' selected' : ''}`;
        });
    }

    function initChipListeners() {
        filterChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const filter = chip.getAttribute('data-filter');
                applyFilter(filter);
            });
        });
    }

    /**
     * Tooltips
     */
    function onStateMouseEnter(e, stateId, stateName, metric) {
        if (!tooltipEl) return;

        const total = metric.total || 0;
        const red = metric.red_new || 0;
        const yellow = metric.yellow_in_progress || 0;
        const green = metric.green_completed || 0;
        const rate = metric.resolution_rate || 0;

        tooltipEl.innerHTML = `
            <div class="map-tooltip-header">${stateName}</div>
            <div class="map-tooltip-row">
                <span>Total Solicitudes:</span>
                <strong>${total}</strong>
            </div>
            <div class="map-tooltip-row">
                <span><span class="tooltip-indicator dot-red"></span>Nuevas:</span>
                <strong>${red}</strong>
            </div>
            <div class="map-tooltip-row">
                <span><span class="tooltip-indicator dot-yellow"></span>En Proceso:</span>
                <strong>${yellow}</strong>
            </div>
            <div class="map-tooltip-row">
                <span><span class="tooltip-indicator dot-green"></span>Completadas:</span>
                <strong>${green} (${rate}%)</strong>
            </div>
            <div style="margin-top: 4px; padding-top: 3px; border-top: 1px dashed rgba(255,255,255,0.2); font-size: 0.68rem; color: #93c5fd; text-align: center;">
                Clic para ver demanda en panel lateral
            </div>
        `;

        tooltipEl.style.display = 'flex';
        tooltipEl.style.opacity = '1';
        positionTooltip(e);
    }

    function onStateMouseMove(e) {
        positionTooltip(e);
    }

    function positionTooltip(e) {
        if (!tooltipEl) return;
        tooltipEl.style.left = `${e.clientX}px`;
        tooltipEl.style.top = `${e.clientY}px`;
    }

    function onStateMouseLeave() {
        if (!tooltipEl) return;
        tooltipEl.style.opacity = '0';
        tooltipEl.style.display = 'none';
    }

    document.addEventListener('DOMContentLoaded', initFullscreenMap);

})();
