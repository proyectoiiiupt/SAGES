/**
 * time-formatter.js
 * Script global institucional para SAGES.
 * Estandarización de Zona Horaria y Formateo Regional para Venezuela (es-VE, America/Caracas).
 * 
 * Funcionalidades:
 * 1. Convierte timestamps UTC de elementos .local-datetime a la hora local del usuario en es-VE.
 * 2. Estandariza e inicializa automáticamente los encabezados de fecha del sistema (banners).
 * 3. Expone funciones globales para re-evaluación en componentes dinámicos (modales, AJAX).
 */

document.addEventListener("DOMContentLoaded", function () {
    initTimeFormatter();
});

function initTimeFormatter() {
    initCurrentDateHeaders();
    formatAllLocalTimes();
}

/**
 * Inicializa automáticamente los elementos de banner y cabecera de fecha actual.
 */
function initCurrentDateHeaders() {
    const headerSelectors = [
        '#current-date-display',
        '#current-date',
        '#dashboard-date-text',
        '#config-date-text',
        '#analytics-date-text',
        '#current-analytics-date',
        '#current-indicators-date',
        '#current-wizard-date',
        '#monitoring-date-text',
        '#delays-date-text',
        '#audit-current-date',
        '#monitoring-current-date',
        '.current-date-display',
        '.current-date-text',
        '[data-current-date]'
    ];

    const elements = document.querySelectorAll(headerSelectors.join(', '));
    const nowIso = new Date().toISOString();

    elements.forEach(el => {
        if (!el.getAttribute('data-utc')) {
            el.setAttribute('data-utc', nowIso);
        }
        if (!el.classList.contains('local-datetime')) {
            el.classList.add('local-datetime');
        }
        if (!el.getAttribute('data-format')) {
            el.setAttribute('data-format', 'full-date');
        }
    });
}

/**
 * Recorre todos los elementos .local-datetime y formatea su data-utc según el data-format especificado.
 */
function formatAllLocalTimes() {
    const timeElements = document.querySelectorAll('.local-datetime');

    timeElements.forEach(el => {
        try {
            let utcString = el.getAttribute('data-utc');
            if (!utcString) return;

            // 1. Limpiar el string de cualquier 'Z' duplicada
            utcString = utcString.replace(/Z+$/, '');

            // 2. Detectar si ya tiene offset (+00:00 o -04:00)
            const hasOffset = utcString.includes('+') || utcString.lastIndexOf('-') > 10;

            // 3. Si no tiene offset, asumimos UTC y le colocamos la 'Z'
            if (!hasOffset) {
                utcString += 'Z';
            }

            const date = new Date(utcString);

            // Verifica que la fecha sea válida
            if (isNaN(date.getTime())) {
                console.warn("time-formatter.js: Fecha inválida detectada ->", utcString);
                return; // Mantiene el texto fallback
            }

            const formatType = el.getAttribute('data-format') || 'standard';
            let formattedStr = '';

            if (formatType === 'standard' || formatType === 'friendly') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    year: 'numeric',
                    month: 'short',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                }).format(date);
            } else if (formatType === 'full') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                }).format(date);
            } else if (formatType === 'full-date') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                }).format(date);
            } else if (formatType === 'date-only' || formatType === 'date') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                }).format(date);
            } else if (formatType === 'time-only' || formatType === 'time') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                }).format(date);
            }

            if (formattedStr) {
                el.innerText = formattedStr;
            }
        } catch (error) {
            console.error("time-formatter.js error:", error);
        }
    });
}

/**
 * Helper programático para formatear un elemento puntual como fecha actual
 */
function formatCurrentDate(element, formatType = 'full-date') {
    if (!element) return;
    element.setAttribute('data-utc', new Date().toISOString());
    element.classList.add('local-datetime');
    element.setAttribute('data-format', formatType);
    formatAllLocalTimes();
}

// Exponer en el objeto global window
window.formatAllLocalTimes = formatAllLocalTimes;
window.formatCurrentDate = formatCurrentDate;
window.initTimeFormatter = initTimeFormatter;
