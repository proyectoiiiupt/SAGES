// Script para el formulario de edición de instituciones
document.addEventListener('DOMContentLoaded', function() {
    // Mostrar fecha actual
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString('es-ES', options);
    }
    
    // Elementos del formulario
    const form = document.querySelector('.edit-form');
    const phoneInput = document.getElementById('phone');
    const institutionNameInput = document.getElementById('institution_name');
    const addressInput = document.getElementById('address');
    const institutionTypeSelect = document.getElementById('institution_type');
    const institutionScopeSelect = document.getElementById('institution_scope');
    const institutionDependencySelect = document.getElementById('institution_dependency');
    
    // Elementos de UI
    const btnSave = document.getElementById('btn-save');
    const btnCancel = document.getElementById('btn-cancel');
    
    // === Validación en tiempo real ===
    
    // Validación de teléfono
    if (phoneInput) {
        // Formatear el teléfono existente al cargar (si viene sin guión de la BD)
        const existingPhone = phoneInput.value;
        if (existingPhone && existingPhone.length === 11 && !existingPhone.includes('-')) {
            phoneInput.value = existingPhone.slice(0, 4) + '-' + existingPhone.slice(4);
        }
        
        phoneInput.addEventListener('input', function(e) {
            // Eliminar cualquier caracter que no sea número
            let value = this.value.replace(/[^0-9]/g, '');
            
            // Limitar a 11 dígitos
            if (value.length > 11) {
                value = value.slice(0, 11);
            }
            
            // Formatear con guión después de los primeros 4 dígitos
            if (value.length > 4) {
                value = value.slice(0, 4) + '-' + value.slice(4);
            }
            
            this.value = value;
            validateFieldInRealTime(this, 'phone');
        });
        
        phoneInput.addEventListener('blur', function() {
            validateFieldInRealTime(this, 'phone');
        });
    }
    
    // Validación de nombre de institución
    if (institutionNameInput) {
        institutionNameInput.addEventListener('input', function() {
            validateFieldInRealTime(this, 'institution_name');
        });
        
        institutionNameInput.addEventListener('blur', function() {
            validateFieldInRealTime(this, 'institution_name');
        });
    }
    
    // Validación de dirección
    if (addressInput) {
        addressInput.addEventListener('input', function() {
            validateFieldInRealTime(this, 'address');
        });
        
        addressInput.addEventListener('blur', function() {
            validateFieldInRealTime(this, 'address');
        });
    }
    
    // Validación de selects
    [institutionTypeSelect, institutionScopeSelect, institutionDependencySelect].forEach(select => {
        if (select) {
            select.addEventListener('change', function() {
                validateFieldInRealTime(this, this.id.replace('institution_', '').replace('_id', ''));
            });
        }
    });
    
    // Función de validación en tiempo real
    function validateFieldInRealTime(field, fieldName) {
        const value = field.value ? field.value.trim() : '';
        let isValid = true;
        let errorMessage = '';
        
        // Remover error anterior si existe
        field.classList.remove('error', 'success');
        const existingError = field.parentElement.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        switch(fieldName) {
            case 'phone':
                const cleanPhone = value.replace(/-/g, '');
                if (!value) {
                    isValid = false;
                    errorMessage = 'El teléfono es obligatorio';
                } else if (!/^(0212|0214|0412|0414|0416|0422|0424|0426)-\d{7}$/.test(value)) {
                    isValid = false;
                    errorMessage = 'Formato inválido. Debe ser XXXX-XXXXXXX (ej: 0212-1234567)';
                }
                break;
                
            case 'institution_name':
                if (!value) {
                    isValid = false;
                    errorMessage = 'El nombre es obligatorio';
                } else if (value.length < 3) {
                    isValid = false;
                    errorMessage = 'Mínimo 3 caracteres';
                } else if (value.length > 100) {
                    isValid = false;
                    errorMessage = 'Máximo 100 caracteres';
                }
                break;
                
            case 'address':
                if (!value) {
                    isValid = false;
                    errorMessage = 'La dirección es obligatoria';
                } else if (value.length < 5) {
                    isValid = false;
                    errorMessage = 'Mínimo 5 caracteres';
                } else if (value.length > 200) {
                    isValid = false;
                    errorMessage = 'Máximo 200 caracteres';
                }
                break;
                
            case 'type':
            case 'scope':
            case 'dependency':
                if (!value) {
                    isValid = false;
                    errorMessage = 'Debe seleccionar una opción';
                }
                break;
        }
        
        // Mostrar validación visual
        if (!isValid && value) {
            field.classList.add('error');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = errorMessage;
            field.parentElement.appendChild(errorDiv);
        } else if (isValid && value) {
            field.classList.add('success');
        }
        
        return isValid;
    }
    
    // === Confirmación de seguridad con SweetAlert2 ===
    
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validar todos los campos
            let isFormValid = true;
            const fieldsToValidate = [
                { field: phoneInput, name: 'phone' },
                { field: institutionNameInput, name: 'institution_name' },
                { field: addressInput, name: 'address' },
                { field: institutionTypeSelect, name: 'type' },
                { field: institutionScopeSelect, name: 'scope' },
                { field: institutionDependencySelect, name: 'dependency' }
            ];
            
            fieldsToValidate.forEach(({ field, name }) => {
                if (field && !validateFieldInRealTime(field, name)) {
                    isFormValid = false;
                }
            });
            
            if (!isFormValid) {
                Swal.fire({
                    icon: 'error',
                    title: 'Errores de validación',
                    text: 'Por favor, corrija los errores en el formulario antes de continuar.',
                    confirmButtonColor: '#d33'
                });
                return;
            }
            
            // Verificar si hay cambios importantes
            const currentName = institutionNameInput ? institutionNameInput.value.trim() : '';
            const currentType = institutionTypeSelect ? institutionTypeSelect.value : '';
            const currentScope = institutionScopeSelect ? institutionScopeSelect.value : '';
            const currentDependency = institutionDependencySelect ? institutionDependencySelect.value : '';
            
            const hasImportantChanges = currentName || currentType || currentScope || currentDependency;
            
            const confirmMessage = hasImportantChanges
                ? 'Está a punto de modificar información oficial importante de la institución. ¿Está seguro de que todos los datos son correctos?'
                : '¿Está seguro de guardar los cambios realizados?';

            Swal.fire({
                title: '¿Está seguro?',
                text: confirmMessage,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Sí, guardar cambios',
                cancelButtonText: 'Cancelar',
                showLoaderOnConfirm: true
            }).then((result) => {
                if (result.isConfirmed) {
                    // El backend se encarga de limpiar el teléfono, así que enviamos con el guión
                    console.log('Enviando formulario con teléfono:', phoneInput ? phoneInput.value : 'No encontrado');

                    // Enviar formulario
                    form.submit();
                }
            });
        });
    }

    // === Lógica para opciones de dependencia según tipo de institución ===
    const currentDependencyId = document.getElementById('current_dependency_id');
    
    if (institutionTypeSelect && institutionDependencySelect) {
        let dependenciesList = window.dependenciesList || [];
        
        const dependenciesDict = {};
        dependenciesList.forEach(dep => {
            dependenciesDict[dep.name] = dep.id;
        });
        
        const dependenciesByCategory = {
            'superior': ['Autónoma', 'Nacional', 'Centralizadas', 'Deconcentradas', 'Descentralizadas'],
            'basica': ['Nacional', 'Estadal', 'Municipal', 'Subvencionada / Convenio MPPE']
        };
        
        const typeMapping = {
            'Centro de Formación Técnica y Laboral': 'superior',
            'Instituto Universitario': 'superior',
            'Universidad': 'superior',
            'Escuela Básica / Primaria': 'basica',
            'Liceo / Educación Media': 'basica',
            'Complejo Educativo Integral': 'basica'
        };
        
        function updateDependencyOptions() {
            const selectedType = institutionTypeSelect.options[institutionTypeSelect.selectedIndex].text;
            const category = typeMapping[selectedType];
            
            institutionDependencySelect.innerHTML = '<option value="">Seleccione...</option>';
            
            if (category && dependenciesByCategory[category]) {
                const uniqueDepNames = [...new Set(dependenciesByCategory[category])];
                
                uniqueDepNames.forEach(depName => {
                    let depId = dependenciesDict[depName];
                    
                    if (depId) {
                        const option = document.createElement('option');
                        option.value = depId;
                        option.textContent = depName;
                        
                        if (currentDependencyId && option.value == currentDependencyId.value) {
                            option.selected = true;
                        }
                        
                        institutionDependencySelect.appendChild(option);
                    }
                });
            }
        }
        
        institutionTypeSelect.addEventListener('change', updateDependencyOptions);
        updateDependencyOptions();
    }
    
    // Restaurar datos del formulario si hay errores de validación
    if (window.validationErrors && Object.keys(window.validationErrors).length > 0) {
        if (window.formData) {
            if (institutionNameInput && window.formData.institution_name) {
                institutionNameInput.value = window.formData.institution_name;
            }
            if (institutionTypeSelect && window.formData.institution_type_id) {
                institutionTypeSelect.value = window.formData.institution_type_id;
            }
            if (institutionScopeSelect && window.formData.institution_scope_id) {
                institutionScopeSelect.value = window.formData.institution_scope_id;
            }
            if (institutionDependencySelect && window.formData.institution_dependency_id) {
                institutionDependencySelect.value = window.formData.institution_dependency_id;
            }
            if (addressInput && window.formData.address) {
                addressInput.value = window.formData.address;
            }
            if (phoneInput && window.formData.phone) {
                const phone = window.formData.phone;
                if (phone.length === 11) {
                    phoneInput.value = phone.slice(0, 4) + '-' + phone.slice(4);
                } else {
                    phoneInput.value = phone;
                }
            }
        }
        
        // Mostrar errores de validación
        setTimeout(() => {
            for (const field in window.validationErrors) {
                const fieldElement = document.getElementById(field === 'institution_type' ? 'institution_type' : 
                                                          field === 'institution_scope' ? 'institution_scope' :
                                                          field === 'institution_dependency' ? 'institution_dependency' : field);
                if (fieldElement) {
                    validateFieldInRealTime(fieldElement, field);
                    fieldElement.classList.add('error');
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error-message';
                    errorDiv.textContent = window.validationErrors[field];
                    fieldElement.parentElement.appendChild(errorDiv);
                }
            }
        }, 100);
    }
});