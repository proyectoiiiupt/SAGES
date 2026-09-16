/**
 * validation_activate.js
 * Lógica de validación para la vista de activación de cuenta (activate.html).
 * Replica el patrón de validation_password.js → PASO 4 (newPasswordForm).
 */
document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // Helpers de error por campo (idénticos a validation_password.js)
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
    // Formulario de activación
    // =========================================================
    const activateForm = document.getElementById('activateForm');
    if (!activateForm) return;

    const pass1Input   = document.getElementById('ac-password');
    const pass1Wrapper = document.getElementById('ac-wrapper-password');
    const pass1Error   = document.getElementById('ac-error-password');

    const pass2Input   = document.getElementById('ac-password2');
    const pass2Wrapper = document.getElementById('ac-wrapper-password2');
    const pass2Error   = document.getElementById('ac-error-password2');

    // Elementos del panel de parámetros (panel izquierdo)
    const paramLength    = document.getElementById('ac-param-length');
    const paramUppercase = document.getElementById('ac-param-uppercase');
    const paramNumber    = document.getElementById('ac-param-number');
    const paramSpecial   = document.getElementById('ac-param-special');

    // ---- Validación de criterios de seguridad ----
    const validatePasswordCriteria = (value) => {
        const rules = {
            length:    value.length >= 8,
            uppercase: /[A-Z]/.test(value),
            number:    /[0-9]/.test(value),
            special:   /[$@.!%*?&]/.test(value)
        };

        const toggleRule = (element, isValid) => {
            if (!element) return;
            const icon = element.querySelector('.ac-param-icon');
            if (isValid) {
                element.classList.add('valid');
                if (icon) icon.textContent = '✔️';
            } else {
                element.classList.remove('valid');
                if (icon) icon.textContent = '❌';
            }
        };

        toggleRule(paramLength,    rules.length);
        toggleRule(paramUppercase, rules.uppercase);
        toggleRule(paramNumber,    rules.number);
        toggleRule(paramSpecial,   rules.special);

        return Object.values(rules).every(Boolean);
    };

    // ---- Listeners en tiempo real ----
    pass1Input.addEventListener('input', () => {
        const val = pass1Input.value;
        validatePasswordCriteria(val);

        if (val.length > 0) clearFieldError(pass1Input, pass1Wrapper, pass1Error);

        // Revalidar coincidencia si el segundo campo ya fue tocado
        if (pass2Input.value.length > 0 && val === pass2Input.value) {
            clearFieldError(pass2Input, pass2Wrapper, pass2Error);
        }
    });

    pass2Input.addEventListener('input', () => {
        if (pass2Input.value.length > 0) clearFieldError(pass2Input, pass2Wrapper, pass2Error);
    });

    // ---- Validación al enviar ----
    activateForm.addEventListener('submit', function(event) {
        let hasError = false;
        const val1 = pass1Input.value;
        const isStrong = validatePasswordCriteria(val1);

        if (!val1) {
            setFieldError(pass1Input, pass1Wrapper, pass1Error, 'Debe ingresar la contraseña');
            hasError = true;
        } else if (!isStrong) {
            setFieldError(pass1Input, pass1Wrapper, pass1Error, 'La contraseña no cumple con los parámetros de seguridad');
            hasError = true;
        } else {
            clearFieldError(pass1Input, pass1Wrapper, pass1Error);
        }

        if (!pass2Input.value) {
            setFieldError(pass2Input, pass2Wrapper, pass2Error, 'Debe confirmar la contraseña');
            hasError = true;
        } else if (val1 !== pass2Input.value) {
            setFieldError(pass2Input, pass2Wrapper, pass2Error, 'Las contraseñas no coinciden');
            hasError = true;
        } else {
            clearFieldError(pass2Input, pass2Wrapper, pass2Error);
        }

        if (hasError) event.preventDefault();
    });

    // ---- Toggle mostrar/ocultar contraseña ----
    const eyeSVG  = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
    const lockSVG = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';

    const setupToggle = (inputId, buttonId, iconId) => {
        const input  = document.getElementById(inputId);
        const button = document.getElementById(buttonId);
        const icon   = document.getElementById(iconId);
        if (!input || !button || !icon) return;

        button.addEventListener('click', () => {
            const isPassword = input.getAttribute('type') === 'password';
            input.setAttribute('type', isPassword ? 'text' : 'password');
            icon.innerHTML = isPassword ? lockSVG : eyeSVG;
        });
    };

    setupToggle('ac-password',  'ac-togglePassword1', 'ac-toggleIcon1');
    setupToggle('ac-password2', 'ac-togglePassword2', 'ac-toggleIcon2');
});

