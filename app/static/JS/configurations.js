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

    // E) Registrar Nueva Sede
    const btnNewPlace = document.getElementById('btn-new-place');
    if (btnNewPlace) {
        btnNewPlace.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'info',
                    title: 'Registro de Sedes',
                    text: 'El formulario de alta de sedes operativas se habilitará en la siguiente fase funcional (Modo Demostración).',
                    confirmButtonColor: '#019577',
                    confirmButtonText: 'Cerrar'
                });
            }
        });
    }

    // F) Acciones de la Tabla de Sedes (Ver / Editar)
    const placeActions = document.querySelectorAll('.btn-table-action');
    placeActions.forEach(btn => {
        btn.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'info',
                    title: 'Sede Operativa',
                    text: 'La consulta y edición de sedes físicas está activa en modo prototipo demostrativo.',
                    confirmButtonColor: '#1c3d73',
                    confirmButtonText: 'Aceptar'
                });
            }
        });
    });

});
