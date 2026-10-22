/**
 * tracking_timeline.js
 * Lógica transversal de interactividad para la Bitácora de Seguimiento (US-45).
 * Utilizado por:
 *  - active_workspace.html (Facilitador UREE / Administrador)
 *  - applicant_request_view.html (Directivo / Solicitante del Plantel)
 * SAGES — CORPOELEC (Gerencia de UREE)
 */

document.addEventListener('DOMContentLoaded', function () {
    initTrackingTimeline();
});

function initTrackingTimeline() {
    const timelineCard = document.querySelector('.tracking-timeline-card');
    if (!timelineCard) return;

    const timelineScrollBox = document.getElementById('timeline-scroll-box');
    const quickNoteInput = document.getElementById('tracking-quick-note');
    const charCountDisplay = document.getElementById('tracking-char-count');
    const btnSaveNote = document.getElementById('btn-save-tracking-note');

    // =========================================================================
    // 1. Desplazamiento automático al final de la cronología
    // =========================================================================
    function scrollTimelineToBottom(smooth = true) {
        if (timelineScrollBox) {
            timelineScrollBox.scrollTo({
                top: timelineScrollBox.scrollHeight,
                behavior: smooth ? 'smooth' : 'auto'
            });
        }
    }
    window.scrollTimelineToBottom = scrollTimelineToBottom;
    scrollTimelineToBottom(false);

    // =========================================================================
    // 2. Contador reactivo de caracteres
    // =========================================================================
    if (quickNoteInput && charCountDisplay) {
        quickNoteInput.addEventListener('input', function () {
            const currentLen = this.value.length;
            charCountDisplay.textContent = `${currentLen} / 500 caracteres`;
            if (currentLen >= 480) {
                charCountDisplay.classList.add('limit-near');
            } else {
                charCountDisplay.classList.remove('limit-near');
            }
            if (currentLen >= 500) {
                charCountDisplay.classList.add('limit-reached');
            } else {
                charCountDisplay.classList.remove('limit-reached');
            }
        });
    }

    // =========================================================================
    // 3. Registro y persistencia asíncrona de notas humanas (AJAX / REST)
    // =========================================================================
    if (btnSaveNote && quickNoteInput) {
        btnSaveNote.addEventListener('click', function () {
            const requestId = btnSaveNote.dataset.requestId;
            const noteText = quickNoteInput.value.trim();

            if (!requestId || requestId === '0') {
                console.error("tracking_timeline.js: Request ID no válido.");
                return;
            }

            if (!noteText) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Nota vacía',
                        text: 'Por favor, ingrese el contenido de la observación antes de registrarla.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert('Por favor, ingrese el contenido de la observación antes de registrarla.');
                }
                quickNoteInput.focus();
                return;
            }

            // Obtener CSRF Token del meta tag global de SAGES
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

            // Estado de carga en botón
            btnSaveNote.disabled = true;
            const originalBtnHtml = btnSaveNote.innerHTML;
            btnSaveNote.innerHTML = `
                <svg class="spinner-inline" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" style="animation: spin 0.8s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
                </svg>
                <span>Asentando...</span>
            `;

            fetch(`/requests/api/requests/${requestId}/tracking-note`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ message: noteText })
            })
            .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, body: data })))
            .then(({ status, ok, body }) => {
                if (!ok || !body.success) {
                    throw new Error(body.message || `Error del servidor (HTTP ${status})`);
                }

                // Inserción reactiva en el DOM usando la respuesta oficial del servidor
                appendNoteToTimeline(body.note);

                // Limpieza de campos
                quickNoteInput.value = '';
                if (charCountDisplay) {
                    charCountDisplay.textContent = '0 / 500 caracteres';
                    charCountDisplay.classList.remove('limit-near', 'limit-reached');
                }

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Nota Asentada',
                        text: body.message || 'La observación ha sido registrada exitosamente en la bitácora.',
                        timer: 2000,
                        showConfirmButton: false
                    });
                }
            })
            .catch(err => {
                console.error("Error al registrar nota en la bitácora:", err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo asentar la nota',
                        text: err.message || 'Ocurrió un error al intentar comunicarse con el servidor.',
                        confirmButtonColor: '#019577'
                    });
                } else {
                    alert(err.message || 'Ocurrió un error al intentar registrar la nota.');
                }
            })
            .finally(() => {
                btnSaveNote.disabled = false;
                btnSaveNote.innerHTML = originalBtnHtml;
            });
        });
    }

    // =========================================================================
    // 4. Inserción reactiva de la nota en el DOM sin recargar
    // =========================================================================
    function appendNoteToTimeline(noteData) {
        if (!timelineScrollBox || !noteData) return;

        // Ocultar estado vacío si estaba visible
        const emptyState = document.getElementById('timeline-empty-state');
        if (emptyState) emptyState.style.display = 'none';

        let listContainer = document.getElementById('timeline-steps-list');
        if (listContainer) {
            listContainer.style.display = 'flex';
        } else {
            listContainer = document.createElement('div');
            listContainer.className = 'timeline-steps-list';
            listContainer.id = 'timeline-steps-list';
            timelineScrollBox.appendChild(listContainer);
        }

        const itemDiv = document.createElement('div');
        itemDiv.className = 'timeline-item';
        itemDiv.setAttribute('data-step-id', noteData.id || '');

        const authorName = noteData.author || 'Usuario SAGES';
        const authorRole = noteData.author_role || '';
        const createdStr = noteData.created_at_str || 'Hace un momento';
        const createdIso = noteData.created_at || '';
        const cleanMsg = noteData.message || '';

        itemDiv.innerHTML = `
            <div class="avatar-circle" title="${escapeHtml(authorName)}">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            </div>
            <div class="timeline-content">
                <div class="timeline-header">
                    <div class="timeline-author-group">
                        <span class="timeline-author">${escapeHtml(authorName)}</span>
                        ${authorRole ? `<span class="timeline-role-pill">${escapeHtml(authorRole)}</span>` : ''}
                    </div>
                    <span class="timeline-time local-datetime" data-utc="${escapeHtml(createdIso)}" data-format="standard">
                        <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 3px;">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        ${escapeHtml(createdStr)}
                    </span>
                </div>
                <p class="timeline-text">${cleanMsg}</p>
            </div>
        `;

        listContainer.appendChild(itemDiv);
        scrollTimelineToBottom(true);

        // Si time-formatter.js está disponible, formatear la nueva etiqueta
        if (typeof formatAllLocalTimes === 'function') {
            try {
                formatAllLocalTimes();
            } catch (e) {
                console.debug("time-formatter ejecución silenciosa:", e);
            }
        }

        // =========================================================================
        // 5. Actualización sincronizada de contadores
        // =========================================================================
        const totalCount = listContainer.children.length;
        const cardBadge = document.getElementById('tracking-counter-badge');
        if (cardBadge) {
            cardBadge.textContent = `${totalCount} eventos`;
        }

        const topbarBadge = document.getElementById('ws-topbar-note-count');
        if (topbarBadge) {
            topbarBadge.textContent = totalCount;
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // =========================================================================
    // 6. Control Transversal del Drawer Lateral Deslizable de la Bitácora
    // =========================================================================
    const btnOpenBitacora = document.getElementById('btn-toggle-bitacora');
    const btnCloseBitacora = document.getElementById('btn-close-bitacora');
    const bitacoraDrawer = document.getElementById('bitacora-drawer');
    const bitacoraBackdrop = document.getElementById('bitacora-backdrop');

    function toggleBitacora(open) {
        if (!bitacoraDrawer || !bitacoraBackdrop) return;
        bitacoraDrawer.classList.toggle('open', open);
        bitacoraBackdrop.style.display = open ? 'block' : 'none';
        if (open) {
            scrollTimelineToBottom(false);
            if (quickNoteInput) {
                setTimeout(() => quickNoteInput.focus(), 250);
            }
        }
    }

    if (!window._bitacoraDrawerInitialized) {
        window._bitacoraDrawerInitialized = true;
        if (btnOpenBitacora) {
            btnOpenBitacora.addEventListener('click', () => toggleBitacora(true));
        }
        if (btnCloseBitacora) {
            btnCloseBitacora.addEventListener('click', () => toggleBitacora(false));
        }
        if (bitacoraBackdrop) {
            bitacoraBackdrop.addEventListener('click', () => toggleBitacora(false));
        }
    }
}

