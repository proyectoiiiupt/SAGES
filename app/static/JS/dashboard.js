/**
 * Dashboard de Indicadores - Scripts
 * Maneja la fecha dinámica y animaciones de contadores numéricos.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Formatear y mostrar la fecha actual en español
    const dateElement = document.getElementById('dashboard-date-text');
    if (dateElement) {
        const today = new Date();
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const formattedDate = today.toLocaleDateString('es-ES', options);
        // Formato requerido: "1 de abril, 2026"
        dateElement.textContent = formattedDate.replace(' de 20', ', 20');
    }

    // 2. Animación suave para los números de los indicadores (KPIs)
    const counters = document.querySelectorAll('.counter-value');
    counters.forEach(counter => {
        const target = parseFloat(counter.getAttribute('data-target') || counter.textContent);
        const isPercent = counter.getAttribute('data-is-percent') === 'true';
        
        if (isNaN(target)) return;

        let current = 0;
        const duration = 800; // ms
        const steps = 30;
        const increment = target / steps;
        const stepTime = duration / steps;

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            counter.textContent = Math.round(current) + (isPercent ? '%' : '');
        }, stepTime);
    });
});
