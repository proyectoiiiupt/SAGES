document.addEventListener('DOMContentLoaded', () => {
    const form           = document.getElementById('corpoelecLoginForm');
    const idCardInput    = document.getElementById('id_card');
    const passwordInput  = document.getElementById('clave');
    const errorContainer = document.getElementById('mensajeError');

    // --- Spans de error por campo ---
    const idCardError   = document.getElementById('error-id_card');
    const passwordError = document.getElementById('error-clave');

    // --- Wrappers para borde rojo ---
    const idCardWrapper   = document.getElementById('wrapper-id_card');
    const passwordWrapper = document.getElementById('wrapper-clave');

    let errorTimeout;

    // =========================================================
    // Mensaje global (flash de Flask: cierre de sesión, etc.)
    // =========================================================
    const showMessage = (text, isSuccess = false) => {
        if (errorTimeout) clearTimeout(errorTimeout);

        if (isSuccess) {
            errorContainer.classList.add('success');
        } else {
            errorContainer.classList.remove('success');
        }

        errorContainer.textContent = text;
        errorContainer.style.display  = 'block';
        errorContainer.style.opacity  = '1';
        errorContainer.style.animation = 'none';
        errorContainer.offsetHeight;                     // reflow para reiniciar animación
        errorContainer.style.animation = 'shake 0.4s';

        errorTimeout = setTimeout(() => {
            errorContainer.style.transition = 'opacity 0.5s ease';
            errorContainer.style.opacity    = '0';
            setTimeout(() => {
                errorContainer.style.display    = 'none';
                errorContainer.style.transition = '';
            }, 500);
        }, 5000);
    };

    // Mostrar mensaje flash de Flask al cargar la página (ej: "Has cerrado sesión")
    if (errorContainer && errorContainer.textContent.trim() !== '' &&
        getComputedStyle(errorContainer).display !== 'none') {
        const isSuccess = errorContainer.classList.contains('success');
        showMessage(errorContainer.textContent.trim(), isSuccess);
    }

    // =========================================================
    // Helpers de error por campo
    // =========================================================
    const setFieldError = (input, wrapper, errorSpan, message) => {
        errorSpan.textContent = message;
        errorSpan.classList.add('visible');
        wrapper.classList.add('input-error');
        input.setAttribute('aria-invalid', 'true');
    };

    const clearFieldError = (input, wrapper, errorSpan) => {
        errorSpan.textContent = '';
        errorSpan.classList.remove('visible');
        wrapper.classList.remove('input-error');
        input.removeAttribute('aria-invalid');
    };

    // =========================================================
    // Validación en tiempo real — mientras el usuario escribe
    // =========================================================

    // Cédula: solo números y limpiar error al empezar a escribir
    idCardInput.addEventListener('input', (e) => {
        // Filtrar caracteres no numéricos
        e.target.value = e.target.value.replace(/[^0-9]/g, '');

        const val = e.target.value.trim();
        if (val.length > 0) {
            clearFieldError(idCardInput, idCardWrapper, idCardError);
        }
    });

    // Contraseña: limpiar error cuando empieza a escribir
    passwordInput.addEventListener('input', () => {
        if (passwordInput.value.length > 0) {
            clearFieldError(passwordInput, passwordWrapper, passwordError);
        }
    });

    // =========================================================
    // Validación al enviar el formulario
    // =========================================================
    form.addEventListener('submit', function(event) {
        event.preventDefault();

        const idCardValue   = idCardInput.value.trim();
        const passwordValue = passwordInput.value.trim();

        let hasError = false;

        // Validar cédula
        const idCardRegex = /^[0-9]{7,8}$/;
        if (!idCardValue) {
            setFieldError(idCardInput, idCardWrapper, idCardError, 'Debe completar el campo N° de Cédula');
            hasError = true;
        } else if (!idCardRegex.test(idCardValue)) {
            setFieldError(idCardInput, idCardWrapper, idCardError, 'La cédula debe tener entre 7 y 8 dígitos numéricos');
            hasError = true;
        } else {
            clearFieldError(idCardInput, idCardWrapper, idCardError);
        }

        // Validar contraseña
        if (!passwordValue) {
            setFieldError(passwordInput, passwordWrapper, passwordError, 'Debe completar el campo Contraseña');
            hasError = true;
        } else {
            clearFieldError(passwordInput, passwordWrapper, passwordError);
        }

        if (hasError) return;

         // --- Envío al servidor ---
        const submitBtn      = form.querySelector('.submit-btn');
        const originalBtnHtml = submitBtn.innerHTML;
        submitBtn.innerHTML  = '<span>Ingresando...</span>';
        submitBtn.disabled   = true;
        // 1. CAPTURAR EL TOKEN CSRF DEL HTML
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        const rememberCheckbox = document.getElementById('remember');
        const rememberValue = rememberCheckbox ? rememberCheckbox.checked : false;

        fetch(form.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                // 2. AGREGARLO A LAS CABECERAS DE LA PETICIÓN
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                identifier: idCardValue,
                password:   passwordValue,
                remember:   rememberValue
            })
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(result => {
            if (result.status === 200) {
                if (result.body.redirect_url) {
                    window.location.href = result.body.redirect_url;
                } else {
                    const role = result.body.role || 'applicant';
                    window.location.href = `/home/${role}`;
                }
            } else {
                showMessage(result.body.error || 'Usuario y/o Contraseña inválidos');
                submitBtn.innerHTML = originalBtnHtml;
                submitBtn.disabled  = false;
            }
        })
        .catch(() => {
            showMessage('Error de comunicación con el servidor');
            submitBtn.innerHTML = originalBtnHtml;
            submitBtn.disabled  = false;
        });
    });

    // =========================================================
    // Toggle mostrar/ocultar contraseña
    // =========================================================
    const togglePassword = document.getElementById('togglePassword');
    const toggleIcon     = document.getElementById('toggleIcon');

    const eyeSVG  = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
    const lockSVG = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';

    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        toggleIcon.innerHTML = type === 'password' ? eyeSVG : lockSVG;
    });

    /* Limpiar flag del loader para que se vuelva a mostrar en el siguiente inicio de sesión */
    sessionStorage.removeItem('systemLoaderShown');

    const passwordSuccessData = document.getElementById('passwordSuccessData');
    if (passwordSuccessData) {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: '¡Éxito!',
                text: passwordSuccessData.getAttribute('data-message'),
                icon: 'success',
                confirmButtonText: 'Aceptar',
                heightAuto: false,
                customClass: {
                    popup: 'swal2-custom-popup',
                    confirmButton: 'swal2-custom-button'
                }
            });
        }
    }
});