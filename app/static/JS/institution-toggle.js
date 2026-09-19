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
                ? `¿Está seguro de que desea <strong>desactivar</strong> esta institución?<br><br>
                   <span style="font-size: 0.9em; color: #6b7280;">Los usuarios afiliados vinculados a esta institución también serán inhabilitados.</span>`
                : `¿Está seguro de que desea <strong>activar</strong> esta institución?<br><br>
                   <span style="font-size: 0.9em; color: #6b7280;">Los usuarios afiliados vinculados a esta institución también serán reactivados.</span>`;
            
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
                    
                    // Construcción profesional del mensaje de éxito
                    let usersNote = '';
                    if (data.affected_users > 0) {
                        const count = data.affected_users;
                        const userText = count === 1 ? '1 usuario afiliado' : `${count} usuarios afiliados`;
                        const actionText = data.new_status === 'Activo'
                            ? (count === 1 ? 'ha sido reactivado' : 'han sido reactivados')
                            : (count === 1 ? 'ha sido inhabilitado' : 'han sido inhabilitados');
                        usersNote = `<br><br><span style="font-size: 0.95em; color: #4b5563;">Asimismo, <strong>${userText}</strong> ${actionText}.</span>`;
                    }
                    
                    const successMessage = `El estado de la institución se actualizó a <strong>${data.new_status}</strong> exitosamente.${usersNote}`;
                    
                    await Swal.fire({
                        title: '¡Operación Exitosa!',
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
