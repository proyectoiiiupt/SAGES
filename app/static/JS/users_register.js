document.addEventListener('DOMContentLoaded', function() {
    const steps = document.querySelectorAll('.wizard-panel');
    const stepIndicators = document.querySelectorAll('.step');
    const btnNext = document.getElementById('btnNext');
    const btnPrev = document.getElementById('btnPrev');
    const btnSubmit = document.getElementById('btnSubmit');
    const registerForm = document.getElementById('registerAdminForm');
    
    let currentStep = 0;

    // Elementos del formulario
    const idType = document.getElementById('identification_type');
    const idNumber = document.getElementById('identification_number');
    const email = document.getElementById('email');
    const stateSelect = document.getElementById('state');
    const placeSelect = document.getElementById('place');
    
    // Auto-clear error on input para todos los inputs
    document.querySelectorAll('.form-control, .form-select').forEach(input => {
        input.addEventListener('input', () => clearError(input));
        input.addEventListener('change', () => clearError(input));
    });

    // Formateo de Cédula (ej. 12.345.678)
    idNumber.addEventListener('input', function (e) {
        let val = this.value.replace(/\D/g, '');
        if (val.length > 8) val = val.substring(0, 8);
        if (val.length > 0) {
            val = parseInt(val, 10).toLocaleString('es-VE').replace(/,/g, '.');
        }
        this.value = val;
    });

    // Formateo de Nombres (Capitalización y letras)
    const nameInputs = [document.getElementById('first_name'), document.getElementById('second_name'), 
                        document.getElementById('last_name'), document.getElementById('middle_name')];
    nameInputs.forEach(input => {
        input.addEventListener('input', function (e) {
            let val = this.value;
            val = val.replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]/g, '');
            if (val.length > 0) {
                val = val.toLowerCase().replace(/(^|\s)\S/g, l => l.toUpperCase());
            }
            this.value = val;
        });
    });

    // Formateo de Teléfonos (ej. (0414)-1234567)
    const phoneInputs = [document.getElementById('mobile'), document.getElementById('phone')];
    phoneInputs.forEach(input => {
        input.addEventListener('input', function (e) {
            let val = this.value.replace(/\D/g, '');
            if (val.length > 11) val = val.substring(0, 11);
            if (val.length > 4) {
                val = `(${val.substring(0, 4)})-${val.substring(4)}`;
            } else if (val.length > 0) {
                val = `(${val}`;
            }
            this.value = val;
        });
    });

    // Inicializar Wizard o Mostrar Modal si es un formulario nuevo
    if (!idNumber.value.trim()) {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'Perfil Administrativo',
                text: '¿Qué tipo de administrador desea registrar?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Administrador Estadal',
                cancelButtonText: 'Super Administrador',
                confirmButtonColor: '#10b981',
                cancelButtonColor: '#0ea5e9',
                allowOutsideClick: false,
                allowEscapeKey: false
            }).then((result) => {
                const roleSelect = document.getElementById('role');
                if (roleSelect) {
                    Array.from(roleSelect.options).forEach(opt => {
                        if (result.isConfirmed && opt.text.toLowerCase().includes('estadal')) {
                            roleSelect.value = opt.value;
                        } else if (!result.isConfirmed && opt.text.toLowerCase().includes('super')) {
                            roleSelect.value = opt.value;
                        }
                    });
                    // Despachar el evento 'change' para limpiar errores de validación
                    roleSelect.dispatchEvent(new Event('change'));
                    roleSelect.dispatchEvent(new Event('input'));
                    
                    // Hacer que el campo sea de solo lectura para evitar cambios posteriores
                    roleSelect.style.pointerEvents = 'none';
                    roleSelect.style.backgroundColor = '#e2e8f0';
                    // Ocultar la flecha del select para que parezca un input normal
                    roleSelect.style.appearance = 'none';
                    roleSelect.style.webkitAppearance = 'none';
                    roleSelect.style.mozAppearance = 'none';
                }
                showStep(currentStep);
            });
        } else {
            showStep(currentStep);
        }
    } else {
        // Si ya hay datos (ej. recarga por error de validación), inicializar directamente
        showStep(currentStep);
    }

    function showStep(stepIndex) {
        steps.forEach((step, index) => {
            step.classList.toggle('active', index === stepIndex);
        });

        stepIndicators.forEach((indicator, index) => {
            if (index < stepIndex) {
                indicator.classList.add('completed');
                indicator.classList.remove('active');
            } else if (index === stepIndex) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        });

        // Botones
        btnPrev.style.display = stepIndex === 0 ? 'none' : 'inline-block';
        
        if (stepIndex === steps.length - 1) {
            btnNext.style.display = 'none';
            btnSubmit.style.display = 'inline-block';
            updateSummary();
        } else {
            btnNext.style.display = 'inline-block';
            btnSubmit.style.display = 'none';
        }
    }

    async function validateStep0() {
        let isValid = true;
        let firstInvalidField = null;

        const first_name = document.getElementById('first_name');
        const last_name = document.getElementById('last_name');

        // Validar Cédula de Identidad
        if (!idNumber.value.trim()) {
            showError(idNumber, 'La cédula de identidad es obligatoria.');
            if (!firstInvalidField) firstInvalidField = idNumber;
            isValid = false;
        } else {
            const rawId = idNumber.value.replace(/\./g, '');
            if (rawId.length < 6) {
                showError(idNumber, 'La cédula debe contener al menos 6 dígitos.');
                if (!firstInvalidField) firstInvalidField = idNumber;
                isValid = false;
            }
        }

        // Validar Primer Nombre
        if (!first_name.value.trim()) {
            showError(first_name, 'El primer nombre es obligatorio.');
            if (!firstInvalidField) firstInvalidField = first_name;
            isValid = false;
        }

        // Validar Primer Apellido
        if (!last_name.value.trim()) {
            showError(last_name, 'El primer apellido es obligatorio.');
            if (!firstInvalidField) firstInvalidField = last_name;
            isValid = false;
        }

        if (!isValid) {
            if (firstInvalidField) firstInvalidField.focus();
            return false;
        }

        // Validación asíncrona de duplicidad en base de datos
        const rawId = idNumber.value.replace(/\./g, '');
        try {
            const response = await fetch(`/users/api/validate-identification?id=${rawId}`);
            const data = await response.json();
            if (!data.valid) {
                showError(idNumber, data.message || 'Esta cédula ya se encuentra registrada.');
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Cédula Existente', 
                    text: data.message, 
                    confirmButtonColor: '#007865' 
                });
                idNumber.focus();
                return false;
            }
        } catch (e) {
            console.error('Error validando cédula:', e);
            return false;
        }

        return true;
    }

    async function validateStep1() {
        let isValid = true;
        let firstInvalidField = null;

        const mobile = document.getElementById('mobile');
        const phone = document.getElementById('phone');
        const role = document.getElementById('role');
        const position = document.getElementById('position');

        // Validar Correo Electrónico
        if (!email.value.trim()) {
            showError(email, 'El correo institucional es obligatorio.');
            if (!firstInvalidField) firstInvalidField = email;
            isValid = false;
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
            showError(email, 'Formato de correo electrónico no válido.');
            if (!firstInvalidField) firstInvalidField = email;
            isValid = false;
        }

        // Validar Teléfono Móvil
        if (!mobile.value.trim()) {
            showError(mobile, 'El teléfono móvil es obligatorio.');
            if (!firstInvalidField) firstInvalidField = mobile;
            isValid = false;
        } else if (mobile.value.length < 14) {
            showError(mobile, 'Teléfono móvil incompleto. Formato requerido: (04XX)-XXXXXXX');
            if (!firstInvalidField) firstInvalidField = mobile;
            isValid = false;
        }

        // Validar Teléfono Local (opcional, pero si tiene caracteres debe ser completo)
        if (phone && phone.value.trim() && phone.value.length < 14) {
            showError(phone, 'Teléfono local incompleto. Formato requerido: (02XX)-XXXXXXX');
            if (!firstInvalidField) firstInvalidField = phone;
            isValid = false;
        }

        // Validar Asignación Corporativa
        if (!role.value) {
            showError(role, 'Seleccione un rol en el sistema.');
            if (!firstInvalidField) firstInvalidField = role;
            isValid = false;
        }
        if (!position.value) {
            showError(position, 'Seleccione un cargo administrativo.');
            if (!firstInvalidField) firstInvalidField = position;
            isValid = false;
        }
        if (!stateSelect.value) {
            showError(stateSelect, 'Seleccione el estado de adscripción.');
            if (!firstInvalidField) firstInvalidField = stateSelect;
            isValid = false;
        }
        if (!placeSelect.value) {
            showError(placeSelect, 'Seleccione la sede asignada.');
            if (!firstInvalidField) firstInvalidField = placeSelect;
            isValid = false;
        }

        if (!isValid) {
            if (firstInvalidField) firstInvalidField.focus();
            return false;
        }

        // Validación asíncrona de correo en base de datos
        try {
            const response = await fetch(`/users/api/validate-email?email=${encodeURIComponent(email.value.trim())}`);
            const data = await response.json();
            if (!data.valid) {
                showError(email, data.message || 'Este correo ya se encuentra registrado.');
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Correo Existente', 
                    text: data.message, 
                    confirmButtonColor: '#007865' 
                });
                email.focus();
                return false;
            }
        } catch (e) {
            console.error('Error validando correo:', e);
            return false;
        }

        return true;
    }

    btnNext.addEventListener('click', async function() {
        let isValid = false;
        
        // Bloquear botón mientras valida
        const originalText = btnNext.innerHTML;
        btnNext.innerHTML = 'Validando...';
        btnNext.disabled = true;

        if (currentStep === 0) {
            isValid = await validateStep0();
        } else if (currentStep === 1) {
            isValid = await validateStep1();
        }

        btnNext.innerHTML = originalText;
        btnNext.disabled = false;

        if (isValid) {
            currentStep++;
            showStep(currentStep);
        }
    });

    btnPrev.addEventListener('click', function() {
        if (currentStep > 0) {
            currentStep--;
            showStep(currentStep);
        }
    });

    // Cascading Select: State -> Place
    stateSelect.addEventListener('change', async function() {
        const stateId = this.value;
        placeSelect.innerHTML = '<option value="">Seleccione Sede...</option>';
        placeSelect.disabled = true;

        if (stateId) {
            try {
                const response = await fetch(`/users/api/places-by-state/${stateId}`);
                const places = await response.json();
                
                places.forEach(place => {
                    const option = document.createElement('option');
                    option.value = place.id;
                    option.textContent = place.name;
                    placeSelect.appendChild(option);
                });
                
                placeSelect.disabled = false;
            } catch (error) {
                console.error('Error fetching places:', error);
            }
        }
    });

    // Utils
    function showError(element, message) {
        if (!element) return;
        element.classList.add('is-invalid');
        const container = element.closest('.form-group') || element.parentNode;
        let feedback = container.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            container.appendChild(feedback);
        }
        feedback.textContent = message;
        feedback.style.display = 'block';
    }

    function clearError(element) {
        if (!element) return;
        element.classList.remove('is-invalid');
        const container = element.closest('.form-group') || element.parentNode;
        const feedback = container.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.style.display = 'none';
        }
    }

    function updateSummary() {
        document.getElementById('sum-cedula').textContent = idType.value + '-' + idNumber.value;
        document.getElementById('sum-name').textContent = document.getElementById('first_name').value + ' ' + document.getElementById('last_name').value;
        document.getElementById('sum-email').textContent = email.value;
        document.getElementById('sum-role').textContent = document.getElementById('role').options[document.getElementById('role').selectedIndex].text;
        document.getElementById('sum-state').textContent = stateSelect.options[stateSelect.selectedIndex].text;
        document.getElementById('sum-place').textContent = placeSelect.options[placeSelect.selectedIndex].text;
    }

    // Modal de confirmación SweetAlert2 (asegurarse de que está cargado)
    btnSubmit.addEventListener('click', function() {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: '¿Confirmar Registro?',
                text: "Se dará de alta a este usuario corporativo y se le enviará un correo de activación.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#10b981',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, registrar',
                cancelButtonText: 'Revisar datos'
            }).then((result) => {
                if (result.isConfirmed) {
                    btnSubmit.disabled = true;
                    btnSubmit.innerHTML = 'Enviando...';
                    registerForm.submit();
                }
            });
        } else {
            if(confirm("¿Está seguro de registrar este usuario administrativo?")) {
                registerForm.submit();
            }
        }
    });

    // Botón Cancelar con SweetAlert2
    const btnCancel = document.getElementById('btnCancelRegistro');
    if (btnCancel) {
        btnCancel.addEventListener('click', function(e) {
            e.preventDefault();
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: '¿Está seguro de que desea cancelar?',
                    text: "Se perderán todos los datos ingresados en el formulario de registro.",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#ef4444',
                    cancelButtonColor: '#64748b',
                    confirmButtonText: 'Sí, cancelar',
                    cancelButtonText: 'No, continuar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        window.location.href = '/users/list';
                    }
                });
            } else {
                if (confirm('¿Está seguro de que desea cancelar? Se perderán todos los datos.')) {
                    window.location.href = '/users/list';
                }
            }
        });
    }
});
