/**
 * app/static/JS/applicant_request_detail.js
 * Lógica interactiva para la ficha de seguimiento y desistimiento voluntario (US-44).
 * Maneja el modal interactivo, validación dual en cliente, envío AJAX y feedback con SweetAlert2.
 */

'use strict';

document.addEventListener('DOMContentLoaded', function () {
    // 1. Elementos del DOM del Modal de Desistimiento
    const modalBackdrop = document.getElementById('applicantCancellationModal');
    const openModalBtn = document.getElementById('openCancellationModalBtn');
    const closeModalBtn = document.getElementById('closeCancellationModalBtn');
    const abortModalBtn = document.getElementById('abortCancellationBtn');
    const cancelForm = document.getElementById('applicantCancelForm');
    const reasonSelect = document.getElementById('cancel-reason-select');
    const justificationTextarea = document.getElementById('cancel-justification');
    const submitBtn = document.getElementById('submitCancellationBtn');
    const currentCharsSpan = document.getElementById('currentChars');
    const charCounterWrap = document.getElementById('justificationCharCounter');
    const charHint = document.getElementById('charLengthHint');

    if (!modalBackdrop || !cancelForm) {
        // Si los componentes del modal no están presentes en la vista, salir pacíficamente
        return;
    }

    const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    const btnSpinner = submitBtn ? submitBtn.querySelector('.btn-spinner') : null;

    // 2. Funciones de apertura y cierre del Modal
    function openModal() {
        modalBackdrop.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        resetFormValidation();

        // Foco de accesibilidad en el primer campo
        if (reasonSelect) {
            setTimeout(() => reasonSelect.focus(), 100);
        }
    }

    function closeModal() {
        modalBackdrop.style.display = 'none';
        document.body.style.overflow = '';
        resetFormValidation();
    }

    function resetFormValidation() {
        cancelForm.reset();
        if (currentCharsSpan) currentCharsSpan.textContent = '0';
        if (charCounterWrap) charCounterWrap.classList.remove('valid');
        if (charHint) {
            charHint.textContent = 'Mínimo 10 caracteres obligatorios (máx. 500).';
            charHint.style.color = '#6b7280';
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            if (btnText) btnText.textContent = 'Confirmar Cancelación';
            if (btnSpinner) btnSpinner.style.display = 'none';
        }
    }

    // 3. Validación en tiempo real (Client-side Validation)
    function validateInput() {
        const hasReason = reasonSelect && reasonSelect.value !== '' && !reasonSelect.value.startsWith('--');
        const textValue = justificationTextarea ? justificationTextarea.value.trim() : '';
        const charCount = textValue.length;

        if (currentCharsSpan) {
            currentCharsSpan.textContent = charCount;
        }

        const isLengthValid = charCount >= 10 && charCount <= 500;

        if (charCounterWrap) {
            if (isLengthValid) {
                charCounterWrap.classList.add('valid');
            } else {
                charCounterWrap.classList.remove('valid');
            }
        }

        if (charHint) {
            if (charCount > 0 && charCount < 10) {
                charHint.textContent = `Faltan ${10 - charCount} caracteres para alcanzar el mínimo requerido.`;
                charHint.style.color = '#ef4444';
            } else if (isLengthValid) {
                charHint.textContent = 'Longitud de justificación válida.';
                charHint.style.color = '#019577';
            } else {
                charHint.textContent = 'Mínimo 10 caracteres obligatorios (máx. 500).';
                charHint.style.color = '#6b7280';
            }
        }

        // Habilitar o deshabilitar botón de confirmación
        if (submitBtn) {
            submitBtn.disabled = !(hasReason && isLengthValid);
        }
    }

    // 4. Registro de Event Listeners
    if (openModalBtn) {
        openModalBtn.addEventListener('click', openModal);
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }

    if (abortModalBtn) {
        abortModalBtn.addEventListener('click', closeModal);
    }

    // Cerrar al hacer clic en el backdrop fuera del diálogo
    modalBackdrop.addEventListener('click', function (event) {
        if (event.target === modalBackdrop) {
            closeModal();
        }
    });

    // Accesibilidad: Cerrar con tecla Escape
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modalBackdrop.style.display === 'flex') {
            closeModal();
        }
    });

    if (reasonSelect) {
        reasonSelect.addEventListener('change', validateInput);
    }

    if (justificationTextarea) {
        justificationTextarea.addEventListener('input', validateInput);
    }

    // 5. Envío Asíncrono del Desistimiento (AJAX Fetch)
    submitBtn.addEventListener('click', async function (event) {
        event.preventDefault();

        const requestId = cancelForm.getAttribute('data-request-id');
        const reasonId = reasonSelect.value;
        const justification = justificationTextarea.value.trim();

        if (!reasonId || justification.length < 10) {
            return;
        }

        // Extraer token CSRF del formulario o de la etiqueta meta
        const csrfTokenInput = cancelForm.querySelector('input[name="csrf_token"]');
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenInput ? csrfTokenInput.value : (csrfMeta ? csrfMeta.getAttribute('content') : '');

        // Estado visual de procesamiento (Prevenir doble envío)
        submitBtn.disabled = true;
        if (btnText) btnText.textContent = 'Procesando...';
        if (btnSpinner) btnSpinner.style.display = 'inline-block';

        const endpointUrl = `/requests/api/applicant/${requestId}/cancel`;

        const formData = new FormData();
        formData.append('csrf_token', csrfToken);
        formData.append('reason_id', reasonId);
        formData.append('justification', justification);

        try {
            const response = await fetch(endpointUrl, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            const result = await response.json().catch(() => ({}));

            if (response.ok && result.success) {
                // Cerrar modal
                closeModal();

                // Alerta SweetAlert2 de confirmación exitosa
                if (typeof Swal !== 'undefined') {
                    await Swal.fire({
                        icon: 'success',
                        title: 'Desistimiento Exitoso',
                        text: result.message || 'Su solicitud ha sido cancelada exitosamente y trasladada a su historial.',
                        confirmButtonText: 'Entendido',
                        confirmButtonColor: '#019577',
                        allowOutsideClick: false,
                        allowEscapeKey: false
                    });
                }

                // Redirigir al panel principal de Mis Solicitudes
                window.location.href = '/requests/my-requests';
            } else {
                // Restaurar estado del botón
                submitBtn.disabled = false;
                if (btnText) btnText.textContent = 'Confirmar Cancelación';
                if (btnSpinner) btnSpinner.style.display = 'none';

                const errorMsg = result.message || 'No fue posible procesar la cancelación de la solicitud.';

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo cancelar',
                        text: errorMsg,
                        confirmButtonText: 'Aceptar',
                        confirmButtonColor: '#dc2626'
                    });
                } else {
                    alert(errorMsg);
                }
            }
        } catch (error) {
            // Error de red o inesperado
            console.error('Error al procesar la cancelación:', error);
            submitBtn.disabled = false;
            if (btnText) btnText.textContent = 'Confirmar Cancelación';
            if (btnSpinner) btnSpinner.style.display = 'none';

            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Conexión',
                    text: 'Ocurrió un problema de comunicación con el servidor. Por favor intente nuevamente.',
                    confirmButtonText: 'Aceptar',
                    confirmButtonColor: '#dc2626'
                });
            } else {
                alert('Ocurrió un problema de comunicación con el servidor.');
            }
        }
    });
});

// 0. Renderizar la fecha actual en el banner superior sin día de la semana
const dateDisplay = document.getElementById('current-date-display');
if (dateDisplay) {
    const today = new Date();
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    // Usamos es-VE para mantener la configuración regional de Venezuela
    const formattedDate = today.toLocaleDateString('es-VE', options);
    // Aplica el formato requerido: "10 de octubre, 2026"
    dateDisplay.textContent = formattedDate.replace(' de 20', ', 20');
}