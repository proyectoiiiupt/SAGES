/**
 * trainings_hub.js
 * Lógica cliente del Hub de Navegación por Módulos Rectores – Bloque 1
 *
 * Responsabilidades:
 *  1. Cargar conteos de temas de forma asíncrona al iniciar la vista.
 *  2. Reemplazar los skeletons con los valores reales usando un efecto count-up.
 *  3. Manejar errores de red con feedback visual no intrusivo.
 */

/* ─────────────────────────────────────────────────────────────────────
   MÓDULO PRINCIPAL
   ───────────────────────────────────────────────────────────────────── */
(function () {
    'use strict';

    /* ── Constantes ─────────────────────────────────────────────────── */
    const COUNTS_URL      = '/training/api/counts';
    const COUNT_UP_DURATION = 900; // ms de animación numérica

    /* ── Inicialización ─────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        fetchModuleCounts();
    });

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * Solicita los conteos al backend y orquesta la actualización de la UI.
     */
    function fetchModuleCounts() {
        const csrfToken = document
            .querySelector('meta[name="csrf-token"]')
            ?.getAttribute('content') ?? '';

        fetch(COUNTS_URL, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
            },
            credentials: 'same-origin',
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (!data.success) {
                    throw new Error(data.message || 'Respuesta inválida del servidor.');
                }
                renderCounts(data.counts, data.is_admin);
            })
            .catch(function (err) {
                console.error('[trainings_hub] Error al obtener conteos:', err);
                showCounterError();
            });
    }

    /* ────────────────────────────────────────────────────────────────── */
    /**
     * Actualiza los contenedores de cada tarjeta con los valores reales.
     * @param {Object} counts   - { "<module_id>": { active, total } }
     * @param {boolean} isAdmin - Si el usuario tiene rol admin.
     */
    function renderCounts(counts, isAdmin) {
        const cards = document.querySelectorAll('[data-module-id]');

        cards.forEach(function (counterEl) {
            const moduleId = counterEl.getAttribute('data-module-id');
            const moduleData = counts[moduleId];

            if (!moduleData) {
                counterEl.innerHTML = buildErrorBadge('Sin datos');
                return;
            }

            const active = moduleData.active || 0;
            const total  = moduleData.total  || 0;

            if (isAdmin) {
                counterEl.innerHTML = buildAdminCounter(active, total);
            } else {
                counterEl.innerHTML = buildApplicantCounter(active);
            }

            // Ejecutar animación count-up en los números
            counterEl.querySelectorAll('[data-count-target]').forEach(function (el) {
                const target = parseInt(el.getAttribute('data-count-target'), 10);
                animateCountUp(el, 0, target, COUNT_UP_DURATION);
            });
        });
    }

    /* ── Constructores de HTML ─────────────────────────────────────── */

    /**
     * Genera el HTML del contador para administradores (activos / total).
     */
    function buildAdminCounter(active, total) {
        return [
            '<div class="counter-values">',
            '  <span class="counter-active" data-count-target="' + active + '">0</span>',
            total !== active
                ? '  <span class="counter-separator">/</span>' +
                  '  <span class="counter-total" data-count-target="' + total + '">0</span>'
                : '',
            '</div>',
            '<div>',
            total !== active
                ? '  <div class="counter-label">Temas Activos / Total</div>'
                : '  <div class="counter-label">Temas Activos</div>',
            '</div>',
        ].join('\n');
    }

    /**
     * Genera el HTML del contador para solicitantes (solo activos).
     */
    function buildApplicantCounter(active) {
        return [
            '<div class="counter-values">',
            '  <span class="counter-active" data-count-target="' + active + '">0</span>',
            '</div>',
            '<div>',
            '  <div class="counter-label">Temas Activos</div>',
            '</div>',
        ].join('\n');
    }

    /**
     * Genera una insignia de error discreta.
     */
    function buildErrorBadge(msg) {
        return '<span style="font-size:0.78rem;color:#9ca3af;font-style:italic;">' + msg + '</span>';
    }

    /* ── Animación Count-Up ──────────────────────────────────────────── */

    /**
     * Anima un elemento numérico de `start` a `end` durante `duration` ms.
     * Usa easing ease-out para una sensación dinámica.
     */
    function animateCountUp(el, start, end, duration) {
        if (end === 0) {
            el.textContent = '0';
            return;
        }

        const startTime = performance.now();

        function step(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Easing ease-out cuadrático
            const eased = 1 - Math.pow(1 - progress, 2);
            const current = Math.round(start + (end - start) * eased);
            el.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = end;
            }
        }

        requestAnimationFrame(step);
    }

    /* ── Manejo de errores ────────────────────────────────────────────── */

    /**
     * Muestra un mensaje de error discreto en todos los contenedores
     * de contadores cuando la solicitud falla.
     */
    function showCounterError() {
        document.querySelectorAll('[data-module-id]').forEach(function (el) {
            el.innerHTML = buildErrorBadge('—');
        });
    }

})();
