/**
 * requests_detail_modal.js
 * Controlador Vanilla del Visor Modal de Evidencias Digitales Custodiadas y
 * Acciones de Fiscalización Superior para Super Administrador (US-45)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ---------------------------------------------------------------------------
    // 1. Estado y Referencias del Visor Modal
    // ---------------------------------------------------------------------------
    const modalElement = document.getElementById('evidenceInspectionModal');
    if (!modalElement) return;

    const modalFilename = document.getElementById('evidence-modal-filename');
    const modalBadgeFormat = document.getElementById('evidence-modal-badge-format');
    const modalFilesize = document.getElementById('evidence-modal-filesize');
    const modalDownloadBtn = document.getElementById('evidence-download-btn');
    const btnCloseHeader = document.getElementById('closeEvidenceModalBtn');
    const btnCloseFooter = document.getElementById('closeEvidenceModalSecondaryBtn');

    const loadingState = document.getElementById('evidence-loading-state');
    const errorState = document.getElementById('evidence-error-state');
    const pdfContainer = document.getElementById('evidence-pdf-container');
    const imageContainer = document.getElementById('evidence-image-container');

    const pdfFrame = document.getElementById('evidence-pdf-frame');
    const imagePreview = document.getElementById('evidence-image-preview');

    // Estado de transformaciones para imágenes
    let currentZoom = 1.0;
    let currentRotation = 0;
    let fallbackTimer = null;

    const imageStage = document.getElementById('evidence-img-stage');

    function applyImageTransform() {
        if (!imagePreview) return;
        imagePreview.style.transform = `scale(${currentZoom}) rotate(${currentRotation}deg)`;
        if (imageStage) {
            imageStage.style.overflow = (currentZoom > 1.05) ? 'auto' : 'hidden';
        }
    }

    function resetViewerState() {
        currentZoom = 1.0;
        currentRotation = 0;
        applyImageTransform();

        if (fallbackTimer) {
            clearTimeout(fallbackTimer);
            fallbackTimer = null;
        }

        if (pdfFrame) {
            pdfFrame.src = 'about:blank';
        }
        if (imagePreview) {
            imagePreview.src = '';
        }

        if (pdfContainer) pdfContainer.style.display = 'none';
        if (imageContainer) imageContainer.style.display = 'none';
        if (errorState) errorState.style.display = 'none';
        if (loadingState) loadingState.style.display = 'flex';
    }

    function openModal() {
        modalElement.style.display = 'flex';
        // Forzar reflow para animación CSS
        void modalElement.offsetWidth;
        modalElement.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modalElement.classList.remove('show');
        setTimeout(() => {
            modalElement.style.display = 'none';
            resetViewerState();
            document.body.style.overflow = '';
        }, 220);
    }

    // Eventos de cierre
    if (btnCloseHeader) btnCloseHeader.addEventListener('click', closeModal);
    if (btnCloseFooter) btnCloseFooter.addEventListener('click', closeModal);

    // Cerrar al hacer clic en el backdrop oscuro exterior
    modalElement.addEventListener('click', (e) => {
        if (e.target === modalElement) {
            closeModal();
        }
    });

    // Cerrar con tecla Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalElement.classList.contains('show')) {
            closeModal();
        }
    });

    // ---------------------------------------------------------------------------
    // 2. Apertura del Visor al hacer clic en "Inspeccionar"
    // ---------------------------------------------------------------------------
    document.querySelectorAll('.btn-inspect-evidence').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const btn = e.target.closest('.btn-inspect-evidence') || button;

            const evidenceUrl = btn.getAttribute('data-evidence-url') || '';
            const downloadUrl = btn.getAttribute('data-download-url') || evidenceUrl;
            const format = (btn.getAttribute('data-format') || 'DOCUMENTO').toUpperCase();
            const filename = btn.getAttribute('data-filename') || 'soporte_documental';
            const filesize = btn.getAttribute('data-filesize') || '';

            resetViewerState();

            // Actualizar metadatos en cabecera
            if (modalFilename) modalFilename.textContent = filename;
            if (modalBadgeFormat) modalBadgeFormat.textContent = format;
            if (modalFilesize) modalFilesize.textContent = filesize;
            if (modalDownloadBtn) {
                modalDownloadBtn.href = downloadUrl;
                modalDownloadBtn.setAttribute('download', filename);
            }

            openModal();

            const isPdf = (format === 'PDF');
            const isImage = ['JPG', 'JPEG', 'PNG', 'WEBP', 'GIF'].includes(format);

            if (isPdf && pdfFrame && pdfContainer) {
                pdfContainer.style.display = 'block';

                pdfFrame.onload = () => {
                    if (loadingState) loadingState.style.display = 'none';
                };

                // Asignar URL al iframe
                pdfFrame.src = evidenceUrl;

                // Fallback timeout para ocultar spinner si el visor interno de PDF no dispara onload
                fallbackTimer = setTimeout(() => {
                    if (loadingState && loadingState.style.display !== 'none') {
                        loadingState.style.display = 'none';
                    }
                }, 1800);

            } else if (isImage && imagePreview && imageContainer) {
                imageContainer.style.display = 'block';

                imagePreview.onload = () => {
                    if (loadingState) loadingState.style.display = 'none';
                };

                imagePreview.onerror = () => {
                    if (loadingState) loadingState.style.display = 'none';
                    if (imageContainer) imageContainer.style.display = 'none';
                    if (errorState) errorState.style.display = 'flex';
                };

                // Iniciar carga de la imagen
                imagePreview.src = evidenceUrl;

                // Temporizador de seguridad: si tarda más de 6 segundos o falla en silencio
                fallbackTimer = setTimeout(() => {
                    if (loadingState && loadingState.style.display !== 'none') {
                        loadingState.style.display = 'none';
                        if (!imagePreview.naturalWidth) {
                            if (imageContainer) imageContainer.style.display = 'none';
                            if (errorState) errorState.style.display = 'flex';
                        }
                    }
                }, 6000);

            } else {
                // Formato no previsualizable directamente
                if (loadingState) loadingState.style.display = 'none';
                if (errorState) errorState.style.display = 'flex';
            }
        });
    });

    // ---------------------------------------------------------------------------
    // 3. Controles de Zoom y Rotación para Imágenes
    // ---------------------------------------------------------------------------
    const btnRotateLeft = document.getElementById('btn-rotate-left');
    const btnRotateRight = document.getElementById('btn-rotate-right');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnZoomReset = document.getElementById('btn-zoom-reset');

    if (btnRotateLeft) {
        btnRotateLeft.addEventListener('click', () => {
            currentRotation = (currentRotation - 90) % 360;
            applyImageTransform();
        });
    }

    if (btnRotateRight) {
        btnRotateRight.addEventListener('click', () => {
            currentRotation = (currentRotation + 90) % 360;
            applyImageTransform();
        });
    }

    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => {
            currentZoom = Math.min(parseFloat((currentZoom + 0.25).toFixed(2)), 3.0);
            applyImageTransform();
        });
    }

    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => {
            currentZoom = Math.max(parseFloat((currentZoom - 0.25).toFixed(2)), 0.5);
            applyImageTransform();
        });
    }

    if (btnZoomReset) {
        btnZoomReset.addEventListener('click', () => {
            currentZoom = 1.0;
            currentRotation = 0;
            applyImageTransform();
        });
    }

    // ---------------------------------------------------------------------------
    // 4. Acción Coercitiva: Exigir Justificación Inmediata
    // ---------------------------------------------------------------------------
    const btnDemandDelay = document.getElementById('btn-demand-delay-audit');
    if (btnDemandDelay) {
        btnDemandDelay.addEventListener('click', async (e) => {
            e.preventDefault();

            const requestId = btnDemandDelay.getAttribute('data-request-id');
            const instName = btnDemandDelay.getAttribute('data-institution') || 'Plantel Educativo';

            if (!requestId) return;

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            // Confirmación obligatoria previa con SweetAlert2
            if (typeof Swal !== 'undefined') {
                const result = await Swal.fire({
                    title: '¿Despachar Intimación Coercitiva?',
                    html: `
                        <div style="text-align: left; font-size: 0.92rem; color: #475569; line-height: 1.5;">
                            <p style="margin-bottom: 8px;">Se emitirá un <strong>requerimiento superior de fiscalización</strong> para la atención inmediata del plantel <strong style="color: #0f172a;">${instName}</strong>.</p>
                            <p style="margin-bottom: 0;">Esta orden estampará un hito formal e inalterable en la bitácora transversal y disparará una notificación con severidad <span style="color: #dc2626; font-weight: 700;">CRÍTICA</span> a la coordinación estadal responsable.</p>
                        </div>
                    `,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, despachar requerimiento',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#64748b',
                    reverseButtons: true
                });

                if (!result.isConfirmed) return;
            } else {
                if (!confirm(`¿Desea despachar requerimiento coercitivo formal para el plantel ${instName}?`)) {
                    return;
                }
            }

            // Bloqueo y animación de carga
            const originalHtml = btnDemandDelay.innerHTML;
            btnDemandDelay.disabled = true;
            btnDemandDelay.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="width: 14px; height: 14px; border: 2px solid #ffffff; border-top-color: transparent; border-radius: 50%; display: inline-block; vertical-align: middle; animation: spin 0.8s linear infinite;"></span>
                <span>Despachando...</span>
            `;

            try {
                const response = await fetch(`/requests/api/delays/${requestId}/demand-response`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ''
                    }
                });

                const data = await response.json().catch(() => ({}));

                if (response.status === 200) {
                    btnDemandDelay.className = 'btn-toolbar-nav';
                    btnDemandDelay.disabled = true;
                    btnDemandDelay.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width: 15px; height: 15px; color: #10b981;">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Requerimiento Despachado</span>
                    `;

                    if (typeof Swal !== 'undefined') {
                        await Swal.fire({
                            title: 'Intimación Despachada',
                            text: data.message || 'Se ha intimado exitosamente al operador responsable. El evento ha quedado registrado en la bitácora.',
                            icon: 'success',
                            confirmButtonColor: '#007865'
                        });
                    }

                    window.location.reload();

                } else if (response.status === 429) {
                    btnDemandDelay.disabled = false;
                    btnDemandDelay.innerHTML = originalHtml;

                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: 'Límite de Frecuencia',
                            text: 'Ya se despachó una intimación recientemente para este expediente. Por favor espere antes de emitir un nuevo requerimiento.',
                            icon: 'info',
                            confirmButtonColor: '#007865'
                        });
                    } else {
                        alert('Ya se despachó una intimación recientemente.');
                    }
                } else {
                    btnDemandDelay.disabled = false;
                    btnDemandDelay.innerHTML = originalHtml;

                    const errMsg = data.message || 'Ocurrió un error al despachar la intimación coercitiva.';
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: 'Error de Despacho',
                            text: errMsg,
                            icon: 'error',
                            confirmButtonColor: '#007865'
                        });
                    } else {
                        alert(errMsg);
                    }
                }
            } catch (err) {
                btnDemandDelay.disabled = false;
                btnDemandDelay.innerHTML = originalHtml;
                console.error("Error al procesar intimación coercitiva:", err);
            }
        });
    }
});
