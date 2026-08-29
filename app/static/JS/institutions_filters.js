// Función para actualizar parroquias según el estado seleccionado
function updateParishesByState() {
    const stateSelect = document.getElementById('state_id');
    const parishSelect = document.getElementById('parish_id');
    const selectedStateId = stateSelect.value;
    
    // Limpiar opciones de parroquias
    parishSelect.innerHTML = '<option value="">Parroquia</option>';
    
    if (selectedStateId) {
        // Cargar parroquias del estado seleccionado
        fetch(`/api/parishes-by-state/${selectedStateId}`)
            .then(response => response.json())
            .then(data => {
                data.parishes.forEach(parish => {
                    const option = document.createElement('option');
                    option.value = parish.id;
                    option.textContent = parish.name;
                    parishSelect.appendChild(option);
                });
            })
            .catch(error => console.error('Error loading parishes:', error));
    }
    
    // Actualizar filtros
    updateFilters();
}

// Función para actualizar filtros (existente)
function updateFilters() {
    const url = new URL(window.location);
    
    // Obtener valores de los filtros
    const searchName = document.getElementById('search_name')?.value || '';
    const institutionType = document.getElementById('institution_type')?.value || '';
    const institutionScope = document.getElementById('institution_scope')?.value || '';
    const institutionDependency = document.getElementById('institution_dependency')?.value || '';
    const status = document.getElementById('status')?.value || '';
    const stateId = document.getElementById('state_id')?.value || '';
    const parishId = document.getElementById('parish_id')?.value || '';
    
    // Actualizar URL
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
    
    if (stateId) url.searchParams.set('state_id', stateId);
    else url.searchParams.delete('state_id');
    
    if (parishId) url.searchParams.set('parish_id', parishId);
    else url.searchParams.delete('parish_id');
    
    // Resetear página a 1
    url.searchParams.delete('page');
    
    // Recargar página
    window.location.href = url.toString();
}