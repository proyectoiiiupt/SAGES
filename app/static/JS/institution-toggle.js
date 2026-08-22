/**
 * JavaScript para manejar el toggle de estatus de instituciones
 * Maneja el botón de activar/desactivar en la página de detalle de institución
 * Usa SweetAlert2 para confirmaciones y mensajes de éxito
 */

document.addEventListener('DOMContentLoaded', function() {
    // Set dynamic date in Spanish format
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        const today = new Date();
        const formattedDate = today.toLocaleDateString('es-ES', options);
        dateElement.textContent = formattedDate.replace(' de 20', ', 20');
    }

    const toggleBtn = document.getElementById('toggle-btn');
    const statusBadge = document.getElementById('status-badge');
    
    // Verificar si el botón existe antes de agregar el event listener
    if (toggleBtn && statusBadge) {
        // Set initial state
        const currentStatus = toggleBtn.dataset.currentStatus;
        if (currentStatus === 'STAT-001') {
            toggleBtn.classList.add('active');
        }
        
        toggleBtn.addEventListener('click', async function() {
            const institutionId = this.dataset.institutionId;
            const isActive = this.classList.contains('active');
            
            // Determinar el mensaje según el estado actual
            const action = isActive ? 'desactivar' : 'activar';
            const newStatus = isActive ? 'Inactivo' : 'Activo';
            
            // Mensaje de confirmación con SweetAlert2
            const confirmMessage = isActive 
                ? `¿Está seguro que desea desactivar esta institución? <br><br>
                   <strong>Esto también desactivará a todos los usuarios afiliados a la institución.</strong>`
                : `¿Está seguro que desea activar esta institución? <br><br>
                   <strong>Esto también activará a todos los usuarios afiliados a la institución.</strong>`;
            
            const result = await Swal.fire({
                title: `¿${action.charAt(0).toUpperCase() + action.slice(1)} institución?`,
                html: confirmMessage,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: isActive ? '#d33' : '#3085d6',
                cancelButtonColor: '#6c757d',
                confirmButtonText: `Sí, ${action}`,
                cancelButtonText: 'Cancelar',
                reverseButtons: true
            });
            
            // Si el usuario cancela, no hacer nada
            if (!result.isConfirmed) {
                return;
            }
            
            // Disable button during request
            this.disabled = true;
            
            try {
                const response = await fetch(`/institutions/${institutionId}/toggle-status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Update button state
                    if (data.new_status === 'Activo') {
                        toggleBtn.classList.add('active');
                    } else {
                        toggleBtn.classList.remove('active');
                    }
                    
                    // Update status badge
                    statusBadge.textContent = data.new_status;
                    statusBadge.className = `status-badge status-${data.status_code}`;
                    
                    // Update data attribute
                    toggleBtn.dataset.currentStatus = data.status_code;
                    
                    // Mensaje de éxito con SweetAlert2
                    const successMessage = data.affected_users > 0
                        ? `Institución cambiada a ${data.new_status} exitosamente.<br><br>
                           <strong>${data.affected_users} usuario(s) afiliado(s) también fueron ${data.new_status.toLowerCase()}ados.</strong>`
                        : `Institución cambiada a ${data.new_status} exitosamente.`;
                    
                    await Swal.fire({
                        title: '¡Éxito!',
                        html: successMessage,
                        icon: 'success',
                        confirmButtonColor: '#3085d6',
                        confirmButtonText: 'Aceptar'
                    });
                } else {
                    // Mensaje de error con SweetAlert2
                    await Swal.fire({
                        title: 'Error',
                        text: data.message,
                        icon: 'error',
                        confirmButtonColor: '#d33',
                        confirmButtonText: 'Aceptar'
                    });
                }
            } catch (error) {
                console.error('Error:', error);
                // Mensaje de error de conexión con SweetAlert2
                await Swal.fire({
                    title: 'Error de conexión',
                    text: 'Error al cambiar el estatus de la institución. Por favor, intente nuevamente.',
                    icon: 'error',
                    confirmButtonColor: '#d33',
                    confirmButtonText: 'Aceptar'
                });
            } finally {
                // Re-enable button
                this.disabled = false;
            }
        });
    }
});
