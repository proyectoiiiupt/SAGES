document.addEventListener('DOMContentLoaded', function () {
    const validationTimers = {
        identification: null,
        email: null
    };

    const identificationInput = document.getElementById('identification_number');
    const emailInput = document.getElementById('email');
    const positionSelect = document.getElementById('position_id');
    const submitButton = document.getElementById('invitation-submit');
    const cancelButton = document.getElementById('cancel-btn');
    const invitationForm = document.getElementById('invitation-form');

    if (!identificationInput || !emailInput || !positionSelect || !submitButton || !cancelButton || !invitationForm) {
        return;
    }

    function clearValidation(field) {
        if (validationTimers[field]) {
            clearTimeout(validationTimers[field]);
            validationTimers[field] = null;
        }

        const validationElement = document.getElementById(`${field}-validation`);
        const inputElement = field === 'identification' ? identificationInput : emailInput;

        if (validationElement) {
            validationElement.className = 'validation-message';
            validationElement.textContent = '';
            validationElement.style.display = 'none';
        }

        if (inputElement) {
            inputElement.classList.remove('has-error', 'is-valid');
        }
    }

    function setValidationState(field, type, message) {
        if (validationTimers[field]) {
            clearTimeout(validationTimers[field]);
        }

        const validationElement = document.getElementById(`${field}-validation`);
        const inputElement = field === 'identification' ? identificationInput : emailInput;

        if (!validationElement || !inputElement) {
            return;
        }

        validationElement.className = 'validation-message';
        validationElement.textContent = '';
        validationElement.style.display = 'none';
        inputElement.classList.remove('has-error', 'is-valid');

        if (type === 'error') {
            validationElement.classList.add('error');
            validationElement.textContent = message;
            validationElement.style.display = 'block';
            inputElement.classList.add('has-error');
        } else if (type === 'success') {
            inputElement.classList.add('is-valid');
        }

        validationTimers[field] = setTimeout(() => {
            clearValidation(field);
        }, 5000);
    }

    function updateSubmitButton() {
        const hasIdentification = identificationInput.value.trim() !== '';
        const hasEmail = emailInput.value.trim() !== '';
        const hasPosition = positionSelect.value !== '';

        submitButton.disabled = !(hasIdentification && hasEmail && hasPosition);
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    identificationInput.addEventListener('input', function () {
        const cleaned = this.value.replace(/\D/g, '').slice(0, 8);
        if (this.value !== cleaned) {
            this.value = cleaned;
        }
        clearValidation('identification');
        updateSubmitButton();
    });

    emailInput.addEventListener('input', function () {
        clearValidation('email');
        updateSubmitButton();
    });

    positionSelect.addEventListener('change', updateSubmitButton);
    updateSubmitButton();

    cancelButton.addEventListener('click', function () {
        Swal.fire({
            title: '¿Estás seguro?',
            text: '¿Deseas cancelar el proceso de invitación? Se perderán los datos ingresados.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, cancelar',
            cancelButtonText: 'No, continuar'
        }).then((result) => {
            if (result.isConfirmed) {
                invitationForm.reset();
                clearValidation('identification');
                clearValidation('email');
                updateSubmitButton();

                Swal.fire({
                    title: 'Cancelado',
                    text: 'El proceso de invitación ha sido cancelado.',
                    icon: 'info'
                });
            }
        });
    });

    invitationForm.addEventListener('submit', async function (event) {
        event.preventDefault();

        clearTimeout(validationTimers.identification);
        clearTimeout(validationTimers.email);

        const identificationValid = await validateField('identification', identificationInput.value.trim());
        const emailValid = await validateField('email', emailInput.value.trim());

        if (!identificationValid || !emailValid) {
            return;
        }

        Swal.fire({
            title: '¿Estás seguro?',
            text: `¿Deseas enviar la invitación a ${emailInput.value}?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Sí, enviar',
            cancelButtonText: 'No, cancelar'
        }).then((result) => {
            if (!result.isConfirmed) return;

            const formData = new FormData(invitationForm);
            submitButton.disabled = true;
            const originalButtonText = submitButton.textContent;
            submitButton.textContent = 'Enviando...';

            fetch(invitationForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(async (response) => {
                const data = await response.json().catch(() => null);
                if (!response.ok || (data && data.success === false)) {
                    const errorMsg = (data && data.message) ? data.message : 'Error en el servidor al enviar la invitación.';
                    throw new Error(errorMsg);
                }
                return data;
            })
            .then((data) => {
                Swal.fire({
                    title: '¡Enviado!',
                    text: (data && data.message) ? data.message : 'La invitación ha sido enviada correctamente.',
                    icon: 'success',
                    confirmButtonColor: '#28a745',
                    confirmButtonText: 'OK'
                }).then(() => {
                    const institutionId = invitationForm.dataset.institutionId || '';
                    if (institutionId) {
                        window.location.href = `/institutions/${institutionId}/users`;
                    }
                });
            })
            .catch((error) => {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
                Swal.fire({
                    title: 'Error',
                    text: error.message || 'Hubo un error al enviar la invitación. Por favor, intenta nuevamente.',
                    icon: 'error',
                    confirmButtonColor: '#d33',
                    confirmButtonText: 'OK'
                });
            });
        });
    });

    async function validateField(field, value) {
        if (!value) {
            setValidationState(field, 'error', 'Este campo es requerido');
            return false;
        }

        if (field === 'identification') {
            if (!/^\d{7,8}$/.test(value)) {
                setValidationState(field, 'error', 'La cédula debe tener entre 7 y 8 dígitos numéricos');
                return false;
            }
        }

        if (field === 'email' && !isValidEmail(value)) {
            setValidationState(field, 'error', 'El formato del correo electrónico no es válido');
            return false;
        }

        try {
            const endpoint = field === 'identification'
                ? `/institutions/api/validate-identification?identification_number=${encodeURIComponent(value)}`
                : `/institutions/api/validate-email?email=${encodeURIComponent(value)}`;

            const response = await fetch(endpoint);
            const data = await response.json();

            if (data.valid === false || data.exists) {
                const message = data.message || (data.exists ? 'Este valor ya está registrado' : 'El correo no es válido');
                setValidationState(field, 'error', message);
                return false;
            }

            setValidationState(field, 'success', '');
            return true;
        } catch (error) {
            setValidationState(field, 'error', 'Error al validar el campo');
            return false;
        }
    }
});
