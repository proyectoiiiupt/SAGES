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
                        ejecutarDescargaSegura(btnDownload, downloadUrl);
                    }
                });
            } else {
                // Fallback convencional si SweetAlert2 no estuviera en el DOM
                if (confirm('¿Desea descargar el informe técnico oficial de esta jornada formativa?')) {
                    ejecutarDescargaSegura(btnDownload, downloadUrl);
                }
            }
        });
    }

    /**
     * Ejecuta la descarga con protección contra sobrecarga en servidor.
     * Deshabilita el botón temporalmente y muestra spinner.
     */
    function ejecutarDescargaSegura(btn, url) {
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

        // Crear enlace temporal invisible para disparar la descarga directa
        const tempLink = document.createElement('a');
        tempLink.href = url;
        tempLink.setAttribute('download', '');
        document.body.appendChild(tempLink);
        tempLink.click();
        document.body.removeChild(tempLink);

        // Notificación de éxito flotante SweetAlert2
        setTimeout(() => {
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

            // Restaurar botón después de 3.5 segundos
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }, 3000);
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
