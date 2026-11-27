/**
 * trainings_list.js
 * Lógica de cliente para la Vista Tabular Maestra de Formaciones (Bloque 3)
 *
 * Características principales:
 *  1. Búsqueda con técnica debounce de 400 ms para optimizar consultas a PostgreSQL.
 *  2. Sanitización de caracteres en vivo en el campo de búsqueda.
 *  3. Auto-envío de filtros en selectores con reseteo de paginación a página 1.
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
        initSearchDebounce();
        initFilterAutoSubmit();
        initToggleTrainingStatus();
    });

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
     * 3. Auto-Envío en Filtros Desplegables
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

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 5. Cambio de Estatus (Activar / Inactivar) de Tema Formativo (Super Admin)
     */
    function initToggleTrainingStatus() {
        const table = document.getElementById('trainings-table');
        if (!table) return;

        table.addEventListener('click', async function (e) {
            const btn = e.target.closest('.toggle-status-action-btn');
            if (!btn || btn.disabled) return;

            const trainingId = btn.dataset.trainingId;
            const trainingName = btn.dataset.trainingName || 'este tema formativo';
            const isCurrentlyActive = btn.dataset.isActive === 'true';
            const actionVerb = isCurrentlyActive ? 'inactivar' : 'activar';
            const actionTitle = isCurrentlyActive ? '¿Inactivar tema formativo?' : '¿Activar tema formativo?';
            const confirmText = isCurrentlyActive
                ? `¿Desea inactivar temporalmente "${trainingName}"? Dejará de estar disponible para nuevas solicitudes.`
                : `¿Desea activar "${trainingName}" para habilitarlo nuevamente en el catálogo?`;

            const confirmResult = await Swal.fire({
                title: actionTitle,
                text: confirmText,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: isCurrentlyActive ? '#f59e0b' : '#10b981',
                cancelButtonColor: '#64748b',
                confirmButtonText: `Sí, ${actionVerb}`,
                cancelButtonText: 'Cancelar'
            });

            if (!confirmResult.isConfirmed) return;

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            btn.disabled = true;

            try {
                const response = await fetch(`/training/toggle_status/${trainingId}`, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    }
                });

                const data = await response.json().catch(() => ({}));

                if (response.ok && data.success === true) {
                    const nextActive = Boolean(data.is_active);
                    const nextCode = data.new_status_code || (nextActive ? 'STAT-001' : 'STAT-002');
                    const nextLabel = data.new_status_name || (nextActive ? 'Activo' : 'Inactivo');

                    const badge = document.querySelector(`[data-status-badge-for="${trainingId}"]`);
                    if (badge) {
                        badge.textContent = nextLabel;
                        badge.className = `status-badge status-${nextCode}`;
                    }

                    btn.classList.toggle('is-active', nextActive);
                    btn.classList.toggle('is-inactive', !nextActive);
                    btn.dataset.isActive = nextActive ? 'true' : 'false';
                    btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
                    btn.setAttribute('title', nextActive ? 'Inactivar tema formativo' : 'Activar tema formativo');
                    btn.setAttribute('aria-label', `${nextActive ? 'Inactivar' : 'Activar'} ${trainingName}`);

                    await Swal.fire({
                        title: '¡Actualizado!',
                        text: data.message || 'Estatus actualizado exitosamente.',
                        icon: 'success',
                        confirmButtonColor: '#007865',
                        confirmButtonText: 'Aceptar'
                    });
                } else if (response.status === 401) {
                    await Swal.fire(
                        'Sesión expirada',
                        data.error || data.message || 'Tu sesión ha expirado. Inicia sesión nuevamente.',
                        'warning'
                    );
                    window.location.href = '/auth/login';
                } else {
                    const isConflict = response.status === 409;
                    await Swal.fire(
                        isConflict ? 'Operación bloqueada' : 'Error',
                        data.message || data.error || 'No se pudo cambiar el estatus del tema formativo.',
                        isConflict ? 'warning' : 'error'
                    );
                }
            } catch (error) {
                console.error('Error al cambiar estatus del tema:', error);
                await Swal.fire('Error', 'Ocurrió un error de red al intentar cambiar el estatus.', 'error');
            } finally {
                btn.disabled = false;
            }
        });
    }

})();
