/**
 * Archivo: requests_active_workspace.js
 * Descripción: Interactividad del Espacio de Trabajo Activo (Vista B.6 - US-46 Actividad 1)
 */

document.addEventListener('DOMContentLoaded', function () {
    const rootEl = document.getElementById('active-workspace-root');
    if (!rootEl) return;

    const canComplete = rootEl.dataset.canComplete === 'true';

    // =========================================================================
    // Botón Formalizar y Marcar como Completada (Reservado a US-48)
    // =========================================================================
    const btnCompleteRequest = document.getElementById('btn-complete-request');
    if (btnCompleteRequest) {
        btnCompleteRequest.addEventListener('click', function () {
            if (!canComplete) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Recaudos Incompletos',
                        text: 'Debe adjuntar al menos una fotografía de la jornada y el acta de asistencia firmada en formato PDF antes de formalizar la culminación.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert('Debe adjuntar al menos una fotografía y el acta firmada.');
                }
                return;
            }

            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: 'Requisitos Probatorios Conformes',
                    text: 'El expediente cuenta con los soportes probatorios mínimos requeridos (fotografía y acta firmada). La interfaz del Espacio de Trabajo Activo queda lista y validada para enlazar la transacción de cierre formal en la historia US-48.',
                    icon: 'success',
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Entendido'
                });
            } else {
                alert('Requisitos Probatorios Conformes. Listo para enlazar a US-48.');
            }
        });
    }
});
