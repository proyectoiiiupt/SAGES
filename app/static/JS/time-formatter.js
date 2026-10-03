/**
 * time-formatter.js
 * Script global para SAGES
 * Encuentra elementos con la clase .local-datetime y convierte su data-utc a la zona horaria local.
 */
document.addEventListener("DOMContentLoaded", function () {
    formatAllLocalTimes();
});

function formatAllLocalTimes() {
    const timeElements = document.querySelectorAll('.local-datetime');
    
    timeElements.forEach(el => {
        try {
            let utcString = el.getAttribute('data-utc');
            if (!utcString) return;
            
            // 1. Limpiar el string de cualquier 'Z' manual que le hayamos puesto en Jinja
            utcString = utcString.replace(/Z+$/, '');
            
            // 2. Detectar si tiene offset (+00:00 o -04:00)
            // Un offset negativo tendrá un '-' después de la fecha (índice > 10).
            const hasOffset = utcString.includes('+') || utcString.lastIndexOf('-') > 10;
            
            // 3. Si no tiene offset, asumimos UTC y le ponemos la 'Z'
            if (!hasOffset) {
                utcString += 'Z';
            }
            
            const date = new Date(utcString);
            
            // Verifica que la fecha sea válida
            if (isNaN(date.getTime())) {
                console.error("time-formatter.js: Fecha inválida detectada ->", utcString);
                return; // Mantiene el texto fallback de Jinja2
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
            } else if (formatType === 'date-only') {
                formattedStr = new Intl.DateTimeFormat('es-VE', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                }).format(date);
            }
            
            el.innerText = formattedStr;
        } catch (error) {
            console.error("time-formatter.js error:", error);
        }
    });
}
