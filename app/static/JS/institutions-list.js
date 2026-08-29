/**
 * JavaScript para la lista de instituciones
 * Maneja filtros, búsqueda con debounce y paginación
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
    // Limpiar el timeout anterior si existe
    clearTimeout(searchTimeout);
    // Establecer un nuevo timeout de 500ms
    searchTimeout = setTimeout(updateFilters, 500);
}

function updateFilters() {
    const searchName = document.getElementById('search_name').value;
    const institutionType = document.getElementById('institution_type').value;
    const institutionDependency = document.getElementById('institution_dependency').value;
    const status = document.getElementById('status').value;

    let url = new URL(window.location.href);
    url.searchParams.set('search_name', searchName);
    url.searchParams.set('institution_type', institutionType);
    url.searchParams.set('institution_dependency', institutionDependency);
    url.searchParams.set('status', status);

    // Verificar si existe el elemento para determinar el rol del usuario
    const stateIdElement = document.getElementById('state_id');
    const parishIdElement = document.getElementById('parish_id');

    if (stateIdElement) {
        // Super_admin: manejar filtro state_id
        url.searchParams.set('state_id', stateIdElement.value);
        url.searchParams.delete('parish_id');
    } else if (parishIdElement) {
        // State_admin: solo manejar parish_id
        url.searchParams.set('parish_id', parishIdElement.value);
        url.searchParams.delete('state_id');
    }

    // Resetear a página 1 cuando se cambian filtros
    url.searchParams.set('page', '1');

    window.location.href = url.toString();
}

function goToPage(page) {
    let url = new URL(window.location.href);
    url.searchParams.set('page', page);
    
    // Mantener todos los filtros actuales
    const searchName = document.getElementById('search_name').value;
    const institutionType = document.getElementById('institution_type').value;
    const institutionDependency = document.getElementById('institution_dependency').value;
    const status = document.getElementById('status').value;

    url.searchParams.set('search_name', searchName);
    url.searchParams.set('institution_type', institutionType);
    url.searchParams.set('institution_dependency', institutionDependency);
    url.searchParams.set('status', status);

    // Verificar si existe el elemento para determinar el rol del usuario
    const stateIdElement = document.getElementById('state_id');
    const parishIdElement = document.getElementById('parish_id');

    if (stateIdElement) {
        // Super_admin: manejar filtro state_id
        url.searchParams.set('state_id', stateIdElement.value);
        url.searchParams.delete('parish_id');
    } else if (parishIdElement) {
        // State_admin: solo manejar parish_id
        url.searchParams.set('parish_id', parishIdElement.value);
        url.searchParams.delete('state_id');
    }

    window.location.href = url.toString();
}
