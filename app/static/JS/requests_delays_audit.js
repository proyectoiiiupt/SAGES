/**
 * requests_delays_audit.js
 * Lógica e interactividad para el Panel de Auditoría de Retrasos SLA (US-38-act2)
 * SAGES - Sistema Automatizado de Gestión para la Eficiencia Social
 *
 * Características:
 *  - Carga asíncrona de descargos (Fetch API) y despliegue en modal.
 *  - Disparador coercitivo con confirmación SweetAlert2 y control anti-doble envío.
 *  - Manejo de respuestas 429 Too Many Requests por Flask-Limiter.
 *  - Filtrado reactivo y preservación de parámetros en URL.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mostrar fecha local actual
    const dateDisplay = document.getElementById('audit-current-date');
    if (dateDisplay) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateDisplay.textContent = formattedDate.replace(' de 20', ', 20');
    }

    // 2. Control de Filtros reactivos y Búsqueda con Debounce
    const filterForm = document.getElementById('audit-filter-form');
    const searchInput = document.getElementById('audit-search-input');
    const stateSelect = document.getElementById('audit-state-select');
    const justificationSelect = document.getElementById('audit-justification-select');
    const clearSearchBtn = document.getElementById('audit-clear-search');

    if (filterForm) {
        // Enviar formulario al alterar cualquier select reseteando a página 1
        const selects = [stateSelect, justificationSelect];
        selects.forEach(sel => {
            if (sel) {
                sel.addEventListener('change', () => {
                    const pageInput = filterForm.querySelector('input[name="page"]');
                    if (pageInput) pageInput.value = '1';
                    filterForm.submit();
                });
            }
        });

        // Debounce en búsqueda textual (400ms)
        if (searchInput) {
            let debounceTimer = null;
            let lastQuery = searchInput.value.trim();

            searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    const currentQuery = e.target.value.trim();
                    if (currentQuery !== lastQuery) {
                        lastQuery = currentQuery;
                        const pageInput = filterForm.querySelector('input[name="page"]');
                        if (pageInput) pageInput.value = '1';
                        filterForm.submit();
                    }
                }, 400);
            });

            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const currentQuery = searchInput.value.trim();
                    if (currentQuery !== lastQuery) {
                        lastQuery = currentQuery;
                        const pageInput = filterForm.querySelector('input[name="page"]');
                        if (pageInput) pageInput.value = '1';
                        filterForm.submit();
                    }
                }
            });
        }

        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                if (searchInput) {
                    searchInput.value = '';
                    const pageInput = filterForm.querySelector('input[name="page"]');
                    if (pageInput) pageInput.value = '1';
                    filterForm.submit();
                }
            });
        }
    }

    // 3. Modal de Inspección de Descargos Operativos
    const modalBackdrop = document.getElementById('justificationModal');
    const modalCloseBtn = document.getElementById('closeJustificationModalBtn');
    const modalCloseActionBtn = document.getElementById('modalCloseActionBtn');
    const modalLoader = document.getElementById('modalLoader');
    const modalDataContent = document.getElementById('modalDataContent');

    function openModal() {
        if (!modalBackdrop) return;
        modalBackdrop.style.display = 'flex';
        // Forzar reflow para animación CSS
        void modalBackdrop.offsetWidth;
        modalBackdrop.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        if (!modalBackdrop) return;
        modalBackdrop.classList.remove('show');
        setTimeout(() => {
            modalBackdrop.style.display = 'none';
            document.body.style.overflow = '';
        }, 250);
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
    if (modalCloseActionBtn) modalCloseActionBtn.addEventListener('click', closeModal);

    if (modalBackdrop) {
        modalBackdrop.addEventListener('click', (e) => {
            if (e.target === modalBackdrop) closeModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modalBackdrop.classList.contains('show')) {
                closeModal();
            }
        });
    }

    // Interceptar botones "Leer Justificación"
    document.querySelectorAll('.btn-view-justification').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const requestId = btn.getAttribute('data-request-id');
            if (!requestId) return;

            openModal();
            if (modalLoader) modalLoader.style.display = 'block';
            if (modalDataContent) modalDataContent.style.display = 'none';

            try {
                const response = await fetch(`/requests/api/delays/${requestId}/justification`, {
                    headers: { 'Accept': 'application/json' }
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error || 'No se pudo obtener el descargo.');
                }

                const data = await response.json();

                // Llenar campos del modal
                const elInstName = document.getElementById('modal-institution-name');
                const elType = document.getElementById('modal-justification-type');
                const elReason = document.getElementById('modal-reason-name');
                const elDate = document.getElementById('modal-created-at');
                const elSubmitter = document.getElementById('modal-submitted-by');
                const elText = document.getElementById('modal-justification-text');

                if (elInstName) elInstName.textContent = data.institution_name || 'Plantel Educativo';
                if (elType) {
                    elType.textContent = (data.justification_type === 'RETRASO_EJECUCION')
                        ? 'Ejecución Presencial'
                        : 'Atención Inicial';
                }
                if (elReason) elReason.textContent = data.reason_name || 'Causa Justificada';
                if (elDate) elDate.textContent = data.created_at || '-';
                if (elSubmitter) elSubmitter.textContent = data.submitted_by || '-';
                if (elText) elText.textContent = data.justification_text || 'Sin texto circunstanciado.';

                if (modalLoader) modalLoader.style.display = 'none';
                if (modalDataContent) modalDataContent.style.display = 'block';

            } catch (err) {
                closeModal();
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        title: 'Aviso de Inspección',
                        text: err.message || 'No fue posible cargar el descargo solicitado.',
                        icon: 'info',
                        confirmButtonColor: '#007865'
                    });
                } else {
                    alert(err.message);
                }
            }
        });
    });

    // 4. Disparador Coercitivo "Exigir Respuesta" con SweetAlert2
    document.querySelectorAll('.btn-demand-response').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const requestId = btn.getAttribute('data-request-id');
            const instName = btn.getAttribute('data-institution') || 'Plantel Educativo';

            if (!requestId) return;

            // Obtener token CSRF seguro
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            // Diálogo de Confirmación Previo Obligatorio
            if (typeof Swal === 'undefined') {
                if (!confirm(`¿Desea emitir intimación formal y notificación crítica para la atención del plantel ${instName}?`)) {
                    return;
                }
            } else {
                const result = await Swal.fire({
                    title: '¿Intimar al operador responsable?',
                    html: `
                        <div style="text-align: left; font-size: 0.92rem; color: #475569; line-height: 1.5;">
                            <p style="margin-bottom: 8px;">Se emitirá un <strong>requerimiento institucional urgente</strong> para la atención del plantel <strong style="color: #0f172a;">${instName}</strong>.</p>
                            <p style="margin-bottom: 0;">Esta acción despachará una notificación con severidad <span style="color: #dc2626; font-weight: 700;">CRÍTICA (DANGER)</span> a la campana del funcionario, enviará un correo electrónico formal de intimación y asentará la traza en la bitácora de auditoría.</p>
                        </div>
                    `,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, exigir respuesta',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#64748b',
                    reverseButtons: true,
                    focusCancel: true
                });

                if (!result.isConfirmed) return;
            }

            // Bloqueo Inmediato Anti-Doble Envío y Spinner de Carga
            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="width: 14px; height: 14px; border: 2px solid #ffffff; border-top-color: transparent; border-radius: 50%; display: inline-block; vertical-align: middle; animation: spin 0.8s linear infinite;"></span>
                <span>Intimando...</span>
            `;

            try {
                const response = await fetch(`/requests/api/delays/${requestId}/demand-response`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ''
                    }
                });

                const data = await response.json().catch(() => ({}));

                if (response.status === 200) {
                    // Éxito: transformar botón y notificar
                    btn.className = 'btn-action-audit btn-demand-success-state';
                    btn.disabled = true;
                    btn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width: 14px; height: 14px;">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Respuesta Exigida</span>
                    `;
                    btn.title = 'Requerimiento formal despachado exitosamente.';

                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: 'Requerimiento Despachado',
                            text: data.message || 'Se ha intimado exitosamente al operador responsable. El evento ha quedado registrado en la bitácora.',
                            icon: 'success',
                            confirmButtonColor: '#007865'
                        });
                    } else {
                        alert(data.message || 'Requerimiento despachado exitosamente.');
                    }
                } else if (response.status === 429) {
                    // Rate Limiter alcanzado (3 cada 2 horas)
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;

                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: 'Límite de Exigencias Alcanzado',
                            text: 'Se ha superado la cuota de 3 requerimientos cada 2 horas para este expediente. Por favor, espere antes de reintentar.',
                            icon: 'warning',
                            confirmButtonColor: '#d97706'
                        });
                    } else {
                        alert('Límite de requerimientos alcanzado (máx. 3 cada 2 horas).');
                    }
                } else {
                    // Errores controlados (403, 404, 422, 500)
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;

                    const errorMsg = data.message || data.error || 'Ocurrió un error al despachar la exigencia.';
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: 'No se pudo emitir la exigencia',
                            text: errorMsg,
                            icon: 'error',
                            confirmButtonColor: '#dc2626'
                        });
                    } else {
                        alert(errorMsg);
                    }
                }

            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        title: 'Error de Conexión',
                        text: 'Fallo al comunicarse con el servidor. Verifique su conexión y reintente.',
                        icon: 'error',
                        confirmButtonColor: '#dc2626'
                    });
                } else {
                    alert('Error de conexión al despachar requerimiento.');
                }
            }
        });
    });
});

/**
 * goToAuditPage(pageNum)
 * Paginación defensiva que preserva los filtros de búsqueda y estado actuales.
 * @param {number} pageNum - Número de página destino
 */
window.goToAuditPage = function(pageNum) {
    const form = document.getElementById('audit-filter-form');
    if (!form) return;

    const pageInput = form.querySelector('input[name="page"]');
    if (pageInput) {
        pageInput.value = pageNum;
    }

    form.submit();
};
