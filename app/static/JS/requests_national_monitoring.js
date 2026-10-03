/**
 * requests_national_monitoring.js
 * Interactivity for Super Admin National Monitoring Dashboard (US-38)
 * - 400ms Debounce on search input
 * - Dynamic form submission on dropdown filters
 * - Redundant request prevention
 */

document.addEventListener('DOMContentLoaded', () => {
    const filterForm = document.getElementById('monitoring-filter-form');
    const searchInput = document.getElementById('monitoring-search-input');
    const stateSelect = document.getElementById('monitoring-state-select');
    const moduleSelect = document.getElementById('monitoring-module-select');
    const statusSelect = document.getElementById('monitoring-status-select');
    const dateDisplay = document.getElementById('monitoring-current-date');

    // 1. Mostrar fecha local actual
    if (dateDisplay) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateDisplay.textContent = formattedDate.replace(' de 20', ', 20');
    }

    if (!filterForm) return;

    // 2. Control de búsqueda con Debounce (400ms) y prevención de peticiones redundantes
    let searchDebounceTimer = null;
    let lastSearchQuery = searchInput ? searchInput.value.trim() : '';

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchDebounceTimer);

            searchDebounceTimer = setTimeout(() => {
                const currentQuery = e.target.value.trim();

                // Disparar solo si el término ha cambiado realmente
                if (currentQuery !== lastSearchQuery) {
                    lastSearchQuery = currentQuery;
                    
                    // Resetear a página 1 al buscar
                    const pageInput = filterForm.querySelector('input[name="page"]');
                    if (pageInput) {
                        pageInput.value = '1';
                    }

                    filterForm.submit();
                }
            }, 400);
        });

        // Prevenir submit inmediato por Enter si el texto no ha cambiado
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const currentQuery = searchInput.value.trim();
                if (currentQuery !== lastSearchQuery) {
                    lastSearchQuery = currentQuery;
                    const pageInput = filterForm.querySelector('input[name="page"]');
                    if (pageInput) {
                        pageInput.value = '1';
                    }
                    filterForm.submit();
                }
            }
        });
    }

    // 3. Envío automático al cambiar filtros desplegables
    const selectElements = [stateSelect, moduleSelect, statusSelect];

    selectElements.forEach(select => {
        if (select) {
            select.addEventListener('change', () => {
                // Resetear paginación a página 1 al alterar cualquier filtro
                const pageInput = filterForm.querySelector('input[name="page"]');
                if (pageInput) {
                    pageInput.value = '1';
                }

                filterForm.submit();
            });
        }
    });
});

/**
 * goToMonPage(pageNum)
 * Navega a la página indicada preservando los filtros activos del formulario.
 * Expuesto globalmente para los botones onclick del paginador (estilo formaciones).
 * @param {number} pageNum - Número de página destino
 */
window.goToMonPage = function (pageNum) {
    const form = document.getElementById('monitoring-filter-form');
    if (!form) return;

    const params = new URLSearchParams();

    const searchInput  = document.getElementById('monitoring-search-input');
    const stateSelect  = document.getElementById('monitoring-state-select');
    const moduleSelect = document.getElementById('monitoring-module-select');
    const statusSelect = document.getElementById('monitoring-status-select');

    if (searchInput  && searchInput.value.trim())  params.set('search',    searchInput.value.trim());
    if (stateSelect  && stateSelect.value)          params.set('state_id',  stateSelect.value);
    if (moduleSelect && moduleSelect.value)         params.set('module_id', moduleSelect.value);
    if (statusSelect && statusSelect.value)         params.set('status_id', statusSelect.value);

    if (pageNum && pageNum > 1) params.set('page', pageNum.toString());

    const action = form.getAttribute('action') || window.location.pathname;
    window.location.href = action + (params.toString() ? '?' + params.toString() : '');
};
