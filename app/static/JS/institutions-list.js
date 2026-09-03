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
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(updateFilters, 500);
}

function updateFilters() {
    let url = new URL(window.location.href);

    const searchName = document.getElementById('search_name')?.value || '';
    const institutionType = document.getElementById('institution_type')?.value || '';
    const institutionScope = document.getElementById('institution_scope')?.value || '';
    const institutionDependency = document.getElementById('institution_dependency')?.value || '';
    const status = document.getElementById('status')?.value || '';
    const stateIdElement = document.getElementById('state_id');
    const parishIdElement = document.getElementById('parish_id');

    if (searchName) url.searchParams.set('search_name', searchName);
    else url.searchParams.delete('search_name');

    if (institutionType) url.searchParams.set('institution_type', institutionType);
    else url.searchParams.delete('institution_type');

    if (institutionScope) url.searchParams.set('institution_scope', institutionScope);
    else url.searchParams.delete('institution_scope');

    if (institutionDependency) url.searchParams.set('institution_dependency', institutionDependency);
    else url.searchParams.delete('institution_dependency');

    if (status) url.searchParams.set('status', status);
    else url.searchParams.delete('status');

    if (stateIdElement && stateIdElement.value) {
        url.searchParams.set('state_id', stateIdElement.value);
        url.searchParams.delete('parish_id');
    } else if (parishIdElement && parishIdElement.value) {
        url.searchParams.set('parish_id', parishIdElement.value);
        url.searchParams.delete('state_id');
    } else {
        url.searchParams.delete('state_id');
        url.searchParams.delete('parish_id');
    }

    // Resetear a página 1 cuando se cambian filtros
    url.searchParams.set('page', '1');

    window.location.href = url.toString();
}

function goToPage(page) {
    let url = new URL(window.location.href);
    url.searchParams.set('page', page);
    window.location.href = url.toString();
}
