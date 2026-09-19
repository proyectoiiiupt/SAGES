document.addEventListener('DOMContentLoaded', function() {
    // --- Código del calendario ---
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateElement.textContent = formattedDate.replace(' de 20', ', 20');
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