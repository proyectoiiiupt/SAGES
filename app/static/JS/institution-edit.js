// Script para el formulario de edición de instituciones
document.addEventListener('DOMContentLoaded', function() {
    // === Validar todos los campos al cargar la página ===
    function validateAllFields() {
        const allInputs = document.querySelectorAll('input[required], select[required]');
        allInputs.forEach(input => {
            if (input.type === 'radio' || input.type === 'checkbox') {
                const name = input.name;
                const group = document.querySelectorAll(`input[name="${name}"]`);
                const isChecked = Array.from(group).some(field => field.checked);
                if (!isChecked) {
                    input.classList.add('error');
                } else {
                    input.classList.remove('error');
                }
            } else {
                if (!input.value || input.value === '') {
                    input.classList.add('error');
                } else {
                    input.classList.remove('error');
                }
            }
        });
    }
    
    validateAllFields();
    
    // Listeners de validación en tiempo real para todos los campos
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
    const institutionNameInput = document.getElementById('institution_name');
    const addressInput = document.getElementById('address');
    const phoneInput = document.getElementById('phone');
    const institutionTypeSelect = document.getElementById('institution_type');
    const institutionScopeSelect = document.getElementById('institution_scope');
    const institutionDependencySelect = document.getElementById('institution_dependency');
    const plantelCodeInput = document.getElementById('plantel_code');
    const unlockPlantelCodeBtn = document.getElementById('unlock-plantel-code');
    
    // Elementos de ubicación
    const stateSelect = document.getElementById('state_id');
    const municipalitySelect = document.getElementById('municipality_id');
    const parishSelect = document.getElementById('parish_id');
    const cityDisplay = document.getElementById('city_display') || document.getElementById('city');
    
    // Elementos de UI
    const btnSave = document.getElementById('btn-save');
    const btnCancel = document.getElementById('btn-cancel');
    
    // === Funcionalidad de desbloqueo de código de plantel (DEA) - Solo Super Admin ===
    let plantelCodeUnlocked = false;
    
    if (unlockPlantelCodeBtn && plantelCodeInput) {
        unlockPlantelCodeBtn.addEventListener('click', function() {
            if (!plantelCodeUnlocked) {
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
                        plantelCodeInput.removeAttribute('readonly');
                        plantelCodeInput.classList.remove('readonly-field');
                        plantelCodeInput.focus();
                        plantelCodeUnlocked = true;
                        
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
                            text: 'Ahora puede editar el código de plantel con formato oficial (4 a 20 caracteres: mayúsculas, números y guiones).',
                            confirmButtonColor: '#ffc107'
                        });
                    }
                });
            } else {
                plantelCodeInput.setAttribute('readonly', true);
                plantelCodeInput.classList.add('readonly-field');
                plantelCodeUnlocked = false;
                
                unlockPlantelCodeBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                `;
                unlockPlantelCodeBtn.title = 'Desbloquear edición de código';
            }
        });
        
        // Validación del código de plantel (regex ^[A-Z0-9\-]{4,20}$)
        plantelCodeInput.addEventListener('input', function() {
            if (plantelCodeUnlocked) {
                let value = this.value.toUpperCase().replace(/[^A-Z0-9\-]/g, '');
                if (value.length > 20) {
                    value = value.slice(0, 20);
                }
                this.value = value;
            }
        });
    }
    
    // === Lógica de Ciudad Informativa derivada automáticamente de Parish ===
    function loadCityByParish(parishId) {
        if (!cityDisplay) return;
        if (!parishId) {
            cityDisplay.value = 'No asignada';
            return;
        }
        
        fetch(`/institutions/api/cities?parish_id=${parishId}`)
            .then(response => response.json())
            .then(data => {
                if (data && data.length > 0) {
                    cityDisplay.value = data[0].name;
                } else {
                    cityDisplay.value = 'No asignada';
                }
            })
            .catch(error => {
                console.error('Error al cargar ciudad informativa:', error);
                cityDisplay.value = 'No asignada';
            });
    }
    
    // === Lógica para selects de ubicación (Estado -> Municipio -> Parroquia -> Ciudad derivada) ===
    const currentParishId = document.getElementById('current_parish_id');
    const currentMunicipalityId = document.getElementById('current_municipality_id');
    const currentstateId = document.getElementById('current_state_id');
    
    // 1. Si existe stateSelect (Super Admin)
    if (stateSelect && municipalitySelect && parishSelect) {
        // Cargar estados al inicio para super_admin
        loadStates(
            currentstateId ? currentstateId.value : null,
            currentMunicipalityId ? currentMunicipalityId.value : null,
            currentParishId ? currentParishId.value : null
        );
        
        stateSelect.addEventListener('change', function() {
            const stateId = this.value;
            municipalitySelect.innerHTML = '<option value="">Seleccione...</option>';
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            if (cityDisplay) cityDisplay.value = 'No asignada';
            
            municipalitySelect.classList.remove('success', 'error');
            parishSelect.classList.remove('success', 'error');
            
            if (stateId) {
                stateSelect.classList.add('success');
                stateSelect.classList.remove('error');
                loadMunicipalities(stateId);
            } else {
                stateSelect.classList.remove('success');
                if (stateSelect.hasAttribute('required')) {
                    stateSelect.classList.add('error');
                }
            }
        });
        
        municipalitySelect.addEventListener('change', function() {
            const municipalityId = this.value;
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            if (cityDisplay) cityDisplay.value = 'No asignada';
            parishSelect.classList.remove('success', 'error');
            
            if (municipalityId) {
                municipalitySelect.classList.add('success');
                municipalitySelect.classList.remove('error');
                loadParishes(municipalityId);
            } else {
                municipalitySelect.classList.remove('success');
                if (municipalitySelect.hasAttribute('required')) {
                    municipalitySelect.classList.add('error');
                }
            }
        });
        
        parishSelect.addEventListener('change', function() {
            const parishId = this.value;
            if (parishId) {
                parishSelect.classList.add('success');
                parishSelect.classList.remove('error');
                loadCityByParish(parishId);
            } else {
                parishSelect.classList.remove('success');
                if (cityDisplay) cityDisplay.value = 'No asignada';
                if (parishSelect.hasAttribute('required')) {
                    parishSelect.classList.add('error');
                }
            }
        });
    } else if (municipalitySelect && parishSelect) {
        // 2. Si no hay stateSelect editable (State Admin: estado bloqueado)
        const lockedStateId = (currentstateId && currentstateId.value) || window.adminStateId;
        
        municipalitySelect.addEventListener('change', function() {
            const municipalityId = this.value;
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            if (cityDisplay) cityDisplay.value = 'No asignada';
            parishSelect.classList.remove('success', 'error');
            
            if (municipalityId) {
                municipalitySelect.classList.add('success');
                municipalitySelect.classList.remove('error');
                loadParishes(municipalityId);
            } else {
                municipalitySelect.classList.remove('success');
                if (municipalitySelect.hasAttribute('required')) {
                    municipalitySelect.classList.add('error');
                }
            }
        });
        
        parishSelect.addEventListener('change', function() {
            const parishId = this.value;
            if (parishId) {
                parishSelect.classList.add('success');
                parishSelect.classList.remove('error');
                loadCityByParish(parishId);
            } else {
                parishSelect.classList.remove('success');
                if (cityDisplay) cityDisplay.value = 'No asignada';
                if (parishSelect.hasAttribute('required')) {
                    parishSelect.classList.add('error');
                }
            }
        });
        
        // Si hay un municipio ya seleccionado al cargar, asegurarse de que las parroquias y ciudad estén listas
        if (municipalitySelect.value && parishSelect.value) {
            loadCityByParish(parishSelect.value);
        }
    }
    
    // Función para cargar estados (Super Admin)
    function loadStates(selectedId = null, currentMunicipalityIdVal = null, currentParishIdVal = null) {
        if (!stateSelect) return;
        fetch('/institutions/api/states')
            .then(response => response.json())
            .then(data => {
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
                
                if (selectedId && stateSelect.value) {
                    loadMunicipalities(stateSelect.value, currentMunicipalityIdVal, currentParishIdVal);
                }
            })
            .catch(error => {
                console.error('Error al cargar estados:', error);
                stateSelect.innerHTML = '<option value="">Error al cargar estados</option>';
            });
    }
    
    // Función para cargar municipios
    function loadMunicipalities(stateId, selectedId = null, currentParishIdVal = null) {
        if (!municipalitySelect) return;
        if (!stateId) {
            municipalitySelect.innerHTML = '<option value="">Seleccione...</option>';
            municipalitySelect.classList.remove('success');
            return;
        }
        
        fetch(`/institutions/api/municipalities/${stateId}`)
            .then(response => response.json())
            .then(data => {
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
                
                if (selectedId && municipalitySelect.value) {
                    loadParishes(municipalitySelect.value, currentParishIdVal);
                }
            })
            .catch(error => {
                console.error('Error al cargar municipios:', error);
                municipalitySelect.innerHTML = '<option value="">Error al cargar municipios</option>';
            });
    }
    
    // Función para cargar parroquias
    function loadParishes(municipalityId, selectedId = null) {
        if (!parishSelect) return;
        if (!municipalityId) {
            parishSelect.innerHTML = '<option value="">Seleccione...</option>';
            parishSelect.classList.remove('success');
            return;
        }
        
        fetch(`/institutions/api/parishes/${municipalityId}`)
            .then(response => response.json())
            .then(data => {
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
                
                if (selectedId && parishSelect.value) {
                    loadCityByParish(parishSelect.value);
                }
            })
            .catch(error => {
                console.error('Error al cargar parroquias:', error);
                parishSelect.innerHTML = '<option value="">Error al cargar parroquias</option>';
            });
    }

    // === Filtrado dinámico de Niveles Educativos según Tipo de Institución (MPPE) ===
    const EDUCATIONAL_LEVELS_MAPPING = {
        'INST-001': ['EDUL-005', 'EDUL-006'], // Universidad
        'INST-002': ['EDUL-005'],             // Instituto Universitario
        'INST-003': ['EDUL-003', 'EDUL-004'], // Liceo / Educación Media
        'INST-004': ['EDUL-001', 'EDUL-002'], // Escuela Básica / Primaria
        'INST-006': ['EDUL-001', 'EDUL-002', 'EDUL-003', 'EDUL-004'], // Complejo Educativo Integral
        'INST-005': []                        // Centro de Formación Técnica y Laboral (ninguno)
    };

    function updateEducationalLevels(isInitial = false) {
        if (!institutionTypeSelect) return;
        const typeId = institutionTypeSelect.value;
        const typeCode = window.institutionTypesMap ? window.institutionTypesMap[typeId] : null;
        const allowedCodes = (typeCode && EDUCATIONAL_LEVELS_MAPPING[typeCode]) ? EDUCATIONAL_LEVELS_MAPPING[typeCode] : [];
        
        const levelCheckboxes = document.querySelectorAll('.edu-level-chk');
        const containerGroup = document.getElementById('group-educational-levels');
        
        if (containerGroup && typeCode === 'INST-005') {
            containerGroup.style.opacity = '0.5';
        } else if (containerGroup) {
            containerGroup.style.opacity = '1';
        }
        
        levelCheckboxes.forEach(chk => {
            const label = chk.closest('label');
            const levelCode = (label && label.dataset.levelCode) || (window.educationalLevelsMap ? window.educationalLevelsMap[chk.value] : null);
            if (allowedCodes.includes(levelCode)) {
                if (label) label.style.display = 'flex';
                // Si es INST-002 (Instituto Universitario), auto-marcar si no es carga inicial
                if (!isInitial && typeCode === 'INST-002' && levelCode === 'EDUL-005') {
                    chk.checked = true;
                }
            } else {
                if (label) label.style.display = 'none';
                if (!isInitial) {
                    chk.checked = false;
                }
            }
        });
    }

    if (institutionTypeSelect && institutionTypeSelect.tagName === 'SELECT') {
        institutionTypeSelect.addEventListener('change', function() {
            updateEducationalLevels(false);
        });
        // Ejecución inicial para mostrar solo los permitidos según el tipo actual
        updateEducationalLevels(true);
    }
    
    // === Lógica para opciones de dependencia según tipo de institución ===
    if (institutionTypeSelect && institutionDependencySelect && institutionTypeSelect.tagName === 'SELECT' && institutionDependencySelect.tagName === 'SELECT') {
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
            const selectedOption = institutionTypeSelect.options[institutionTypeSelect.selectedIndex];
            const selectedType = selectedOption ? selectedOption.text : '';
            const category = typeMapping[selectedType];
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
                        if (currentValue && option.value == currentValue) {
                            option.selected = true;
                        }
                        institutionDependencySelect.appendChild(option);
                    }
                });
            }
            
            if (currentValue && institutionDependencySelect.value === '') {
                const optionExists = Array.from(institutionDependencySelect.options).some(opt => opt.value == currentValue);
                if (!optionExists) {
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
    
    // === Confirmación de seguridad con SweetAlert2 al enviar ===
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const currentName = institutionNameInput ? institutionNameInput.value.trim() : '';
            const currentType = institutionTypeSelect ? institutionTypeSelect.value : '';
            const currentScope = institutionScopeSelect ? institutionScopeSelect.value : '';
            const currentDependency = institutionDependencySelect ? institutionDependencySelect.value : '';
            const hasImportantChanges = currentName || currentType || currentScope || currentDependency;
            
            const confirmMessage = hasImportantChanges
                ? 'Está a punto de modificar información oficial de la institución. ¿Está seguro de que todos los datos son correctos según los lineamientos del MPPE?'
                : '¿Está seguro de guardar los cambios realizados?';

            Swal.fire({
                title: '¿Confirmar actualización?',
                text: confirmMessage,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#007865',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Sí, guardar cambios',
                cancelButtonText: 'Cancelar',
                showLoaderOnConfirm: true
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    }
    
    // === Confirmación al cancelar ===
    if (btnCancel) {
        btnCancel.addEventListener('click', function(e) {
            e.preventDefault();
            Swal.fire({
                title: '¿Desea cancelar?',
                text: 'Los cambios no guardados se perderán. ¿Desea salir de la edición?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, cancelar',
                cancelButtonText: 'Continuar editando'
            }).then((result) => {
                if (result.isConfirmed) {
                    const cancelUrl = btnCancel.getAttribute('href');
                    if (cancelUrl) {
                        window.location.href = cancelUrl;
                    } else {
                        window.location.href = '/institutions';
                    }
                }
            });
        });
    }
});
