/**
 * public.js — CORPOELEC | Homepage Pública
 * Lógica interactiva: Menú móvil, Navbar scroll, Carrusel,
 * Acordeón FAQ, Animaciones Reveal (IntersectionObserver).
 * Sin dependencias externas (CDN ni librerías).
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. MENÚ MÓVIL
    // =========================================================
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu    = document.getElementById('mobile-menu');

    if (mobileMenuBtn && mobileMenu) {
        const mobileLinks = mobileMenu.querySelectorAll('a');

        const toggleMenu = () => {
            mobileMenu.classList.toggle('open');
        };

        mobileMenuBtn.addEventListener('click', toggleMenu);

        mobileLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (mobileMenu.classList.contains('open')) toggleMenu();
            });
        });
    }

    // =========================================================
    // 2. NAVBAR — Efecto al hacer scroll
    // =========================================================
    const navbar = document.getElementById('navbar');

    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        }, { passive: true });
    }

    // =========================================================
    // 3. CARRUSEL "EL SISTEMA"
    // =========================================================
    const slides = document.querySelectorAll('.system-slide');
    const dots   = document.querySelectorAll('.nav-dot');

    if (slides.length > 0 && dots.length > 0) {
        let currentSlideIdx = 0;
        let slideInterval;

        const activateSlide = (index) => {
            slides.forEach((slide, i) => {
                if (i === index) {
                    slide.classList.add('slide-active');
                } else {
                    slide.classList.remove('slide-active');
                }
            });

            dots.forEach((dot, i) => {
                if (i === index) {
                    dot.classList.add('dot-active');
                } else {
                    dot.classList.remove('dot-active');
                }
            });

            currentSlideIdx = index;
        };

        const startSlideShow = () => {
            slideInterval = setInterval(() => {
                const nextIdx = (currentSlideIdx + 1) % slides.length;
                activateSlide(nextIdx);
            }, 5000);
        };

        const resetSlideShow = () => {
            clearInterval(slideInterval);
            startSlideShow();
        };

        dots.forEach((dot) => {
            dot.addEventListener('click', () => {
                const idx = parseInt(dot.getAttribute('data-index'), 10);
                activateSlide(idx);
                resetSlideShow();
            });
        });

        activateSlide(0);
        startSlideShow();
    }

    // =========================================================
    // 4. ACORDEÓN FAQ
    // =========================================================
    const faqQuestions = document.querySelectorAll('.faq-question');

    faqQuestions.forEach(button => {
        button.addEventListener('click', () => {
            const faqItem = button.closest('.faq-item');
            const answer  = faqItem.querySelector('.faq-answer');
            const icon    = faqItem.querySelector('.faq-icon');
            const isOpen  = faqItem.classList.contains('active');

            document.querySelectorAll('.faq-item').forEach(otherItem => {
                otherItem.classList.remove('active');
                const otherAnswer = otherItem.querySelector('.faq-answer');
                if (otherAnswer) otherAnswer.style.maxHeight = null;
                otherItem.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
            });

            if (!isOpen) {
                faqItem.classList.add('active');
                answer.style.maxHeight = answer.scrollHeight + 'px';
                button.setAttribute('aria-expanded', 'true');
            }
        });
    });

    // =========================================================
    // 5. REVEAL AL SCROLL (IntersectionObserver)
    // =========================================================
    const revealElements = document.querySelectorAll('.reveal');

    if (revealElements.length > 0) {
        const revealOptions = {
            threshold: 0.15,
            rootMargin: '0px 0px -50px 0px'
        };

        const revealObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('active');
                    observer.unobserve(entry.target);
                }
            });
        }, revealOptions);

        revealElements.forEach(el => {
            revealObserver.observe(el);
        });
    }

    // =========================================================
    // 6. NAVBAR — Link activo según sección visible
    // =========================================================
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
    const trackedSections = ['#home', '#system', '#catalog', '#faq', '#join'];

    if (navLinks.length > 0) {
        const ratioMap = {};
        trackedSections.forEach(id => { ratioMap[id] = 0; });

        let rafPending = false;

        const updateActiveLink = () => {
            let maxRatio = 0;
            let activeId = trackedSections[0];

            trackedSections.forEach(id => {
                if (ratioMap[id] > maxRatio) {
                    maxRatio = ratioMap[id];
                    activeId = id;
                }
            });

            navLinks.forEach(link => {
                if (link.getAttribute('href') === activeId) {
                    link.classList.add('nav-active');
                } else {
                    link.classList.remove('nav-active');
                }
            });

            rafPending = false;
        };

        const sectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const id = '#' + entry.target.id;
                if (ratioMap.hasOwnProperty(id)) {
                    ratioMap[id] = entry.intersectionRatio;
                }
            });

            if (!rafPending) {
                rafPending = true;
                requestAnimationFrame(updateActiveLink);
            }
        }, {
            threshold: Array.from({ length: 21 }, (_, i) => i * 0.05)
        });

        trackedSections.forEach(id => {
            const el = document.querySelector(id);
            if (el) sectionObserver.observe(el);
        });

        // Estado inicial: marcar Inicio como activo
        if (navLinks[0]) navLinks[0].classList.add('nav-active');
    }
});
