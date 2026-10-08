/**
 * ============================================================================
 * CONTROLADOR JS: ALERTA DE CUMPLIMIENTO POST-FECHA PAUTADA (SPAM DE CIERRE)
 * Modal bloqueante que intercepta al Administrador Estadal cuando una solicitud
 * superó su fecha de formación sin evidencias registradas.
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', function () {
    const modalBackdrop = document.getElementById('closureAlertModal');
    if (!modalBackdrop) return;

    const shouldTrigger = modalBackdrop.dataset.shouldTrigger === 'true';
    if (shouldTrigger) {
        initClosureAlertModal(modalBackdrop);
    }
});

function initClosureAlertModal(modal) {
    const requestId = modal.dataset.requestId;

    // 1. Mostrar el modal como bloqueante forzado
    modal.style.display = 'flex';
    document.body.classList.add('closure-modal-open');

    // 2. Bloquear cierre con tecla ESC
    window.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.keyCode === 27) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    // 3. Bloquear cierre por clic en el fondo oscuro (backdrop)
    modal.addEventListener('click', function (e) {
        if (e.target === modal) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // 4. Configurar restricciones de fecha mínima para reprogramación (mañana en adelante)
    setupRescheduleDateConstraints();

    // 5. Configurar navegación de pestañas (Tabs)
    setupTabs();

    // 6. Configurar gestión de subida de evidencias
    setupEvidenceUpload(requestId);

    // 7. Configurar formulario de reprogramación
    setupRescheduleForm(requestId);
}

/**
 * Fija la fecha mínima para reprogramación: estrictamente posterior a hoy (mañana en adelante).
 * No tiene límite superior.
 */
function setupRescheduleDateConstraints() {
    const dateInput = document.getElementById('closureNewDate');
    if (!dateInput) return;

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);

    const year = tomorrow.getFullYear();
    const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
    const day = String(tomorrow.getDate()).padStart(2, '0');

    dateInput.min = `${year}-${month}-${day}`;
}

/**
 * Alterna entre pestañas de Evidencias y Reprogramación.
 */
function setupTabs() {
    const btnEvidences = document.getElementById('tabBtnEvidences');
    const btnReschedule = document.getElementById('tabBtnReschedule');
    const panelEvidences = document.getElementById('panelEvidences');
    const panelReschedule = document.getElementById('panelReschedule');

    if (!btnEvidences || !panelEvidences) return;

    if (!btnReschedule || !panelReschedule) {
        panelEvidences.style.display = 'block';
        return;
    }

    btnEvidences.addEventListener('click', function () {
        btnEvidences.classList.add('active');
        btnEvidences.setAttribute('aria-selected', 'true');
        btnReschedule.classList.remove('active');
        btnReschedule.setAttribute('aria-selected', 'false');

        panelEvidences.style.display = 'block';
        panelReschedule.style.display = 'none';
    });

    btnReschedule.addEventListener('click', function () {
        btnReschedule.classList.add('active');
        btnReschedule.setAttribute('aria-selected', 'true');
        btnEvidences.classList.remove('active');
        btnEvidences.setAttribute('aria-selected', 'false');

        panelReschedule.style.display = 'block';
        panelEvidences.style.display = 'none';
    });
}

/**
 * Helper para obtener el token CSRF disponible en el DOM.
 */
function getCsrfToken() {
    const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (metaToken) return metaToken;
    const inputToken = document.querySelector('input[name="csrf_token"]')?.value;
    return inputToken || '';
}

/**
 * Formatea bytes en formato legible (KB, MB).
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Carga y envío de evidencias digitales de cumplimiento.
 */
function setupEvidenceUpload(requestId) {
    const dropZone = document.getElementById('closureDropZone');
    const fileInput = document.getElementById('closureFileInput');
    const filesList = document.getElementById('closureFilesList');
    const filesUl = document.getElementById('closureFilesUl');
    const filesCountSpan = document.getElementById('closureFilesCount');
    const btnSubmit = document.getElementById('btnSubmitEvidence');
    const form = document.getElementById('closureEvidenceForm');

    if (!dropZone || !fileInput || !form) return;

    let selectedFiles = [];
    const MAX_FILES = 3;
    const MAX_SIZE = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_EXTS = ['pdf', 'png', 'jpg', 'jpeg'];

    // Clic en dropzone abre selector
    dropZone.addEventListener('click', function () {
        fileInput.click();
    });

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, function (e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('is-dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, function (e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('is-dragover');
        });
    });

    dropZone.addEventListener('drop', function (e) {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files.length) {
            handleNewFiles(dt.files);
        }
    });

    fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files.length) {
            handleNewFiles(fileInput.files);
        }
        fileInput.value = ''; // Reset input to allow selecting same file again if removed
    });

    function handleNewFiles(fileList) {
        for (let i = 0; i < fileList.length; i++) {
            const f = fileList[i];
            const ext = f.name.split('.').pop().toLowerCase();

            if (!ALLOWED_EXTS.includes(ext)) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Formato no permitido',
                        text: `El archivo "${f.name}" no es compatible. Solo se admiten archivos PDF, JPG o PNG.`
                    });
                } else {
                    alert(`El archivo "${f.name}" no es compatible. Solo se admiten PDF, JPG o PNG.`);
                }
                continue;
            }

            if (f.size > MAX_SIZE) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Archivo demasiado grande',
                        text: `El archivo "${f.name}" (${formatFileSize(f.size)}) supera el límite de 5 MB.`
                    });
                } else {
                    alert(`El archivo "${f.name}" supera el límite de 5 MB.`);
                }
                continue;
            }

            if (selectedFiles.length >= MAX_FILES) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Límite de archivos',
                        text: `Solo puede adjuntar un máximo de ${MAX_FILES} archivos de evidencia.`
                    });
                }
                break;
            }

            // Evitar duplicados por nombre y tamaño
            const isDuplicate = selectedFiles.some(existing => existing.name === f.name && existing.size === f.size);
            if (!isDuplicate) {
                selectedFiles.push(f);
            }
        }

        renderFiles();
    }

    function renderFiles() {
        filesUl.innerHTML = '';
        filesCountSpan.textContent = selectedFiles.length;

        if (selectedFiles.length === 0) {
            filesList.style.display = 'none';
            btnSubmit.disabled = true;
            return;
        }

        filesList.style.display = 'block';
        btnSubmit.disabled = false;

        selectedFiles.forEach((file, idx) => {
            const li = document.createElement('li');
            li.className = 'closure-file-item';

            const ext = file.name.split('.').pop().toUpperCase();

            li.innerHTML = `
                <div class="closure-file-info">
                    <span class="closure-file-ext-badge">${ext}</span>
                    <span class="closure-file-name" title="${file.name}">${file.name}</span>
                    <span class="closure-file-size">${formatFileSize(file.size)}</span>
                </div>
                <button type="button" class="closure-file-remove" data-index="${idx}" title="Eliminar archivo">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `;

            li.querySelector('.closure-file-remove').addEventListener('click', function () {
                const targetIdx = parseInt(this.dataset.index, 10);
                selectedFiles.splice(targetIdx, 1);
                renderFiles();
            });

            filesUl.appendChild(li);
        });
    }

    // Envío del formulario de evidencias
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (selectedFiles.length === 0) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Soportes requeridos',
                    text: 'Debe adjuntar al menos un archivo de evidencia para cerrar la solicitud.'
                });
            }
            return;
        }

        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('evidences', file);
        });

        const csrfToken = getCsrfToken();

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'Procesando evidencias...',
                text: 'Guardando los soportes y actualizando el estado de la solicitud.',
                allowOutsideClick: false,
                allowEscapeKey: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
        }

        btnSubmit.disabled = true;

        try {
            const response = await fetch(`/requests/api/${requestId}/close-with-evidences`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            const data = await response.json();

            if (response.ok && data.success) {
                if (typeof Swal !== 'undefined') {
                    await Swal.fire({
                        icon: 'success',
                        title: '¡Solicitud Completada!',
                        text: data.message || 'Las evidencias se guardaron exitosamente y la solicitud ha sido completada.',
                        confirmButtonText: 'Aceptar',
                        confirmButtonColor: '#019577'
                    });
                }
                window.location.reload();
            } else {
                btnSubmit.disabled = false;
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo cerrar la solicitud',
                        text: data.message || 'Ocurrió un error al procesar las evidencias.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert(data.message || 'Error al procesar las evidencias.');
                }
            }
        } catch (err) {
            btnSubmit.disabled = false;
            console.error('Error al subir evidencias:', err);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de conexión',
                    text: 'No se pudo comunicar con el servidor. Verifique su conexión e intente nuevamente.'
                });
            } else {
                alert('Error de conexión con el servidor.');
            }
        }
    });
}

/**
 * Justificación y reprogramación de la fecha pautada.
 */
function setupRescheduleForm(requestId) {
    const form = document.getElementById('closureRescheduleForm');
    const newDateInput = document.getElementById('closureNewDate');
    const reasonSelect = document.getElementById('closureReasonSelect');
    const justificationTextarea = document.getElementById('closureJustificationText');
    const charCounter = document.getElementById('closureCharCounter');
    const btnSubmit = document.getElementById('btnSubmitReschedule');

    if (!form || !newDateInput || !reasonSelect || !justificationTextarea) return;

    // Contador de caracteres reactivo
    justificationTextarea.addEventListener('input', function () {
        const length = justificationTextarea.value.trim().length;
        if (length < 20) {
            charCounter.textContent = `${length} / 20 caracteres mínimos`;
            charCounter.classList.add('text-danger');
            charCounter.classList.remove('text-success');
        } else {
            charCounter.textContent = `${length} caracteres (válido)`;
            charCounter.classList.remove('text-danger');
            charCounter.classList.add('text-success');
        }
    });

    // Envío del formulario de reprogramación
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        const newDate = newDateInput.value;
        const reasonId = reasonSelect.value;
        const justification = justificationTextarea.value.trim();

        // Validaciones en frontend
        if (!newDate) {
            newDateInput.focus();
            if (typeof Swal !== 'undefined') {
                Swal.fire({ icon: 'warning', title: 'Fecha requerida', text: 'Indique la nueva fecha para la reprogramación.' });
            }
            return;
        }

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const selectedDate = new Date(newDate + 'T00:00:00');

        if (selectedDate <= today) {
            newDateInput.focus();
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Fecha inválida',
                    text: 'La nueva fecha planificada debe ser estrictamente posterior a hoy.'
                });
            }
            return;
        }

        if (!reasonId) {
            reasonSelect.focus();
            if (typeof Swal !== 'undefined') {
                Swal.fire({ icon: 'warning', title: 'Motivo requerido', text: 'Seleccione un motivo oficial de reprogramación.' });
            }
            return;
        }

        if (justification.length < 20) {
            justificationTextarea.focus();
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Justificación insuficiente',
                    text: 'La exposición de motivos debe contener al menos 20 caracteres.'
                });
            }
            return;
        }

        const csrfToken = getCsrfToken();

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'Guardando reprogramación...',
                text: 'Registrando la justificación y actualizando la fecha pautada.',
                allowOutsideClick: false,
                allowEscapeKey: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
        }

        btnSubmit.disabled = true;

        try {
            const response = await fetch(`/requests/api/${requestId}/reschedule-closure`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    new_date: newDate,
                    reason_id: parseInt(reasonId, 10),
                    justification: justification
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                if (typeof Swal !== 'undefined') {
                    await Swal.fire({
                        icon: 'success',
                        title: '¡Reprogramación Exitosa!',
                        text: data.message || 'La solicitud ha sido reprogramada y la justificación fue asentada en el expediente.',
                        confirmButtonText: 'Continuar',
                        confirmButtonColor: '#019577'
                    });
                }
                window.location.reload();
            } else {
                btnSubmit.disabled = false;
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error al reprogramar',
                        text: data.message || 'No se pudo guardar la reprogramación.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert(data.message || 'Error al reprogramar.');
                }
            }
        } catch (err) {
            btnSubmit.disabled = false;
            console.error('Error al reprogramar solicitud:', err);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de conexión',
                    text: 'No se pudo comunicar con el servidor. Intente nuevamente.'
                });
            } else {
                alert('Error de conexión con el servidor.');
            }
        }
    });
}
