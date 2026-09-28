document.addEventListener('DOMContentLoaded', function () {
    // =========================================================================
    // 0. Configuración Global y Limpieza (Mudanza del JS en línea de Fase 2)
    // =========================================================================
    const dateElement = document.getElementById('current-date-display');
    if (dateElement) {
        dateElement.setAttribute('data-utc', new Date().toISOString());
        if (typeof formatAllLocalTimes === 'function') {
            formatAllLocalTimes();
        }
    }

    // =========================================================================
    // 1. Elementos del DOM y Nodos de Interfaz
    // =========================================================================
    const moduleSelect = document.getElementById('module_select');
    const trainingSelect = document.getElementById('training_id');
    const descriptionInput = document.getElementById('description');
    const charCounter = document.getElementById('char-counter');
    const btnNext = document.getElementById('btn-next');
    const btnPrev = document.getElementById('btn-prev');
    const btnSubmit = document.getElementById('btn-submit');

    const panelStep1 = document.getElementById('panel-step-1');
    const panelStep2 = document.getElementById('panel-step-2');
    const step2Indicator = document.getElementById('indicator-step-2');
    const step1Indicator = document.getElementById('indicator-step-1');

    // =========================================================================
    // 2. Lógica Continua de Validación y Contador (Paso 1)
    // =========================================================================
    function validateStep1() {
        const descLength = descriptionInput.value.length;
        charCounter.textContent = `${descLength} / 200`;

        let isDescValid = descLength >= 10 && descLength <= 200;

        if (!isDescValid && descLength > 0) {
            charCounter.classList.add('invalid');
        } else {
            charCounter.classList.remove('invalid');
        }

        const isModuleSelected = moduleSelect.value !== "";
        const isTrainingSelected = trainingSelect.value !== "";

        // Habilita el botón Siguiente solo si todo es correcto
        btnNext.disabled = !(isModuleSelected && isTrainingSelected && isDescValid);
    }

    // Evita pasar de 200 caracteres de manera nativa y re-evalúa
    descriptionInput.addEventListener('input', () => {
        if (descriptionInput.value.length > 200) {
            descriptionInput.value = descriptionInput.value.substring(0, 200);
        }
        validateStep1();
    });

    // Re-evaluar cuando el usuario escoja un tema formativo final
    trainingSelect.addEventListener('change', validateStep1);

    // =========================================================================
    // 3. API Fetch en Cascada y Combo-box Dinámico (Autocomplete Select)
    // =========================================================================
    let currentTrainings = [];
    const trainingSearch = document.getElementById('training_search');
    const trainingOptionsList = document.getElementById('training-options-list');
    const comboboxWrapper = document.getElementById('training-combobox-wrapper');

    // Renderiza la lista flotante de opciones
    function renderComboboxOptions(trainingsList) {
        trainingOptionsList.innerHTML = '';
        if (trainingsList.length === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'combobox-option no-results';
            emptyDiv.textContent = 'No se encontraron coincidencias...';
            trainingOptionsList.appendChild(emptyDiv);
        } else {
            trainingsList.forEach(t => {
                const opt = document.createElement('div');
                opt.className = 'combobox-option';
                opt.textContent = t.name;
                opt.dataset.id = t.id;
                
                // Evento al seleccionar una opción
                opt.addEventListener('click', function(e) {
                    e.stopPropagation(); // Evita que se cierre inmediatamente el dropdown
                    
                    // Asigna el texto al input visible y el ID al select oculto
                    trainingSearch.value = this.textContent;
                    trainingSelect.value = this.dataset.id;
                    
                    // Dispara validación para habilitar el botón "Siguiente"
                    validateStep1();
                    
                    // Cierra el menú y quita la clase open
                    trainingOptionsList.classList.remove('show');
                    comboboxWrapper.classList.remove('open');
                });
                
                trainingOptionsList.appendChild(opt);
            });
        }
    }

    if (trainingSearch) {
        // Al escribir en la caja
        trainingSearch.addEventListener('input', function() {
            const term = this.value.toLowerCase().trim();
            
            // Si el usuario borra todo, limpiamos el select oculto
            if (term === '') {
                trainingSelect.value = '';
                validateStep1();
            }
            
            // Filtramos en memoria y renderizamos
            const filtered = term ? currentTrainings.filter(t => t.name.toLowerCase().includes(term)) : currentTrainings;
            renderComboboxOptions(filtered);
            
            // Nos aseguramos que el menú esté visible
            trainingOptionsList.classList.add('show');
            comboboxWrapper.classList.add('open');
        });
        
        // Al hacer clic en la caja
        trainingSearch.addEventListener('click', function(e) {
            if (!this.disabled && currentTrainings.length > 0) {
                // Si la caja ya tiene un valor válido, seleccionamos el texto para que pueda borrar rápido
                if (trainingSelect.value) {
                    this.select();
                }
                
                // Si el menú estaba oculto, renderizamos todo y lo mostramos
                if (!trainingOptionsList.classList.contains('show')) {
                    renderComboboxOptions(currentTrainings);
                    trainingOptionsList.classList.add('show');
                    comboboxWrapper.classList.add('open');
                } else {
                    trainingOptionsList.classList.remove('show');
                    comboboxWrapper.classList.remove('open');
                }
            }
        });
        
        // Evita cerrar al dar clic en la propia lista (ej: barra de scroll)
        trainingOptionsList.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }

    // Cerrar el combo-box al hacer clic en cualquier parte fuera de él
    document.addEventListener('click', function(e) {
        if (trainingSearch && trainingOptionsList) {
            if (e.target !== trainingSearch && !trainingOptionsList.contains(e.target)) {
                trainingOptionsList.classList.remove('show');
                comboboxWrapper.classList.remove('open');
                
                // Restauración anti-errores: Si escribió algo pero no eligió de la lista,
                // restauramos el texto del ID que actualmente tiene seleccionado, o lo limpiamos.
                if (trainingSelect.value) {
                    const selectedTraining = currentTrainings.find(t => t.id.toString() === trainingSelect.value.toString());
                    if (selectedTraining) {
                        trainingSearch.value = selectedTraining.name;
                    }
                } else {
                    trainingSearch.value = '';
                }
            }
        }
    });

    // Carga de Temas al Seleccionar un Módulo (API Fetch)
    moduleSelect.addEventListener('change', async function () {
        const moduleId = this.value;
        
        // Reset Visual
        trainingSearch.disabled = true;
        trainingSearch.value = '';
        trainingSearch.placeholder = 'Cargando temas...';
        trainingOptionsList.classList.remove('show');
        comboboxWrapper.classList.remove('open');
        
        // Reset Funcional
        trainingSelect.value = '';
        currentTrainings = [];
        validateStep1();

        if (!moduleId) return;

        try {
            const response = await fetch(`/training/api/modules/${moduleId}/trainings`);
            if (!response.ok) throw new Error('Error al conectar con el servidor.');

            currentTrainings = await response.json();

            if (currentTrainings.length === 0) {
                trainingSearch.placeholder = 'No hay temas activos en este módulo';
            } else {
                trainingSearch.placeholder = 'Buscar o seleccionar tema...';
                trainingSearch.disabled = false;
                trainingSelect.disabled = false;
                
                // Llenar el select oculto para que el navegador acepte el ID cuando hagamos click
                trainingSelect.innerHTML = '<option value="" selected disabled></option>';
                currentTrainings.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = t.name;
                    trainingSelect.appendChild(opt);
                });
            }
        } catch (error) {
            console.error('API Error:', error);
            trainingSearch.placeholder = 'Error de conexión. Intente luego.';
        }
    });

    // =========================================================================
    // 4. Motor de Navegación del Wizard y Pre-llenado (DOM manipulation)
    // =========================================================================
    btnNext.addEventListener('click', function () {
        // Pre-llenar la Tarjeta de Resumen con la información tipeada
        const selectedTrainingText = trainingSelect.options[trainingSelect.selectedIndex].text;
        document.getElementById('summary-training').textContent = selectedTrainingText;
        document.getElementById('summary-description').textContent = descriptionInput.value;

        // Transición visual: Esconder Paso 1, Mostrar Paso 2
        panelStep1.classList.remove('active');
        panelStep2.classList.add('active');

        // Pintar barra superior
        step1Indicator.classList.add('completed');
        step2Indicator.classList.add('active');
    });

    btnPrev.addEventListener('click', function () {
        // Transición visual reversa
        panelStep2.classList.remove('active');
        panelStep1.classList.add('active');

        // Deshacer progreso en barra superior
        step1Indicator.classList.remove('completed');
        step2Indicator.classList.remove('active');
    });

    // =========================================================================
    // 5. Motor de Inserción y SweetAlert2 (Cierre Transaccional)
    // =========================================================================
    btnSubmit.addEventListener('click', async function () {
        // Deshabilitar botón para evitar envíos dobles (Double-submit)
        btnSubmit.disabled = true;
        const originalText = btnSubmit.innerHTML;
        btnSubmit.innerHTML = 'Procesando validaciones...';

        // Capturar Token de Seguridad Inyectado por WTForms
        const csrfTokenInput = document.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

        // Estructurar el cuerpo de la petición como lo exige Flask backend
        const payload = {
            training_id: parseInt(trainingSelect.value, 10),
            description: descriptionInput.value.trim()
        };

        try {
            const response = await fetch('/requests/submit-new', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken // Seguridad Anti-CSRF
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Alerta nativa corporativa SAGES
                Swal.fire({
                    icon: 'success',
                    title: '¡Solicitud Registrada con Éxito!',
                    text: data.message || 'La solicitud ha sido cursada exitosamente.',
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Continuar al Panel',
                    allowOutsideClick: false,
                    allowEscapeKey: false
                }).then(() => {
                    // Redirección exigida por los Criterios de Aceptación
                    window.location.href = '/requests/my-requests';
                });
            } else {
                // Si el backend aborta (Anti-duplicidad o validación)
                Swal.fire({
                    icon: 'error',
                    title: 'Acción Denegada',
                    text: data.message || 'Se rechazó la solicitud por integridad de datos.',
                    confirmButtonColor: '#d33'
                });
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = originalText;
            }
        } catch (error) {
            console.error('Servidor inaccesible:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error de Comunicación',
                text: 'Hubo un problema de conexión con el servidor. Por favor, verifique su internet o intente más tarde.',
                confirmButtonColor: '#d33'
            });
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = originalText;
        }
    });

    // =========================================================================
    // 6. Prevención de Pérdida de Datos (Cancelación Segura)
    // =========================================================================
    const btnCancelWizard = document.getElementById('btn-cancel-wizard');
    if (btnCancelWizard) {
        btnCancelWizard.addEventListener('click', function(e) {
            e.preventDefault(); // Detener la navegación inmediata
            const targetUrl = this.href;
            
            Swal.fire({
                title: '¿Desea cancelar el registro?',
                text: "Se perderán todos los datos ingresados y no se registrará la solicitud.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#1c3d73',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, cancelar',
                cancelButtonText: 'No, continuar'
            }).then((result) => {
                if (result.isConfirmed) {
                    window.location.href = targetUrl; // Redirigir si confirma
                }
            });
        });
    }
});
