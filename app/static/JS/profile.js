/**
 * JavaScript para la Sección de Perfil de Usuario - SAGES
 * Controla pestañas, alternancia de visibilidad de contraseñas y validación interactiva.
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. CONTROL DE PESTAÑAS (TABS)
    // =========================================================
    const tabButtons = document.querySelectorAll('.profile-tab-btn');
    const tabContents = document.querySelectorAll('.profile-tab-content');

    const switchTab = (tabId) => {
        tabButtons.forEach(btn => {
            const target = btn.getAttribute('data-tab');
            if (target === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        tabContents.forEach(content => {
            if (content.id === `tab-content-${tabId}`) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    };

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            if (target) {
                switchTab(target);
                // Actualizar hash sin scroll
                history.replaceState(null, null, `#${target}`);
            }
        });
    });

    // Activar pestaña según parámetro URL o hash
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    const hashParam = window.location.hash.replace('#', '');
    const initialTab = tabParam || hashParam || 'personal';

    if (initialTab && document.getElementById(`tab-content-${initialTab}`)) {
        switchTab(initialTab);
    }

    // =========================================================
    // 2. TOGGLE DE VISIBILIDAD DE CONTRASEÑAS (OJITO)
    // =========================================================
    const eyeSVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
    const eyeOffSVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';

    const setupToggle = (btnId, inputId) => {
        const btn = document.getElementById(btnId);
        const input = document.getElementById(inputId);
        if (!btn || !input) return;

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const isPassword = input.getAttribute('type') === 'password';
            input.setAttribute('type', isPassword ? 'text' : 'password');
            btn.innerHTML = isPassword ? eyeOffSVG : eyeSVG;
        });
    };

    setupToggle('toggleCurrentPassword', 'current_password');
    setupToggle('toggleNewPassword', 'new_password');
    setupToggle('toggleConfirmPassword', 'confirm_password');

    // =========================================================
    // 3. VALIDACIÓN INTERACTIVA DE CRITERIOS DE CONTRASEÑA
    // =========================================================
    const currentPassInput = document.getElementById('current_password');
    const newPassInput = document.getElementById('new_password');
    const confirmPassInput = document.getElementById('confirm_password');
    const form = document.getElementById('changePasswordForm');
    const btnReset = document.getElementById('btnResetPasswordForm');

    const ruleLength = document.getElementById('rule-length');
    const ruleUppercase = document.getElementById('rule-uppercase');
    const ruleNumber = document.getElementById('rule-number');
    const ruleSpecial = document.getElementById('rule-special');

    const errorCurrent = document.getElementById('error-current-password');
    const errorNew = document.getElementById('error-new-password');
    const errorConfirm = document.getElementById('error-confirm-password');

    const updateRuleElement = (el, isValid) => {
        if (!el) return;
        const icon = el.querySelector('.rule-icon');
        if (isValid) {
            el.classList.remove('invalid');
            el.classList.add('valid');
            if (icon) icon.textContent = '✔️';
        } else {
            el.classList.remove('valid');
            el.classList.add('invalid');
            if (icon) icon.textContent = '❌';
        }
    };

    const validateNewPasswordCriteria = (val) => {
        const rules = {
            length: val.length >= 8 && val.length <= 128,
            uppercase: /[A-Z]/.test(val),
            number: /[0-9]/.test(val),
            special: /[$@.!%*?&]/.test(val)
        };

        updateRuleElement(ruleLength, rules.length);
        updateRuleElement(ruleUppercase, rules.uppercase);
        updateRuleElement(ruleNumber, rules.number);
        updateRuleElement(ruleSpecial, rules.special);

        return Object.values(rules).every(Boolean);
    };

    const clearError = (input, errorEl) => {
        if (input) input.classList.remove('input-error');
        if (errorEl) {
            errorEl.textContent = '';
            errorEl.classList.remove('visible');
        }
    };

    const setError = (input, errorEl, msg) => {
        if (input) input.classList.add('input-error');
        if (errorEl) {
            errorEl.textContent = msg;
            errorEl.classList.add('visible');
        }
    };

    if (newPassInput) {
        newPassInput.addEventListener('input', () => {
            const val = newPassInput.value;
            validateNewPasswordCriteria(val);
            clearError(newPassInput, errorNew);

            // Revalidar confirmación si ya tiene texto
            if (confirmPassInput && confirmPassInput.value.length > 0) {
                if (val === confirmPassInput.value) {
                    clearError(confirmPassInput, errorConfirm);
                } else {
                    setError(confirmPassInput, errorConfirm, 'Las contraseñas no coinciden.');
                }
            }
        });
    }

    if (currentPassInput) {
        currentPassInput.addEventListener('input', () => {
            clearError(currentPassInput, errorCurrent);
        });
    }

    if (confirmPassInput) {
        confirmPassInput.addEventListener('input', () => {
            clearError(confirmPassInput, errorConfirm);
            if (newPassInput && confirmPassInput.value !== newPassInput.value) {
                setError(confirmPassInput, errorConfirm, 'Las contraseñas no coinciden.');
            } else {
                clearError(confirmPassInput, errorConfirm);
            }
        });
    }

    // Botón Cancelar / Limpiar
    if (btnReset && form) {
        btnReset.addEventListener('click', () => {
            form.reset();
            clearError(currentPassInput, errorCurrent);
            clearError(newPassInput, errorNew);
            clearError(confirmPassInput, errorConfirm);
            validateNewPasswordCriteria('');
        });
    }

    // =========================================================
    // 4. SUBMIT DEL FORMULARIO CON VALIDACIONES COMPLETAS
    // =========================================================
    if (form) {
        form.addEventListener('submit', (e) => {
            let hasError = false;

            const currentVal = currentPassInput ? currentPassInput.value.trim() : '';
            const newVal = newPassInput ? newPassInput.value : '';
            const confirmVal = confirmPassInput ? confirmPassInput.value : '';

            // Validar clave actual
            if (!currentVal) {
                setError(currentPassInput, errorCurrent, 'Debe ingresar su contraseña actual.');
                hasError = true;
            } else {
                clearError(currentPassInput, errorCurrent);
            }

            // Validar nueva clave
            if (!newVal) {
                setError(newPassInput, errorNew, 'Debe ingresar la nueva contraseña.');
                hasError = true;
            } else if (!validateNewPasswordCriteria(newVal)) {
                setError(newPassInput, errorNew, 'La nueva contraseña no cumple con los requisitos de seguridad.');
                hasError = true;
            } else if (currentVal && currentVal === newVal) {
                setError(newPassInput, errorNew, 'La nueva contraseña no puede ser igual a la contraseña actual.');
                hasError = true;
            } else {
                clearError(newPassInput, errorNew);
            }

            // Validar confirmación
            if (!confirmVal) {
                setError(confirmPassInput, errorConfirm, 'Debe confirmar la nueva contraseña.');
                hasError = true;
            } else if (newVal !== confirmVal) {
                setError(confirmPassInput, errorConfirm, 'Las contraseñas no coinciden.');
                hasError = true;
            } else {
                clearError(confirmPassInput, errorConfirm);
            }

            if (hasError) {
                e.preventDefault();
                return;
            }

            // Deshabilitar botón para evitar doble envío
            const submitBtn = form.querySelector('.btn-save-password');
            if (submitBtn) {
                submitBtn.disabled = true;
                const span = submitBtn.querySelector('span');
                if (span) span.textContent = 'Actualizando...';
            }
        });
    }

    // =========================================================
    // 5. FORMULARIO DE CONTACTO (VALIDACIÓN Y RESTABLECIMIENTO)
    // =========================================================
    const contactForm = document.getElementById('contactForm');
    const contactEmail = document.getElementById('contact_email');
    const contactMobile = document.getElementById('contact_mobile');
    const contactPhone = document.getElementById('contact_phone');
    const btnResetContact = document.getElementById('btnResetContact');

    const errorEmail = document.getElementById('error-contact-email');
    const errorMobile = document.getElementById('error-contact-mobile');
    const errorPhone = document.getElementById('error-contact-phone');

    if (contactForm) {
        // Guardar valores iniciales para permitir restablecer
        const initialContact = {
            email: contactEmail ? contactEmail.value : '',
            mobile: contactMobile ? contactMobile.value : '',
            phone: contactPhone ? contactPhone.value : ''
        };

        // Limpiar errores al escribir y permitir solo números en teléfonos
        if (contactEmail) {
            contactEmail.addEventListener('input', () => clearError(contactEmail, errorEmail));
        }

        if (contactMobile) {
            contactMobile.addEventListener('input', () => {
                contactMobile.value = contactMobile.value.replace(/\D/g, '');
                clearError(contactMobile, errorMobile);
            });
        }

        if (contactPhone) {
            contactPhone.addEventListener('input', () => {
                contactPhone.value = contactPhone.value.replace(/\D/g, '');
                clearError(contactPhone, errorPhone);
            });
        }

        // Botón Restablecer
        if (btnResetContact) {
            btnResetContact.addEventListener('click', () => {
                if (contactEmail) contactEmail.value = initialContact.email;
                if (contactMobile) contactMobile.value = initialContact.mobile;
                if (contactPhone) contactPhone.value = initialContact.phone;
                clearError(contactEmail, errorEmail);
                clearError(contactMobile, errorMobile);
                clearError(contactPhone, errorPhone);
            });
        }

        // Validación en el envío
        contactForm.addEventListener('submit', (e) => {
            let hasError = false;

            const emailVal = contactEmail ? contactEmail.value.trim() : '';
            const mobileVal = contactMobile ? contactMobile.value.trim() : '';
            const phoneVal = contactPhone ? contactPhone.value.trim() : '';

            // Validar correo
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailVal) {
                setError(contactEmail, errorEmail, 'El correo electrónico es obligatorio.');
                hasError = true;
            } else if (!emailRegex.test(emailVal)) {
                setError(contactEmail, errorEmail, 'El correo electrónico no tiene un formato válido.');
                hasError = true;
            } else {
                clearError(contactEmail, errorEmail);
            }

            // Validar teléfono móvil
            if (!mobileVal) {
                setError(contactMobile, errorMobile, 'El teléfono principal es obligatorio.');
                hasError = true;
            } else if (!/^\d{7,15}$/.test(mobileVal)) {
                setError(contactMobile, errorMobile, 'El teléfono principal debe contener entre 7 y 15 dígitos numéricos.');
                hasError = true;
            } else {
                clearError(contactMobile, errorMobile);
            }

            // Validar teléfono secundario (opcional)
            if (phoneVal && !/^\d{7,15}$/.test(phoneVal)) {
                setError(contactPhone, errorPhone, 'El teléfono secundario debe contener entre 7 y 15 dígitos numéricos.');
                hasError = true;
            } else {
                clearError(contactPhone, errorPhone);
            }

            if (hasError) {
                e.preventDefault();
                return;
            }

            // Deshabilitar botón para evitar doble envío
            const submitBtn = contactForm.querySelector('#btnSaveContact');
            if (submitBtn) {
                submitBtn.disabled = true;
                const span = submitBtn.querySelector('span');
                if (span) span.textContent = 'Guardando...';
            }
        });
    }
});
