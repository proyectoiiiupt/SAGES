/**
 * ============================================================================
 * MOTOR VECTORIAL DEL MAPA GEOGRÁFICO NACIONAL
 * ============================================================================
 */

(function () {
    'use strict';

    // Evitar ejecución si el widget no está presente en el DOM
    const widgetEl = document.getElementById('dashboard-map-widget');
    if (!widgetEl) return;

    // Elementos del DOM
    const svgContainer = document.getElementById('map-svg-wrapper');
    const loadingOverlay = document.getElementById('map-loading-overlay');
    const filterChips = document.querySelectorAll('.map-chip');

    /**
     * Obtiene o crea de forma segura el elemento contenedor del tooltip
     */
    function getTooltipElement() {
        let el = document.getElementById('map-floating-tooltip');
        if (!el) {
            el = document.createElement('div');
            el.id = 'map-floating-tooltip';
            el.className = 'map-tooltip';
            document.body.appendChild(el);
        }
        return el;
    }

    // Estado del mapa
    let geojsonData = null;
    let statesMetrics = {};
    let nationalSummary = {};
    let activeFilter = 'all';

    // Dimensiones del canvas SVG
    const VIEW_WIDTH = 800;
    const VIEW_HEIGHT = 600;
    const PADDING = 25;

    /**
     * Inicialización del mapa
     */
    async function initMap() {
        try {
            // Carga asíncrona paralela del GeoJSON local y la API de métricas
            const [geoResp, apiResp] = await Promise.all([
                fetch('/static/maps/venezuela_states.geojson'),
                fetch('/dashboard/api/map/states')
            ]);

            if (!geoResp.ok) throw new Error(`Error al cargar GeoJSON: ${geoResp.status}`);
            if (!apiResp.ok) throw new Error(`Error al consultar métricas del mapa: ${apiResp.status}`);

            geojsonData = await geoResp.json();
            const apiData = await apiResp.json();

            if (!apiData.success) throw new Error(apiData.error || 'Error en respuesta de la API');

            // Indexar métricas por state_id
            statesMetrics = {};
            (apiData.states || []).forEach(st => {
                statesMetrics[st.state_id] = st;
            });

            nationalSummary = apiData.summary || {};

            // Actualizar contadores numéricos en los chips
            updateChipCounters();

            // Renderizar el mapa SVG
            renderSvgMap();

            // Ocultar overlay de carga
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }

            // Registrar eventos de chips
            initChipListeners();

        } catch (error) {
            console.error('Error inicializando el mapa nacional SAGES:', error);
            if (loadingOverlay) {
                loadingOverlay.innerHTML = `
                    <div style="color: #ef4444; font-size: 0.82rem; text-align: center; padding: 1rem;">
                        <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" stroke-width="2" fill="none" style="margin-bottom: 6px;">
                            <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        <div>No se pudo cargar el mapa geográfico.</div>
                    </div>`;
            }
        }
    }

    /**
     * Actualiza los contadores numéricos de los chips superiores
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
     * Proyecta coordenadas geográficas (longitud, latitud) en coordenadas SVG (X, Y)
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

        // Asegurar margen
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
     * Convierte la geometría GeoJSON en un string de comando SVG "d"
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
        currentScale = Math.min(Math.max(currentScale * factor, 1), 6);

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
     * Renderiza el mapa SVG con todos sus polígonos dentro de un grupo con soporte de Zoom/Pan
     */
    function renderSvgMap() {
        if (!geojsonData || !geojsonData.features) return;

        const features = geojsonData.features;
        const project = createProjector(features);

        // Crear elemento SVG nativo
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('id', 'venezuela-map-svg');
        svg.setAttribute('viewBox', `0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`);
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.setAttribute('fill-rule', 'evenodd');

        // Grupo contenedor para Zoom y Pan
        zoomGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        zoomGroup.setAttribute('id', 'map-zoom-group');

        features.forEach(feat => {
            const props = feat.properties || {};
            const stateId = props.db_id;
            const stateCode = props.state_code;
            const stateName = props.name;

            const pathD = geometryToPathD(feat.geometry, project);
            if (!pathD) return;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('id', `state-path-${stateId}`);
            path.setAttribute('data-state-id', stateId);
            path.setAttribute('data-state-code', stateCode);
            path.setAttribute('data-name', stateName);
            path.setAttribute('d', pathD);

            // Obtener métricas del estado
            const m = statesMetrics[stateId] || {
                red_new: 0,
                yellow_in_progress: 0,
                green_completed: 0,
                gray_closed: 0,
                total: 0,
                predominant_color: 'gray'
            };

            // Asignar clase de color según el semáforo
            const colorClass = getColorClassForState(m, activeFilter);
            path.setAttribute('class', `state-polygon ${colorClass}`);

            // Eventos del cursor (Tooltips e interacción)
            path.addEventListener('mouseenter', (e) => onStateMouseEnter(e, stateId, stateName, m));
            path.addEventListener('mousemove', onStateMouseMove);
            path.addEventListener('mouseleave', onStateMouseLeave);
            path.addEventListener('click', () => {
                if (hasDragged) return;
                onStateClick(stateId);
            });

            zoomGroup.appendChild(path);
        });

        svg.appendChild(zoomGroup);

        // Limpiar y montar
        svgContainer.innerHTML = '';
        svgContainer.appendChild(svg);

        // Inicializar interacción de Zoom & Pan
        initZoomAndPanEvents();
    }

    /**
     * Registra eventos de rueda del ratón y arrastre (Pan)
     */
    function initZoomAndPanEvents() {
        // Rueda del ratón para ampliar / alejar
        svgContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = svgContainer.getBoundingClientRect();
            const cursorX = ((e.clientX - rect.left) / rect.width) * VIEW_WIDTH;
            const cursorY = ((e.clientY - rect.top) / rect.height) * VIEW_HEIGHT;

            const factor = e.deltaY < 0 ? 1.25 : 0.8;
            zoom(factor, cursorX, cursorY);
        }, { passive: false });

        // Arrastre (Click & Drag)
        svgContainer.addEventListener('mousedown', (e) => {
            if (e.button !== 0 || e.target.closest('.map-zoom-controls')) return;
            isPanning = true;
            hasDragged = false;
            startX = e.clientX;
            startY = e.clientY;
            svgContainer.classList.add('is-panning');
        });

        window.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasDragged = true;
            }

            const rect = svgContainer.getBoundingClientRect();
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
                svgContainer.classList.remove('is-panning');
            }
        });

        // Botones de Zoom en Toolbar
        const btnIn = document.getElementById('btn-zoom-in');
        const btnOut = document.getElementById('btn-zoom-out');
        const btnReset = document.getElementById('btn-zoom-reset');

        if (btnIn) btnIn.onclick = () => zoom(1.3, VIEW_WIDTH / 2, VIEW_HEIGHT / 2);
        if (btnOut) btnOut.onclick = () => zoom(0.77, VIEW_WIDTH / 2, VIEW_HEIGHT / 2);
        if (btnReset) btnReset.onclick = () => resetZoom();
    }

    /**
     * Obtiene la clase de color adecuada para el estado según el filtro activo
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
     * Actualiza los colores de los polígonos al cambiar el filtro de chips
     */
    function applyFilter(filterKey) {
        activeFilter = filterKey;

        // Actualizar chips activos
        filterChips.forEach(chip => {
            if (chip.getAttribute('data-filter') === filterKey) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });

        // Recalcular clases en los polígonos SVG
        const paths = svgContainer.querySelectorAll('.state-polygon');
        paths.forEach(p => {
            const sId = parseInt(p.getAttribute('data-state-id'), 10);
            const m = statesMetrics[sId];
            p.className.baseVal = `state-polygon ${getColorClassForState(m, activeFilter)}`;
        });
    }

    /**
     * Registra los eventos de clic en los chips
     */
    function initChipListeners() {
        filterChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const filter = chip.getAttribute('data-filter');
                applyFilter(filter);
            });
        });
    }

    /**
     * Tooltip: Mostrar al entrar al polígono
     */
    function onStateMouseEnter(e, stateId, stateName, metric) {
        const tooltip = getTooltipElement();
        if (!tooltip) return;

        const total = metric.total || 0;
        const red = metric.red_new || 0;
        const yellow = metric.yellow_in_progress || 0;
        const green = metric.green_completed || 0;
        const rate = metric.resolution_rate || 0;

        const completedText = total > 0 ? `${green} (${rate}%)` : `${green}`;

        tooltip.innerHTML = `
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
                <strong>${completedText}</strong>
            </div>
            <div style="margin-top: 4px; padding-top: 3px; border-top: 1px dashed rgba(255,255,255,0.2); font-size: 0.68rem; color: #93c5fd; text-align: center;">
                Clic para ver mapa completo
            </div>
        `;

        tooltip.style.display = 'flex';
        tooltip.style.opacity = '1';
        positionTooltip(e);
    }

    /**
     * Tooltip: Seguir la posición del puntero
     */
    function onStateMouseMove(e) {
        positionTooltip(e);
    }

    function positionTooltip(e) {
        const tooltip = getTooltipElement();
        if (!tooltip) return;
        const x = e.clientX;
        const y = e.clientY;

        if (y < 130) {
            tooltip.style.transform = 'translate(-50%, 15px)';
        } else {
            tooltip.style.transform = 'translate(-50%, -115%)';
        }

        tooltip.style.left = `${x}px`;
        tooltip.style.top = `${y}px`;
    }

    /**
     * Tooltip: Ocultar al salir del polígono
     */
    function onStateMouseLeave() {
        const tooltip = document.getElementById('map-floating-tooltip');
        if (!tooltip) return;
        tooltip.style.opacity = '0';
        tooltip.style.display = 'none';
    }

    /**
     * Clic en un estado: Redirige a la vista completa con el estado seleccionado
     */
    function onStateClick(stateId) {
        window.location.href = `/dashboard/mapa?state_id=${stateId}`;
    }

    // Inicializar cuando el DOM esté listo
    document.addEventListener('DOMContentLoaded', initMap);

})();
