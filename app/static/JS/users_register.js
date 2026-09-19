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
        const first_name = document.getElementById('first_name');
        const last_name = document.getElementById('last_name');

        if (!idNumber.value.trim()) {
            Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'La cédula es requerida', confirmButtonColor: '#0ea5e9' });
            idNumber.focus();
            return false;
        }

        const rawId = idNumber.value.replace(/\./g, '');
        if (rawId.length < 6) {
            Swal.fire({ icon: 'warning', title: 'Datos inválidos', text: 'Cédula muy corta', confirmButtonColor: '#0ea5e9' });
            idNumber.focus();
            return false;
        }

        try {
            const response = await fetch(`/users/api/validate-identification?id=${rawId}`);
            const data = await response.json();
            if (!data.valid) {
                Swal.fire({ icon: 'error', title: 'Cédula Existente', text: data.message, confirmButtonColor: '#0ea5e9' });
                idNumber.focus();
                return false;
            }
        } catch (e) {
            console.error(e);
            return false;
        }

        if (!first_name.value.trim()) {
            Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Primer nombre requerido', confirmButtonColor: '#0ea5e9' });
            first_name.focus();
            return false;
        }

        if (!last_name.value.trim()) {
            Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Primer apellido requerido', confirmButtonColor: '#0ea5e9' });
            last_name.focus();
            return false;
        }

        return true;
    }

    async function validateStep1() {
        if (!email.value.trim()) {
            Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'El correo es requerido', confirmButtonColor: '#0ea5e9' });
            email.focus();
            return false;
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
            Swal.fire({ icon: 'warning', title: 'Datos inválidos', text: 'Formato de correo inválido', confirmButtonColor: '#0ea5e9' });
            email.focus();
            return false;
        }

        try {
            const response = await fetch(`/users/api/validate-email?email=${email.value}`);
            const data = await response.json();
            if (!data.valid) {
                Swal.fire({ icon: 'error', title: 'Correo Existente', text: data.message, confirmButtonColor: '#0ea5e9' });
                email.focus();
                return false;
            }
        } catch (e) {
            console.error(e);
            return false;
        }

        const role = document.getElementById('role');
        const position = document.getElementById('position');
        const mobile = document.getElementById('mobile');

        if (!role.value) { Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Seleccione un rol', confirmButtonColor: '#0ea5e9' }); role.focus(); return false; }
        if (!position.value) { Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Seleccione un cargo', confirmButtonColor: '#0ea5e9' }); position.focus(); return false; }
        if (!stateSelect.value) { Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Seleccione un estado', confirmButtonColor: '#0ea5e9' }); stateSelect.focus(); return false; }
        if (!placeSelect.value) { Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'Seleccione una sede', confirmButtonColor: '#0ea5e9' }); placeSelect.focus(); return false; }
        if (!mobile.value.trim() || mobile.value.length < 14) { Swal.fire({ icon: 'warning', title: 'Datos inválidos', text: 'Teléfono móvil válido requerido', confirmButtonColor: '#0ea5e9' }); mobile.focus(); return false; }

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
        element.classList.add('is-invalid');
        let feedback = element.nextElementSibling;
        if (!feedback || !feedback.classList.contains('invalid-feedback')) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            element.parentNode.insertBefore(feedback, element.nextSibling);
        }
        feedback.textContent = message;
        feedback.style.display = 'block';
    }

    function clearError(element) {
        element.classList.remove('is-invalid');
        const feedback = element.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
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

    // Fecha en el Header
    const dateSpan = document.getElementById('current-date');
    if (dateSpan) {
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        dateSpan.textContent = new Date().toLocaleDateString('es-ES', options);
    }

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
