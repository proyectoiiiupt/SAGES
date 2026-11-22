/**
 * ============================================================================
 * CONTROLADOR JS: ARCHIVO HISTÓRICO DE SOLICITUDES (state_history.html)
 * SAGES — CORPOELEC (UREE)
 * ============================================================================
 */
(function () {
    'use strict';

    const DEBOUNCE_DELAY = 400;

    document.addEventListener('DOMContentLoaded', function () {
        initCurrentDate();
        initSearchDebounce();
        initFilterAutoSubmit();
    });

    /**
     * 1. Fecha Dinámica del Sistema (Formato Institucional SAGES)
     */
    function initCurrentDate() {
        const dateEl = document.getElementById('current-date');
        if (!dateEl) return;

        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formatted = today.toLocaleDateString('es-ES', options);
        dateEl.textContent = formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }

    /**
     * 2. Búsqueda con Técnica Debounce (400 ms) y Sanitización en Vivo
     */
    function initSearchDebounce() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        let debounceTimer = null;

        searchInput.addEventListener('input', function () {
            const rawVal = searchInput.value;
            const sanitizedVal = rawVal.replace(/[<>"'`;]/g, '');

            if (rawVal !== sanitizedVal) {
                searchInput.value = sanitizedVal;
            }

            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                submitFormWithPage(1);
            }, DEBOUNCE_DELAY);
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                submitFormWithPage(1);
            }
        });
    }

    /**
     * 3. Auto-Envío en Filtros Desplegables
     */
    function initFilterAutoSubmit() {
        const autoInputs = [
            document.getElementById('state-select'),
            document.getElementById('status-select'),
            document.getElementById('municipality-select')
        ];

        autoInputs.forEach(function (el) {
            if (!el) return;
            el.addEventListener('change', function () {
                submitFormWithPage(1);
            });
        });
    }

    /**
     * 4. Paginación y Persistencia de Parámetros
     */
    function submitFormWithPage(pageNum) {
        const form = document.getElementById('historical-filter-form');
        if (!form) return;

        const params = new URLSearchParams();
        const searchInput = document.getElementById('search-input');
        const stateSelect = document.getElementById('state-select');
        const statusSelect = document.getElementById('status-select');
        const municipalitySelect = document.getElementById('municipality-select');

        if (searchInput && searchInput.value.trim()) {
            params.set('search', searchInput.value.trim());
        }
        if (stateSelect && stateSelect.value) {
            params.set('state_id', stateSelect.value);
        }
        if (statusSelect && statusSelect.value) {
            params.set('status', statusSelect.value);
        }
        if (municipalitySelect && municipalitySelect.value) {
            params.set('municipality_id', municipalitySelect.value);
        }

        if (pageNum && pageNum > 1) {
            params.set('page', pageNum.toString());
        }

        const targetUrl = form.getAttribute('action') + (params.toString() ? '?' + params.toString() : '');
        window.location.href = targetUrl;
    }

    window.goToPage = function (pageNum) {
        submitFormWithPage(pageNum);
    };
})();
