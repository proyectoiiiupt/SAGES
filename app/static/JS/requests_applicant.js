/**
 * app/static/JS/requests_applicant.js
 * Manejo de interactividad y accesibilidad para el panel de solicitudes del solicitante.
 */

'use strict';

document.addEventListener('DOMContentLoaded', function () {
    // Seleccionamos todas las tarjetas de solicitud interactiva
    const requestCards = document.querySelectorAll('.request-card');

    /**
     * Extrae el atributo data-url del elemento y redirige al usuario.
     * @param {HTMLElement} element - La tarjeta HTML seleccionada.
     */
    const navigateToRequest = (element) => {
        const url = element.getAttribute('data-url');
        if (url && url !== '#') {
            window.location.href = url;
        }
    };

    // Aplicar los listeners de eventos a cada tarjeta
    requestCards.forEach(card => {
        // 1. Manejo del clic convencional del ratón
        card.addEventListener('click', function () {
            navigateToRequest(this);
        });

        // 2. Manejo de Accesibilidad Institucional (Navegación por Teclado - SR-NF-002)
        card.addEventListener('keydown', function (event) {
            // Permitir que la tecla "Enter" o "Espacio" actúen como un clic
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault(); // Evitar el scroll indeseado de la página al usar espacio
                navigateToRequest(this);
            }
        });
    });
});
