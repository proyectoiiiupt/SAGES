/**
 * JavaScript para manejar el toggle de estatus de instituciones
 * Maneja el botón de activar/desactivar en la página de detalle de institución
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
                    
                    // Show success message
                    alert(data.message);
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error al cambiar el estatus de la institución');
            } finally {
                // Re-enable button
                this.disabled = false;
            }
        });
    }
});
