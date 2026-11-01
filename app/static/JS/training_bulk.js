/**
 * training_bulk.js
 * Lógica de cliente para la interfaz de Carga Masiva de Temas Formativos.
 * Maneja Drag & Drop, previsualización asíncrona y procesamiento final.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Setear la fecha actual en la cabecera
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        dateElement.textContent = new Date().toLocaleDateString('es-ES', options);
    }
    // Helper para escapar HTML y prevenir XSS
    function escapeHTML(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Referencias al DOM
    const container = document.querySelector('.bulk-container');
    const previewUrl = container.dataset.previewUrl;
    const processUrl = container.dataset.processUrl;

    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const dropzoneDefault = document.getElementById('dropzone-default');
    const dropzoneSelected = document.getElementById('dropzone-selected');
    const fileNameSpan = document.getElementById('selected-file-name');
    const uploadCard = document.getElementById('upload-card');

    const btnClear = document.getElementById('btn-clear-file');
    const btnPreview = document.getElementById('btn-preview');
    
    const previewSection = document.getElementById('preview-section');
    const statTotal = document.getElementById('stat-total');
    const statValid = document.getElementById('stat-valid');
    const statInvalid = document.getElementById('stat-invalid');
    const previewTbody = document.getElementById('preview-tbody');
    
    const btnCancel = document.getElementById('btn-cancel-process');
    const btnConfirm = document.getElementById('btn-confirm-process');
    const btnDownloadErrors = document.getElementById('btn-download-errors');
    const btnBackToCatalog = document.getElementById('btn-back-to-catalog');
    const downloadErrorsUrl = container.dataset.downloadErrorsUrl;

    // Archivo actualmente seleccionado
    let currentFile = null;

    // ==========================================
    // 1. LÓGICA DE SELECCIÓN DE ARCHIVOS (Drag & Drop)
    // ==========================================

    // Prevenir comportamientos por defecto
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Efectos visuales al arrastrar
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
    });

    // Manejar archivo soltado
    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }, false);

    // Manejar archivo seleccionado por botón
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        // Validar extensión
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'xlsx' && ext !== 'csv') {
            Swal.fire({
                title: 'Formato Inválido',
                text: 'Por favor, selecciona un archivo Excel (.xlsx) o CSV (.csv)',
                icon: 'warning',
                confirmButtonColor: '#0d9488'
            });
            return;
        }

        // Validar peso del archivo (Límite 5 MB)
        const maxSizeBytes = 5 * 1024 * 1024;
        if (file.size > maxSizeBytes) {
            Swal.fire({
                title: 'Archivo muy pesado',
                text: 'El archivo supera el límite permitido de 5 MB. Por favor, revisa el archivo e intenta de nuevo.',
                icon: 'error',
                confirmButtonColor: '#0d9488'
            });
            return;
        }

        currentFile = file;
        
        // Actualizar UI
        fileNameSpan.textContent = file.name;
        dropzoneDefault.style.display = 'none';
        dropzoneSelected.classList.add('active');
        
        // Ocultar sección de preview si estaba abierta de un intento anterior
        previewSection.classList.remove('active');
    }

    // Cancelar archivo seleccionado en la primera vista
    btnClear.addEventListener('click', resetUploader);

    function resetUploader() {
        currentFile = null;
        fileInput.value = '';
        dropzoneSelected.classList.remove('active');
        dropzoneDefault.style.display = 'block';
        previewSection.classList.remove('active');
        uploadCard.style.display = 'block';
        btnConfirm.disabled = true;
        btnConfirm.style.opacity = '0.5';
        btnConfirm.style.cursor = 'not-allowed';
        btnDownloadErrors.style.display = 'none';
    }


    // ==========================================
    // 2. LÓGICA DE PREVISUALIZACIÓN (Dry Run)
    // ==========================================
    
    btnPreview.addEventListener('click', async () => {
        if (!currentFile) return;

        // Mostrar un loader
        btnPreview.disabled = true;
        btnPreview.innerHTML = `
            <svg class="spinner" style="animation: spin 1s linear infinite; width:1.25rem; height:1.25rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="0.8"></path>
            </svg>
            Analizando...
        `;

        const formData = new FormData();
        formData.append('file', currentFile);

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        try {
            const response = await fetch(previewUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Error al analizar el archivo');
            }

            renderPreview(result);

        } catch (error) {
            Swal.fire({
                title: 'Error de Análisis',
                text: error.message,
                icon: 'error',
                confirmButtonColor: '#0d9488'
            });
        } finally {
            // Restaurar botón
            btnPreview.disabled = false;
            btnPreview.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                </svg>
                Analizar Archivo
            `;
        }
    });

    function renderPreview(data) {
        // Actualizar métricas
        statTotal.textContent = data.stats.total_rows;
        statValid.textContent = data.stats.valid_count;
        statInvalid.textContent = data.stats.invalid_count;

        // Limpiar tabla
        previewTbody.innerHTML = '';

        // Unificar válidos e inválidos para la previsualización
        let previewData = [];
        if (data.invalid_rows) {
            previewData = previewData.concat(data.invalid_rows.map(r => ({
                is_valid: false,
                row: r.row_number,
                module_detected: r.module_input,
                topic_name: r.name_input,
                error: r.error
            })));
        }
        if (data.valid_rows) {
            previewData = previewData.concat(data.valid_rows.map(r => ({
                is_valid: true,
                row: r.row_index,
                module_detected: r.module_code,
                topic_name: r.name,
                description: r.description
            })));
        }

        // Ordenar por número de fila original
        previewData.sort((a, b) => a.row - b.row);

        if (previewData.length === 0) {
            previewTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 2rem;">No se encontraron datos procesables en el archivo.</td></tr>`;
        } else {
            // Llenar tabla
            previewData.forEach(row => {
                const tr = document.createElement('tr');
                tr.className = row.is_valid ? 'row-valid' : 'row-invalid';

                let errorsHtml = '';
                if (!row.is_valid && row.error) {
                    errorsHtml = `<ul style="margin: 0.5rem 0 0 0; padding-left: 1.2rem;">
                        <li class="error-text">${escapeHTML(row.error)}</li>
                    </ul>`;
                }

                tr.innerHTML = `
                    <td><strong>${escapeHTML(row.row)}</strong></td>
                    <td>${row.module_detected ? escapeHTML(row.module_detected) : '<span style="color:#ef4444;">No Especificado</span>'}</td>
                    <td>${row.topic_name ? escapeHTML(row.topic_name) : '<span style="color:#ef4444;">Vacío</span>'}</td>
                    <td>
                        ${row.description ? escapeHTML(row.description) : (row.is_valid ? '<em style="color:#94a3b8;">Sin descripción</em>' : '')}
                        ${errorsHtml}
                    </td>
                `;
                previewTbody.appendChild(tr);
            });
        }

        // Mostrar botón de descarga de errores y tooltip si aplica
        if (data.stats.invalid_count > 0) {
            btnDownloadErrors.style.display = 'inline-flex';
            document.getElementById('error-tooltip').style.display = 'block';
        } else {
            btnDownloadErrors.style.display = 'none';
            document.getElementById('error-tooltip').style.display = 'none';
        }

        // Habilitar el botón de Confirmar SOLO si hay datos válidos (al menos 1)
        if (data.stats.valid_count > 0) {
            btnConfirm.disabled = false;
            btnConfirm.style.opacity = '1';
            btnConfirm.style.cursor = 'pointer';
        } else {
            btnConfirm.disabled = true;
            btnConfirm.style.opacity = '0.5';
            btnConfirm.style.cursor = 'not-allowed';
        }

        // Ocultar zona de carga y mostrar resultados
        uploadCard.style.display = 'none';
        previewSection.classList.add('active');
        
        // Smooth scroll a resultados
        previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Cancelar el proceso después de previsualizar
    btnCancel.addEventListener('click', async () => {
        if (!currentFile) return;
        const result = await Swal.fire({
            title: '¿Descartar Archivo?',
            text: 'Se perderán todos los datos no guardados de la previsualización.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, descartar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            resetUploader();
            container.scrollIntoView({ behavior: 'smooth' });
        }
    });

    // Validación al volver al catálogo
    if (btnBackToCatalog) {
        btnBackToCatalog.addEventListener('click', async (e) => {
            if (currentFile) {
                e.preventDefault();
                const result = await Swal.fire({
                    title: '¿Estás seguro de volver?',
                    text: 'Si vuelves al catálogo se cancelará el proceso y perderás los datos cargados no guardados.',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#d33',
                    cancelButtonColor: '#3085d6',
                    confirmButtonText: 'Sí, volver',
                    cancelButtonText: 'Cancelar'
                });

                if (result.isConfirmed) {
                    window.location.href = btnBackToCatalog.getAttribute('href');
                }
            }
        });
    }


    // ==========================================
    // 3. LÓGICA DE PROCESAMIENTO FINAL (Guardar)
    // ==========================================

    btnConfirm.addEventListener('click', async () => {
        if (!currentFile || btnConfirm.disabled) return;

        // Confirmación visual extra usando SweetAlert con mensaje dinámico
        const validCount = statValid.textContent;
        const invalidCount = parseInt(statInvalid.textContent) || 0;
        
        let alertText = `Se crearán ${validCount} temas formativos en el sistema.`;
        if (invalidCount > 0) {
            alertText = `Se guardarán ${validCount} temas con éxito y las ${invalidCount} filas con errores serán ignoradas.\n\n⚠️ IMPORTANTE: Si deseas conservar el registro de los errores para corregirlos, asegúrate de haberlos descargado ANTES de continuar.`;
        }

        const confirmDialog = await Swal.fire({
            title: '¿Confirmar Inserción?',
            text: alertText,
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#0d9488',
            cancelButtonColor: '#64748b',
            confirmButtonText: 'Sí, Guardar',
            cancelButtonText: 'Cancelar'
        });

        if (!confirmDialog.isConfirmed) return;

        // Iniciar guardado
        btnConfirm.disabled = true;
        btnCancel.disabled = true;
        btnConfirm.innerHTML = `Guardando...`;

        const formData = new FormData();
        formData.append('file', currentFile);

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        try {
            const response = await fetch(processUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Ocurrió un error en el servidor al intentar guardar los temas.');
            }

            // Éxito total o parcial
            await Swal.fire({
                title: '¡Operación Exitosa!',
                text: result.message,
                icon: 'success',
                confirmButtonColor: '#0d9488'
            });

            // Redirigir al Hub
            window.location.href = '/training';

        } catch (error) {
            Swal.fire({
                title: 'Error de Procesamiento',
                text: error.message,
                icon: 'error',
                confirmButtonColor: '#0d9488'
            });
        } finally {
            btnConfirm.disabled = false;
            btnCancel.disabled = false;
            btnConfirm.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                Confirmar e Insertar en Base de Datos
            `;
        }
    });

    // ==========================================
    // 4. LÓGICA DE DESCARGA DE ERRORES
    // ==========================================
    
    btnDownloadErrors.addEventListener('click', async () => {
        if (!currentFile) return;

        btnDownloadErrors.disabled = true;
        const originalText = btnDownloadErrors.innerHTML;
        btnDownloadErrors.innerHTML = `Generando...`;

        const formData = new FormData();
        formData.append('file', currentFile);

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        try {
            const response = await fetch(downloadErrorsUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            if (!response.ok) {
                let errorMsg = 'Error al generar el archivo de errores.';
                try {
                    const result = await response.json();
                    errorMsg = result.message || errorMsg;
                } catch(e) { }
                throw new Error(errorMsg);
            }

            // Descargar el archivo Blob (Excel)
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            
            // Intentar obtener el nombre del header Content-Disposition si es posible, o usar uno por defecto
            let filename = 'Reporte_Errores.xlsx';
            const disposition = response.headers.get('Content-Disposition');
            if (disposition && disposition.indexOf('attachment') !== -1) {
                const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                const matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) { 
                    filename = matches[1].replace(/['"]/g, '');
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();

        } catch (error) {
            Swal.fire({
                title: 'Error de Descarga',
                text: error.message,
                icon: 'error',
                confirmButtonColor: '#0d9488'
            });
        } finally {
            btnDownloadErrors.disabled = false;
            btnDownloadErrors.innerHTML = originalText;
        }
    });

});

/* CSS Inject for Spinner Animation (si no existe globalmente) */
const style = document.createElement('style');
style.innerHTML = `
@keyframes spin { 
    100% { transform: rotate(360deg); } 
}
`;
document.head.appendChild(style);
