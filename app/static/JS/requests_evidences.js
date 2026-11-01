/**
 * requests_evidences.js
 * ---------------------
 * Controlador Frontend para la Zona Drag & Drop y Galería de Custodia Documental.
 */

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('evidence-management-container');
    if (!container) return;

    const requestId = container.dataset.requestId;
    const canUpload = container.dataset.canUpload === 'true';

    // Elementos del Dropzone y Carga
    const dropzone = document.getElementById('evidence-dropzone');
    const fileInput = document.getElementById('evidence-file-input');
    const dzIdle = document.getElementById('dz-idle');
    const dzPreview = document.getElementById('dz-preview');
    const dzFileName = document.getElementById('dz-file-name');
    const dzFileSize = document.getElementById('dz-file-size');
    const btnDzClear = document.getElementById('btn-dz-clear');
    const btnConfirmUpload = document.getElementById('btn-confirm-upload');

    // Elementos de Progreso de Subida
    const uploadProgress = document.getElementById('evidence-upload-progress');
    const progressBar = document.getElementById('evidence-progress-bar');
    const progressPct = document.getElementById('evidence-upload-pct');
    const progressFilename = document.getElementById('evidence-upload-filename');

    // Elementos de la Galería
    const galleryGrid = document.getElementById('evidence-gallery-grid');
    const emptyState = document.getElementById('evidence-empty-state');
    const galleryCountBadge = document.getElementById('evidence-count-val');

    // Modales de Interfaz (US-46)
    const modalUpload = document.getElementById('evidenceUploadModal');
    const modalGallery = document.getElementById('evidenceGalleryModal');
    const btnOpenUpload = document.getElementById('btn-open-upload-modal');
    const btnOpenGallery = document.getElementById('btn-open-gallery-modal');
    const btnCloseUpload = document.getElementById('btn-close-upload-modal');
    const btnCancelUpload = document.getElementById('btn-cancel-upload-modal');
    const btnCloseGallery = document.getElementById('btn-close-gallery-modal');
    const btnSwitchToGallery = document.getElementById('btn-switch-to-gallery');
    const btnSwitchToUpload = document.getElementById('btn-switch-to-upload');

    // Referencias al Modal Legacy (para compatibilidad con tests y layouts)
    const modalElement = document.getElementById('evidenceInspectionModal');

    // Constantes de Validación Normativa
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];

    // Archivo actualmente preparado para subida
    let stagedFile = null;

    // Obtención del Token CSRF
    function getCsrfToken() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag && metaTag.content) return metaTag.content;
        const inputTag = document.querySelector('input[name="csrf_token"]');
        if (inputTag && inputTag.value) return inputTag.value;
        return '';
    }

    // Formateador de bytes para UI
    function formatBytes(bytes, decimals = 1) {
        if (!bytes || bytes === 0) return '0 KB';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // =========================================================================
    // 1. TRANSICIONES Y CONTROL DE MODALES (SUBIDA Y GALERÍA)
    // =========================================================================
    function openModal(modal) {
        if (!modal) return;
        modal.style.display = 'flex';
        void modal.offsetWidth;
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
            if (!document.querySelector('.evidence-popup-backdrop.show, .evidence-modal-backdrop.show')) {
                document.body.style.overflow = '';
            }
        }, 180);
    }

    // Transición atómica limpia entre modales sin desajustes de backdrops
    function switchModals(fromModal, toModal) {
        if (fromModal) {
            fromModal.classList.remove('show');
            fromModal.style.display = 'none';
        }
        if (toModal) {
            toModal.style.display = 'flex';
            void toModal.offsetWidth;
            toModal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    }

    if (btnOpenUpload && modalUpload) {
        btnOpenUpload.addEventListener('click', (e) => {
            e.preventDefault();
            resetStagedFile();
            openModal(modalUpload);
        });
    }

    if (btnOpenGallery && modalGallery) {
        btnOpenGallery.addEventListener('click', (e) => {
            e.preventDefault();
            openModal(modalGallery);
        });
    }

    if (btnCloseUpload && modalUpload) {
        btnCloseUpload.addEventListener('click', () => {
            closeModal(modalUpload);
            resetStagedFile();
        });
    }

    if (btnCancelUpload && modalUpload) {
        btnCancelUpload.addEventListener('click', () => {
            closeModal(modalUpload);
            resetStagedFile();
        });
    }

    if (btnCloseGallery && modalGallery) {
        btnCloseGallery.addEventListener('click', () => closeModal(modalGallery));
    }

    // Cierre del modal de carga y paso inmediato a la galería
    if (btnSwitchToGallery && modalUpload && modalGallery) {
        btnSwitchToGallery.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            resetStagedFile();
            switchModals(modalUpload, modalGallery);
        });
    }

    // Cierre del modal de galería y paso inmediato a la carga
    if (btnSwitchToUpload && modalUpload && modalGallery) {
        btnSwitchToUpload.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            resetStagedFile();
            switchModals(modalGallery, modalUpload);
        });
    }

    // Cerrar al hacer clic en el fondo oscuro exterior
    [modalUpload, modalGallery].forEach(m => {
        if (m) {
            m.addEventListener('click', (e) => {
                if (e.target === m) {
                    closeModal(m);
                    if (m === modalUpload) resetStagedFile();
                }
            });
        }
    });

    // Cerrar con la tecla Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (modalUpload && modalUpload.classList.contains('show')) {
                closeModal(modalUpload);
                resetStagedFile();
            } else if (modalGallery && modalGallery.classList.contains('show')) {
                closeModal(modalGallery);
            }
        }
    });

    // =========================================================================
    // 2. GESTIÓN DE DRAG & DROP Y SELECCIÓN PREVENTIVA (STAGING)
    // =========================================================================
    function resetStagedFile() {
        stagedFile = null;
        if (fileInput) fileInput.value = '';
        if (dzIdle) dzIdle.style.display = 'flex';
        if (dzPreview) dzPreview.style.display = 'none';
        if (dzFileName) dzFileName.textContent = '';
        if (dzFileSize) dzFileSize.textContent = '';
        if (btnConfirmUpload) btnConfirmUpload.setAttribute('disabled', 'disabled');
        if (uploadProgress) uploadProgress.style.display = 'none';
        if (progressBar) progressBar.style.width = '0%';
        if (progressPct) progressPct.textContent = '0%';
    }

    function stageFile(file) {
        if (!file) return;

        // 1. Validar extensión permitida
        const ext = file.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Formato no permitido',
                    text: `El archivo "${file.name}" no es válido. Solo se admiten formatos PDF, JPG y PNG.`,
                    confirmButtonColor: '#019577'
                });
            } else {
                alert(`El archivo "${file.name}" no es válido. Solo se admiten formatos PDF, JPG y PNG.`);
            }
            resetStagedFile();
            return;
        }

        // 2. Validar tamaño máximo permitido (5 MB)
        if (file.size > MAX_FILE_SIZE) {
            const sizeMB = (file.size / 1024 / 1024).toFixed(2);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Archivo demasiado pesado',
                    text: `El archivo "${file.name}" pesa ${sizeMB} MB. El límite máximo permitido es de 5.00 MB por archivo.`,
                    confirmButtonColor: '#019577'
                });
            } else {
                alert(`El archivo "${file.name}" supera el límite de 5 MB.`);
            }
            resetStagedFile();
            return;
        }

        // Archivo válido: configurar estado staged para revisión del usuario
        stagedFile = file;
        if (dzIdle) dzIdle.style.display = 'none';
        if (dzPreview) dzPreview.style.display = 'flex';
        if (dzFileName) dzFileName.textContent = file.name;
        if (dzFileSize) dzFileSize.textContent = formatBytes(file.size);
        if (btnConfirmUpload) btnConfirmUpload.removeAttribute('disabled');
    }

    // Controles para preparar archivos (Dropzone y File Input)
    if (canUpload && dropzone && fileInput) {
        // Prevenir comportamiento nativo por defecto
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
            document.body.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        // Efectos visuales de arrastre
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.remove('dragover');
            }, false);
        });

        // Evento Drop
        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                stageFile(dt.files[0]);
            }
        });

        // Evento Clic en el Dropzone para abrir el selector (excepto si se pulsa "Quitar archivo")
        dropzone.addEventListener('click', (e) => {
            if (e.target.closest('#btn-dz-clear')) return;
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        // Evento Change del Input File
        fileInput.addEventListener('change', function () {
            if (this.files && this.files.length > 0) {
                stageFile(this.files[0]);
            }
        });

        // Botón "Quitar archivo"
        if (btnDzClear) {
            btnDzClear.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                resetStagedFile();
            });
        }
    }

    // Función puente compatible con llamadas directas
    function handleFiles(fileList) {
        const files = Array.from(fileList || []);
        if (files.length > 0) {
            stageFile(files[0]);
        }
    }

    // =========================================================================
    // 3. SUBIDA ASÍNCRONA AJAX Y CONFIRMACIÓN EXPLÍCITA
    // =========================================================================
    function uploadSingleFile(file) {
        return new Promise((resolve) => {
            const formData = new FormData();
            formData.append('file', file);

            const uploadUrl = `/requests/api/${requestId}/evidences/upload`;

            if (uploadProgress && progressBar && progressPct && progressFilename) {
                progressFilename.textContent = `Subiendo "${file.name}"...`;
                progressBar.style.width = '0%';
                progressPct.textContent = '0%';
                uploadProgress.style.display = 'flex';
            }

            const xhr = new XMLHttpRequest();
            xhr.open('POST', uploadUrl, true);
            xhr.setRequestHeader('X-CSRFToken', getCsrfToken());
            xhr.setRequestHeader('Accept', 'application/json');

            // Seguimiento de Progreso
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable && progressBar && progressPct) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = `${percent}%`;
                    progressPct.textContent = `${percent}%`;
                }
            };

            // Respuesta Completada
            xhr.onload = () => {
                setTimeout(() => {
                    if (uploadProgress) uploadProgress.style.display = 'none';
                }, 350);

                let resData = {};
                try {
                    resData = JSON.parse(xhr.responseText);
                } catch (e) {
                    resData = { success: false, message: 'Respuesta no válida del servidor.' };
                }

                if (xhr.status === 201 && resData.success && resData.evidence) {
                    const ev = resData.evidence;
                    insertEvidenceCard(ev);
                    updateWorkspaceMetrics(ev.metrics);

                    if (typeof Swal !== 'undefined') {
                        const Toast = Swal.mixin({
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 3500,
                            timerProgressBar: true
                        });
                        Toast.fire({
                            icon: 'success',
                            title: `"${ev.file_name}" custodiado exitosamente`
                        });
                    }
                    resolve(true);
                } else {
                    const errorMsg = resData.message || 'No se pudo adjuntar el archivo de evidencia.';
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error de Carga',
                            text: errorMsg,
                            confirmButtonColor: '#019577'
                        });
                    } else {
                        alert(`Error: ${errorMsg}`);
                    }
                    resolve(false);
                }
            };

            // Error de Red
            xhr.onerror = () => {
                if (uploadProgress) uploadProgress.style.display = 'none';
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error de Conexión',
                        text: 'Ocurrió una interrupción de red al contactar al servidor de almacenamiento.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert('Error de conexión al cargar la evidencia.');
                }
                resolve(false);
            };

            xhr.send(formData);
        });
    }

    // Botón "Confirmar archivo"
    if (btnConfirmUpload) {
        btnConfirmUpload.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!stagedFile) return;

            btnConfirmUpload.setAttribute('disabled', 'disabled');
            const fileToUpload = stagedFile;

            const isSuccess = await uploadSingleFile(fileToUpload);
            if (isSuccess) {
                resetStagedFile();
                // Cerrar modal de carga y desplegar galería actualizada
                switchModals(modalUpload, modalGallery);
            } else {
                btnConfirmUpload.removeAttribute('disabled');
            }
        });
    }

    // =========================================================================
    // 4. CREACIÓN E INSERCIÓN DINÁMICA DE TARJETAS EN EL DOM
    // =========================================================================
    function insertEvidenceCard(ev) {
        if (!galleryGrid) return;

        // Ocultar estado vacío si estaba visible
        if (emptyState) emptyState.style.display = 'none';

        const isPdf = ev.format === 'PDF';
        const isImage = ['JPG', 'JPEG', 'PNG', 'WEBP'].includes(ev.format);

        const card = document.createElement('div');
        card.className = 'evidence-card card-enter';
        card.id = `evidence-card-${ev.id}`;
        card.setAttribute('data-evidence-id', ev.id);

        let previewHtml = '';
        if (isImage) {
            previewHtml = `
                <img src="${ev.view_url}" alt="${ev.file_name}" class="evidence-card-img" loading="lazy">
                <div class="evidence-card-overlay">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    <span>Inspeccionar</span>
                </div>
            `;
        } else {
            previewHtml = `
                <div class="evidence-card-pdf-placeholder">
                    <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="#dc2626" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="9" y1="13" x2="15" y2="13"></line>
                        <line x1="9" y1="17" x2="15" y2="17"></line>
                    </svg>
                    <span class="evidence-pdf-badge">PDF</span>
                </div>
                <div class="evidence-card-overlay">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    <span>Leer</span>
                </div>
            `;
        }

        const deleteBtnHtml = canUpload ? `
            <button type="button" 
                    class="evidence-action-btn btn-delete" 
                    data-action="delete"
                    data-evidence-id="${ev.id}"
                    data-file-name="${ev.file_name}"
                    title="Eliminar evidencia probatoria">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
            </button>
        ` : '';

        card.innerHTML = `
            <div class="evidence-card-preview" 
                 data-action="preview" 
                 data-evidence-id="${ev.id}"
                 data-file-url="${ev.view_url}"
                 data-file-name="${ev.file_name}"
                 data-file-size="${ev.file_weight_str}"
                 data-format="${ev.format}"
                 role="button"
                 tabindex="0"
                 title="Clic para inspeccionar ${ev.file_name}">
                ${previewHtml}
            </div>
            <div class="evidence-card-meta">
                <p class="evidence-card-filename" title="${ev.file_name}">${ev.file_name}</p>
                <div class="evidence-card-subinfo">
                    <span class="evidence-format-pill ${isPdf ? 'pill-pdf' : 'pill-image'}">${ev.format}</span>
                    <span class="evidence-weight-text">${ev.file_weight_str}</span>
                </div>
                <span class="evidence-date-text">${ev.created_at}</span>
            </div>
            <div class="evidence-card-actions">
                <a href="${ev.download_url}" class="evidence-action-btn btn-download" title="Descargar soporte original" download target="_blank">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                </a>
                ${deleteBtnHtml}
            </div>
        `;

        galleryGrid.prepend(card);
    }

    // =========================================================================
    // 5. SUPRESIÓN CONTROLADA DE EVIDENCIAS (DELETE)
    // =========================================================================
    if (galleryGrid) {
        galleryGrid.addEventListener('click', async (e) => {
            const deleteBtn = e.target.closest('[data-action="delete"]');
            if (!deleteBtn) return;

            e.preventDefault();
            e.stopPropagation();

            const evidenceId = deleteBtn.getAttribute('data-evidence-id');
            const fileName = deleteBtn.getAttribute('data-file-name') || 'esta evidencia';

            if (!evidenceId) return;

            let isConfirmed = false;
            if (typeof Swal !== 'undefined') {
                const result = await Swal.fire({
                    title: '¿Retirar evidencia probatoria?',
                    text: `Se eliminará físicamente el archivo "${fileName}". Esta acción asentará un hito formal en la bitácora transversal.`,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#64748b',
                    confirmButtonText: 'Sí, retirar archivo',
                    cancelButtonText: 'Cancelar'
                });
                isConfirmed = result.isConfirmed;
            } else {
                isConfirmed = confirm(`¿Desea retirar de forma definitiva el archivo "${fileName}"?`);
            }

            if (!isConfirmed) return;

            try {
                let response = await fetch(`/requests/api/evidences/${evidenceId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Accept': 'application/json'
                    }
                });

                // Fallback a POST /delete si el entorno o proxy intercepta DELETE
                if (response.status === 405 || !response.ok) {
                    response = await fetch(`/requests/api/evidences/${evidenceId}/delete`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'Accept': 'application/json'
                        }
                    });
                }

                const resData = await response.json();

                if (response.ok && resData.success) {
                    const card = document.getElementById(`evidence-card-${evidenceId}`);
                    if (card) {
                        card.classList.add('card-exit');
                        setTimeout(() => {
                            card.remove();
                            // Si ya no quedan tarjetas, mostrar estado vacío
                            const remainingCards = galleryGrid.querySelectorAll('.evidence-card');
                            if (remainingCards.length === 0 && emptyState) {
                                emptyState.style.display = 'flex';
                            }
                        }, 250);
                    }

                    if (resData.data && resData.data.metrics) {
                        updateWorkspaceMetrics(resData.data.metrics);
                    }

                    if (typeof Swal !== 'undefined') {
                        const Toast = Swal.mixin({
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 3000,
                            timerProgressBar: true
                        });
                        Toast.fire({
                            icon: 'success',
                            title: `"${fileName}" retirada de la custodia`
                        });
                    }
                } else {
                    const errorMsg = resData.message || 'No fue posible retirar la evidencia probatoria.';
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error al Retirar',
                            text: errorMsg,
                            confirmButtonColor: '#019577'
                        });
                    } else {
                        alert(`Error: ${errorMsg}`);
                    }
                }
            } catch (err) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error de Red',
                        text: 'Ocurrió un fallo de conexión al procesar la eliminación.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert('Error de conexión al eliminar la evidencia.');
                }
            }
        });
    }

    // =========================================================================
    // 6. ACTUALIZACIÓN REACTIVA DE MÉTRICAS DEL EXPEDIENTE
    // =========================================================================
    function updateWorkspaceMetrics(metrics) {
        if (!metrics) return;

        // 1. Contador de la galería y de la tarjeta
        if (galleryCountBadge) {
            galleryCountBadge.textContent = metrics.total_evidences;
        }
        const wsEvidencePill = document.getElementById('ws-evidence-pill');
        if (wsEvidencePill) {
            wsEvidencePill.textContent = metrics.total_evidences;
        }

        // 2. Contadores del Checklist
        const photoCountVal = document.getElementById('photo-count-val');
        if (photoCountVal) photoCountVal.textContent = metrics.photo_count;

        const pdfCountVal = document.getElementById('pdf-count-val');
        if (pdfCountVal) pdfCountVal.textContent = metrics.pdf_count;

        // 3. Iconos del Checklist (Checkmark verde vs Círculo pendiente)
        const photoIconWrap = document.getElementById('check-photo-icon-wrap');
        if (photoIconWrap) {
            if (metrics.has_photo_evidence) {
                photoIconWrap.innerHTML = `
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                `;
            } else {
                photoIconWrap.innerHTML = `
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="8" y1="12" x2="16" y2="12"></line>
                    </svg>
                `;
            }
        }

        const pdfIconWrap = document.getElementById('check-pdf-icon-wrap');
        if (pdfIconWrap) {
            if (metrics.has_pdf_evidence) {
                pdfIconWrap.innerHTML = `
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                `;
            } else {
                pdfIconWrap.innerHTML = `
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="8" y1="12" x2="16" y2="12"></line>
                    </svg>
                `;
            }
        }

        // 4. Barra de Progreso y Porcentaje
        const pct = metrics.request_progress_pct || 75;
        const compliancePctText = document.getElementById('compliance-pct-text');
        if (compliancePctText) {
            compliancePctText.textContent = `${pct}% completado`;
        }

        const complianceProgressBar = document.getElementById('compliance-progress-bar');
        if (complianceProgressBar) {
            complianceProgressBar.style.width = `${pct}%`;
        }

        // 5. Botón de Formalización / Culminación de Solicitud
        const btnComplete = document.getElementById('btn-complete-request');
        if (btnComplete) {
            if (metrics.can_complete) {
                btnComplete.removeAttribute('disabled');
            } else {
                btnComplete.setAttribute('disabled', 'disabled');
            }
        }

        // 6. Dataset en raíz
        const rootEl = document.getElementById('active-workspace-root');
        if (rootEl) {
            rootEl.dataset.canComplete = metrics.can_complete ? 'true' : 'false';
            rootEl.dataset.hasPhoto = metrics.has_photo_evidence ? 'true' : 'false';
            rootEl.dataset.hasPdf = metrics.has_pdf_evidence ? 'true' : 'false';
            rootEl.dataset.progressPct = pct;
        }
    }

    // =========================================================================
    // 7. INSPECCIÓN FORENSE / VISTA PREVIA INTEGRADA (ESTILO APP/USERS/ VIA SWEETALERT2)
    // =========================================================================
    function openForensicModal(fileUrl, downloadUrl, format, filename, filesize) {
        const isPdf = (format || '').toUpperCase() === 'PDF';

        let contentHtml = '';
        if (isPdf) {
            contentHtml = `
                <div class="evidence-preview-frame-wrap">
                    <iframe src="${fileUrl}" allowfullscreen></iframe>
                </div>
                <div class="evidence-preview-meta-footer">
                    <div>
                        <span class="evidence-preview-meta-text">${filename}</span> 
                        <span style="margin: 0 4px;">•</span> 
                        <span>${filesize || 'PDF'}</span>
                    </div>
                    <a href="${downloadUrl}" download="${filename}" target="_blank" class="evidence-preview-download-link">
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        Descargar original
                    </a>
                </div>
            `;
        } else {
            contentHtml = `
                <div class="evidence-preview-img-wrap">
                    <img src="${fileUrl}" alt="${filename}">
                </div>
                <div class="evidence-preview-meta-footer">
                    <div>
                        <span class="evidence-preview-meta-text">${filename}</span> 
                        <span style="margin: 0 4px;">•</span> 
                        <span>${filesize || 'Imagen'}</span>
                    </div>
                    <a href="${downloadUrl}" download="${filename}" target="_blank" class="evidence-preview-download-link">
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        Descargar original
                    </a>
                </div>
            `;
        }

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: isPdf ? 'Vista Previa del Documento' : 'Vista Previa de la Fotografía',
                html: contentHtml,
                width: 'min(94vw, 860px)',
                showCloseButton: true,
                showConfirmButton: true,
                confirmButtonText: 'Cerrar vista previa',
                confirmButtonColor: '#019577',
                focusConfirm: false,
                customClass: {
                    popup: 'swal2-evidence-preview-popup'
                }
            });
        } else if (modalElement) {
            // Fallback en caso de que Swal no esté cargado
            modalElement.style.display = 'flex';
        }
    }

    function closeForensicModal() {
        if (typeof Swal !== 'undefined' && Swal.isVisible()) {
            Swal.close();
        }
        if (modalElement) {
            modalElement.style.display = 'none';
        }
    }

    // Delegación de clic para abrir el visor desde la tarjeta
    if (galleryGrid) {
        galleryGrid.addEventListener('click', (e) => {
            const previewTarget = e.target.closest('[data-action="preview"]');
            if (!previewTarget) return;

            // Si se hizo clic en un botón de acción (eliminar/descargar), ignorar
            if (e.target.closest('.evidence-card-actions')) return;

            const fileUrl = previewTarget.getAttribute('data-file-url');
            const downloadUrl = (previewTarget.getAttribute('data-file-url') || '') + '?download=1';
            const format = previewTarget.getAttribute('data-format') || 'ARCHIVO';
            const filename = previewTarget.getAttribute('data-file-name') || 'soporte_documental';
            const filesize = previewTarget.getAttribute('data-file-size') || '';

            if (fileUrl) {
                openForensicModal(fileUrl, downloadUrl, format, filename, filesize);
            }
        });
    }

    // Exponer helpers en window para interacciones cruzadas o testing si fuera necesario
    window.evidenceController = {
        openModal,
        closeModal,
        switchModals,
        stageFile,
        resetStagedFile,
        openForensicModal,
        closeForensicModal,
        handleFiles
    };
});
