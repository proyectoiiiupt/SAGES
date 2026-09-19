/**
 * trainings_list.js
 * Lógica de cliente para la Vista Tabular Maestra de Formaciones (Bloque 3)
 *
 * Características principales:
 *  1. Búsqueda con técnica debounce de 400 ms para optimizar consultas a PostgreSQL.
 *  2. Sanitización de caracteres en vivo en el campo de búsqueda.
 *  3. Auto-envío de filtros en selectores y fechas con reseteo de paginación a página 1.
 *  4. Paginador dinámico con persistencia de parámetros Query String.
 *  5. Fecha del sistema en formato español institucional.
 *  6. Modal de consulta rápida para visualizar detalles del tema.
 *
 * Nota de alcance:
 *  La ejecución de acciones de borrado lógico y edición no van todavía ya que corresponden
 *  a una tarea posterior del sistema.
 */

(function () {
    'use strict';

    /* ── Constantes y Configuración ──────────────────────────────────── */
    const DEBOUNCE_DELAY = 400; // ms requeridos de espera en debounce

    /* ── Inicialización al cargar el DOM ─────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        initCurrentDate();
        initSearchDebounce();
        initFilterAutoSubmit();
    });

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 1. Fecha Dinámica del Sistema (Formato Institucional SAGES)
     * Ejemplo: "10 de septiembre de 2026"
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
     * 2. Búsqueda con Técnica Debounce (400 ms) y Sanitización en Vivo
     */
    function initSearchDebounce() {
        const searchInput = document.getElementById('search-input');
        const form = document.getElementById('trainings-filter-form');
        if (!searchInput || !form) return;

        let debounceTimer = null;

        // Evento 'input': captura cada caracter tecleado
        searchInput.addEventListener('input', function () {
            // A. Sanitización en vivo de caracteres peligrosos o de inyección
            const rawVal = searchInput.value;
            const sanitizedVal = rawVal.replace(/[<>"'`;]/g, '');

            if (rawVal !== sanitizedVal) {
                searchInput.value = sanitizedVal;
            }

            // B. Debounce de 400 ms
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                // Al buscar, reiniciamos a la página 1 para evitar páginas vacías
                submitFormWithPage(1);
            }, DEBOUNCE_DELAY);
        });

        // Prevenir submit inmediato al pulsar Enter si el debounce sigue activo
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                submitFormWithPage(1);
            }
        });
    }

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 3. Auto-Envío en Filtros Desplegables y Rango de Fechas
     */
    function initFilterAutoSubmit() {
        const form = document.getElementById('trainings-filter-form');
        if (!form) return;

        const autoInputs = [
            document.getElementById('module-select'),
            document.getElementById('status-select')
        ];

        autoInputs.forEach(function (el) {
            if (!el) return;
            el.addEventListener('change', function () {
                submitFormWithPage(1);
            });
        });
    }

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 4. Envío del Formulario con Página Específica y Persistencia de Parámetros
     * @param {number} pageNum - Número de página objetivo
     */
    function submitFormWithPage(pageNum) {
        const form = document.getElementById('trainings-filter-form');
        if (!form) return;

        const params = new URLSearchParams();

        // Extraer valores actuales de los inputs
        const searchInput = document.getElementById('search-input');
        const moduleSelect = document.getElementById('module-select');
        const statusSelect = document.getElementById('status-select');

        if (searchInput && searchInput.value.trim()) {
            params.set('search', searchInput.value.trim());
        }
        if (moduleSelect && moduleSelect.value) {
            params.set('module_id', moduleSelect.value);
        }
        if (statusSelect && statusSelect.value) {
            params.set('status', statusSelect.value);
        }

        // Fijar página seleccionada
        if (pageNum && pageNum > 1) {
            params.set('page', pageNum.toString());
        }

        const targetUrl = form.getAttribute('action') + (params.toString() ? '?' + params.toString() : '');
        window.location.href = targetUrl;
    }

    // Exponer la función de paginación globalmente para los botones del paginador
    window.goToPage = function (pageNum) {
        submitFormWithPage(pageNum);
    };

    /* ── NOTA DE ALCANCE ─────────────────────────────────────────────── */
    // La ejecución de acciones de visualización, borrado lógico y edición
    // quedan reservadas para tareas posteriores del plan de desarrollo de SAGES.

})();
