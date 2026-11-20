/**
 * app/static/js/requests_history.js
 * Interactividad para el Archivo Histórico de Solicitudes y Descarga de Informe Oficial (US-50)
 * - Confirmación SweetAlert2 antes de descarga
 * - Prevención de descargas simultáneas (loading state)
 * - Visor modal de evidencias custodiadas (imágenes y PDFs)
 */

'use strict';

document.addEventListener('DOMContentLoaded', function () {

    // =========================================================================
    // 1. Manejo de Descarga de Informe Técnico con Confirmación SweetAlert2
    // =========================================================================
    const btnDownload = document.getElementById('btnDownloadReport');

    if (btnDownload) {
        btnDownload.addEventListener('click', function (e) {
            e.preventDefault();

            const downloadUrl = this.getAttribute('data-download-url');
            const downloadFilename = this.getAttribute('data-filename') || '';

            if (!downloadUrl) return;

            // Verificar si SweetAlert2 está disponible
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: '¿Desea descargar el informe técnico?',
                    text: 'Se compilará el Informe Técnico Oficial con membrete institucional de CORPOELEC y sello criptográfico QR.',
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#019577',
                    cancelButtonColor: '#64748b',
                    confirmButtonText: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle; margin-right:6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Descargar Informe',
                    cancelButtonText: 'Cancelar',
                    reverseButtons: true,
                    focusConfirm: true
                }).then((result) => {
                    if (result.isConfirmed) {
                        ejecutarDescargaSegura(btnDownload, downloadUrl, downloadFilename);
                    }
                });
            } else {
                // Fallback convencional si SweetAlert2 no estuviera en el DOM
                if (confirm('¿Desea descargar el informe técnico oficial de esta jornada formativa?')) {
                    ejecutarDescargaSegura(btnDownload, downloadUrl, downloadFilename);
                }
            }
        });
    }

    /**
     * Ejecuta la descarga con protección contra sobrecarga en servidor y descarga limpia vía Blob.
     * Deshabilita el botón temporalmente, muestra spinner y previene advertencias de descargas
     * inseguras de Chrome en entornos HTTP al transferir mediante objeto Blob en memoria.
     */
    async function ejecutarDescargaSegura(btn, url, filename) {
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="spinner-svg" viewBox="0 0 50 50" style="width:18px; height:18px; animation:spin 1s linear infinite; display:inline-block; vertical-align:middle; margin-right:6px;">
                <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="5" stroke-dasharray="31.4 31.4" stroke-linecap="round"></circle>
            </svg> Compilando Informe PDF...
        `;

        // Añadir regla de animación de rotación si no existe
        if (!document.getElementById('spinner-style')) {
            const style = document.createElement('style');
            style.id = 'spinner-style';
            style.innerHTML = `@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`;
            document.head.appendChild(style);
        }

        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/pdf'
                }
            });

            if (!response.ok) {
                let errorMsg = 'Error del servidor al compilar el informe técnico.';
                try {
                    const errData = await response.json();
                    errorMsg = errData.message || errData.error || errorMsg;
                } catch (_) {}
                throw new Error(errorMsg);
            }

            // Obtener nombre del archivo desde cabecera Content-Disposition si está disponible
            let finalFilename = filename || 'Informe_Tecnico_Oficial.pdf';
            const disposition = response.headers.get('Content-Disposition');
            if (disposition && disposition.indexOf('filename=') !== -1) {
                const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
                if (matches && matches[1]) {
                    finalFilename = matches[1].replace(/['"]/g, '').trim();
                }
            }

            // Convertir respuesta a Blob para descarga directa en memoria (evita bloqueo HTTP de Chrome)
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const tempLink = document.createElement('a');
            tempLink.style.display = 'none';
            tempLink.href = blobUrl;
            tempLink.download = finalFilename;
            document.body.appendChild(tempLink);
            tempLink.click();

            setTimeout(() => {
                window.URL.revokeObjectURL(blobUrl);
                tempLink.remove();
            }, 1500);

            // Notificación de éxito solo cuando la descarga efectivamente se procesó
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
                    title: 'Informe técnico generado con éxito'
                });
            }

        } catch (err) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: 'Error de Descarga',
                    text: err.message || 'No fue posible compilar o descargar el documento del expediente.',
                    icon: 'error',
                    confirmButtonColor: '#dc2626'
                });
            } else {
                alert(err.message || 'Error al descargar el documento.');
            }
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }

    // =========================================================================
    // 2. Visor Modal de Evidencias Custodiadas (Multimedia)
    // =========================================================================
    const modalOverlay = document.getElementById('mediaModalOverlay');
    const modalBody = document.getElementById('modalMediaBody');
    const modalTitle = document.getElementById('modalMediaTitle');
    const btnCloseModal = document.getElementById('btnModalClose');

    const previewButtons = document.querySelectorAll('.btn-preview-media');

    if (modalOverlay && modalBody) {
        previewButtons.forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                const url = this.getAttribute('data-url');
                const format = (this.getAttribute('data-format') || '').toUpperCase();
                const filename = this.getAttribute('data-filename') || 'Evidencia Custodiada';

                if (!url) return;

                if (modalTitle) {
                    modalTitle.textContent = `Inspección: ${filename}`;
                }

                modalBody.innerHTML = '';

                if (['JPG', 'JPEG', 'PNG', 'WEBP'].includes(format)) {
                    const img = document.createElement('img');
                    img.src = url;
                    img.alt = filename;
                    img.style.borderRadius = '6px';
                    modalBody.appendChild(img);
                } else if (format === 'PDF') {
                    const iframe = document.createElement('iframe');
                    iframe.src = url;
                    modalBody.appendChild(iframe);
                } else {
                    modalBody.innerHTML = `<p style="color:white; padding:20px;">Formato no soportado para previsualización directa. <a href="${url}?download=1" style="color:#38bdf8;">Descargar archivo</a></p>`;
                }

                modalOverlay.style.display = 'flex';
                document.body.style.overflow = 'hidden'; // Prevenir scroll de fondo
            });
        });

        const cerrarModal = () => {
            modalOverlay.style.display = 'none';
            modalBody.innerHTML = '';
            document.body.style.overflow = '';
        };

        if (btnCloseModal) {
            btnCloseModal.addEventListener('click', cerrarModal);
        }

        modalOverlay.addEventListener('click', function (e) {
            if (e.target === modalOverlay) {
                cerrarModal();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modalOverlay.style.display === 'flex') {
                cerrarModal();
            }
        });
    }

});
