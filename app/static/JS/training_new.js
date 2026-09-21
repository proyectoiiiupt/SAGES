document.addEventListener('DOMContentLoaded', function() {

    const form = document.getElementById('form-new-training');
    const moduleInput = document.getElementById('training_module_id');
    const nameInput = document.getElementById('name');
    const descInput = document.getElementById('description');
    const feedbackDiv = document.getElementById('name-validation-feedback');
    const submitBtn = document.getElementById('btn-save-training');

    let isNameValid = true;
    let nameValidationTimeout = null;

    // 0. Set current date in header
    const dateSpan = document.getElementById('current-date');
    if (dateSpan) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        dateSpan.textContent = new Date().toLocaleDateString('es-ES', options);
    }

    // 0.5. Validación al presionar el botón "Volver"
    const backBtn = document.getElementById('btn-back-to-catalog');
    if (backBtn) {
        backBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href');
            Swal.fire({
                title: '¿Estás seguro?',
                text: 'Si vuelves, se perderán todos los datos ingresados en el formulario.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc2626',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, volver y descartar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    window.location.href = url;
                }
            });
        });
    }

    // 1.5 Carga dinámica de módulos (AJAX)
    if (moduleInput) {
        fetch('/training/api/active-modules')
            .then(response => response.json())
            .then(data => {
                moduleInput.innerHTML = '<option value="">Seleccione un módulo</option>';
                data.forEach(m => {
                    const option = document.createElement('option');
                    option.value = m.id;
                    option.textContent = m.name;
                    moduleInput.appendChild(option);
                });

                // Seleccionar el valor por defecto si existe (por GET ?module_id= o por POST re-render)
                const preselected = moduleInput.getAttribute('data-selected') || new URLSearchParams(window.location.search).get('module_id');
                if (preselected) {
                    moduleInput.value = preselected;
                }
            })
            .catch(err => {
                console.error('Error fetching modules:', err);
                moduleInput.innerHTML = '<option value="">Error cargando módulos</option>';
            });
    }

    // 2. Validación asíncrona y formato de nombre de tema (Debounce)
    if (nameInput) {
        nameInput.addEventListener('input', function() {
            // Formatear el campo: Mayúscula inicial (conservando mayúsculas extras), sin dobles espacios, permite paréntesis
            let val = this.value;
            val = val.replace(/[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-\'\"°\(\)]/g, '');
            val = val.replace(/\s{2,}/g, ' ');
            val = val.replace(/(?:^|[\s\.\-\'\"°\(\)])[a-záéíóúñ]/g, function (match) {
                return match.toUpperCase();
            });
            this.value = val;

            clearTimeout(nameValidationTimeout);
            const nameVal = this.value.trim();
            
            // Limpiar feedback si está vacío
            if (nameVal.length === 0) {
                feedbackDiv.innerHTML = '';
                nameInput.classList.remove('is-invalid');
                isNameValid = false;
                return;
            }

            if (nameVal.length < 10) {
                feedbackDiv.innerHTML = '<span style="color: #f59e0b; font-size: 0.9rem;">El título debe tener al menos 10 caracteres.</span>';
                isNameValid = false;
                return;
            }

            feedbackDiv.innerHTML = '<span style="color: #64748b; font-size: 0.9rem;">Verificando disponibilidad...</span>';

            // Debounce de 500ms
            nameValidationTimeout = setTimeout(() => {
                const moduleVal = moduleInput ? moduleInput.value : '';
                if (!moduleVal || moduleVal === '0') {
                    feedbackDiv.innerHTML = '<span style="color: #f59e0b; font-size: 0.9rem;">Por favor, seleccione un módulo primero para validar.</span>';
                    isNameValid = false;
                    return;
                }

                fetch(`/training/api/validate-name?name=${encodeURIComponent(nameVal)}&module_id=${moduleVal}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Parámetros incompletos');
                        return response.json();
                    })
                    .then(data => {
                        if (data.exists) {
                            feedbackDiv.innerHTML = '<span style="color: #dc2626; font-size: 0.9rem; font-weight: bold;">Este nombre ya está en uso.</span>';
                            nameInput.classList.add('is-invalid');
                            isNameValid = false;
                        } else {
                            feedbackDiv.innerHTML = '<span style="color: #10b981; font-size: 0.9rem;">Nombre disponible.</span>';
                            nameInput.classList.remove('is-invalid');
                            isNameValid = true;
                        }
                    })
                    .catch(err => {
                        console.error("Error validando nombre:", err);
                        feedbackDiv.innerHTML = '';
                    });
            }, 500);
        });
    }

    // 3. Validación y confirmación interactiva al enviar el formulario
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();

            const moduleVal = moduleInput ? moduleInput.value : '';
            const nameVal = nameInput ? nameInput.value.trim() : '';
            const descVal = descInput ? descInput.value.trim() : '';

            if (!moduleVal || moduleVal === '0') {
                Swal.fire({
                    title: 'Campo obligatorio',
                    text: 'Por favor, selecciona un Módulo Rector.',
                    icon: 'warning',
                    confirmButtonColor: '#0d9488',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    if (moduleInput) moduleInput.focus();
                });
                return;
            }

            if (!nameVal) {
                Swal.fire({
                    title: 'Campo obligatorio',
                    text: 'Debe escribir un título para el tema formativo.',
                    icon: 'warning',
                    confirmButtonColor: '#0d9488',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    if (nameInput) nameInput.focus();
                });
                return;
            }

            if (nameVal.length < 10) {
                Swal.fire({
                    title: 'Título muy corto',
                    text: 'El título del tema formativo debe tener al menos 10 caracteres.',
                    icon: 'warning',
                    confirmButtonColor: '#0d9488',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    if (nameInput) nameInput.focus();
                });
                return;
            }

            if (!isNameValid) {
                Swal.fire({
                    title: 'Nombre no disponible',
                    text: 'El nombre ingresado ya existe o no es válido. Por favor, cámbialo.',
                    icon: 'error',
                    confirmButtonColor: '#0d9488',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    if (nameInput) nameInput.focus();
                });
                return;
            }

            if (!descVal || descVal.length < 15) {
                Swal.fire({
                    title: 'Descripción muy corta',
                    text: 'La descripción debe tener al menos 15 caracteres.',
                    icon: 'warning',
                    confirmButtonColor: '#0d9488',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    if (descInput) descInput.focus();
                });
                return;
            }

            // Confirmación antes de guardar
            Swal.fire({
                title: '¿Registrar Tema Formativo?',
                text: '¿Deseas guardar este nuevo Tema Formativo en el sistema?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#0d9488',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, guardar',
                cancelButtonText: 'Revisar'
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.fire({
                        title: 'Guardando Tema Formativo...',
                        text: 'Procesando el registro, por favor espera',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    // Enviar formulario
                    form.submit();
                }
            });
        });
    }
});

