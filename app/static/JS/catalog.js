/*
JavaScript para el Catálogo de Formaciones
Funcionalidad: Filtros con debounce, gestión de URL y fecha dinámica
*/

let searchTimeout;

document.addEventListener('DOMContentLoaded', function () {
    // Set dynamic date in Spanish format
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateElement.textContent = formattedDate.replace(' de 20', ', 20');
    }
});

function debouncedSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(updateFilters, 500);
}

function updateFilters() {
    const searchName = document.getElementById('search_name') ? document.getElementById('search_name').value : '';
    const category = document.getElementById('category') ? document.getElementById('category').value : '';
    const status = document.getElementById('status') ? document.getElementById('status').value : '';

    let url = new URL(window.location.href);
    
    if (searchName) {
        url.searchParams.set('search_name', searchName);
    } else {
        url.searchParams.delete('search_name');
    }
    
    if (category) {
        url.searchParams.set('category', category);
    } else {
        url.searchParams.delete('category');
    }
    
    if (status) {
        url.searchParams.set('status', status);
    } else {
        url.searchParams.delete('status');
    }

    url.searchParams.set('page', '1');
    window.location.href = url.toString();
}

function goToPage(page) {
    let url = new URL(window.location.href);
    url.searchParams.set('page', page);
    
    const searchName = document.getElementById('search_name') ? document.getElementById('search_name').value : '';
    const category = document.getElementById('category') ? document.getElementById('category').value : '';
    const status = document.getElementById('status') ? document.getElementById('status').value : '';

    if (searchName) {
        url.searchParams.set('search_name', searchName);
    } else {
        url.searchParams.delete('search_name');
    }
    
    if (category) {
        url.searchParams.set('category', category);
    } else {
        url.searchParams.delete('category');
    }
    
    if (status) {
        url.searchParams.set('status', status);
    } else {
        url.searchParams.delete('status');
    }

    window.location.href = url.toString();
}