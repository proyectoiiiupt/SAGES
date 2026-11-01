/**
 * ============================================================================
 * SAGES - Controlador de Panel Estadal 
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const tableBody = document.getElementById('dashboardTableBody');
    let debounceTimer;

    // Inicialización del reloj del banner
    const dateElement = document.getElementById('current-date-display');
    if (dateElement) {
        dateElement.setAttribute('data-utc', new Date().toISOString());
        dateElement.classList.add('local-datetime');
        dateElement.setAttribute('data-format', 'full-date');

        if (typeof formatAllLocalTimes === 'function') {
            formatAllLocalTimes();
        }
    }

    /**
     * Función principal que solicita la tabla actualizada al servidor
     */
    const fetchDashboardData = async (queryStr = '') => {
        try {
            // Se inyecta la bandera 'ajax=1' para alertar a la ruta que devuelva el template parcial
            const response = await fetch(`/requests/state-dashboard?ajax=1&${queryStr}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                if (response.status === 403) {
                    console.error("SAGES Security: Acceso denegado a la ruta estadal.");
                    return;
                }
                throw new Error("Fallo de conectividad con el servidor.");
            }

            const htmlPartial = await response.text();

            // Inyección quirúrgica del HTML en el DOM
            tableBody.innerHTML = htmlPartial;

            // Re-vincular los eventos de paginación a los nuevos botones que llegaron en el HTML
            bindPaginationEvents();

            // Re-ejecutar el formateador global de fechas si existe (time-formatter.js)
            if (typeof formatAllLocalTimes === 'function') {
                formatAllLocalTimes();
            }

        } catch (error) {
            console.error("SAGES UI Error:", error);
            tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: red; padding: 30px;">Error al cargar la información. Verifique su conexión e intente nuevamente.</td></tr>`;
        }
    };

    const statusFilter = document.getElementById('statusFilter');
    const municipalityFilter = document.getElementById('municipalityFilter');

    /**
     * Construye la cadena de parámetros cruzando la búsqueda de texto y los filtros.
     */
    const getFilterParams = (pageNum = null) => {
        const params = new URLSearchParams();
        const currentSearch = searchInput ? searchInput.value.trim() : '';
        const currentStatus = statusFilter ? statusFilter.value : '';
        const currentMunicipality = municipalityFilter ? municipalityFilter.value : '';

        if (pageNum) params.append('page', pageNum);
        if (currentSearch) params.append('search', currentSearch);
        if (currentStatus) params.append('status', currentStatus);
        if (currentMunicipality) params.append('municipality', currentMunicipality);

        return params;
    };

    /**
     * Secuestra (Hijack) los eventos de clic en los botones de paginación.
     * En lugar de cambiar de página perdiendo la búsqueda, fusiona ambos parámetros.
     */
    const bindPaginationEvents = () => {
        const paginationLinks = document.querySelectorAll('.pagination-buttons a.page-link');

        paginationLinks.forEach(link => {
            // Evitar vinculaciones dobles (Event Delegation defensivo)
            link.removeEventListener('click', handlePaginationClick);
            link.addEventListener('click', handlePaginationClick);
        });
    };

    /**
     * Manejador asíncrono para el click en paginación
     */
    const handlePaginationClick = (e) => {
        e.preventDefault(); // Detiene la navegación nativa del navegador

        // 1. Extraer el número de página clickeado de su href nativo ("?page=X")
        const linkHref = e.currentTarget.getAttribute('href');
        const urlParams = new URLSearchParams(linkHref.split('?')[1]);
        const pageNum = urlParams.get('page');

        // 2. Fusionar estados y hacer petición al servidor
        const newParams = getFilterParams(pageNum);
        
        tableBody.style.opacity = '0.5';
        fetchDashboardData(newParams.toString()).then(() => {
            tableBody.style.opacity = '1';
        });
    };

    /**
     * Disparador universal de filtros. (Debounce para texto, Directo para Selects)
     */
    const applyFilters = () => {
        const params = getFilterParams();
        tableBody.style.opacity = '0.5';
        fetchDashboardData(params.toString()).then(() => {
            tableBody.style.opacity = '1';
        });
    };

    // Escudo anti-Spam (Debounce de 400ms) para la barra de búsqueda de texto.
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                applyFilters();
            }, 400); // Ventana de gracia de 400 milisegundos
        });
    }

    // Eventos inmediatos para los filtros desplegables
    if (statusFilter) {
        statusFilter.addEventListener('change', applyFilters);
    }
    if (municipalityFilter) {
        municipalityFilter.addEventListener('change', applyFilters);
    }

    // Inicializar el secuestro de botones al cargar la página por primera vez
    bindPaginationEvents();

    /**
     * ------------------------------------------------------------------------
     * Animación suave para los números de los indicadores (KPIs)
     * ------------------------------------------------------------------------
     */
    const counters = document.querySelectorAll('.counter-value');
    counters.forEach(counter => {
        const target = parseFloat(counter.getAttribute('data-target') || counter.textContent);
        const isPercent = counter.getAttribute('data-is-percent') === 'true';
        
        if (isNaN(target)) return;

        let current = 0;
        const duration = 800; // ms
        const steps = 30;
        const increment = target / steps;
        const stepTime = duration / steps;

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            counter.textContent = Math.round(current) + (isPercent ? '%' : '');
        }, stepTime);
    });
});
