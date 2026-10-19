/**
 * SAGES - Módulo de Configuraciones Globales
 * Tarea: US-53-settings-ui-prototype
 * Lógica del lado del cliente: alternancia de pestañas agrupadas,
 * apertura/cierre de modal de permisos y simulación interactiva con SweetAlert2.
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================================
    // 1. FECHA ACTUAL DINÁMICA
    // =========================================================================
    const dateElement = document.getElementById('config-date-text');
    if (dateElement) {
        const today = new Date();
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateElement.textContent = formattedDate.replace(' de 20', ', 20');
    }

    // =========================================================================
    // 2. CONMUTADOR DE PESTAÑAS (TABS)
    // =========================================================================
    const tabButtons = Array.from(document.querySelectorAll('.config-tab-btn'));
    const tabPanels = Array.from(document.querySelectorAll('.config-tab-content'));

    const switchTab = (tabId, updateHash = true) => {
        const targetBtn = tabButtons.find(btn => btn.dataset.tab === tabId);
        const targetPanel = document.getElementById(`tab-${tabId}`);

        if (!targetBtn || !targetPanel) return;

        // Remover estado activo
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabPanels.forEach(panel => panel.classList.remove('active'));

        // Activar seleccionados
        targetBtn.classList.add('active');
        targetPanel.classList.add('active');

        // Sincronizar URL hash sin salto de scroll
        if (updateHash) {
            history.replaceState(null, '', `#${tabId}`);
        }
    };

    tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = btn.dataset.tab;
            if (tabId) {
                switchTab(tabId, true);
            }
        });
    });

    // Leer hash inicial al cargar
    const initialHash = window.location.hash.replace('#', '').trim();
    if (initialHash && document.getElementById(`tab-${initialHash}`)) {
        switchTab(initialHash, false);
    }

    // Soporte para botones Atrás/Adelante del navegador
    window.addEventListener('popstate', () => {
        const currentHash = window.location.hash.replace('#', '').trim();
        if (currentHash && document.getElementById(`tab-${currentHash}`)) {
            switchTab(currentHash, false);
        } else {
            switchTab('roles', false);
        }
    });

    // =========================================================================
    // 3. APERTURA Y CIERRE DEL MODAL DE PERMISOS (#modal-permissions)
    // =========================================================================
    const modalPermissions = document.getElementById('modal-permissions');
    const modalTitle = document.getElementById('modal-role-title');
    const btnCloseModalX = document.getElementById('btn-close-modal-x');
    const btnCancelModal = document.getElementById('btn-cancel-modal');
    const btnSavePermissions = document.getElementById('btn-save-permissions');

    const openModal = (roleName, roleCode) => {
        if (!modalPermissions) return;

        if (modalTitle) {
            modalTitle.textContent = `Matriz de Permisos — ${roleName}`;
        }

        // Configuración condicional según rol (Regla Anti-Lockout para super_admin)
        const isSuperAdmin = roleCode === 'super_admin';
        
        // Elementos que deben estar bloqueados para super_admin
        const protectedCheckboxes = [
            'chk-admin-panel',
            'chk-manage-users',
            'chk-sys-config'
        ];

        protectedCheckboxes.forEach(id => {
            const chk = document.getElementById(id);
            if (chk) {
                chk.disabled = isSuperAdmin;
                if (isSuperAdmin) chk.checked = true;
            }
        });

        // Mostrar modal
        modalPermissions.style.display = 'flex';
    };

    const closeModal = () => {
        if (modalPermissions) {
            modalPermissions.style.display = 'none';
        }
    };

    // Botones "Gestionar" en la tabla de roles — sin acción (prototipo UI)
    const manageButtons = document.querySelectorAll('.btn-manage-role');
    manageButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            // Sin acción en esta fase del prototipo
        });
    });

    // Cierre del modal
    if (btnCloseModalX) btnCloseModalX.addEventListener('click', closeModal);
    if (btnCancelModal) btnCancelModal.addEventListener('click', closeModal);

    // Cierre al hacer clic fuera de la tarjeta modal
    if (modalPermissions) {
        modalPermissions.addEventListener('click', (e) => {
            if (e.target === modalPermissions) {
                closeModal();
            }
        });
    }

    // =========================================================================
    // 4. SIMULACIONES INTERACTIVAS CON SWEETALERT2
    // =========================================================================

    // A) Guardar Privilegios en el Modal
    if (btnSavePermissions) {
        btnSavePermissions.addEventListener('click', () => {
            closeModal();
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'Privilegios actualizados',
                    text: 'La matriz de permisos ha sido guardada satisfactoriamente (Modo Demostración).',
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Entendido'
                });
            }
        });
    }

    // B) Guardar Cambios en Datos Corporativos
    const btnSaveCorporate = document.getElementById('btn-save-corporate');
    if (btnSaveCorporate) {
        btnSaveCorporate.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'Configuración guardada',
                    text: 'Los datos corporativos han sido actualizados satisfactoriamente (Modo Demostración).',
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Aceptar'
                });
            }
        });
    }

    // C) Definir Programación de Respaldo Automático
    const triggerScheduleModal = () => {
        if (typeof Swal === 'undefined') return;

        Swal.fire({
            title: 'Definir Respaldo Automático',
            html: `
                <div style="text-align: left; font-size: 0.95rem; color: #334155; display: flex; flex-direction: column; gap: 14px;">
                    <p style="margin: 0; color: #64748b; font-size: 0.88rem;">
                        Configura la periodicidad y hora del respaldo automático en segundo plano para no saturar los recursos del sistema con copias diarias.
                    </p>
                    <div>
                        <label style="display: block; font-weight: 700; margin-bottom: 5px; color: #1e293b;">Periodicidad:</label>
                        <select id="swal-freq-select" class="swal2-input" style="margin: 0; width: 100%; font-size: 0.95rem; height: 42px;">
                            <option value="none">Ninguno</option>
                            <option value="daily">Diario</option>
                            <option value="weekly" selected>Semanal (Recomendado)</option>
                            <option value="monthly">Mensual (Fin de Mes)</option>
                        </select>
                    </div>
                    <div id="swal-day-container">
                        <label style="display: block; font-weight: 700; margin-bottom: 5px; color: #1e293b;">Día de Ejecución:</label>
                        <select id="swal-day-select" class="swal2-input" style="margin: 0; width: 100%; font-size: 0.95rem; height: 42px;">
                            <option value="Domingos" selected>Domingo (Horario no laboral)</option>
                            <option value="Sábados">Sábado</option>
                            <option value="Viernes">Viernes</option>
                            <option value="Lunes">Lunes</option>
                        </select>
                    </div>
                    <div id="swal-time-container">
                        <label style="display: block; font-weight: 700; margin-bottom: 5px; color: #1e293b;">Hora de Ejecución (Caracas):</label>
                        <input type="time" id="swal-time-input" class="swal2-input" value="23:00" style="margin: 0; width: 100%; font-size: 0.95rem; height: 42px;">
                    </div>
                </div>
            `,
            showCancelButton: true,
            confirmButtonColor: '#019577',
            cancelButtonColor: '#94a3b8',
            confirmButtonText: 'Guardar Programación',
            cancelButtonText: 'Cancelar',
            didOpen: () => {
                const freqSelect = document.getElementById('swal-freq-select');
                const dayContainer = document.getElementById('swal-day-container');
                const timeContainer = document.getElementById('swal-time-container');

                const updateVisibility = () => {
                    const val = freqSelect.value;
                    if (dayContainer) {
                        dayContainer.style.display = val === 'weekly' ? 'block' : 'none';
                    }
                    if (timeContainer) {
                        timeContainer.style.display = val === 'none' ? 'none' : 'block';
                    }
                };

                if (freqSelect) {
                    freqSelect.addEventListener('change', updateVisibility);
                    updateVisibility();
                }
            },
            preConfirm: () => {
                const freq = document.getElementById('swal-freq-select').value;
                const day = document.getElementById('swal-day-select').value;
                const time = document.getElementById('swal-time-input').value || '23:00';
                return { freq, day, time };
            }
        }).then((result) => {
            if (result.isConfirmed && result.value) {
                const { freq, day, time } = result.value;
                const kpiFreq = document.getElementById('kpi-schedule-freq');
                const kpiNext = document.getElementById('kpi-schedule-next');

                let freqText = 'Semanal (Domingos)';
                let nextText = `Próxima ejecución: Domingo ${time}`;
                let alertMessage = '';

                if (freq === 'none') {
                    freqText = 'Ninguno';
                    nextText = 'Próxima ejecución: Sin programar';
                    alertMessage = 'El respaldo automático ha sido desactivado (Modo Demostración — Cero persistencia en BD).';
                } else if (freq === 'daily') {
                    freqText = 'Diario';
                    nextText = `Próxima ejecución: Todos los días a las ${time}`;
                    alertMessage = `El respaldo automático se ha configurado de forma diaria a las ${time} hrs (Modo Demostración — Cero persistencia en BD).`;
                } else if (freq === 'weekly') {
                    freqText = `Semanal (${day})`;
                    nextText = `Próxima ejecución: Próximo ${day.slice(0, -1)} ${time}`;
                    alertMessage = `El respaldo automático se ha configurado de forma semanal los ${day} a las ${time} hrs (Modo Demostración — Cero persistencia en BD).`;
                } else if (freq === 'monthly') {
                    freqText = 'Mensual (Fin de Mes)';
                    nextText = `Próxima ejecución: Fin de mes a las ${time}`;
                    alertMessage = `El respaldo automático se ha configurado de forma mensual (fin de mes) a las ${time} hrs (Modo Demostración — Cero persistencia en BD).`;
                }

                if (kpiFreq) kpiFreq.textContent = freqText;
                if (kpiNext) kpiNext.textContent = nextText;

                Swal.fire({
                    icon: 'success',
                    title: 'Programación Registrada (Prototipo)',
                    text: alertMessage,
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Entendido'
                });
            }
        });
    };

    const btnScheduleBackup = document.getElementById('btn-schedule-backup');
    if (btnScheduleBackup) {
        btnScheduleBackup.addEventListener('click', triggerScheduleModal);
    }

    const btnConfigScheduleKpi = document.getElementById('btn-config-schedule-kpi');
    if (btnConfigScheduleKpi) {
        btnConfigScheduleKpi.addEventListener('click', triggerScheduleModal);
    }

    // D) Descargar SQL Actual (Respaldos)
    const btnDownloadSql = document.getElementById('btn-download-sql');
    if (btnDownloadSql) {
        btnDownloadSql.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'info',
                    title: 'Generando Respaldo',
                    text: 'Se ha iniciado la descarga del volcado completo backup_sages_20260929.sql (Modo Demostración).',
                    confirmButtonColor: '#1c3d73',
                    confirmButtonText: 'Descargar'
                });
            }
        });
    }

    // D) Restaurar Respaldo Antiguo
    const btnRestoreBackup = document.getElementById('btn-restore-backup');
    if (btnRestoreBackup) {
        btnRestoreBackup.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Restauración por Consola',
                    html: `
                        <p style="font-size: 0.92rem; color: #475569; margin-bottom: 12px; text-align: left;">
                            Por políticas estrictas de seguridad e integridad de la base de datos, la restauración de volcados SQL no se ejecuta vía HTTP. Debe ejecutarse directamente en el servidor mediante el cliente oficial de PostgreSQL:
                        </p>
                        <div style="background: #f1f5f9; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; color: #0f172a; text-align: left; border: 1px solid #cbd5e1;">
                            psql -U postgres -d sages &lt; backup_sages.sql
                        </div>
                    `,
                    confirmButtonColor: '#d97706',
                    confirmButtonText: 'Entendido'
                });
            }
        });
    }

    // =========================================================================
    // E) CONTROL DE SEDES — US-56-places-management
    //    Cascada geográfica, modal unificado, AJAX CRUD, toggle de estatus
    // =========================================================================

    // ── Helpers de cascada geográfica ──────────────────────────────────────

    /**
     * Reemplaza las opciones de un <select> con un array [{id, name}].
     * @param {HTMLSelectElement} selectEl - El selector objetivo.
     * @param {Array}             items    - Datos [{id, name}].
     * @param {string}            placeholder - Texto de la opción vacía.
     */
    function fillSelect(selectEl, items, placeholder) {
        selectEl.innerHTML = `<option value="">${placeholder}</option>`;
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value       = item.id;
            opt.textContent = item.name;
            selectEl.appendChild(opt);
        });
    }

    /**
     * Carga municipios desde la API y llena el selector.
     * Si se provee selectedMunicipalityId, preselecciona y carga parroquias.
     */
    async function loadMunicipalities(stateId, selectedMunicipalityId = null, selectedParishId = null) {
        const munSel    = document.getElementById('place_municipality');
        const parishSel = document.getElementById('place_parish');
        if (!munSel || !parishSel) return;

        munSel.disabled    = true;
        parishSel.disabled = true;
        fillSelect(parishSel, [], '— Seleccione Parroquia —');

        if (!stateId) {
            fillSelect(munSel, [], '— Seleccione Municipio —');
            return;
        }

        try {
            const resp = await fetch(`/configurations/api/municipalities/${stateId}`);
            if (!resp.ok) throw new Error('Error al cargar municipios');
            const data = await resp.json();
            fillSelect(munSel, data, '— Seleccione Municipio —');
            munSel.disabled = false;

            if (selectedMunicipalityId) {
                munSel.value = selectedMunicipalityId;
                await loadParishes(selectedMunicipalityId, selectedParishId);
            }
        } catch (err) {
            console.error('[US-56] loadMunicipalities:', err);
            fillSelect(munSel, [], '— Error cargando municipios —');
        }
    }

    /**
     * Carga parroquias desde la API y llena el selector.
     * Si se provee selectedParishId, preselecciona la opción.
     */
    async function loadParishes(municipalityId, selectedParishId = null) {
        const parishSel = document.getElementById('place_parish');
        if (!parishSel) return;

        parishSel.disabled = true;

        if (!municipalityId) {
            fillSelect(parishSel, [], '— Seleccione Parroquia —');
            return;
        }

        try {
            const resp = await fetch(`/configurations/api/parishes/${municipalityId}`);
            if (!resp.ok) throw new Error('Error al cargar parroquias');
            const data = await resp.json();
            fillSelect(parishSel, data, '— Seleccione Parroquia —');
            parishSel.disabled = false;

            if (selectedParishId) {
                parishSel.value = selectedParishId;
            }
        } catch (err) {
            console.error('[US-56] loadParishes:', err);
            fillSelect(parishSel, [], '— Error cargando parroquias —');
        }
    }

    // ── Listeners de cascada ────────────────────────────────────────────────

    const placeStateSelect = document.getElementById('place_state');
    const placeMunSel      = document.getElementById('place_municipality');

    if (placeStateSelect) {
        placeStateSelect.addEventListener('change', function () {
            loadMunicipalities(this.value);
        });
    }

    if (placeMunSel) {
        placeMunSel.addEventListener('change', function () {
            loadParishes(this.value);
        });
    }

    // ── Modal de sedes (abrir / cerrar) ────────────────────────────────────

    const modalPlace       = document.getElementById('modal-place');
    const modalPlaceTitle  = document.getElementById('modal-place-title');
    const placeIdHidden    = document.getElementById('place-id-hidden');
    const formPlace        = document.getElementById('form-place');
    const btnSavePlaceText = document.getElementById('btn-save-place-text');

    function openPlaceModal() {
        if (modalPlace) modalPlace.style.display = 'flex';
    }

    function closePlaceModal() {
        if (modalPlace) modalPlace.style.display = 'none';
    }

    // Cerrar con X y botón Cancelar
    const btnClosePlaceX  = document.getElementById('btn-close-place-modal-x');
    const btnCancelPlace  = document.getElementById('btn-cancel-place-modal');
    if (btnClosePlaceX) btnClosePlaceX.addEventListener('click', closePlaceModal);
    if (btnCancelPlace) btnCancelPlace.addEventListener('click', closePlaceModal);

    // Cerrar al hacer clic fuera del card
    if (modalPlace) {
        modalPlace.addEventListener('click', e => {
            if (e.target === modalPlace) closePlaceModal();
        });
    }

    // ── Abrir en modo CREACIÓN ──────────────────────────────────────────────

    const btnNewPlace = document.getElementById('btn-new-place');
    if (btnNewPlace) {
        btnNewPlace.addEventListener('click', () => {
            if (modalPlaceTitle)  modalPlaceTitle.textContent = 'Registrar Nueva Sede';
            if (btnSavePlaceText) btnSavePlaceText.textContent = 'Guardar Sede';
            if (placeIdHidden)    placeIdHidden.value = '';
            if (formPlace)        formPlace.reset();

            // Resetear cascada
            const munSel    = document.getElementById('place_municipality');
            const parishSel = document.getElementById('place_parish');
            if (munSel)    { fillSelect(munSel,    [], '— Seleccione Municipio —'); munSel.disabled    = true; }
            if (parishSel) { fillSelect(parishSel, [], '— Seleccione Parroquia —'); parishSel.disabled = true; }

            openPlaceModal();
        });
    }

    // ── Abrir en modo EDICIÓN (delegado en document) ────────────────────────

    document.addEventListener('click', async e => {
        const btn = e.target.closest('.btn-edit-place');
        if (!btn) return;

        const d = btn.dataset;

        if (modalPlaceTitle)  modalPlaceTitle.textContent = `Editar Sede: ${d.name}`;
        if (btnSavePlaceText) btnSavePlaceText.textContent = 'Guardar Cambios';
        if (placeIdHidden)    placeIdHidden.value = d.id;

        // Rellenar campos simples
        const nameInput    = document.getElementById('place_name');
        const phoneInput   = document.getElementById('place_phone');
        const addressInput = document.getElementById('place_address');
        const stateSelect  = document.getElementById('place_state');

        if (nameInput)    nameInput.value    = d.name    || '';
        if (phoneInput)   phoneInput.value   = d.phone   || '';
        if (addressInput) addressInput.value = d.address || '';
        if (stateSelect)  stateSelect.value  = d.stateId || '';

        // Cargar la cascada con preselección
        await loadMunicipalities(d.stateId, d.municipalityId, d.parishId);

        openPlaceModal();
    });

    // ── Guardado AJAX (Crear o Editar) ──────────────────────────────────────

    const btnSavePlace = document.getElementById('btn-save-place');
    if (btnSavePlace) {
        btnSavePlace.addEventListener('click', async () => {
            if (!formPlace) return;

            const placeId = placeIdHidden ? placeIdHidden.value : '';
            const url     = placeId
                ? `/configurations/places/${placeId}/edit`
                : '/configurations/places/new';

            // Deshabilitar botón durante la petición
            btnSavePlace.disabled = true;
            if (btnSavePlaceText) btnSavePlaceText.textContent = 'Guardando...';

            try {
                const formData = new FormData(formPlace);

                const resp = await fetch(url, {
                    method: 'POST',
                    body  : formData
                });

                const result = await resp.json();

                if (result.success) {
                    closePlaceModal();
                    Swal.fire({
                        icon             : 'success',
                        title            : placeId ? 'Sede Actualizada' : 'Sede Registrada',
                        text             : result.message,
                        confirmButtonColor: '#019577',
                        confirmButtonText : 'Aceptar'
                    }).then(() => {
                        if (window.location.hash !== '#places') {
                            window.location.hash = '#places';
                        }
                        window.location.reload();
                    });

                } else {
                    // Mostrar errores de validación
                    let errorMsg = 'Revise los campos del formulario.';
                    if (result.errors) {
                        const msgs = Object.values(result.errors).flat();
                        errorMsg   = msgs.join(' ');
                    } else if (result.message) {
                        errorMsg = result.message;
                    }
                    Swal.fire({
                        icon             : 'warning',
                        title            : 'Error de Validación',
                        text             : errorMsg,
                        confirmButtonColor: '#d97706',
                        confirmButtonText : 'Corregir'
                    });
                }
            } catch (err) {
                console.error('[US-56] btnSavePlace fetch error:', err);
                Swal.fire({
                    icon : 'error',
                    title: 'Error de Red',
                    text : 'No fue posible comunicarse con el servidor. Intente nuevamente.'
                });
            } finally {
                btnSavePlace.disabled = false;
                if (btnSavePlaceText) {
                    btnSavePlaceText.textContent = placeId ? 'Guardar Cambios' : 'Guardar Sede';
                }
            }
        });
    }

    // ── Toggle de Estatus con SweetAlert2 + manejo HTTP 409 ────────────────

    document.addEventListener('click', async e => {
        const btn = e.target.closest('.btn-toggle-place');
        if (!btn) return;

        const placeId     = btn.dataset.id;
        const placeName   = btn.dataset.name;
        const currentStat = btn.dataset.currentStatus;
        const isActive    = currentStat === 'STAT-001';
        const action      = isActive ? 'inactivar' : 'activar';

        // Confirmación previa con SweetAlert2
        const confirm = await Swal.fire({
            icon            : 'question',
            title           : '¿Confirmar cambio de estatus?',
            html            : `¿Desea <strong>${action}</strong> la sede<br><strong>"${placeName}"</strong>?`,
            showCancelButton: true,
            confirmButtonColor: isActive ? '#d97706' : '#019577',
            cancelButtonColor : '#94a3b8',
            confirmButtonText : `Sí, ${action}`,
            cancelButtonText  : 'Cancelar'
        });

        if (!confirm.isConfirmed) return;

        // Obtener CSRF token del formulario del modal de sedes
        const csrfToken = formPlace
            ? (formPlace.querySelector('input[name="csrf_token"]') || {}).value
            : null;

        try {
            const resp = await fetch(`/configurations/places/${placeId}/toggle-status`, {
                method : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
                },
                body: JSON.stringify({})
            });

            // ── HTTP 409: bloqueo por personal adscrito activo ────────────
            if (resp.status === 409) {
                const result = await resp.json();
                Swal.fire({
                    icon             : 'warning',
                    title            : 'Acción Denegada — Integridad Referencial',
                    html             : `
                        <p style="text-align:left; margin-bottom:10px;">${result.message}</p>
                        <div style="background:#fef3c7; border:1px solid #fbbf24; border-radius:6px;
                                    padding:10px 14px; text-align:left; font-size:0.88rem; color:#92400e;">
                            <strong>Personal activo adscrito:</strong> ${result.staff_count} funcionario${result.staff_count !== 1 ? 's' : ''}
                        </div>
                        <p style="margin-top:10px; font-size:0.84rem; color:#94a3b8; text-align:left;">
                            Reasigne o inactive al personal antes de inactivar esta sede.
                        </p>`,
                    confirmButtonColor: '#d97706',
                    confirmButtonText : 'Entendido'
                });
                return;
            }

            const result = await resp.json();

            if (result.success) {
                Swal.fire({
                    icon             : 'success',
                    title            : 'Estatus Actualizado',
                    text             : result.message,
                    confirmButtonColor: '#019577',
                    timer            : 2000,
                    showConfirmButton : false
                }).then(() => {
                    if (window.location.hash !== '#places') {
                        window.location.hash = '#places';
                    }
                    window.location.reload();
                });
            } else {
                Swal.fire({
                    icon : 'error',
                    title: 'Error',
                    text : result.message || 'No fue posible actualizar el estatus.'
                });
            }

        } catch (err) {
            console.error('[US-56] toggleStatus fetch error:', err);
            Swal.fire({
                icon : 'error',
                title: 'Error de Red',
                text : 'No fue posible comunicarse con el servidor. Intente nuevamente.'
            });
        }
    });

});
