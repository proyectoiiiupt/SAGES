/**
 * requests_survey.js — US-51 / SR-F-019
 * Widget interactivo de estrellas, validación de cliente y envío
 * asíncrono para la Encuesta de Satisfacción Post-Cierre.
 *
 * Dependencias: SweetAlert2 (sweetalert2.all.min.js, cargado en el layout base)
 */

'use strict';

document.addEventListener('DOMContentLoaded', () => {

    // ================================================================
    // 1. INICIALIZACIÓN DEL WIDGET DE ESTRELLAS
    // ================================================================

    /**
     * Ilumina las estrellas del 1 hasta upTo inclusive.
     * Si selected=true aplica .selected; si selected=false aplica .hovered.
     * Limpia ambas clases en el resto.
     */
    function applyStarState(stars, upTo, selected) {
        stars.forEach(star => {
            const val = parseInt(star.dataset.value, 10);
            star.classList.remove('hovered', 'selected');
            if (val <= upTo) {
                star.classList.add(selected ? 'selected' : 'hovered');
            }
        });
    }

    /**
     * Restaura el grupo de estrellas al último valor fijado (currentValue).
     * Si currentValue === 0, apaga todas.
     */
    function restoreStars(stars, currentValue) {
        stars.forEach(star => {
            const val = parseInt(star.dataset.value, 10);
            star.classList.remove('hovered', 'selected');
            if (val <= currentValue) {
                star.classList.add('selected');
            }
        });
    }

    // Registrar comportamiento en cada grupo de estrellas
    document.querySelectorAll('.star-rating-group').forEach(group => {
        const stars      = Array.from(group.querySelectorAll('.star'));
        const fieldId    = group.dataset.field;
        const hiddenInput = document.getElementById(fieldId);
        let currentValue = 0;

        // Hover: iluminar hasta la estrella N
        stars.forEach(star => {
            star.addEventListener('mouseenter', () => {
                const val = parseInt(star.dataset.value, 10);
                applyStarState(stars, val, false);
            });
        });

        // Mouseleave en el grupo: restaurar al valor fijado
        group.addEventListener('mouseleave', () => {
            restoreStars(stars, currentValue);
        });

        // Click: fijar valor y limpiar estado de error
        stars.forEach(star => {
            star.addEventListener('click', () => {
                const val = parseInt(star.dataset.value, 10);
                currentValue       = val;
                hiddenInput.value  = val;
                applyStarState(stars, val, true);

                // Limpiar estado de error visual
                group.classList.remove('error');
                const card    = document.getElementById(`card-${fieldId}`);
                const errMsg  = document.getElementById(`err-${fieldId}`);
                if (card)   card.classList.remove('has-error');
                if (errMsg) errMsg.style.display = 'none';
            });
        });
    });

    // ================================================================
    // 2. CONTADOR DE CARACTERES EN EL TEXTAREA
    // ================================================================

    const commentBox = document.getElementById('comment');
    const charCount  = document.getElementById('charCount');

    if (commentBox && charCount) {
        commentBox.addEventListener('input', () => {
            charCount.textContent = commentBox.value.length;
        });
    }

    // ================================================================
    // 3. ENVÍO ASÍNCRONO CON VALIDACIÓN DE CLIENTE
    // ================================================================

    const form    = document.getElementById('surveyForm');
    const btn     = document.getElementById('btnSubmitSurvey');
    const btnText = btn ? btn.querySelector('.btn-survey-text')    : null;
    const btnLoad = btn ? btn.querySelector('.btn-survey-loading') : null;

    if (!form || !btn) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // --- 3.1 Validar que las 3 preguntas tengan valor >= 1 ---
        const requiredFields = ['score_activity', 'score_instructor', 'score_admin_response'];
        let allValid = true;

        requiredFields.forEach(fieldId => {
            const hiddenInput = document.getElementById(fieldId);
            const val         = parseInt(hiddenInput ? hiddenInput.value : '0', 10);
            const group       = document.getElementById(`group-${fieldId}`);
            const card        = document.getElementById(`card-${fieldId}`);
            const errMsg      = document.getElementById(`err-${fieldId}`);

            if (!val || val < 1) {
                allValid = false;
                if (group)  group.classList.add('error');
                if (card)   card.classList.add('has-error');
                if (errMsg) errMsg.style.display = 'block';
            }
        });

        if (!allValid) {
            // Desplazar al primer campo sin calificar
            const firstError = document.querySelector('.survey-question-card.has-error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            Swal.fire({
                icon: 'warning',
                title: 'Atención',
                text: 'Por favor, califique las 3 preguntas antes de enviar la encuesta.',
                confirmButtonText: 'Entendido',
                confirmButtonColor: '#019577'
            });
            return;
        }

        // --- 3.2 Deshabilitar botón y mostrar spinner (anti-doble clic) ---
        btn.disabled = true;
        if (btnText) btnText.style.display = 'none';
        if (btnLoad) btnLoad.style.display = 'inline-flex';

        // --- 3.3 Enviar vía Fetch API ---
        try {
            const formData = new FormData(form);
            const response = await fetch(form.action, {
                method:  'POST',
                body:    formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Confirmación exitosa → redirigir al panel
                await Swal.fire({
                    icon:              'success',
                    title:             '¡Muchas gracias por su opinión!',
                    text:              'Su evaluación ha sido registrada exitosamente.',
                    confirmButtonText: 'Ir a mis solicitudes',
                    confirmButtonColor: '#019577',
                    allowOutsideClick: false,
                    allowEscapeKey:    false
                });
                window.location.href = '/requests/my-requests';

            } else {
                // Error devuelto por el servidor
                Swal.fire({
                    icon:              'error',
                    title:             'No se pudo registrar la evaluación',
                    text:              data.message || 'Ha ocurrido un error inesperado.',
                    confirmButtonText: 'Cerrar',
                    confirmButtonColor: '#019577'
                });
                // Rehabilitar el botón
                btn.disabled = false;
                if (btnText) btnText.style.display = 'inline-flex';
                if (btnLoad) btnLoad.style.display = 'none';
            }

        } catch (networkError) {
            Swal.fire({
                icon:              'error',
                title:             'Error de conexión',
                text:              'No se pudo conectar con el servidor. Verifique su conexión e intente nuevamente.',
                confirmButtonText: 'Cerrar',
                confirmButtonColor: '#019577'
            });
            btn.disabled = false;
            if (btnText) btnText.style.display = 'inline-flex';
            if (btnLoad) btnLoad.style.display = 'none';
        }
    });

});
