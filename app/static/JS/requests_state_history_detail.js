/**
 * app/static/JS/requests_state_history_detail.js
 * Scripts específicos de la vista de Expediente Histórico (Modelo Expediente).
 * Mantiene el HTML libre de scripts en línea.
 */

'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const dateEl = document.getElementById('current-date-display');
    if (dateEl) {
        const opts = { day: 'numeric', month: 'long', year: 'numeric' };
        const formatted = new Date().toLocaleDateString('es-ES', opts);
        dateEl.textContent = formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }
});
