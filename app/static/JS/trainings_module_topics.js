/**
 * trainings_module_topics.js
 * Lógica cliente para la Vista Focalizada de Temas por Módulo Rector
 *
 * Responsabilidades:
 *  1. Inicializar la fecha dinámica del sistema en formato institucional español.
 *  2. Búsqueda y filtrado reactivo en tiempo real con debounce.
 *  3. Navegación de página con persistencia del filtro de búsqueda.
 *
 * Nota de alcance:
 *  La acción de visualización detallada (modal) está reservada
 *  para una tarea posterior del plan de desarrollo de SAGES.
 */

(function () {
    'use strict';

    /* ── Constantes ─────────────────────────────────────────────────── */
    const SEARCH_DEBOUNCE_DELAY = 250; // ms de espera en debounce para búsqueda

    /* ── Inicialización ─────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        initCurrentDate();
        initSearchFilter();
    });

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 1. Fecha Dinámica del Sistema (Formato Institucional SAGES)
     * Ejemplo: "23 de septiembre de 2026"
     */
    function initCurrentDate() {
        const dateEl = document.getElementById('current-date');
        if (!dateEl) return;

        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formatted = today.toLocaleDateString('es-ES', options);
        dateEl.textContent = formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 2. Búsqueda y Filtrado Reactivo en la Tabla (por nombre del tema formativo)
     */
    function initSearchFilter() {
        const searchInput = document.getElementById('search-input');
        const clearBtn = document.getElementById('btn-clear-search');
        const clearWrapper = document.getElementById('search-clear-wrapper');
        const noResultsRow = document.getElementById('no-results-row');
        const rows = document.querySelectorAll('#topics-table-body .topic-row');

        if (!searchInput) return;

        let debounceTimer = null;

        function applyFilter() {
            const rawVal = searchInput.value.trim().toLowerCase();
            let visibleCount = 0;

            if (clearWrapper) {
                clearWrapper.style.display = rawVal.length > 0 ? 'block' : 'none';
            }

            rows.forEach(function (row) {
                const name = row.getAttribute('data-name') || '';

                if (!rawVal || name.includes(rawVal)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            if (noResultsRow) {
                noResultsRow.style.display = (visibleCount === 0 && rows.length > 0) ? '' : 'none';
            }
        }

        searchInput.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(applyFilter, SEARCH_DEBOUNCE_DELAY);
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                searchInput.value = '';
                applyFilter();
                searchInput.focus();
            });
        }
    }


    /**
     * 4. Navegación de Página con Persistencia del Filtro de Búsqueda
     * Construye la URL destino conservando el query param 'search' si está activo.
     * @param {number} pageNum - Número de página objetivo
     */
    function navigateToPage(pageNum) {
        const params = new URLSearchParams(window.location.search);

        // Leer el valor actual del input de búsqueda
        const searchInput = document.getElementById('search-input');
        const searchVal = searchInput ? searchInput.value.trim() : '';

        if (searchVal) {
            params.set('search', searchVal);
        } else {
            params.delete('search');
        }

        if (pageNum && pageNum > 1) {
            params.set('page', pageNum.toString());
        } else {
            params.delete('page');
        }

        const baseUrl = window.location.pathname;
        window.location.href = baseUrl + (params.toString() ? '?' + params.toString() : '');
    }

    // Exponer globalmente para los botones del paginador en el template
    window.goToPage = navigateToPage;

})();
