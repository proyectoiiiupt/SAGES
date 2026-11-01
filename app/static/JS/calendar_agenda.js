/**
 * ============================================================================
 * SAGES - Controlador de Agenda y Calendario Mensual (calendar_agenda.js)
 * ============================================================================
 * - Carga asíncrona de eventos vía /requests/api/calendar-events
 * - Cuadrícula mensual interactiva de 7 columnas (Lunes a Domingo)
 * - Tooltips dinámicos con diferenciación de rol:
 *     * Super Admin: visualiza Operador Asignado y Plantel Educativo
 *     * Admin Estadal: visualiza Plantel Educativo y Tema Formativo
 * - Navegación directa al expediente (/requests/<id>/detail)
 * - Panel lateral (Drawer) para días con múltiples formaciones
 * ============================================================================
 */

(function () {
    'use strict';

    // Constantes de Meses en Español
    const MONTH_NAMES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    // Estado del Calendario
    const state = {
        currentYear: new Date().getFullYear(),
        currentMonth: new Date().getMonth() + 1, // 1-indexed (1-12)
        selectedStateId: '',
        userRole: 'state_admin',
        events: [],
        isLoading: false,
        activeTooltipTarget: null,
        tooltipTimeout: null
    };

    // Referencias a elementos del DOM
    let elements = {};

    function cacheElements() {
        elements = {
            modal: document.getElementById('calendarAgendaModal'),
            closeBtn: document.getElementById('closeCalendarModalBtn'),
            prevBtn: document.getElementById('calPrevMonthBtn'),
            nextBtn: document.getElementById('calNextMonthBtn'),
            todayBtn: document.getElementById('calTodayBtn'),
            monthLabel: document.getElementById('calCurrentMonthLabel'),
            stateFilter: document.getElementById('calStateFilter'),
            loaderBar: document.getElementById('calLoaderBar'),
            gridBody: document.getElementById('calendarGridBody'),
            totalBadge: document.getElementById('calTotalEventsBadge'),
            floatingTooltip: document.getElementById('calFloatingTooltip'),
            drawer: document.getElementById('calDayDrawer'),
            drawerTitle: document.getElementById('calDrawerDateTitle'),
            drawerList: document.getElementById('calDrawerEventsList'),
            drawerCloseBtn: document.getElementById('calCloseDrawerBtn'),
            openTriggers: document.querySelectorAll('#btn-open-agenda, .btn-open-calendar-agenda, [data-open-calendar]')
        };

        if (elements.modal) {
            const roleAttr = elements.modal.getAttribute('data-user-role');
            if (roleAttr) {
                state.userRole = roleAttr;
            }
        }
    }

    /**
     * Abre el modal de agenda y sincroniza el calendario
     */
    function openCalendarModal() {
        if (!elements.modal) return;
        elements.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        // Sincronizar al mes actual la primera vez o mantener estado
        fetchAndRenderCalendar(state.currentYear, state.currentMonth, state.selectedStateId);
    }

    /**
     * Cierra el modal de agenda
     */
    function closeCalendarModal() {
        if (!elements.modal) return;
        elements.modal.style.display = 'none';
        document.body.style.overflow = '';
        hideTooltip();
        closeDrawer();
    }

    /**
     * Cierra el panel lateral de detalles
     */
    function closeDrawer() {
        if (elements.drawer) {
            elements.drawer.style.display = 'none';
        }
    }

    /**
     * Consulta asíncrona al endpoint JSON /requests/api/calendar-events
     */
    async function fetchAndRenderCalendar(year, month, stateId = '') {
        if (state.isLoading) return;
        state.isLoading = true;

        if (elements.loaderBar) elements.loaderBar.style.display = 'block';
        if (elements.monthLabel) {
            elements.monthLabel.textContent = `${MONTH_NAMES[month - 1]} ${year}`;
        }

        try {
            const params = new URLSearchParams({
                year: year.toString(),
                month: month.toString()
            });

            if (stateId) {
                params.append('state_id', stateId);
            }

            const response = await fetch(`/requests/api/calendar-events?${params.toString()}`, {
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                state.events = data.events || [];
                if (data.user_role) {
                    state.userRole = data.user_role;
                }
            } else {
                state.events = [];
                console.warn("SAGES Calendar warning:", data.error);
            }

            // Actualizar contador del pie
            if (elements.totalBadge) {
                const count = state.events.length;
                elements.totalBadge.textContent = `${count} ${count === 1 ? 'actividad' : 'actividades'} este mes`;
            }

            renderCalendarGrid(year, month, state.events);

        } catch (error) {
            console.error("SAGES Calendar Fetch Error:", error);
            if (elements.gridBody) {
                elements.gridBody.innerHTML = `
                    <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #ef4444;">
                        <p style="font-weight: 600; font-size: 0.95rem;">No fue posible cargar el cronograma de actividades.</p>
                        <small style="color: #64748b;">Verifique su conexión e intente nuevamente.</small>
                    </div>
                `;
            }
        } finally {
            state.isLoading = false;
            if (elements.loaderBar) elements.loaderBar.style.display = 'none';
        }
    }

    /**
     * Renderiza la cuadrícula de días y eventos del mes
     */
    function renderCalendarGrid(year, month, events) {
        if (!elements.gridBody) return;
        elements.gridBody.innerHTML = '';

        // Agrupar eventos por fecha (YYYY-MM-DD)
        const eventsByDate = {};
        events.forEach(evt => {
            if (evt.date) {
                if (!eventsByDate[evt.date]) eventsByDate[evt.date] = [];
                eventsByDate[evt.date].push(evt);
            }
        });

        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

        // Cálculo de fechas: primer día del mes (1-31)
        const firstDayOfMonth = new Date(year, month - 1, 1);
        const lastDayOfMonth = new Date(year, month, 0);
        const daysInCurrentMonth = lastDayOfMonth.getDate();

        // Determinar día de la semana del primer día (0=Dom, 1=Lun, ..., 6=Sáb)
        // Convertir a base Lunes (0=Lun, 6=Dom)
        let startingDayOfWeek = firstDayOfMonth.getDay() - 1;
        if (startingDayOfWeek === -1) startingDayOfWeek = 6;

        // Días del mes anterior para relleno
        const prevMonthLastDay = new Date(year, month - 1, 0).getDate();

        const totalCells = 42; // Matriz estándar de 6 semanas x 7 días
        const fragment = document.createDocumentFragment();

        for (let i = 0; i < totalCells; i++) {
            const cell = document.createElement('div');
            cell.className = 'calendar-day-cell';

            let cellDayNumber;
            let cellDateString;
            let isCurrentMonth = false;

            if (i < startingDayOfWeek) {
                // Días del mes anterior
                cellDayNumber = prevMonthLastDay - startingDayOfWeek + i + 1;
                const prevM = month === 1 ? 12 : month - 1;
                const prevY = month === 1 ? year - 1 : year;
                cellDateString = `${prevY}-${String(prevM).padStart(2, '0')}-${String(cellDayNumber).padStart(2, '0')}`;
                cell.classList.add('other-month');
            } else if (i < startingDayOfWeek + daysInCurrentMonth) {
                // Días del mes actual
                cellDayNumber = i - startingDayOfWeek + 1;
                cellDateString = `${year}-${String(month).padStart(2, '0')}-${String(cellDayNumber).padStart(2, '0')}`;
                isCurrentMonth = true;

                if (cellDateString === todayStr) {
                    cell.classList.add('is-today');
                }
            } else {
                // Días del mes siguiente
                cellDayNumber = i - (startingDayOfWeek + daysInCurrentMonth) + 1;
                const nextM = month === 12 ? 1 : month + 1;
                const nextY = month === 12 ? year + 1 : year;
                cellDateString = `${nextY}-${String(nextM).padStart(2, '0')}-${String(cellDayNumber).padStart(2, '0')}`;
                cell.classList.add('other-month');
            }

            cell.setAttribute('data-date', cellDateString);

            // Cabecera del día
            const dayHeader = document.createElement('div');
            dayHeader.className = 'calendar-day-header';

            const dayNumberEl = document.createElement('span');
            dayNumberEl.className = 'calendar-day-number';
            dayNumberEl.textContent = cellDayNumber;
            dayHeader.appendChild(dayNumberEl);

            const dayEvents = eventsByDate[cellDateString] || [];
            if (dayEvents.length > 0) {
                const dayCountEl = document.createElement('span');
                dayCountEl.className = 'calendar-day-count';
                dayCountEl.textContent = `${dayEvents.length}`;
                dayHeader.appendChild(dayCountEl);
            }

            cell.appendChild(dayHeader);

            // Contenedor de eventos
            const eventsContainer = document.createElement('div');
            eventsContainer.className = 'calendar-day-events';

            const maxVisible = 2;
            const visibleEvents = dayEvents.slice(0, maxVisible);

            visibleEvents.forEach(evt => {
                const pill = createEventPill(evt);
                eventsContainer.appendChild(pill);
            });

            // Si hay más eventos de los visibles, botón "+X más"
            if (dayEvents.length > maxVisible) {
                const remaining = dayEvents.length - maxVisible;
                const morePill = document.createElement('div');
                morePill.className = 'calendar-more-pill';
                morePill.textContent = `+${remaining} más`;
                morePill.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openDayDrawer(cellDateString, dayEvents);
                });
                eventsContainer.appendChild(morePill);
            }

            cell.appendChild(eventsContainer);

            // Click en la celda completa (si tiene eventos, abre el drawer)
            if (dayEvents.length > 0) {
                cell.style.cursor = 'pointer';
                cell.addEventListener('click', () => {
                    openDayDrawer(cellDateString, dayEvents);
                });
            }

            fragment.appendChild(cell);
        }

        elements.gridBody.appendChild(fragment);
    }

    /**
     * Construye una píldora visual para un evento en la cuadrícula
     */
    function createEventPill(evt) {
        const pill = document.createElement('div');
        pill.className = `calendar-event-pill pill-status-${evt.status_code || 'default'}`;
        pill.setAttribute('role', 'button');
        pill.setAttribute('tabindex', '0');

        const dot = document.createElement('span');
        dot.className = 'calendar-event-dot';
        pill.appendChild(dot);

        const text = document.createElement('span');
        text.className = 'calendar-event-text';

        // Texto resumido en la píldora según el rol
        if (state.userRole === 'super_admin') {
            text.textContent = evt.institution_name || evt.request_code;
        } else {
            text.textContent = evt.institution_name || evt.request_code;
        }
        pill.appendChild(text);

        // Eventos para el Tooltip flotante
        pill.addEventListener('mouseenter', (e) => {
            e.stopPropagation();
            showTooltip(evt, pill);
        });

        pill.addEventListener('mouseleave', () => {
            scheduleHideTooltip();
        });

        // Click directo en la píldora navega al expediente
        pill.addEventListener('click', (e) => {
            e.stopPropagation();
            if (evt.detail_url) {
                window.location.href = evt.detail_url;
            }
        });

        return pill;
    }

    /**
     * Despliega el Tooltip adaptativo según el rol
     * - Super Admin: Operador Asignado + Plantel Educativo
     * - Admin Estadal: Plantel Educativo + Tema Formativo
     */
    function showTooltip(evt, targetElement) {
        if (!elements.floatingTooltip) return;
        clearTimeout(state.tooltipTimeout);
        state.activeTooltipTarget = targetElement;

        const isSuperAdmin = (state.userRole === 'super_admin');

        let bodyContentHtml = '';

        if (isSuperAdmin) {
            // Super Admin visualiza operador y plantel
            bodyContentHtml = `
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">👤</span>
                    <div>
                        <span class="cal-tooltip-label">Operador Asignado</span>
                        <span class="cal-tooltip-value" style="color: #019577; font-weight: 700;">
                            ${escapeHtml(evt.operator_name || 'Sin Asignar')}
                        </span>
                    </div>
                </div>
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">🏫</span>
                    <div>
                        <span class="cal-tooltip-label">Plantel Educativo</span>
                        <span class="cal-tooltip-value">${escapeHtml(evt.institution_name || 'N/A')}</span>
                    </div>
                </div>
                ${evt.state_name ? `
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">📍</span>
                    <div>
                        <span class="cal-tooltip-label">Ubicación</span>
                        <span class="cal-tooltip-value" style="font-size: 0.76rem; color: #64748b;">
                            ${escapeHtml(evt.municipality_name ? evt.municipality_name + ', ' : '')}${escapeHtml(evt.state_name)}
                        </span>
                    </div>
                </div>` : ''}
            `;
        } else {
            // Admin Estadal visualiza plantel y tema
            bodyContentHtml = `
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">🏫</span>
                    <div>
                        <span class="cal-tooltip-label">Plantel Educativo</span>
                        <span class="cal-tooltip-value" style="color: #0f172a; font-weight: 700;">
                            ${escapeHtml(evt.institution_name || 'N/A')}
                        </span>
                    </div>
                </div>
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">📚</span>
                    <div>
                        <span class="cal-tooltip-label">Tema Formativo</span>
                        <span class="cal-tooltip-value" style="color: #0284c7;">
                            ${escapeHtml(evt.topic_name || 'Sin Tema Asignado')}
                        </span>
                    </div>
                </div>
                ${evt.municipality_name ? `
                <div class="cal-tooltip-row">
                    <span class="cal-tooltip-icon">📍</span>
                    <div>
                        <span class="cal-tooltip-label">Municipio</span>
                        <span class="cal-tooltip-value" style="font-size: 0.76rem; color: #64748b;">
                            ${escapeHtml(evt.municipality_name)}
                        </span>
                    </div>
                </div>` : ''}
            `;
        }

        const tooltipHtml = `
            <div class="cal-tooltip-header">
                <span class="cal-tooltip-status status-${evt.status_code}">${escapeHtml(evt.status_name)}</span>
            </div>
            <div class="cal-tooltip-body">
                ${bodyContentHtml}
            </div>
            <div class="cal-tooltip-footer">
                <a href="${evt.detail_url}" class="cal-tooltip-btn" id="calTooltipExpBtn">
                    <span>Ver Expediente</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                </a>
            </div>
        `;

        elements.floatingTooltip.innerHTML = tooltipHtml;
        elements.floatingTooltip.style.display = 'block';

        // Posicionamiento inteligente del tooltip
        positionTooltip(targetElement);

        // Prevenir que se oculte al pasar el mouse por encima del propio tooltip
        elements.floatingTooltip.onmouseenter = () => {
            clearTimeout(state.tooltipTimeout);
        };
        elements.floatingTooltip.onmouseleave = () => {
            scheduleHideTooltip();
        };
    }

    /**
     * Calcula las coordenadas de despliegue del tooltip evitando desbordar el viewport
     */
    function positionTooltip(targetElement) {
        const tooltip = elements.floatingTooltip;
        if (!tooltip || !targetElement) return;

        const targetRect = targetElement.getBoundingClientRect();
        const tooltipWidth = 320;
        const margin = 10;

        let left = targetRect.left + (targetRect.width / 2) - (tooltipWidth / 2);
        let top = targetRect.bottom + margin;

        // Ajuste horizontal
        if (left + tooltipWidth > window.innerWidth - margin) {
            left = window.innerWidth - tooltipWidth - margin;
        }
        if (left < margin) {
            left = margin;
        }

        // Si no cabe abajo, posicionar arriba
        const tooltipHeight = tooltip.offsetHeight || 180;
        if (top + tooltipHeight > window.innerHeight - margin) {
            top = targetRect.top - tooltipHeight - margin;
        }

        tooltip.style.left = `${Math.round(left)}px`;
        tooltip.style.top = `${Math.round(top)}px`;
    }

    function scheduleHideTooltip() {
        clearTimeout(state.tooltipTimeout);
        state.tooltipTimeout = setTimeout(() => {
            hideTooltip();
        }, 180);
    }

    function hideTooltip() {
        if (elements.floatingTooltip) {
            elements.floatingTooltip.style.display = 'none';
        }
        state.activeTooltipTarget = null;
    }

    /**
     * Abre el Drawer lateral de actividades del día
     */
    function openDayDrawer(dateStr, dayEvents) {
        if (!elements.drawer) return;
        hideTooltip();

        const [y, m, d] = dateStr.split('-');
        const dateObj = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
        const dateLabel = dateObj.toLocaleDateString('es-ES', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });

        if (elements.drawerTitle) {
            elements.drawerTitle.textContent = dateLabel.charAt(0).toUpperCase() + dateLabel.slice(1);
        }

        if (elements.drawerList) {
            elements.drawerList.innerHTML = '';

            const isSuperAdmin = (state.userRole === 'super_admin');

            dayEvents.forEach(evt => {
                const card = document.createElement('div');
                card.className = 'cal-drawer-card';

                const cardHeader = `
                    <div style="display: flex; justify-content: flex-end; align-items: center; margin-bottom: 6px;">
                        <span class="cal-tooltip-status status-${evt.status_code}">${escapeHtml(evt.status_name)}</span>
                    </div>
                `;

                let cardDetails = '';
                if (isSuperAdmin) {
                    cardDetails = `
                        <div style="font-size: 0.9rem; line-height: 1.5;">
                            <div style="margin-bottom: 5px;"><strong>Operador:</strong> <span style="color: #019577;">${escapeHtml(evt.operator_name || 'Sin Asignar')}</span></div>
                            <div style="color: #1e293b;"><strong>Plantel:</strong> ${escapeHtml(evt.institution_name)}</div>
                            ${evt.state_name ? `<div style="color: #64748b; font-size: 0.82rem; margin-top: 3px;">📍 ${escapeHtml(evt.state_name)}</div>` : ''}
                        </div>
                    `;
                } else {
                    cardDetails = `
                        <div style="font-size: 0.9rem; line-height: 1.5;">
                            <div style="margin-bottom: 5px;"><strong>Plantel:</strong> ${escapeHtml(evt.institution_name)}</div>
                            <div style="color: #0284c7;"><strong>Tema:</strong> ${escapeHtml(evt.topic_name)}</div>
                            ${evt.municipality_name ? `<div style="color: #64748b; font-size: 0.82rem; margin-top: 3px;">📍 ${escapeHtml(evt.municipality_name)}</div>` : ''}
                        </div>
                    `;
                }

                const cardFooter = `
                    <div style="display: flex; justify-content: flex-end; margin-top: 6px;">
                        <a href="${evt.detail_url}" class="cal-tooltip-btn">
                            Ver Expediente &rarr;
                        </a>
                    </div>
                `;

                card.innerHTML = cardHeader + cardDetails + cardFooter;
                elements.drawerList.appendChild(card);
            });
        }

        elements.drawer.style.display = 'flex';
    }

    /**
     * Utilidad defensiva contra inyección XSS
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Vinculación de Eventos
     */
    function bindEvents() {
        // Disparadores de Apertura
        if (elements.openTriggers) {
            elements.openTriggers.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    openCalendarModal();
                });
            });
        }

        // Cierre de Modal
        if (elements.closeBtn) {
            elements.closeBtn.addEventListener('click', closeCalendarModal);
        }

        if (elements.modal) {
            elements.modal.addEventListener('click', (e) => {
                if (e.target === elements.modal) {
                    closeCalendarModal();
                }
            });
        }

        // Cierre con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && elements.modal && elements.modal.style.display !== 'none') {
                if (elements.drawer && elements.drawer.style.display !== 'none') {
                    closeDrawer();
                } else {
                    closeCalendarModal();
                }
            }
        });

        // Botón Mes Anterior
        if (elements.prevBtn) {
            elements.prevBtn.addEventListener('click', () => {
                if (state.currentMonth === 1) {
                    state.currentMonth = 12;
                    state.currentYear -= 1;
                } else {
                    state.currentMonth -= 1;
                }
                closeDrawer();
                fetchAndRenderCalendar(state.currentYear, state.currentMonth, state.selectedStateId);
            });
        }

        // Botón Mes Siguiente
        if (elements.nextBtn) {
            elements.nextBtn.addEventListener('click', () => {
                if (state.currentMonth === 12) {
                    state.currentMonth = 1;
                    state.currentYear += 1;
                } else {
                    state.currentMonth += 1;
                }
                closeDrawer();
                fetchAndRenderCalendar(state.currentYear, state.currentMonth, state.selectedStateId);
            });
        }

        // Botón Hoy
        if (elements.todayBtn) {
            elements.todayBtn.addEventListener('click', () => {
                const now = new Date();
                state.currentYear = now.getFullYear();
                state.currentMonth = now.getMonth() + 1;
                closeDrawer();
                fetchAndRenderCalendar(state.currentYear, state.currentMonth, state.selectedStateId);
            });
        }

        // Filtro por Estado (Super Admin)
        if (elements.stateFilter) {
            elements.stateFilter.addEventListener('change', (e) => {
                state.selectedStateId = e.target.value;
                closeDrawer();
                fetchAndRenderCalendar(state.currentYear, state.currentMonth, state.selectedStateId);
            });
        }

        // Cierre del Drawer
        if (elements.drawerCloseBtn) {
            elements.drawerCloseBtn.addEventListener('click', closeDrawer);
        }
    }

    // Inicialización al cargar el DOM
    document.addEventListener('DOMContentLoaded', () => {
        cacheElements();
        bindEvents();
    });

    // Exponer API global por si se necesita abrir programáticamente
    window.openSagesCalendar = openCalendarModal;
    window.closeSagesCalendar = closeCalendarModal;

})();
