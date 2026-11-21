document.addEventListener('DOMContentLoaded', function() {
    // --- Código del calendario (time-formatter.js / es-VE) ---
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        if (typeof formatCurrentDate === 'function') {
            formatCurrentDate(dateElement, 'full-date');
        } else {
            const today = new Date();
            const options = { day: 'numeric', month: 'long', year: 'numeric' };
            dateElement.textContent = today.toLocaleDateString('es-VE', options);
        }
    }

    // --- Buscador y filtros automáticos ---
    const filterForm = document.querySelector('.filter-form');
    
    if (filterForm) {
        // Auto-enviar al cambiar cualquier lista desplegable (select)
        const selects = filterForm.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                filterForm.submit();
            });
        });

        // Auto-enviar al escribir en el buscador (espera 0.8 segundos)
        const searchInput = filterForm.querySelector('.search-input');
        let typingTimer;
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                clearTimeout(typingTimer);
                typingTimer = setTimeout(() => {
                    filterForm.submit();
                }, 800);
            });
        }
    }
});

// Navegación de página con preservación de filtros
window.goToPage = function(page) {
    const url = new URL(window.location.href);
    url.searchParams.set('page', page);
    window.location.href = url.toString();
};