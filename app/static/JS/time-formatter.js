/**
 * time-formatter.js
 * Script global institucional para SAGES.
 * Estandarización de Zona Horaria y Formateo Regional para Venezuela (es-VE, America/Caracas).
 *
 * Funcionalidades:
 * 1. Convierte timestamps UTC de elementos .local-datetime a la hora oficial de Venezuela (es-VE).
 * 2. Estandariza e inicializa automáticamente los encabezados de fecha del sistema (banners).
 * 3. Expone funciones globales para re-evaluación en componentes dinámicos (modales, AJAX).
 */

const SAGES_LOCALE = 'es-VE';
const SAGES_TIMEZONE = 'America/Caracas';

document.addEventListener("DOMContentLoaded", function () {
    initTimeFormatter();
});

function initTimeFormatter() {
    initCurrentDateHeaders();
    formatAllLocalTimes();
}

/**
 * Formatea un objeto Date con la configuración regional estándar de SAGES (es-VE, America/Caracas),
 * con fallback seguro en caso de navegadores antiguos sin soporte IANA timeZone.
 */
function formatDateWithOptions(date, options) {
    try {
        return new Intl.DateTimeFormat(
            SAGES_LOCALE,
            Object.assign({ timeZone: SAGES_TIMEZONE }, options)
        ).format(date);
    } catch (e) {
        return new Intl.DateTimeFormat(SAGES_LOCALE, options).format(date);
    }
}

/**
 * Normaliza un string UTC/ISO y lo formatea según el tipo estándar SAGES.
 */
function formatLocalTimestamp(utcString, formatType = 'standard') {
    if (!utcString) return '';

    let normalized = String(utcString).trim().replace(/Z+$/, '');
    const hasOffset = normalized.includes('+') || normalized.lastIndexOf('-') > 10;
    if (!hasOffset) {
        normalized += 'Z';
    }

    const date = new Date(normalized);
    if (isNaN(date.getTime())) {
        console.warn("time-formatter.js: Fecha inválida detectada ->", utcString);
        return '';
    }

    if (formatType === 'standard' || formatType === 'friendly') {
        return formatDateWithOptions(date, {
            year: 'numeric',
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }
    if (formatType === 'full') {
        return formatDateWithOptions(date, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }
    if (formatType === 'full-date') {
        return formatDateWithOptions(date, {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }
    if (formatType === 'date-only' || formatType === 'date') {
        return formatDateWithOptions(date, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }
    if (formatType === 'time-only' || formatType === 'time') {
        return formatDateWithOptions(date, {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }

    return '';
}

/**
 * Inicializa automáticamente los elementos de banner y cabecera de fecha actual.
 */
function initCurrentDateHeaders() {
    const headerSelectors = [
        '.sages-page-banner__date-value',
        '[data-current-date]',
        '#current-date-display',
        '#current-date',
        '#hub-current-date',
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
        '.current-date-text'
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
            const utcString = el.getAttribute('data-utc');
            if (!utcString) return;

            const formatType = el.getAttribute('data-format') || 'standard';
            const formattedStr = formatLocalTimestamp(utcString, formatType);

            if (formattedStr) {
                el.textContent = formattedStr;
            }
        } catch (error) {
            console.error("time-formatter.js error:", error);
        }
    });
}

/**
 * Helper programático para formatear un elemento puntual como fecha actual.
 */
function formatCurrentDate(element, formatType = 'full-date') {
    if (!element) return;
    element.setAttribute('data-utc', new Date().toISOString());
    element.classList.add('local-datetime');
    element.setAttribute('data-format', formatType);
    formatAllLocalTimes();
}

// Exponer en el objeto global window
window.formatLocalTimestamp = formatLocalTimestamp;
window.formatAllLocalTimes = formatAllLocalTimes;
window.formatCurrentDate = formatCurrentDate;
window.initTimeFormatter = initTimeFormatter;
