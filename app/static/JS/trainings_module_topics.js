/**
 * trainings_module_topics.js
 * Lógica cliente para la Vista Focalizada de Temas por Módulo Rector
 *
 * Responsabilidades:
 *  1. Inicializar la fecha dinámica del sistema en formato institucional español.
 *  2. Búsqueda y filtrado reactivo en tiempo real con debounce.
 *  3. Navegación de página con persistencia del filtro de búsqueda.
 */

(function () {
    'use strict';

    /* ── Constantes ─────────────────────────────────────────────────── */
    const SEARCH_DEBOUNCE_DELAY = 250; // ms de espera en debounce para búsqueda

    /* ── Inicialización ─────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        initSearchFilter();
        initToggleTrainingStatus();
    });

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
                const params = new URLSearchParams(window.location.search);
                if (params.has('search')) {
                    window.location.href = window.location.pathname;
                    return;
                }
                searchInput.value = '';
                applyFilter();
                searchInput.focus();
            });
        }
    }


    /**
     * 3. Navegación de Página con Persistencia del Filtro de Búsqueda
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

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * 4. Cambio de Estatus (Activar / Inactivar) de Tema Formativo (Super Admin)
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
