document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // Helpers compartidos de error por campo
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
    // PASO 1 — Validar Cédula (password.html step 1)
    // =========================================================
    const step1Form = document.getElementById('passwordStep1Form');

    if (step1Form) {
        const idCardInput   = document.getElementById('id_card');
        const idCardWrapper = document.getElementById('wrapper-id_card_p');
        const idCardError   = document.getElementById('error-id_card_p');

        // Solo números; el error desaparece en cuanto el usuario empieza a escribir
        idCardInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
            if (e.target.value.length > 0) {
                clearFieldError(idCardInput, idCardWrapper, idCardError);
            }
        });

        step1Form.addEventListener('submit', function(event) {
            const val = idCardInput.value.trim();

            if (!val) {
                event.preventDefault();
                setFieldError(idCardInput, idCardWrapper, idCardError, 'Debe completar el campo N° de Cédula');
                return;
            }
            if (!/^[0-9]{7,8}$/.test(val)) {
                event.preventDefault();
                setFieldError(idCardInput, idCardWrapper, idCardError, 'La cédula debe tener entre 7 y 8 dígitos numéricos');
                return;
            }
            clearFieldError(idCardInput, idCardWrapper, idCardError);
        });
    }

    // =========================================================
    // PASO 2 — Validar Correo Electrónico (password.html step 2)
    // =========================================================
    const step2Form = document.getElementById('passwordStep2Form');

    if (step2Form) {
        const emailInput   = document.getElementById('email');
        const emailWrapper = document.getElementById('wrapper-email');
        const emailError   = document.getElementById('error-email');

        emailInput.addEventListener('input', () => {
            if (emailInput.value.trim().length > 0) {
                clearFieldError(emailInput, emailWrapper, emailError);
            }
        });

        step2Form.addEventListener('submit', function(event) {
            // Prevenir doble envío si ya se está procesando
            if (step2Form.dataset.submitting === 'true') {
                event.preventDefault();
                return;
            }

            const val = emailInput.value.trim();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!val) {
                event.preventDefault();
                setFieldError(emailInput, emailWrapper, emailError, 'Debe completar el campo Correo Electrónico');
                return;
            }
            if (!emailRegex.test(val)) {
                event.preventDefault();
                setFieldError(emailInput, emailWrapper, emailError, 'Ingrese un correo electrónico válido');
                return;
            }
            clearFieldError(emailInput, emailWrapper, emailError);

            // Validado correctamente, deshabilitar botón para evitar doble envío
            step2Form.dataset.submitting = 'true';
            const submitBtn = step2Form.querySelector('.submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.7';
                submitBtn.style.cursor = 'not-allowed';
                const span = submitBtn.querySelector('span');
                if (span) {
                    span.textContent = 'Enviando...';
                }
            }
        });
    }

    // =========================================================
    // PASO 3 — Validar Código de Verificación (verify_code.html)
    // =========================================================
    const verifyCodeForm = document.getElementById('verifyCodeForm');

    if (verifyCodeForm) {
        const codeInput   = document.getElementById('code');
        const codeWrapper = document.getElementById('wrapper-code');
        const codeError   = document.getElementById('error-code');

        // Manejo de los 6 inputs individuales (dígitos)
        const container = document.querySelector('.code-inputs-container');
        if (container) {
            const digitInputs = [...container.querySelectorAll('.digit-input')];

            const updateHiddenInput = () => {
                codeInput.value = digitInputs.map(input => input.value).join('');
                codeInput.dispatchEvent(new Event('input', { bubbles: true }));
            };

            digitInputs.forEach((input, index) => {
                input.addEventListener('input', (e) => {
                    const val = e.target.value;
                    e.target.value = val.replace(/[^0-9]/g, '');
                    if (e.target.value.length > 0 && index < digitInputs.length - 1) {
                        digitInputs[index + 1].focus();
                    }
                    updateHiddenInput();
                });

                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Backspace') {
                        if (input.value === '') {
                            if (index > 0) {
                                digitInputs[index - 1].focus();
                                digitInputs[index - 1].value = '';
                                updateHiddenInput();
                            }
                        } else {
                            input.value = '';
                            updateHiddenInput();
                        }
                        e.preventDefault();
                    } else if (e.key === 'ArrowLeft') {
                        if (index > 0) digitInputs[index - 1].focus();
                    } else if (e.key === 'ArrowRight') {
                        if (index < digitInputs.length - 1) digitInputs[index + 1].focus();
                    }
                });

                input.addEventListener('paste', (e) => {
                    const data = (e.clipboardData || window.clipboardData).getData('text');
                    const cleanData = data.replace(/[^0-9]/g, '').slice(0, 6);
                    if (cleanData) {
                        const digits = cleanData.split('');
                        digits.forEach((digit, idx) => {
                            if (digitInputs[idx]) {
                                digitInputs[idx].value = digit;
                            }
                        });
                        const lastFocusedIndex = Math.min(digits.length - 1, digitInputs.length - 1);
                        digitInputs[lastFocusedIndex].focus();
                        updateHiddenInput();
                    }
                    e.preventDefault();
                });
            });
        }

        // Solo números; el error desaparece al escribir
        codeInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
            if (e.target.value.length > 0) {
                clearFieldError(codeInput, codeWrapper, codeError);
            }
        });

        // Temporizador / Cuenta regresiva
        const timerElement = document.getElementById('timer');
        if (timerElement) {
            let remainingTime = parseInt(timerElement.getAttribute('data-remaining'), 10) || 0;

            if (remainingTime > 0) {
                const countdownInterval = setInterval(() => {
                    const minutes = Math.floor(remainingTime / 60);
                    let seconds = remainingTime % 60;
                    seconds = seconds < 10 ? '0' + seconds : seconds;

                    timerElement.textContent = `El código expira en: ${minutes}:${seconds}`;

                    if (remainingTime <= 0) {
                        clearInterval(countdownInterval);
                        timerElement.textContent = "EL CÓDIGO HA EXPIRADO";
                    } else {
                        remainingTime--;
                    }
                }, 1000);
            }
        }

        verifyCodeForm.addEventListener('submit', function(event) {
            const val = codeInput.value.trim();

            if (!val) {
                event.preventDefault();
                setFieldError(codeInput, codeWrapper, codeError, 'Debe ingresar el código de verificación');
                return;
            }
            if (!/^\d{6}$/.test(val)) {
                event.preventDefault();
                setFieldError(codeInput, codeWrapper, codeError, 'El código debe ser de exactamente 6 dígitos');
                return;
            }
            clearFieldError(codeInput, codeWrapper, codeError);
        });
    }

    // =========================================================
    // PASO 4 — Nueva Contraseña (new_password.html)
    // =========================================================
    const newPasswordForm = document.getElementById('newPasswordForm');

    if (newPasswordForm) {
        const pass1Input    = document.getElementById('password');
        const pass1Wrapper  = document.getElementById('wrapper-password');
        const pass1Error    = document.getElementById('error-password');

        const pass2Input    = document.getElementById('password2');
        const pass2Wrapper  = document.getElementById('wrapper-password2');
        const pass2Error    = document.getElementById('error-password2');

        // Elementos de la lista de parámetros de seguridad
        const paramLength    = document.getElementById('param-length');
        const paramUppercase = document.getElementById('param-uppercase');
        const paramNumber    = document.getElementById('param-number');
        const paramSpecial   = document.getElementById('param-special');

        const validatePasswordCriteria = (value) => {
            const rules = {
                length: value.length >= 6,
                uppercase: /[A-Z]/.test(value),
                number: /[0-9]/.test(value),
                special: /[$@.!%*?&]/.test(value)
            };

            const toggleRule = (element, isValid) => {
                if (!element) return;
                const iconSpan = element.querySelector('.param-icon');
                if (isValid) {
                    element.classList.remove('invalid');
                    element.classList.add('valid');
                    if (iconSpan) iconSpan.textContent = '✅';
                } else {
                    element.classList.remove('valid');
                    element.classList.add('invalid');
                    if (iconSpan) iconSpan.textContent = '❌';
                }
            };

            toggleRule(paramLength, rules.length);
            toggleRule(paramUppercase, rules.uppercase);
            toggleRule(paramNumber, rules.number);
            toggleRule(paramSpecial, rules.special);

            return Object.values(rules).every(Boolean);
        };

        // Limpiar errores y validar fuerza mientras escribe
        pass1Input.addEventListener('input', () => {
            const val = pass1Input.value;
            validatePasswordCriteria(val);

            if (val.length > 0) {
                clearFieldError(pass1Input, pass1Wrapper, pass1Error);
            }
            // Revalidar coincidencia en tiempo real si ya se tocó el segundo campo
            if (pass2Input.value.length > 0 && val === pass2Input.value) {
                clearFieldError(pass2Input, pass2Wrapper, pass2Error);
            }
        });

        pass2Input.addEventListener('input', () => {
            if (pass2Input.value.length > 0) {
                clearFieldError(pass2Input, pass2Wrapper, pass2Error);
            }
        });

        newPasswordForm.addEventListener('submit', function(event) {
            let hasError = false;
            const val1 = pass1Input.value;
            const isStrong = validatePasswordCriteria(val1);

            // Validar contraseña nueva
            if (!val1) {
                setFieldError(pass1Input, pass1Wrapper, pass1Error, 'Debe ingresar la nueva contraseña');
                hasError = true;
            } else if (!isStrong) {
                setFieldError(pass1Input, pass1Wrapper, pass1Error, 'La contraseña no cumple con los parámetros de seguridad');
                hasError = true;
            } else {
                clearFieldError(pass1Input, pass1Wrapper, pass1Error);
            }

            // Validar confirmación
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

        // Toggle mostrar/ocultar contraseña
        const setupToggle = (inputId, buttonId, iconId) => {
            const input  = document.getElementById(inputId);
            const button = document.getElementById(buttonId);
            const icon   = document.getElementById(iconId);
            if (!input || !button || !icon) return;

            const eyeSVG  = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
            const lockSVG = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';

            button.addEventListener('click', function() {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                icon.innerHTML = type === 'password' ? eyeSVG : lockSVG;
            });
        };

        setupToggle('password',  'togglePassword1', 'toggleIcon1');
        setupToggle('password2', 'togglePassword2', 'toggleIcon2');
    }
});
