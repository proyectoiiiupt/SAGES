/**
 * @file pre_registration.js
 * @description Orquestador del lado del cliente (Frontend) para el pre-registro.
 * 
 * Se encarga de:
 *  - Navegación entre los diferentes pasos (paneles) del formulario.
 *  - Validación en vivo y aplicación de máscaras a los inputs (teléfono, cédula).
 *  - Consumo de la API REST (AJAX) para validaciones parciales y el envío final (submit).
 *  - Manejo dinámico de catálogos en cascada (estado -> municipio -> parroquia).
 *  - Gestión del modal de carga de evidencias y declaración jurada.
 */

/* global Swal, turnstile */
'use strict';

(function () {

    const API = {
        validatePlantel: '/pre-registration/validar-plantel',
        validateEmail: '/pre-registration/validar-correo',
        validateCedula: '/pre-registration/validar-cedula',
        municipalities: (stateId) => `/pre-registration/catalog/municipios/${stateId}`,
        parishes: (municipalityId) => `/pre-registration/catalog/parroquias/${municipalityId}`,
        complete: '/pre-registration/completar',
    };

    // ─────────────────────────────────────────────────────────────────
    // Diccionario de prefijos por código de tipo de institución
    // Fuente: documento de implementación (implementacion-pre-registro.docx)
    // INST-001 (Universidad) y INST-002 (Instituto Universitario) => solo acrónimo, sin prefijo
    // INST-005 (Centro de Formación) => sin prefijo ni acrónimo
    // ─────────────────────────────────────────────────────────────────
    const INSTITUTION_PREFIXES = {
        'INST-003': [
            'Liceo',
            'Liceo Nacional',
            'Liceo Bolivariano',
            'E.T.I. (Escuela Técnica Industrial)',
            'E.T.C. (Escuela Técnica Comercial)',
            'E.T.A. (Escuela Técnica Agropecuaria)',
            'U.E. (Unidad Educativa)',
            'U.E.N. (Unidad Educativa Nacional)',
            'U.E.E. (Unidad Educativa Estadal)',
            'U.E.M. (Unidad Educativa Municipal)',
            'U.E.P. (Unidad Educativa Privada)',
        ],
        'INST-004': [
            'Escuela Básica',
            'E.B.N. (Escuela Básica Nacional)',
            'E.B.E. (Escuela Básica Estadal)',
            'U.E.B. (Unidad Educativa Básica)',
            'U.E. (Unidad Educativa)',
            'U.E.N. (Unidad Educativa Nacional)',
            'U.E.E. (Unidad Educativa Estadal)',
            'U.E.M. (Unidad Educativa Municipal)',
            'U.E.P. (Unidad Educativa Privada)',
        ],
        'INST-006': [
            'Complejo Educativo',
            'U.E. (Unidad Educativa)',
            'U.E.C. (Unidad Educativa Colegio)',
            'U.E.P. (Unidad Educativa Privada)',
            'U.E.N. (Unidad Educativa Nacional)',
            'U.E.E. (Unidad Educativa Estadal)',
            'U.E.M. (Unidad Educativa Municipal)',
        ],
    };
    // Tipos que muestran solo acrónimo (sin prefijo)
    const ACRONYM_ONLY_TYPES = new Set(['INST-001', 'INST-002']);
    // Tipos que no muestran nada adicional
    const PLAIN_NAME_TYPES = new Set(['INST-005']);

    /**
     * Actualiza la visibilidad y opciones del select de prefijo y
     * el campo de acrónimo según el tipo de institución seleccionado.
     * @param {string} typeCode  - Código de negocio (ej. "INST-003")
     */
    function updateInstitutionFields(typeCode) {
        const selPrefix = qs('#sel-institution-prefix');
        const groupAcronym = qs('#group-institution-acronym');
        const inpAcronym = qs('#inp-institution-acronym');

        if (!selPrefix || !groupAcronym || !inpAcronym) return;

        const prefixes = INSTITUTION_PREFIXES[typeCode] || null;
        const showPrefix = prefixes !== null;
        const showAcronym = ACRONYM_ONLY_TYPES.has(typeCode);

        // — Prefijo —————————————————————————————————————————
        selPrefix.value = '';  // limpiar selección anterior
        if (showPrefix) {
            // Rellenar opciones
            selPrefix.innerHTML = '<option value="">Prefijo</option>';
            (prefixes || []).forEach(p => {
                const opt = document.createElement('option');
                // Extraer solo el acrónimo (todo antes de ' (') para el value
                const val = p.split(' (')[0];
                opt.value = val;
                opt.textContent = p;
                selPrefix.appendChild(opt);
            });
            selPrefix.style.display = '';
            selPrefix.tabIndex = 0;
        } else {
            selPrefix.style.display = 'none';
            selPrefix.tabIndex = -1;
            selPrefix.value = '';
        }

        // — Acrónimo ————————————————————————————————————————
        groupAcronym.style.display = showAcronym ? '' : 'none';
        if (!showAcronym && inpAcronym) inpAcronym.value = '';
    }

    // ─────────────────────────────────────────────────────────────────
    // Niveles Educativos por tipo de institución
    // ─────────────────────────────────────────────────────────────────
    const EDUCATIONAL_LEVELS_MAPPING = {
        'INST-001': ['EDUL-005', 'EDUL-006'], // Universidad
        'INST-002': ['EDUL-005'],             // Instituto Universitario
        'INST-003': ['EDUL-003', 'EDUL-004'], // Liceo
        'INST-004': ['EDUL-001', 'EDUL-002'], // Escuela
        'INST-006': ['EDUL-001', 'EDUL-002', 'EDUL-003', 'EDUL-004'], // Complejo
        'INST-005': []                        // Centro Formación (ninguno)
    };

    /**
     * Reconstruye los checkboxes de niveles educativos según el tipo.
     */
    function updateEducationalLevels(typeCode) {
        const groupLevels = qs('#group-educational-levels');
        const container = qs('#niveles-contenedor');
        if (!groupLevels || !container) return;

        const allowedCodes = EDUCATIONAL_LEVELS_MAPPING[typeCode] || [];

        container.innerHTML = ''; // Limpiar anteriores

        // Ocultar si no hay niveles o si es INST-002 (se auto-asigna)
        if (allowedCodes.length === 0 || typeCode === 'INST-002') {
            groupLevels.style.display = 'none';
            return;
        }

        groupLevels.style.display = '';

        // Filtrar del catálogo global (inyectado) solo los permitidos
        const levels = (CATALOGS.educational_levels || []).filter(l => allowedCodes.includes(l.id));

        levels.forEach(level => {
            const lbl = document.createElement('label');
            lbl.className = 'checkbox-item';

            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = level.id;
            chk.className = 'edu-level-chk';

            const txt = document.createElement('span');
            txt.textContent = level.name;

            lbl.appendChild(chk);
            lbl.appendChild(txt);
            container.appendChild(lbl);

            // Toggle de clase selected para estilos
            chk.addEventListener('change', () => {
                if (chk.checked) {
                    lbl.classList.add('selected');
                } else {
                    lbl.classList.remove('selected');
                }
            });
        });
    }

    // ─────────────────────────────────────────────────────────────
    // CSRF — Lectura del token desde el meta tag
    // ─────────────────────────────────────────────────────────────
    // Flask-WTF inyecta el token en <meta name="csrf-token"> al renderizar
    // el template. Lo capturamos UNA SOLA VEZ al iniciar el módulo para
    // no releer el DOM en cada request.
    // Si la meta no existe (página sin CSRF), csrfToken queda vacío y
    // los requests GET siguen funcionando sin problema.
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ?? '';

    // Almacena el código de plantel validado por el servidor en el Paso 0.
    // Se usa en el payload del submit final para garantizar que el código
    // que se envía coincide con el que fue verificado (y no fue modificado).
    let validatedPlantelCode = '';

    /**
     * Alias rápido para document.querySelector.
     * 
     * @param {string} selector - Selector CSS del elemento a buscar.
     * @returns {Element|null} El elemento encontrado o null.
     */
    const qs = (selector) => document.querySelector(selector);
    const qsa = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

    function setLoading(btn, isLoading) {
        if (!btn) return;
        btn.disabled = isLoading;
        isLoading
            ? btn.classList.add('btn-loading')
            : btn.classList.remove('btn-loading');
    }

    /**
     * Llena un elemento <select> HTML con datos provenientes del backend.
     * 
     * @param {HTMLSelectElement} selectEl - Elemento DOM del select.
     * @param {Array} items - Array de objetos con 'id' y 'name'.
     * @param {string} placeholder - Texto a mostrar por defecto (opcional).
     * @returns {void}
     */
    function populateSelect(selectEl, items, placeholder = 'Seleccione...') {
        selectEl.innerHTML = `<option value="" disabled selected>${placeholder}</option>`;
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.name;
            // Propagate extra fields as data-* attributes when present
            if (item.code !== undefined) opt.dataset.code = item.code;
            selectEl.appendChild(opt);
        });
        selectEl.disabled = items.length === 0;
    }

    function resetSelect(selectEl, placeholder = 'Seleccione...') {
        selectEl.innerHTML = `<option value="" disabled selected>${placeholder}</option>`;
        selectEl.disabled = true;
    }

    // ─────────────────────────────────────────────────────────────
    // Stepper
    // ─────────────────────────────────────────────────────────────
    const stepCircles = qsa('.stepper-step');
    const stepPanels = qsa('.step-panel');

    let _step2Interval = null;

    /**
     * Cambia la vista activa del formulario multi-paso.
     * Oculta el paso actual y muestra el paso indicado (0, 1 o 2).
     * 
     * @param {number} target - Índice del panel a mostrar (0-2).
     * @returns {void}
     */
    function goToStep(target) {
        if (_step2Interval) {
            clearInterval(_step2Interval);
            _step2Interval = null;
        }

        stepPanels.forEach((panel, i) => {
            panel.classList.toggle('step-panel-active', i === target);
        });

        stepCircles.forEach((step, i) => {
            step.classList.remove('step-active', 'step-done');
            if (i < target) step.classList.add('step-done');
            else if (i === target) step.classList.add('step-active');
        });

        const card = qs('.registro-card');
        if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function getSelectedEducationalLevels() {
        const typeId = qs('#sel-institution-type')?.value;
        if (typeId === 'INST-002') return ['EDUL-005'];
        return qsa('.edu-level-chk:checked').map(chk => chk.value);
    }

    // ─────────────────────────────────────────────────────────────
    // apiFetch — Wrapper centralizado de fetch
    // ─────────────────────────────────────────────────────────────
    async function apiFetch(url, options = {}) {
        const method = (options.method || 'GET').toUpperCase();
        const isMultipart = options._multipart === true;

        const headers = isMultipart
            ? { 'X-Requested-With': 'XMLHttpRequest' }
            : { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' };

        if (method === 'POST' || method === 'PUT' || method === 'PATCH' || method === 'DELETE') {
            headers['X-CSRFToken'] = csrfToken;
        }

        const { _multipart: _, ...fetchOptions } = options;
        const response = await fetch(url, {
            ...fetchOptions,
            headers: { ...headers, ...(options.headers || {}) },
        });
        const data = await response.json().catch(() => ({}));
        return { ok: response.ok, status: response.status, data };
    }


    // ─────────────────────────────────────────────────────────────
    // Formatter / Masks (Real-time)
    // ─────────────────────────────────────────────────────────────
    function initMasks() {
        const phoneInputs = qsa('.phone-mask');
        phoneInputs.forEach(input => {
            input.addEventListener('input', function (e) {
                // Remove everything except numbers
                let val = this.value.replace(/\D/g, '');
                if (val.length > 11) val = val.substring(0, 11);

                // Format: (0414)-1234567
                if (val.length > 4) {
                    val = `(${val.substring(0, 4)})-${val.substring(4)}`;
                } else if (val.length > 0) {
                    val = `(${val}`;
                }
                this.value = val;
            });
        });

        const cedulaInputs = qsa('.cedula-mask');
        cedulaInputs.forEach(input => {
            input.addEventListener('input', function (e) {
                let val = this.value.replace(/\D/g, '');
                if (val.length > 8) val = val.substring(0, 8);

                // Format: 12.345.678
                if (val.length > 0) {
                    val = parseInt(val, 10).toLocaleString('es-VE'); // Adds dots
                }
                this.value = val;
            });
        });

        // Formateo Automático de Nombres
        const nameInputs = qsa('#inp-first-name, #inp-second-name, #inp-last-name, #inp-middle-name');
        nameInputs.forEach(input => {
            input.addEventListener('input', function (e) {
                let val = this.value;
                val = val.replace(/[^a-zA-ZñÑáéíóúÁÉÍÓÚ\s]/g, '');
                if (val.length > 0) {
                    val = val.toLowerCase().replace(/(^|\s)\S/g, l => l.toUpperCase());
                }
                this.value = val;
            });
        });
    }

    // Utility to strip formatting for backend payload
    function stripFormatting(val) {
        if (!val) return '';
        return val.replace(/\D/g, '');
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 0 — Plantel code validation
    // ─────────────────────────────────────────────────────────────
    function initStep0() {
        const btn = qs('#btn-validate-plantel');
        const input = qs('#input-plantel-code');
        const wrapper = qs('#wrapper-plantel-code');
        const errorEl = qs('#error-plantel-code');

        if (!btn || !input) return;

        /**
         * Muestra visualmente un error debajo de un input específico.
         * 
         * @param {string} msg - Mensaje de error a mostrar.
         * @returns {void}
         */
        function showError(msg) {
            wrapper.classList.add('input-error');
            errorEl.textContent = msg;
            errorEl.classList.add('visible');
        }

        function clearError() {
            wrapper.classList.remove('input-error');
            errorEl.textContent = '';
            errorEl.classList.remove('visible');
        }

        // Auto clear error on type
        input.addEventListener('input', clearError);

        btn.addEventListener('click', async () => {
            const raw = input.value.trim();
            if (!raw) {
                showError('El código de plantel es obligatorio.');
                input.focus();
                return;
            }

            // Smart Loader: si el código ya fue validado y no ha cambiado, saltamos la validación
            if (raw === validatedPlantelCode && raw !== '') {
                clearError();
                // Si es Ruta B (ya existe), saltamos al Paso 2, si no al Paso 1
                if (window._joinExisting) {
                    goToStep(2);
                } else {
                    goToStep(1);
                }
                return;
            }

            clearError();
            setLoading(btn, true);

            try {
                const { ok, status, data } = await apiFetch(API.validatePlantel, {
                    method: 'POST',
                    body: JSON.stringify({ plantel_code: raw }),
                });

                if (ok) {
                    validatedPlantelCode = data.plantel_code || raw;
                    window._joinExisting = false; // Ruta A: nueva institución

                    // UX Improvement: No Modal. Change button state.
                    const originalHTML = btn.innerHTML;
                    btn.classList.add('btn-success');
                    btn.innerHTML = `
                        <span class="btn-text" style="display: flex; align-items: center; gap: 0.5rem;">
                            Validado 
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                        </span>
                    `;

                    // Load catalogs in background while showing success state
                    loadCatalogs();

                    // Delay for transition UX
                    setTimeout(() => {
                        btn.innerHTML = originalHTML; // restore for back nav
                        btn.classList.remove('btn-success');
                        setLoading(btn, false); // Fix: re-enable button
                        goToStep(1);
                    }, 800);

                } else if (status === 409) {
                    // Ruta B: el plantel ya existe, ofrecer unirse como nuevo representante
                    const result = await Swal.fire({
                        icon: 'info',
                        title: 'Institución registrada',
                        html:
                            '<p>El código de plantel <strong>' + raw + '</strong> ya se encuentra registrado en el sistema.</p>' +
                            '<p style="font-size:.875rem;color:#6b7280;margin-top:.5rem;">Si eres un nuevo representante y deseas solicitar acceso a esta institución, haz clic en <strong>"Solicitar Acceso"</strong>.</p>',
                        showCancelButton: true,
                        confirmButtonText: 'Solicitar Acceso',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#1fcab0',
                        cancelButtonColor: '#64748b',
                        customClass: { popup: 'swal2-custom-popup' }
                    });

                    if (result.isConfirmed) {
                        // Guardar el código de plantel existente y activar flag Ruta B
                        validatedPlantelCode = raw;
                        window._joinExisting = true;
                        if (data.institution) {
                            window._existingInstitution = data.institution;
                        }
                        // Cargar catálogos para asegurar que los selects del Paso 2 (ej. Cargo) se pueblen
                        loadCatalogs();
                        // Omitir Paso 1 (datos institucionales) — saltar directo al Paso 2
                        goToStep(2);
                    }
                } else {
                    showError(data.error || 'No se pudo validar el código. Intente nuevamente.');
                }
            } catch {
                showError('No pudimos conectar con el servidor. Verifique su conexión a internet y vuelva a intentarlo.');
            } finally {
                if (!btn.classList.contains('btn-success')) {
                    setLoading(btn, false);
                }
            }
        });

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') btn.click();
        });
    }

    // ─────────────────────────────────────────────────────────────
    // Catalog loading
    // ─────────────────────────────────────────────────────────────
    let catalogsLoaded = false;
    /**
     * Carga inicial de catálogos desde la variable global inyectada en el servidor.
     * 
     * @returns {Promise<void>}
     */
    async function loadCatalogs() {
        if (catalogsLoaded) return;

        const selType = qs('#sel-institution-type');
        const selScope = qs('#sel-institution-scope');
        const selDep = qs('#sel-institution-dependency');
        const selState = qs('#sel-state');
        const selPos = qs('#sel-position');

        try {
            // Utilizamos la variable global CATALOGS inyectada en el HTML
            // Esto elimina 5 peticiones AJAX, haciendo la carga instantánea.
            if (selType) populateSelect(selType, CATALOGS.institution_types || [], 'Seleccione tipo...');
            if (selScope) populateSelect(selScope, CATALOGS.institution_scopes || [], 'Seleccione alcance...');
            if (selDep) populateSelect(selDep, CATALOGS.institution_deps || [], 'Seleccione dependencia...');
            if (selState) populateSelect(selState, CATALOGS.states || [], 'Seleccione estado...');
            if (selPos) populateSelect(selPos, CATALOGS.positions || [], 'Seleccione cargo...');


            catalogsLoaded = true;
        } catch {
            console.error('No se pudieron cargar catálogos.');
        }
    }

    function initDynamicSelects() {
        const selState = qs('#sel-state');
        const selMunic = qs('#sel-municipality');
        const selParish = qs('#sel-parish');
        const selType = qs('#sel-institution-type');

        if (!selState || !selMunic || !selParish) return;

        // Listener de tipo de institución → actualiza prefijo / acrónimo / niveles
        if (selType) {
            selType.addEventListener('change', () => {
                const code = selType.value;   // ya es el código string (INST-00X)
                updateInstitutionFields(code);
                updateEducationalLevels(code);
            });
        }

        selState.addEventListener('change', async () => {
            const stateId = selState.value;
            resetSelect(selMunic, 'Cargando...');
            resetSelect(selParish);

            if (!stateId) return;

            try {
                const { ok, data } = await apiFetch(API.municipalities(stateId));
                populateSelect(selMunic, ok ? data : [], 'Seleccione municipio...');
            } catch {
                populateSelect(selMunic, [], 'Error al obtener los datos. Reintente.');
            }
        });

        selMunic.addEventListener('change', async () => {
            const municipalityId = selMunic.value;
            resetSelect(selParish, 'Cargando...');

            if (!municipalityId) return;

            try {
                const { ok, data } = await apiFetch(API.parishes(municipalityId));
                populateSelect(selParish, ok ? data : [], 'Seleccione parroquia...');
            } catch {
                populateSelect(selParish, [], 'Error al obtener los datos. Reintente.');
            }
        });
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 1 → STEP 2 navigation
    // ─────────────────────────────────────────────────────────────
    function initStep1Nav() {
        const btnNext = qs('#btn-next-step1');
        const btnBack = qs('#btn-back-step1');

        // Formateo Automático de Nombre de Institución (Allowlist, trim, Title Case)
        const inpInstitutionName = qs('#inp-institution-name');
        if (inpInstitutionName) {
            inpInstitutionName.addEventListener('input', function () {
                let val = this.value;
                // Permitir alfanuméricos, acentos, ñ, espacios, ., -, ', °
                val = val.replace(/[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-\'\"°]/g, '');
                // Evitar espacios múltiples consecutivos
                val = val.replace(/\s{2,}/g, ' ');
                // Title Case: Convertir a mayúscula primera letra (o después de espacio, punto, guion)
                val = val.toLowerCase().replace(/(?:^|[\s\.\-])[a-záéíóúñ]/g, function (match) {
                    return match.toUpperCase();
                });
                this.value = val;
            });
            inpInstitutionName.addEventListener('blur', function () {
                this.value = this.value.trim();
            });
        }

        if (btnNext) {
            btnNext.addEventListener('click', () => {
                // Validar los datos antes de avanzar en el orden progresivo visual:
                // Tipo, Alcance, Prefijo (si aplica), Nombre
                const reqFields = [
                    { id: '#sel-institution-type', msg: 'Seleccione un tipo de institución.' },
                    { id: '#sel-institution-scope', msg: 'Seleccione el alcance.' },
                    {
                        id: '#sel-institution-prefix',
                        msg: 'Seleccione el prefijo de la institución.',
                        condition: (el) => el.style.display !== 'none'
                    },
                    { id: '#inp-institution-name', msg: 'El nombre de la institución es requerido.' },
                    { id: '#sel-institution-dependency', msg: 'Seleccione la dependencia.' },
                    { id: '#sel-state', msg: 'Seleccione un estado.' },
                    { id: '#sel-municipality', msg: 'Seleccione un municipio.' },
                    { id: '#sel-parish', msg: 'Seleccione una parroquia.' },
                    { id: '#inp-address', msg: 'La dirección de la sede es requerida.' }
                ];

                let hasError = false;
                for (const field of reqFields) {
                    // Interceptar para validar niveles educativos justo antes de validar el estado
                    if (field.id === '#sel-state') {
                        const typeId = qs('#sel-institution-type')?.value;
                        // INST-005 (Centro de formación) no lleva niveles. INST-002 (Universitario) se autoasigna.
                        if (typeId && typeId !== 'INST-005' && typeId !== 'INST-002') {
                            const checkedLevels = qsa('.edu-level-chk:checked');
                            if (checkedLevels.length === 0) {
                                Swal.fire({
                                    icon: 'warning',
                                    title: 'Faltan datos',
                                    text: 'Debe seleccionar al menos un nivel educativo.',
                                    confirmButtonColor: '#1fcab0'
                                });
                                hasError = true;
                                break;
                            }
                        }
                    }

                    const el = qs(field.id);
                    if (field.condition && el && !field.condition(el)) {
                        continue; // Saltar si no cumple condición (ej. prefijo oculto)
                    }

                    if (el && !el.value.trim()) {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Faltan datos',
                            text: field.msg,
                            confirmButtonColor: '#1fcab0'
                        });
                        if (el.focus) el.focus();
                        hasError = true;
                        break;
                    }
                }

                if (!hasError) {
                    goToStep(2);
                }
            });
        }
        if (btnBack) btnBack.addEventListener('click', () => goToStep(0));
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 2 navigation + final submission
    // ─────────────────────────────────────────────────────────────
    function initStep2Nav() {
        const btnBack = qs('#btn-back-step2');
        const btnSubmit = qs('#btn-submit-registration');

        if (btnBack) {
            btnBack.addEventListener('click', () => {
                goToStep(window._joinExisting ? 0 : 1);
            });
        }
        if (!btnSubmit) return;

        // Tarea 2: Dynamic button state
        function updateSubmitButtonState() {
            const btnText = btnSubmit.querySelector('.btn-text');
            if (!btnText) return;

            const captchaToken = document.querySelector('[name="cf-turnstile-response"]')?.value;
            const hasVoucher = !!window._voucherFile;

            let text = (captchaToken && hasVoucher) ? "Aceptar" : "Validar";

            // Solo actualizar si el texto cambió, para evitar re-render innecesario
            if (!btnText.textContent.includes(text)) {
                btnText.innerHTML = `
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    ${text}
                `;
            }
        }
        // Ejecutar evento al resolver CAPTCHA
        document.querySelector('.cf-turnstile')?.addEventListener('cf-turnstile-callback', updateSubmitButtonState);
        window._updateSubmitBtnState = updateSubmitButtonState;
        updateSubmitButtonState(); // initial call

        btnSubmit.addEventListener('click', async () => {
            const idInput = qs('#inp-id-number');
            const idValRaw = idInput ? idInput.value : '';
            const idVal = stripFormatting(idValRaw);

            // 1. Cédula Validation
            if (!idVal) {
                Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'La cédula de identidad es requerida.', confirmButtonColor: '#1fcab0' });
                if (idInput) idInput.focus();
                return;
            }
            if (idVal.length < 7) {
                Swal.fire({ icon: 'warning', title: 'Datos inválidos', text: 'La cédula debe tener un mínimo de 7 caracteres.', confirmButtonColor: '#1fcab0' });
                if (idInput) idInput.focus();
                return;
            }

            setLoading(btnSubmit, true);
            try {
                const checkRes = await apiFetch(API.validateCedula, {
                    method: 'POST',
                    body: JSON.stringify({ identification_number: idVal })
                });
                if (checkRes.status === 409) {
                    Swal.fire({ icon: 'warning', title: 'Registro duplicado', text: checkRes.data.error || 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.', confirmButtonColor: '#1fcab0' });
                    if (idInput) idInput.focus();
                    setLoading(btnSubmit, false);
                    return;
                } else if (checkRes.status === 400) {
                    Swal.fire({ icon: 'error', title: 'Cédula Inválida', text: checkRes.data.error || 'La cédula tiene un formato inválido.', confirmButtonColor: '#1fcab0' });
                    if (idInput) idInput.focus();
                    setLoading(btnSubmit, false);
                    return;
                }
            } catch (e) {
                console.warn('[pre_registration] Red no disponible para validar correo; se verificará al enviar.', e);
            }
            setLoading(btnSubmit, false);

            // 2. Other Required Fields Validation (Follow form visual order: Position -> Name -> Last Name -> Mobile)
            const reqFields = [
                { id: '#sel-position', msg: 'Seleccione un cargo en la institución.' },
                { id: '#inp-first-name', msg: 'El primer nombre es requerido.' },
                { id: '#inp-last-name', msg: 'El primer apellido es requerido.' },
                { id: '#inp-mobile', msg: 'El teléfono principal es requerido.' }
            ];

            let hasError = false;
            for (const field of reqFields) {
                const el = qs(field.id);
                if (el && !el.value.trim()) {
                    Swal.fire({ icon: 'warning', title: 'Faltan datos', text: field.msg, confirmButtonColor: '#1fcab0' });
                    el.focus();
                    hasError = true;
                    break;
                }
            }
            if (hasError) return;

            // 3. Email Validation (Last field in the form)
            const emailInput = qs('#inp-email');
            const emailVal = emailInput ? emailInput.value.trim() : '';

            if (!emailVal) {
                Swal.fire({ icon: 'warning', title: 'Faltan datos', text: 'El correo electrónico es requerido.', confirmButtonColor: '#1fcab0' });
                if (emailInput) emailInput.focus();
                return;
            }

            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(emailVal)) {
                Swal.fire({ icon: 'warning', title: 'Datos inválidos', text: 'El correo electrónico tiene un formato inválido.', confirmButtonColor: '#1fcab0' });
                if (emailInput) emailInput.focus();
                return;
            }

            setLoading(btnSubmit, true);
            try {
                const checkRes = await apiFetch(API.validateEmail, {
                    method: 'POST',
                    body: JSON.stringify({ email: emailVal })
                });
                if (checkRes.status === 409) {
                    Swal.fire({ icon: 'warning', title: 'Correo Existente', text: checkRes.data.error || 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.', confirmButtonColor: '#1fcab0' });
                    if (emailInput) emailInput.focus();
                    setLoading(btnSubmit, false);
                    return;
                } else if (checkRes.status === 400) {
                    Swal.fire({ icon: 'error', title: 'Correo Inválido', text: checkRes.data.error || 'El correo tiene un formato inválido.', confirmButtonColor: '#1fcab0' });
                    if (emailInput) emailInput.focus();
                    setLoading(btnSubmit, false);
                    return;
                }
            } catch (e) {
                console.warn('[pre_registration] Red no disponible para validar cédula; se verificará al enviar.', e);
            }
            setLoading(btnSubmit, false);

            // ── Capturar el token del CAPTCHA generado por Turnstile ──────────────
            const captchaToken = document.querySelector('[name="cf-turnstile-response"]')?.value;

            // ── Validar que el comprobante fue adjuntado ──────────────────────
            if (!window._voucherFile) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Comprobante requerido',
                    html: '<p>Debe adjuntar un <strong>comprobante de vinculación institucional</strong> para continuar.</p>' +
                        '<p style="font-size:.85rem;color:#6b7280;margin-top:.5rem;">Desplácese hasta la sección "Comprobante de Vinculación" y suba su documento.</p>',
                    confirmButtonColor: '#1fcab0',
                    confirmButtonText: 'Entendido'
                });
                return;
            }

            // ── Validar CAPTCHA ──────────────────────────────────────────────────────
            if (!captchaToken) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Verificación requerida',
                    text: 'Por favor, complete el desafío de seguridad (CAPTCHA) antes de continuar.',
                    confirmButtonText: 'Aceptar',
                    confirmButtonColor: '#1fcab0',
                });
                return;
            }

            // ── Abrir la Declaración Jurada antes de enviar ───────────────────
            openSwornDeclarationModal();
        });
    }

    // ─────────────────────────────────────────────────────────────
    // Declaración Jurada — lógica del modal y envío real
    // ─────────────────────────────────────────────────────────────

    /**
     * Construye el payload final y lo envía al servidor para registrar la institución.
     * 
     * Engloba los datos institucionales, los personales, el token CAPTCHA y
     * el archivo de comprobante en un FormData (multipart/form-data).
     * 
     * @param {HTMLButtonElement} btnConfirm - Botón que disparó el evento.
     * @returns {Promise<void>}
     */
    async function _submitRegistration(btnConfirm) {
        const selectedLevels = getSelectedEducationalLevels();

        const institutionPayload = {
            plantel_code: validatedPlantelCode,
            institution_name: (qs('#inp-institution-name')?.value || '').trim(),
            institution_prefix: (qs('#sel-institution-prefix')?.value || '').trim(),
            institution_acronym: (qs('#inp-institution-acronym')?.value || '').trim(),
            institution_type_id: qs('#sel-institution-type')?.value || '',
            institution_scope_id: qs('#sel-institution-scope')?.value || '',
            institution_dependency_id: qs('#sel-institution-dependency')?.value || '',
            phone: stripFormatting(qs('#inp-institution-phone')?.value),
            parish_id: qs('#sel-parish')?.value || '',
            address: (qs('#inp-address')?.value || '').trim(),
            educational_levels: selectedLevels,
        };

        const personPayload = {
            identification_type: qs('#sel-id-type')?.value || '',
            identification_number: stripFormatting(qs('#inp-id-number')?.value),
            first_name: (qs('#inp-first-name')?.value || '').trim(),
            second_name: (qs('#inp-second-name')?.value || '').trim(),
            last_name: (qs('#inp-last-name')?.value || '').trim(),
            middle_name: (qs('#inp-middle-name')?.value || '').trim(),
            email: (qs('#inp-email')?.value || '').trim(),
            mobile: stripFormatting(qs('#inp-mobile')?.value),
            phone: stripFormatting(qs('#inp-person-phone')?.value),
            position_id: qs('#sel-position')?.value || '',
        };

        const captchaToken = document.querySelector('[name="cf-turnstile-response"]')?.value;

        setLoading(btnConfirm, true);
        try {
            const formData = new FormData();
            formData.append('payload', JSON.stringify({
                institution: institutionPayload,
                person: personPayload,
                captcha_token: captchaToken,
                join_existing: window._joinExisting === true,
                plantel_code_existing: validatedPlantelCode,
            }));
            formData.append('evidence', window._voucherFile);
            formData.append('document_type', window._voucherDocType || '');

            const { ok, status, data } = await apiFetch(API.complete, {
                method: 'POST',
                body: formData,
                _multipart: true,
            });

            if (ok) {
                document.getElementById('sworn-declaration-modal').style.display = 'none';
                document.body.style.overflow = '';

                await Swal.fire({
                    icon: 'success',
                    title: '¡Pre-registro Exitoso!',
                    html:
                        '<p>Su solicitud ha sido recibida. Verificaremos los datos de la institución y le notificaremos por correo electrónico.</p>',
                    confirmButtonText: 'Aceptar',
                    confirmButtonColor: '#1c3d73',
                    allowOutsideClick: false,
                    customClass: { popup: 'swal2-custom-popup', confirmButton: 'swal2-custom-button' }
                });
                window.location.href = '/';

            } else if (status === 400 && data.errors) {
                // Si el error fue por el CAPTCHA, lo reseteamos para que el usuario intente de nuevo sin recargar la página
                if (data.errors.some(e => e.includes('CAPTCHA')) && typeof turnstile !== 'undefined') {
                    turnstile.reset();
                }
                const errList = data.errors.map(e => `<li>${e}</li>`).join('');
                Swal.fire({
                    icon: 'error', title: 'Datos inválidos',
                    html: `<ul style="text-align:left;padding-left:1rem;margin:0;">${errList}</ul>`,
                    confirmButtonText: 'Revisar', confirmButtonColor: '#1fcab0',
                });
            } else if (status === 409) {
                Swal.fire({
                    icon: 'warning', title: 'Registro duplicado',
                    text: data.error || 'Algunos datos ya se encuentran registrados.',
                    confirmButtonText: 'Revisar', confirmButtonColor: '#1fcab0',
                });
            } else {
                Swal.fire({
                    icon: 'error', title: 'Error del servidor',
                    text: data.error || 'No se pudo completar el registro. Intente nuevamente.',
                    confirmButtonText: 'Cerrar', confirmButtonColor: '#1fcab0',
                });
            }
        } catch {
            Swal.fire({
                icon: 'error', title: 'Error de conexión',
                text: 'No se pudo contactar al servidor. Verifique su conexión e intente nuevamente.',
                confirmButtonText: 'Cerrar', confirmButtonColor: '#1fcab0',
            });
        } finally {
            setLoading(btnConfirm, false);
        }
    }

    /**
     * Rellena el modal de declaración jurada con los valores actuales del DOM
     * y lo muestra. No contacta al backend.
     */
    function openSwornDeclarationModal() {
        const modal = qs('#sworn-declaration-modal');
        if (!modal) return;

        // ── Datos del Solicitante ─────────────────────────────────────────
        const idType = qs('#sel-id-type')?.value || '';
        const idNumber = stripFormatting(qs('#inp-id-number')?.value || '');
        const fn = (qs('#inp-first-name')?.value || '').trim();
        const sn = (qs('#inp-second-name')?.value || '').trim();
        const ln = (qs('#inp-last-name')?.value || '').trim();
        const mn = (qs('#inp-middle-name')?.value || '').trim();
        const fullName = [fn, sn, ln, mn].filter(Boolean).join(' ');

        const positionEl = qs('#sel-position');
        const positionText = positionEl?.options[positionEl.selectedIndex]?.text || '—';

        qs('#swd-cedula').textContent = idType && idNumber ? `${idType}-${idNumber}` : '—';
        qs('#swd-nombre').textContent = fullName || '—';
        qs('#swd-email').textContent = (qs('#inp-email')?.value || '').trim() || '—';
        qs('#swd-mobile').textContent = (qs('#inp-mobile')?.value || '').trim() || '—';
        qs('#swd-cargo').textContent = positionText;

        // ── Datos de la Institución ───────────────────────────────────────
        const isJoinExisting = window._joinExisting === true;

        if (isJoinExisting) {
            const extInst = window._existingInstitution || {};
            qs('#swd-plantel').textContent = validatedPlantelCode || '—';
            qs('#swd-tipo').textContent = extInst.type || '(Institución existente)';
            qs('#swd-nombre-inst').textContent = extInst.name || '—';
            qs('#swd-dependencia').textContent = extInst.dependency || '—';
            qs('#swd-sector').textContent = extInst.scope || '—';
            qs('#swd-direccion').textContent = extInst.address || '—';
        } else {
            const tipoEl = qs('#sel-institution-type');
            const depEl = qs('#sel-institution-dependency');
            const scopeEl = qs('#sel-institution-scope');
            const stateEl = qs('#sel-state');
            const muniEl = qs('#sel-municipality');
            const parishEl = qs('#sel-parish');
            const getText = (sel) => sel?.options[sel.selectedIndex]?.text || '—';

            const prefix = (qs('#sel-institution-prefix')?.value || '').split('(')[0].trim();
            const rawName = (qs('#inp-institution-name')?.value || '').trim();
            const acronym = (qs('#inp-institution-acronym')?.value || '').trim();
            let instName = rawName;
            if (prefix) instName = `${prefix} ${rawName}`;
            if (acronym) instName += ` (${acronym})`;

            const state = getText(stateEl);
            const muni = getText(muniEl);
            const parish = getText(parishEl);
            const geoStr = [state, muni, parish].filter(t => t && t !== '—').join(' / ');
            const address = (qs('#inp-address')?.value || '').trim();
            const dirStr = [geoStr, address].filter(Boolean).join(' — ');

            qs('#swd-plantel').textContent = validatedPlantelCode || '—';
            qs('#swd-tipo').textContent = getText(tipoEl);
            qs('#swd-nombre-inst').textContent = instName || '—';
            qs('#swd-dependencia').textContent = getText(depEl);
            qs('#swd-sector').textContent = getText(scopeEl);
            qs('#swd-direccion').textContent = dirStr || '—';
        }

        // ── Resetear checkbox y botón ─────────────────────────────────────
        const chk = qs('#chk-sworn-accept');
        const btnConf = qs('#btn-confirm-sworn-modal');
        if (chk) chk.checked = false;

        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function initSwornDeclarationModal() {
        const modal = qs('#sworn-declaration-modal');
        if (!modal) return;

        const chk = qs('#chk-sworn-accept');
        const btnConf = qs('#btn-confirm-sworn-modal');
        const btnClose = qs('#btn-close-sworn-modal');
        const btnCancel = qs('#btn-cancel-sworn-modal');

        // Confirmar → envío real al backend
        if (btnConf) {
            btnConf.addEventListener('click', async () => {
                if (!chk?.checked) {
                    Swal.fire({
                        toast: true, position: 'top-end', icon: 'warning',
                        title: 'Debe aceptar la declaración jurada para finalizar el registro.',
                        showConfirmButton: false, timer: 3500, timerProgressBar: true
                    });
                    return;
                }
                await _submitRegistration(btnConf);
            });
        }

        // Cerrar modal (cancela, el formulario sigue intacto)
        const closeModal = () => {
            modal.style.display = 'none';
            document.body.style.overflow = '';
            if (chk) chk.checked = false;
        };
        if (btnClose) btnClose.addEventListener('click', closeModal);
        if (btnCancel) btnCancel.addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    }

    // ─────────────────────────────────────────────────────────────
    // Init
    // ─────────────────────────────────────────────────────────────
    function initBackButton() {
        const btnBackHome = qs('#btn-back-home');
        if (btnBackHome) {
            btnBackHome.addEventListener('click', async (e) => {
                e.preventDefault();
                const result = await Swal.fire({
                    title: '¿Estás seguro?',
                    text: "Si vuelves al inicio, perderás los datos no guardados del registro.",
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#1fcab0',
                    cancelButtonColor: '#e02424',
                    confirmButtonText: 'Sí, volver',
                    cancelButtonText: 'No, quedarse aquí'
                });

                if (result.isConfirmed) {
                    // Limpiar formularios o caché si fuera necesario
                    const forms = qsa('input, select, textarea');
                    forms.forEach(f => f.value = '');
                    window.location.href = '/';
                }
            });
        }
    }

    // ─────────────────────────────────────────────────────────────
    // Modal de subida de comprobante
    // ─────────────────────────────────────────────────────────────
    function initVoucherModal() {
        const modal = qs('#voucher-modal');
        const dropzone = qs('#dropzone');
        const fileInput = qs('#inp-evidence');
        const dzIdle = qs('#dz-idle');
        const dzPreview = qs('#dz-preview');
        const dzFileName = qs('#dz-file-name');
        const dzFileSize = qs('#dz-file-size');
        const btnClear = qs('#btn-dz-clear');
        const btnConfirm = qs('#btn-confirm-voucher');
        const btnOpen = qs('#btn-open-voucher-modal');
        const btnClose = qs('#btn-close-voucher-modal');
        const btnCancel = qs('#btn-cancel-voucher');
        const btnRemove = qs('#btn-remove-voucher');
        const voucherEmpty = qs('#voucher-empty');
        const voucherLoaded = qs('#voucher-loaded');
        const voucherNameEl = qs('#voucher-file-name');
        const voucherSizeEl = qs('#voucher-file-size');

        if (!modal) return;

        const ALLOWED_EXTS = ['pdf', 'jpg', 'jpeg', 'png'];
        const ALLOWED_MIME = ['application/pdf', 'image/jpeg', 'image/png'];
        const MAX_SIZE = 2 * 1024 * 1024; // 2MB

        function formatSize(bytes) {
            return bytes < 1024 * 1024
                ? `${(bytes / 1024).toFixed(1)} KB`
                : `${(bytes / 1024 / 1024).toFixed(2)} MB`;
        }

        function openModal() {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
        function closeModal() {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }

        function setDropzonePreview(file) {
            dzFileName.textContent = file.name;
            dzFileSize.textContent = formatSize(file.size);
            dzIdle.style.display = 'none';
            dzPreview.style.display = '';
        }

        function clearDropzone() {
            fileInput.value = '';
            dzIdle.style.display = '';
            dzPreview.style.display = 'none';
        }

        function validateFile(file) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (!ALLOWED_EXTS.includes(ext)) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'error',
                    title: 'Formato no permitido (solo PDF, JPG, PNG).',
                    showConfirmButton: false, timer: 3500, timerProgressBar: true
                });
                return false;
            }
            if (!ALLOWED_MIME.includes(file.type)) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'error',
                    title: 'El archivo no es un PDF, JPG o PNG válido.',
                    showConfirmButton: false, timer: 3500, timerProgressBar: true
                });
                return false;
            }
            if (file.size > MAX_SIZE) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'error',
                    title: `El archivo supera el límite de 2MB. Tamaño actual: ${formatSize(file.size)}`,
                    showConfirmButton: false, timer: 3500, timerProgressBar: true
                });
                return false;
            }
            return true;
        }

        // Handlers
        if (btnOpen) btnOpen.addEventListener('click', openModal);
        if (btnClose) btnClose.addEventListener('click', closeModal);
        if (btnCancel) btnCancel.addEventListener('click', closeModal);

        // Cerrar al hacer clic en el overlay
        modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

        // Clic en dropzone → abrir selector de archivo
        dropzone.addEventListener('click', (e) => {
            if (e.target === btnClear || btnClear?.contains(e.target)) return;
            fileInput.click();
        });

        // Teclado accesible en dropzone
        dropzone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

        // Cambio de archivo desde el input
        fileInput.addEventListener('change', () => {
            const file = fileInput.files[0];
            if (file && validateFile(file)) setDropzonePreview(file);
            else clearDropzone();
        });

        // Drag & drop
        ['dragenter', 'dragover'].forEach(ev => {
            dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add('drag-over'); });
        });
        ['dragleave', 'drop'].forEach(ev => {
            dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove('drag-over'); });
        });
        dropzone.addEventListener('drop', (e) => {
            const file = e.dataTransfer?.files[0];
            if (file && validateFile(file)) {
                setDropzonePreview(file);
                // Sincronizar el input real para que btnConfirm tenga el file
                const dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
            }
        });

        // Quitar archivo en dropzone
        if (btnClear) btnClear.addEventListener('click', (e) => { e.stopPropagation(); clearDropzone(); });

        // Confirmar archivo → actualizar tarjeta de la card
        if (btnConfirm) btnConfirm.addEventListener('click', () => {
            const file = fileInput.files[0];
            const selDocType = qs('#sel-document-type');

            if (selDocType && !selDocType.value) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'warning',
                    title: 'Debe seleccionar qué tipo de documento está adjuntando.',
                    showConfirmButton: false, timer: 3500, timerProgressBar: true
                });
                return;
            }

            if (!file) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'warning',
                    title: 'Debe seleccionar un archivo (constancia) para continuar.',
                    showConfirmButton: false, timer: 3500, timerProgressBar: true
                });
                return;
            }

            // Guardar en variable global para el submit
            window._voucherFile = file;
            window._voucherDocType = selDocType ? selDocType.value : '';
            if (window._updateSubmitBtnState) window._updateSubmitBtnState();

            voucherNameEl.textContent = file.name;
            voucherSizeEl.textContent = formatSize(file.size);
            voucherEmpty.style.display = 'none';
            voucherLoaded.style.display = '';

            closeModal();
        });

        // Quitar archivo desde la tarjeta
        if (btnRemove) btnRemove.addEventListener('click', () => {
            window._voucherFile = null;
            if (window._updateSubmitBtnState) window._updateSubmitBtnState();

            voucherEmpty.style.display = '';
            voucherLoaded.style.display = 'none';
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        goToStep(0);
        initStep0();
        initDynamicSelects();
        initMasks();
        initStep1Nav();
        initStep2Nav();
        initBackButton();
        initVoucherModal();
        initSwornDeclarationModal();
    });

})();