// Script para el formulario de edición de instituciones
document.addEventListener('DOMContentLoaded', function() {
    // Mostrar fecha actual
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString('es-ES', options);
    }
    
    // === Validar todos los campos al cargar la página ===
    function validateAllFields() {
        const allInputs = document.querySelectorAll('input[required], select[required]');
        allInputs.forEach(input => {
            if (input.type === 'radio' || input.type === 'checkbox') {
                // Para radio/checkbox, verificar si hay alguno seleccionado en el grupo
                const name = input.name;
                const group = document.querySelectorAll(`input[name="${name}"]`);
                const isChecked = Array.from(group).some(field => field.checked);
                if (!isChecked) {
                    input.classList.add('error');
                } else {
                    input.classList.remove('error');
                }
            } else {
                // Para inputs y selects normales
                if (!input.value || input.value === '') {
                    input.classList.add('error');
                } else {
                    input.classList.remove('error');
                }
            }
        });
    }
    
    // Validar todos los campos al cargar
    validateAllFields();
    
    // Agregar listeners de validación en tiempo real para todos los campos
    const allInputs = document.querySelectorAll('input, select');
    allInputs.forEach(input => {
        input.addEventListener('input', function() {
            if (this.value && this.value !== '') {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required')) {
                    this.classList.add('error');
                }
            }
        });
        
        input.addEventListener('change', function() {
            if (this.value && this.value !== '') {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required')) {
                    this.classList.add('error');
                }
            }
        });
    });
    
    // Elementos del formulario
    const form = document.querySelector('.edit-form');
    const phoneInput = document.getElementById('phone');
    const institutionNameInput = document.getElementById('institution_name');
    const addressInput = document.getElementById('address');
    const institutionTypeSelect = document.getElementById('institution_type');
    const institutionScopeSelect = document.getElementById('institution_scope');
    const institutionDependencySelect = document.getElementById('institution_dependency');
    const plantelCodeInput = document.getElementById('plantel_code');
    const unlockPlantelCodeBtn = document.getElementById('unlock-plantel-code');
    
    // Elementos de ubicación
    const stateSelect = document.getElementById('state_id');
    const municipalitySelect = document.getElementById('municipality_id');
    const parishSelect = document.getElementById('parish_id');
    const citySelect = document.getElementById('city_id');
    
    // Elementos de UI
    const btnSave = document.getElementById('btn-save');
    const btnCancel = document.getElementById('btn-cancel');
    
    // === Funcionalidad de desbloqueo de código de plantel (DEA) ===
    let plantelCodeUnlocked = false;
    
    if (unlockPlantelCodeBtn && plantelCodeInput) {
        unlockPlantelCodeBtn.addEventListener('click', function() {
            if (!plantelCodeUnlocked) {
                // Solicitar confirmación antes de desbloquear
                Swal.fire({
                    title: 'Desbloquear Código de Plantel (DEA)',
                    text: 'El código de plantel es un dato oficial importante. ¿Está seguro de que necesita modificarlo?',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#ffc107',
                    cancelButtonColor: '#d33',
                    confirmButtonText: 'Sí, desbloquear',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        // Desbloquear el campo
                        plantelCodeInput.removeAttribute('readonly');
                        plantelCodeInput.classList.remove('readonly-field');
                        plantelCodeInput.focus();
                        plantelCodeUnlocked = true;
                        
                        // Cambiar el botón a icono de candado abierto
                        unlockPlantelCodeBtn.innerHTML = `
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path d="M7 11V7a5 5 0 0 1 9.9-1"></path>
                            </svg>
                        `;
                        unlockPlantelCodeBtn.title = 'Bloquear edición de código';
                        
                        Swal.fire({
                            icon: 'success',
                            title: 'Campo desbloqueado',
                            text: 'Ahora puede editar el código de plantel. Verifique que la información sea correcta.',
                            confirmButtonColor: '#ffc107'
                        });
                    }
                });
            } else {
                // Volver a bloquear el campo
                plantelCodeInput.setAttribute('readonly', true);
                plantelCodeInput.classList.add('readonly-field');
                plantelCodeUnlocked = false;
                
                // Cambiar el botón a icono de candado cerrado
                unlockPlantelCodeBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                `;
                unlockPlantelCodeBtn.title = 'Desbloquear edición de código';
            }
        });
        
        // Validación del código de plantel cuando se desbloquea
        plantelCodeInput.addEventListener('input', function() {
            if (plantelCodeUnlocked) {
                // Formato DEA: XXX-X0000 (ej: DEA-U0001)
                let value = this.value.toUpperCase().replace(/[^A-Z0-9-]/g, '');
                
                // Limitar longitud
                if (value.length > 9) {
                    value = value.slice(0, 9);
                }
                
                // Formatear automáticamente
                if (value.length > 3 && !value.includes('-')) {
                    value = value.slice(0, 3) + '-' + value.slice(3);
                }
                
                this.value = value;
            }
        });
    }
    
    // === Lógica para selects de ubicación (Estado -> Municipio -> Parroquia -> Ciudad) ===
    if (stateSelect && municipalitySelect && parishSelect && citySelect) {
        console.log('Inicializando selects de ubicación...');
        
        // Obtener valores actuales
        const currentParishId = document.getElementById('current_parish_id');
        const currentMunicipalityId = document.getElementById('current_municipality_id');
        const currentCityId = document.getElementById('current_city_id');
        const currentstateId = document.getElementById('current_state_id');
        
        console.log('Valores actuales:', {
            stateId: currentstateId ? currentstateId.value : null,
            municipalityId: currentMunicipalityId ? currentMunicipalityId.value : null,
            parishId: currentParishId ? currentParishId.value : null,
            cityId: currentCityId ? currentCityId.value : null
        });
        
        // Cargar estados al inicio
        loadStates(currentstateId ? currentstateId.value : null, currentMunicipalityId ? currentMunicipalityId.value : null, currentParishId ? currentParishId.value : null, currentCityId ? currentCityId.value : null);
        
        // Cargar municipios cuando se selecciona un estado
        stateSelect.addEventListener('change', function() {
            const stateId = this.value;
            console.log('Estado seleccionado:', stateId);
            
            // Limpiar selects de municipio, parroquia y ciudad al cambiar estado
            municipalitySelect.innerHTML = '<option value="">Seleccione...</option>';
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            citySelect.innerHTML = '<option value="">Seleccione...</option>';
            
            // Remover estilos de los selects limpiados
            municipalitySelect.classList.remove('success', 'error');
            parishSelect.classList.remove('success', 'error');
            citySelect.classList.remove('success', 'error');
            
            // Aplicar estilo verde al estado seleccionado, rojo si está vacío y es requerido
            if (stateId) {
                stateSelect.classList.add('success');
                stateSelect.classList.remove('error');
                loadMunicipalities(stateId);
            } else {
                stateSelect.classList.remove('success');
                // Si es requerido y está vacío, aplicar error
                if (stateSelect.hasAttribute('required')) {
                    stateSelect.classList.add('error');
                }
            }
        });
        
        // Cargar parroquias cuando se selecciona un municipio
        municipalitySelect.addEventListener('change', function() {
            const municipalityId = this.value;
            console.log('Municipio seleccionado:', municipalityId);
            
            // Limpiar selects de parroquia y ciudad al cambiar municipio
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            citySelect.innerHTML = '<option value="">Seleccione...</option>';
            
            // Remover estilos de los selects limpiados
            parishSelect.classList.remove('success', 'error');
            citySelect.classList.remove('success', 'error');
            
            // Aplicar estilo verde al municipio seleccionado, rojo si está vacío y es requerido
            if (municipalityId) {
                municipalitySelect.classList.add('success');
                municipalitySelect.classList.remove('error');
                loadParishes(municipalityId);
            } else {
                municipalitySelect.classList.remove('success');
                // Si es requerido y está vacío, aplicar error
                if (municipalitySelect.hasAttribute('required')) {
                    municipalitySelect.classList.add('error');
                }
            }
        });
        
        // Cargar ciudades cuando se selecciona una parroquia
        parishSelect.addEventListener('change', function() {
            const parishId = this.value;
            console.log('Parroquia seleccionada:', parishId);
            
            // Limpiar select de ciudad al cambiar parroquia
            citySelect.innerHTML = '<option value="">Seleccione...</option>';
            
            // Remover estilo de ciudad
            citySelect.classList.remove('success', 'error');
            
            // Aplicar estilo verde a la parroquia seleccionada, rojo si está vacío y es requerido
            if (parishId) {
                parishSelect.classList.add('success');
                parishSelect.classList.remove('error');
                loadCitiesByParish(parishId);
            } else {
                parishSelect.classList.remove('success');
                // Si es requerido y está vacío, aplicar error
                if (parishSelect.hasAttribute('required')) {
                    parishSelect.classList.add('error');
                }
            }
        });
        
        // Aplicar estilo verde cuando se selecciona una ciudad, rojo si está vacío y es requerido
        citySelect.addEventListener('change', function() {
            const cityId = this.value;
            console.log('Ciudad seleccionada:', cityId);
            
            if (cityId) {
                citySelect.classList.add('success');
                citySelect.classList.remove('error');
            } else {
                citySelect.classList.remove('success');
                // Si es requerido y está vacío, aplicar error
                if (citySelect.hasAttribute('required')) {
                    citySelect.classList.add('error');
                }
            }
        });
    } else {
        console.error('No se encontraron todos los selects de ubicación');
    }
    
    // Función para cargar estados
    function loadStates(selectedId = null, currentMunicipalityId = null, currentParishId = null, currentCityId = null) {
        console.log('Cargando estados, selectedId:', selectedId, 'currentMunicipalityId:', currentMunicipalityId, 'currentParishId:', currentParishId, 'currentCityId:', currentCityId);
        fetch('/institutions/api/states')
            .then(response => {
                console.log('Respuesta de estados:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Datos de estados:', data);
                stateSelect.innerHTML = '<option value="">Seleccione...</option>';
                data.forEach(state => {
                    const option = document.createElement('option');
                    option.value = state.id;
                    option.textContent = state.name;
                    if (selectedId && state.id == selectedId) {
                        option.selected = true;
                    }
                    stateSelect.appendChild(option);
                });
                
                // No aplicar estilo verde en carga inicial, solo en selección manual
                
                // Después de cargar estados, cargar municipios si hay un estado seleccionado
                if (selectedId && stateSelect.value) {
                    console.log('Cargando municipios después de cargar estados con stateId:', stateSelect.value);
                    loadMunicipalities(stateSelect.value, currentMunicipalityId, currentParishId, currentCityId);
                }
            })
            .catch(error => {
                console.error('Error al cargar estados:', error);
                stateSelect.innerHTML = '<option value="">Error al cargar estados</option>';
            });
    }
    
    // Función para cargar ciudades filtradas por parroquia
    function loadCitiesByParish(parishId, selectedId = null) {
        console.log('Cargando ciudades por parroquia, parishId:', parishId, 'selectedId:', selectedId);
        if (!parishId) {
            citySelect.innerHTML = '<option value="">Seleccione...</option>';
            citySelect.classList.remove('success');
            return;
        }
        
        fetch(`/institutions/api/cities?parish_id=${parishId}`)
            .then(response => {
                console.log('Respuesta de ciudades:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Datos de ciudades:', data);
                citySelect.innerHTML = '<option value="">Seleccione...</option>';
                data.forEach(city => {
                    const option = document.createElement('option');
                    option.value = city.id;
                    option.textContent = city.name;
                    if (selectedId && city.id == selectedId) {
                        option.selected = true;
                    }
                    citySelect.appendChild(option);
                });
                
                // No aplicar estilo verde en carga inicial, solo en selección manual
            })
            .catch(error => {
                console.error('Error al cargar ciudades:', error);
                citySelect.innerHTML = '<option value="">Error al cargar ciudades</option>';
            });
    }
    
    // Función para cargar municipios
    function loadMunicipalities(stateId, selectedId = null, currentParishId = null, currentCityId = null) {
        console.log('Cargando municipios, stateId:', stateId, 'selectedId:', selectedId, 'currentParishId:', currentParishId, 'currentCityId:', currentCityId);
        if (!stateId) {
            municipalitySelect.innerHTML = '<option value="">Seleccione...</option>';
            municipalitySelect.classList.remove('success');
            return;
        }
        
        fetch(`/institutions/api/municipalities/${stateId}`)
            .then(response => {
                console.log('Respuesta de municipios:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Datos de municipios:', data);
                municipalitySelect.innerHTML = '<option value="">Seleccione...</option>';
                data.forEach(municipality => {
                    const option = document.createElement('option');
                    option.value = municipality.id;
                    option.textContent = municipality.name;
                    if (selectedId && municipality.id == selectedId) {
                        option.selected = true;
                    }
                    municipalitySelect.appendChild(option);
                });
                
                // No aplicar estilo verde en carga inicial, solo en selección manual
                
                // Después de cargar municipios, cargar parroquias si hay un municipio seleccionado
                if (selectedId && municipalitySelect.value) {
                    console.log('Cargando parroquias después de cargar municipios con municipalityId:', municipalitySelect.value);
                    loadParishes(municipalitySelect.value, currentParishId, currentCityId);
                }
            })
            .catch(error => {
                console.error('Error al cargar municipios:', error);
                municipalitySelect.innerHTML = '<option value="">Error al cargar municipios</option>';
            });
    }
    
    // Función para cargar parroquias
    function loadParishes(municipalityId, selectedId = null, currentCityId = null) {
        console.log('Cargando parroquias, municipalityId:', municipalityId, 'selectedId:', selectedId, 'currentCityId:', currentCityId);
        if (!municipalityId) {
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            parishSelect.classList.remove('success');
            return;
        }
        
        fetch(`/institutions/api/parishes/${municipalityId}`)
            .then(response => {
                console.log('Respuesta de parroquias:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Datos de parroquias:', data);
                parishSelect.innerHTML = '<option value="">Seleccione...</option>';
                data.forEach(parish => {
                    const option = document.createElement('option');
                    option.value = parish.id;
                    option.textContent = parish.name;
                    if (selectedId && parish.id == selectedId) {
                        option.selected = true;
                    }
                    parishSelect.appendChild(option);
                });
                
                // No aplicar estilo verde en carga inicial, solo en selección manual
                
                // Después de cargar parroquias, cargar ciudades si hay una parroquia seleccionada
                if (selectedId && parishSelect.value) {
                    console.log('Cargando ciudades después de cargar parroquias con parishId:', parishSelect.value);
                    loadCitiesByParish(parishSelect.value, currentCityId);
                }
            })
            .catch(error => {
                console.error('Error al cargar parroquias:', error);
                parishSelect.innerHTML = '<option value="">Error al cargar parroquias</option>';
            });
    }
    
    // === Validación en tiempo real ===
    
    // Formateo de nombre de institución (solo letras, title case)
    if (institutionNameInput) {
        institutionNameInput.addEventListener('input', function(e) {
            // Solo permitir letras y espacios
            let value = this.value.replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]/g, '');
            
            // Convertir a minúsculas y luego a title case
            value = value.toLowerCase().replace(/\b\w/g, function(char) {
                return char.toUpperCase();
            });
            
            this.value = value;
            
            // Validación visual
            if (value && value !== '') {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required')) {
                    this.classList.add('error');
                }
            }
        });
    }
    
    // Validación de teléfono con formateo automático
    if (phoneInput) {
        // Formatear el teléfono existente al cargar (si viene sin formato de la BD)
        const existingPhone = phoneInput.value;
        if (existingPhone) {
            // Limpiar cualquier caracter no numérico
            let cleanPhone = existingPhone.replace(/[^0-9]/g, '');
            
            // Si tiene 11 dígitos y no está formateado, formatearlo
            if (cleanPhone.length === 11 && !existingPhone.includes('(')) {
                phoneInput.value = '(' + cleanPhone.slice(0, 4) + ')-' + cleanPhone.slice(4);
            }
        }
        
        phoneInput.addEventListener('input', function(e) {
            // Solo permitir números
            let value = this.value.replace(/[^0-9]/g, '');
            
            // Limitar a máximo 11 dígitos
            if (value.length > 11) {
                value = value.slice(0, 11);
            }
            
            // Formatear automáticamente: (XXXX)-XXXXXXX
            if (value.length > 4) {
                value = '(' + value.slice(0, 4) + ')-' + value.slice(4);
            }
            
            this.value = value;
            
            // Validación visual
            if (value && value.length === 14) { // ( + 4 dígitos + ) + - + 7 dígitos = 14 caracteres
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required') && value.length < 14) {
                    this.classList.add('error');
                }
            }
        });
        
        phoneInput.addEventListener('blur', function() {
            // Validación visual al perder el foco
            let value = this.value;
            if (value && value.length === 14) {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required') && value.length < 14) {
                    this.classList.add('error');
                }
            }
        });
    }
    
    // Validación de dirección
    if (addressInput) {
        addressInput.addEventListener('input', function() {
            if (this.value && this.value !== '') {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required')) {
                    this.classList.add('error');
                }
            }
        });
        
        addressInput.addEventListener('blur', function() {
            if (this.value && this.value !== '') {
                this.classList.add('success');
                this.classList.remove('error');
            } else {
                this.classList.remove('success');
                if (this.hasAttribute('required')) {
                    this.classList.add('error');
                }
            }
        });
    }
    
    // === Confirmación de seguridad con SweetAlert2 ===
    
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
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
    
    // === Confirmación al cancelar con SweetAlert2 ===
    
    if (btnCancel) {
        btnCancel.addEventListener('click', function(e) {
            e.preventDefault();
            
            Swal.fire({
                title: '¿Está seguro?',
                text: 'Los cambios no guardados se perderán. ¿Desea cancelar la edición?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, cancelar',
                cancelButtonText: 'No, continuar editando'
            }).then((result) => {
                if (result.isConfirmed) {
                    // Redirigir a la vista anterior o a la vista de consulta
                    const cancelUrl = btnCancel.getAttribute('href');
                    if (cancelUrl) {
                        window.location.href = cancelUrl;
                    } else {
                        // Si no hay href específico, ir a la vista de consulta
                        const institutionId = form.getAttribute('action').split('/').pop();
                        if (institutionId) {
                            window.location.href = `/institutions/${institutionId}`;
                        } else {
                            // Fallback a la lista de instituciones
                            window.location.href = '/institutions';
                        }
                    }
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
            
            // Guardar el valor actual seleccionado
            const currentValue = institutionDependencySelect.value;
            
            institutionDependencySelect.innerHTML = '<option value="">Seleccione...</option>';
            
            if (category && dependenciesByCategory[category]) {
                const uniqueDepNames = [...new Set(dependenciesByCategory[category])];
                
                uniqueDepNames.forEach(depName => {
                    let depId = dependenciesDict[depName];
                    
                    if (depId) {
                        const option = document.createElement('option');
                        option.value = depId;
                        option.textContent = depName;
                        
                        // Mantener el valor seleccionado si coincide
                        if (currentValue && option.value == currentValue) {
                            option.selected = true;
                        }
                        
                        institutionDependencySelect.appendChild(option);
                    }
                });
            }
            
            // Si después de filtrar no hay coincidencia, intenta seleccionar el valor actual
            if (currentValue && institutionDependencySelect.value === '') {
                // Buscar si el valor actual existe en las opciones filtradas
                const optionExists = Array.from(institutionDependencySelect.options).some(opt => opt.value == currentValue);
                if (!optionExists) {
                    // Si no existe en las opciones filtradas, agregarlo
                    const depName = Object.keys(dependenciesDict).find(key => dependenciesDict[key] == currentValue);
                    if (depName) {
                        const option = document.createElement('option');
                        option.value = currentValue;
                        option.textContent = depName;
                        option.selected = true;
                        institutionDependencySelect.appendChild(option);
                    }
                }
            }
        }
        
        institutionTypeSelect.addEventListener('change', updateDependencyOptions);
        updateDependencyOptions();
    }
});