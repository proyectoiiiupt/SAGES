/**
 * Archivo: requests_active_workspace.js
 * Descripción: Interactividad del Espacio de Trabajo Activo (US-46 & US-48 Finalización Formal)
 */

document.addEventListener('DOMContentLoaded', function () {
    const rootEl = document.getElementById('active-workspace-root');
    if (!rootEl) return;

    /**
     * Obtención segura del Token CSRF para peticiones fetch AJAX
     */
    function getCsrfToken() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) return metaTag.getAttribute('content');
        const inputTag = document.querySelector('input[name="csrf_token"]');
        if (inputTag) return inputTag.value;
        return '';
    }

    // =========================================================================
    // Botón Formalizar y Marcar como Completada (US-48 / SR-F-019)
    // =========================================================================
    const btnCompleteRequest = document.getElementById('btn-complete-request');
    if (btnCompleteRequest) {
        btnCompleteRequest.addEventListener('click', function () {
            // 1. Evaluación dinámica del balance probatorio
            const isCanComplete = rootEl.dataset.canComplete === 'true';
            const hasPhoto = rootEl.dataset.hasPhoto === 'true';
            const hasPdf = rootEl.dataset.hasPdf === 'true';
            const requestId = btnCompleteRequest.dataset.requestId || rootEl.dataset.requestId;

            if (!isCanComplete) {
                let missingMsg = 'Debe adjuntar al menos una fotografía de la jornada y el acta de asistencia firmada en formato PDF antes de formalizar la culminación.';
                if (hasPhoto && !hasPdf) {
                    missingMsg = 'Falta adjuntar el acta de asistencia firmada en formato PDF para certificar el cumplimiento.';
                } else if (!hasPhoto && hasPdf) {
                    missingMsg = 'Falta adjuntar al menos una fotografía de la jornada formativa presencial.';
                }

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Recaudos Incompletos',
                        text: missingMsg,
                        confirmButtonColor: '#019577',
                        confirmButtonText: 'Entendido'
                    });
                } else {
                    alert(missingMsg);
                }
                return;
            }

            if (!requestId) {
                console.error('Identificador de solicitud no encontrado en el DOM.');
                return;
            }

            // 2. Diálogo SweetAlert2 de Confirmación Institucional
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: '¿Desea dar por culminada esta solicitud de formación?',
                    text: 'Esta acción transicionará el expediente a Completado y lo trasladará al archivo histórico de la UREE. Una vez formalizado el cierre, no se admitirán modificaciones ni carga de nuevos recaudos.',
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, finalizar solicitud',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#019577',
                    cancelButtonColor: '#64748b',
                    reverseButtons: true,
                    focusCancel: true
                }).then((result) => {
                    if (result.isConfirmed) {
                        executeFormalClosure(requestId);
                    }
                });
            } else {
                if (confirm('¿Desea dar por culminada esta solicitud de formación? La solicitud pasará al historial.')) {
                    executeFormalClosure(requestId);
                }
            }
        });
    }

    /**
     * Ejecuta la petición AJAX de cierre formal al backend (US-48)
     */
    function executeFormalClosure(requestId) {
        if (!btnCompleteRequest) return;

        // Deshabilitar botón durante el procesamiento para evitar doble clic
        btnCompleteRequest.setAttribute('disabled', 'disabled');

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'Procesando Culminación...',
                text: 'Validando recaudos en base de datos y archivando expediente.',
                allowOutsideClick: false,
                allowEscapeKey: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
        }

        const csrfToken = getCsrfToken();

        fetch(`/requests/api/${requestId}/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        })
        .then(async (response) => {
            const data = await response.json().catch(() => ({}));
            return { ok: response.ok, status: response.status, data: data };
        })
        .then(({ ok, status, data }) => {
            if (ok && data.success) {
                // Despliegue de Ventana de Éxito en Pantalla (Figma Flow)
                const redirectUrl = (data.data && data.data.redirect_url) ? data.data.redirect_url : '/requests/state-dashboard';

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Felicidades la Solicitud ha sido Finalizada con Éxito',
                        text: 'La Solicitud pasará al Historial',
                        confirmButtonText: 'Continuar',
                        confirmButtonColor: '#019577',
                        allowOutsideClick: false,
                        allowEscapeKey: false
                    }).then(() => {
                        window.location.href = redirectUrl;
                    });
                } else {
                    alert('Felicidades la Solicitud ha sido Finalizada con Éxito. La Solicitud pasará al Historial.');
                    window.location.href = redirectUrl;
                }
            } else {
                // Reactivar botón ante fallo de validación
                if (rootEl.dataset.canComplete === 'true') {
                    btnCompleteRequest.removeAttribute('disabled');
                }

                const errorMsg = data.message || 'No fue posible formalizar la culminación de la solicitud.';
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo culminar la solicitud',
                        text: errorMsg,
                        confirmButtonColor: '#019577',
                        confirmButtonText: 'Entendido'
                    });
                } else {
                    alert(errorMsg);
                }
            }
        })
        .catch((error) => {
            console.error('Error de red al completar solicitud:', error);
            if (rootEl.dataset.canComplete === 'true') {
                btnCompleteRequest.removeAttribute('disabled');
            }

            const connMsg = 'Ocurrió un problema de conexión al comunicarse con el servidor. Intente nuevamente.';
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Comunicación',
                    text: connMsg,
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Entendido'
                });
            } else {
                alert(connMsg);
            }
        });
    }
});

