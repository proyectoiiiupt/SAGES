document.addEventListener('DOMContentLoaded', function () {
    // 1. Fecha dinámica en cabecera
    const dateEl = document.getElementById('current-wizard-date');
    if (dateEl) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateEl.textContent = formattedDate;
    }

    // 2. Elementos del Stepper
    const panel1 = document.getElementById('wizard-panel-1');
    const panel2 = document.getElementById('wizard-panel-2');
    const stepNav1 = document.getElementById('step-nav-1');
    const stepNav2 = document.getElementById('step-nav-2');

    const btnNext = document.getElementById('btn-next-step');
    const btnPrev = document.getElementById('btn-prev-step');
    const inputReportName = document.getElementById('report_name');

    // ── NAVEGACIÓN: PASO 1 -> PASO 2 ──
    if (btnNext) {
        btnNext.addEventListener('click', function () {
            const nameVal = inputReportName ? inputReportName.value.trim() : '';

            // Validación en cliente: Nombre obligatorio
            if (!nameVal || nameVal.length < 3) {
                Swal.fire({
                    title: 'Nombre requerido',
                    text: 'Debe ingresar un nombre descriptivo para el reporte (mínimo 3 caracteres).',
                    icon: 'warning',
                    confirmButtonColor: '#019577'
                }).then(() => {
                    if (inputReportName) inputReportName.focus();
                });
                return;
            }

            // Validación en cliente: Al menos una fuente de datos seleccionada
            const chkUser = document.getElementById('chk-include-user')?.checked;
            const chkReq = document.getElementById('chk-include-requests')?.checked;
            const chkMet = document.getElementById('chk-include-metrics')?.checked;

            if (!chkUser && !chkReq && !chkMet) {
                Swal.fire({
                    title: 'Fuentes de datos requeridas',
                    text: 'Debe seleccionar al menos una fuente de datos a incluir en el reporte.',
                    icon: 'warning',
                    confirmButtonColor: '#019577'
                });
                return;
            }

            // Transición visual al Paso 2
            panel1.style.display = 'none';
            panel1.classList.remove('active');

            panel2.style.display = 'block';
            panel2.classList.add('active');

            stepNav1.classList.remove('active');
            stepNav2.classList.add('active');
        });
    }

    // ── NAVEGACIÓN: PASO 2 -> PASO 1 ──
    if (btnPrev) {
        btnPrev.addEventListener('click', function () {
            panel2.style.display = 'none';
            panel2.classList.remove('active');

            panel1.style.display = 'block';
            panel1.classList.add('active');

            stepNav2.classList.remove('active');
            stepNav1.classList.add('active');
        });
    }

    // 3. Selección interactiva de Tarjetas de Formato (PDF, Excel, CSV)
    const formatCards = document.querySelectorAll('.format-card');
    formatCards.forEach(card => {
        card.addEventListener('click', function () {
            formatCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            const radio = this.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 4. Alternancia temporal en Barra Lateral (Mes vs Rango)
    const wRadioMonth = document.getElementById('w-radio-month');
    const wRadioRange = document.getElementById('w-radio-range');
    const wWrapMonth = document.getElementById('w-wrapper-month');
    const wWrapRange = document.getElementById('w-wrapper-range');

    if (wRadioMonth && wRadioRange) {
        wRadioMonth.addEventListener('change', function () {
            if (this.checked) {
                wWrapMonth.style.display = 'block';
                wWrapRange.style.display = 'none';
            }
        });
        wRadioRange.addEventListener('change', function () {
            if (this.checked) {
                wWrapMonth.style.display = 'none';
                wWrapRange.style.display = 'block';
            }
        });
    }

    // 5. Cascada territorial en Barra Lateral (si es Super Admin)
    const wState = document.getElementById('w-filter-state');
    const wMuni = document.getElementById('w-filter-municipality');
    const wParish = document.getElementById('w-filter-parish');

    if (wState && wMuni && wParish && wState.tagName === 'SELECT') {
        wState.addEventListener('change', function () {
            const stateId = this.value;
            wMuni.innerHTML = '<option value="">Todos los Municipios</option>';
            wParish.innerHTML = '<option value="">Todas las Parroquias</option>';
            wParish.disabled = true;

            if (!stateId) {
                wMuni.disabled = true;
                return;
            }

            fetch(`/analytics/api/geo/municipalities/${stateId}`)
                .then(r => r.json())
                .then(municipalities => {
                    municipalities.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.id;
                        opt.textContent = m.name;
                        wMuni.appendChild(opt);
                    });
                    wMuni.disabled = false;
                })
                .catch(err => console.error("Error al cargar municipios:", err));
        });

        wMuni.addEventListener('change', function () {
            const muniId = this.value;
            wParish.innerHTML = '<option value="">Todas las Parroquias</option>';

            if (!muniId) {
                wParish.disabled = true;
                return;
            }

            fetch(`/analytics/api/geo/parishes/${muniId}`)
                .then(r => r.json())
                .then(parishes => {
                    parishes.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p.id;
                        opt.textContent = p.name;
                        wParish.appendChild(opt);
                    });
                    wParish.disabled = false;
                })
                .catch(err => console.error("Error al cargar parroquias:", err));
        });
    }

    // 6. Preparación para el submit del botón [Generar Reporte] (conectado a la siguiente tarea)
    const btnSubmit = document.getElementById('btn-submit-wizard');
    if (btnSubmit) {
        btnSubmit.addEventListener('click', function () {
            // Se valida que la UI esté lista
            const formatSelected = document.querySelector('input[name="export_format"]:checked')?.value || 'pdf';
            const deliverySelected = document.querySelector('input[name="delivery_method"]:checked')?.value || 'local';
            
            // Notificación provisional de interfaz antes de conectar los motores de exportación
            console.log(`[WIZARD LISTO]: Formato: ${formatSelected} | Entrega: ${deliverySelected}`);
        });
    }
});
