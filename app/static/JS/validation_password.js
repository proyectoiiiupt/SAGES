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

        const submitBtn = step1Form.querySelector('.submit-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.5';
            submitBtn.style.cursor = 'not-allowed';
        }

        // Solo números; el error desaparece en cuanto el usuario empieza a escribir
        idCardInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
            const valLen = e.target.value.length;
            if (valLen > 0) {
                clearFieldError(idCardInput, idCardWrapper, idCardError);
            }
            if (submitBtn) {
                if (valLen >= 7 && valLen <= 8) {
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                    submitBtn.style.cursor = 'pointer';
                } else {
                    submitBtn.disabled = true;
                    submitBtn.style.opacity = '0.5';
                    submitBtn.style.cursor = 'not-allowed';
                }
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

        // Temporizador / Cuenta regresiva (Reloj visual con contador reactivo)
        const timerElement = document.getElementById('timer');
        const resendLink = document.getElementById('btnResendCode') || document.querySelector('.support-links a');
        if (timerElement) {
            let remainingTime = parseInt(timerElement.getAttribute('data-remaining'), 10);
            if (isNaN(remainingTime)) remainingTime = 300;

            const formatClock = (secondsLeft) => {
                const minutes = Math.floor(secondsLeft / 60);
                let seconds = secondsLeft % 60;
                seconds = seconds < 10 ? '0' + seconds : seconds;
                return `${minutes}:${seconds}`;
            };

            const renderTimer = () => {
                if (remainingTime <= 0) {
                    timerElement.innerHTML = `
                        <div style="display: inline-flex; align-items: center; justify-content: center; gap: 6px; color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 4px 10px; font-size: 0.85rem; font-weight: 600;">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="12" y1="8" x2="12" y2="12"></line>
                                <line x1="12" y1="16" x2="12.01" y2="16"></line>
                            </svg>
                            <span>EL CÓDIGO HA EXPIRADO</span>
                        </div>`;
                    if (resendLink) {
                        resendLink.style.pointerEvents = 'auto';
                        resendLink.style.opacity = '1';
                        resendLink.textContent = 'Reenviar código';
                    }
                } else {
                    timerElement.innerHTML = `
                        <div style="display: inline-flex; align-items: center; justify-content: center; gap: 6px; color: #0284c7; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 4px 10px; font-size: 0.85rem; font-weight: 600;">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>
                            <span>Código válido por: <strong style="font-family: monospace; font-size: 0.95rem;">${formatClock(remainingTime)}</strong></span>
                        </div>`;
                    if (remainingTime > 60 && resendLink) {
                        const waitSec = remainingTime - 60;
                        resendLink.style.pointerEvents = 'none';
                        resendLink.style.opacity = '0.6';
                        resendLink.textContent = `Reenviar código (esperar ${formatClock(waitSec)})`;
                    } else if (resendLink) {
                        resendLink.style.pointerEvents = 'auto';
                        resendLink.style.opacity = '1';
                        resendLink.textContent = 'Reenviar código';
                    }
                }
            };

            renderTimer();
            const countdownInterval = setInterval(() => {
                if (remainingTime <= 0) {
                    clearInterval(countdownInterval);
                    renderTimer();
                } else {
                    remainingTime--;
                    renderTimer();
                }
            }, 1000);
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
        
        // Manejo del botón Cancelar con SweetAlert
        const btnCancel = document.getElementById('btnCancelReset');
        const cancelForm = document.getElementById('cancelResetForm');
        
        if (btnCancel && cancelForm) {
            btnCancel.addEventListener('click', function() {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        title: '¿Cancelar recuperación?',
                        text: "Si cancelas, el código enviado quedará invalidado por seguridad y volverás al inicio de sesión.",
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonColor: '#e53e3e',
                        cancelButtonColor: '#6b7280',
                        confirmButtonText: 'Sí, cancelar proceso',
                        cancelButtonText: 'No, continuar',
                        reverseButtons: true,
                        heightAuto: false,
                        customClass: {
                            popup: 'swal2-custom-popup',
                            confirmButton: 'swal2-custom-button',
                            cancelButton: 'swal2-custom-button'
                        }
                    }).then((result) => {
                        if (result.isConfirmed) {
                            cancelForm.submit();
                        }
                    });
                } else {
                    // Fallback si no carga SweetAlert
                    if (confirm("¿Estás seguro de que deseas cancelar la recuperación de contraseña? El código actual quedará invalidado.")) {
                        cancelForm.submit();
                    }
                }
            });
        }
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
                length: value.length >= 8,
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
                    if (iconSpan) iconSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                } else {
                    element.classList.remove('valid');
                    element.classList.add('invalid');
                    if (iconSpan) iconSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
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

    if (document.getElementById('verifyCodeForm') || document.getElementById('newPasswordForm')) {
        if (window.history && window.history.pushState) {
            window.history.pushState(null, null, window.location.href);
            window.addEventListener('popstate', function () {
                window.history.pushState(null, null, window.location.href);
            });
        }
    }
});

// ==========================================
// PREVENCIÓN DE BFCACHE EN RECUPERACIÓN DE CLAVE
// ==========================================
window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
        window.location.reload();
    }
});
