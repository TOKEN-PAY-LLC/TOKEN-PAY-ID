// ===== PARTICLE SYSTEM =====
class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: null, y: null, radius: 150 };
        this.resize();
        this.init();
        this.bindEvents();
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    init() {
        const count = Math.min(120, Math.floor((window.innerWidth * window.innerHeight) / 10000));
        this.particles = [];
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                size: Math.random() * 2 + 0.5,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                opacity: Math.random() * 0.5 + 0.1,
                color: '255, 255, 255'
            });
        }
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
            this.init();
        });

        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        window.addEventListener('mouseout', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.particles.forEach((p, i) => {
            p.x += p.speedX;
            p.y += p.speedY;

            if (p.x < 0 || p.x > this.canvas.width) p.speedX *= -1;
            if (p.y < 0 || p.y > this.canvas.height) p.speedY *= -1;

            // Mouse interaction
            if (this.mouse.x !== null) {
                const dx = p.x - this.mouse.x;
                const dy = p.y - this.mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < this.mouse.radius) {
                    const force = (this.mouse.radius - dist) / this.mouse.radius;
                    p.x += dx * force * 0.02;
                    p.y += dy * force * 0.02;
                }
            }

            // Draw particle
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(${p.color}, ${p.opacity})`;
            this.ctx.fill();

            // Draw connections
            for (let j = i + 1; j < this.particles.length; j++) {
                const p2 = this.particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(p.x, p.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.strokeStyle = `rgba(255, 255, 255, ${0.06 * (1 - dist / 150)})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.stroke();
                }
            }
        });

        requestAnimationFrame(() => this.animate());
    }
}

// ===== SCROLL ANIMATIONS =====
class ScrollAnimator {
    constructor() {
        this.elements = document.querySelectorAll('.animate-on-scroll');
        this.init();
    }

    init() {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                    }
                });
            },
            { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
        );

        this.elements.forEach((el) => observer.observe(el));
    }
}

// ===== COUNTER ANIMATION =====
class CounterAnimator {
    constructor() {
        this.counters = document.querySelectorAll('[data-count]');
        this.animated = new Set();
        this.init();
    }

    init() {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting && !this.animated.has(entry.target)) {
                        this.animated.add(entry.target);
                        this.animateCounter(entry.target);
                    }
                });
            },
            { threshold: 0.5 }
        );

        this.counters.forEach((counter) => observer.observe(counter));
    }

    animateCounter(el) {
        const target = parseInt(el.getAttribute('data-count'));
        const duration = 2000;
        const startTime = performance.now();

        const step = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 4); // easeOutQuart
            const current = Math.floor(eased * target);

            el.textContent = current.toLocaleString('ru-RU');

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = target.toLocaleString('ru-RU');
            }
        };

        requestAnimationFrame(step);
    }
}

// ===== NAVBAR =====
class Navbar {
    constructor() {
        this.navbar = document.getElementById('navbar');
        this.toggle = document.getElementById('navToggle');
        this.links = document.getElementById('navLinks');
        this.init();
    }

    init() {
        // Scroll effect
        window.addEventListener('scroll', () => {
            this.navbar.classList.toggle('scrolled', window.scrollY > 50);
        });

        // Mobile toggle
        this.toggle.addEventListener('click', () => {
            this.links.classList.toggle('active');
            this.toggle.classList.toggle('active');
        });

        // Close on link click
        this.links.querySelectorAll('.nav-link').forEach((link) => {
            link.addEventListener('click', () => {
                this.links.classList.remove('active');
                this.toggle.classList.remove('active');
            });
        });

        // Active link on scroll
        const sections = document.querySelectorAll('section[id]');
        window.addEventListener('scroll', () => {
            const scrollY = window.scrollY + 100;
            sections.forEach((section) => {
                const top = section.offsetTop;
                const height = section.offsetHeight;
                const id = section.getAttribute('id');
                const link = this.links.querySelector(`a[href="#${id}"]`);
                if (link) {
                    if (scrollY >= top && scrollY < top + height) {
                        link.style.color = '#e8e8f0';
                    } else {
                        link.style.color = '';
                    }
                }
            });
        });
    }
}

// ===== SMOOTH SCROLL =====
document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Contact form handled by initContactForm() in DOMContentLoaded

// ===== MAGNETIC BUTTONS =====
document.querySelectorAll('.btn-primary').forEach((btn) => {
    btn.addEventListener('mousemove', function (e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        this.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
    });

    btn.addEventListener('mouseleave', function () {
        this.style.transform = '';
    });
});

// ===== TILT EFFECT ON CARDS =====
document.querySelectorAll('.service-card, .about-card').forEach((card) => {
    card.addEventListener('mousemove', function (e) {
        const rect = this.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        this.style.transform = `perspective(800px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg) translateY(-4px)`;
    });
    card.addEventListener('mouseleave', function () {
        this.style.transform = '';
    });
});

// ===== PARALLAX ON HERO ORBS =====
window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    document.querySelectorAll('.hero-orb').forEach((orb, i) => {
        const speed = (i + 1) * 0.15;
        orb.style.transform = `translateY(${scrollY * speed}px)`;
    });
});

// ===== LANGUAGE (auto IP + manual toggle) =====
class LanguageManager {
    constructor() {
        this.lang = localStorage.getItem('tp_lang') || null;
        this.btn = document.getElementById('langToggle');
        this.label = this.btn ? this.btn.querySelector('.lang-label') : null;
        if (this.lang) { this.apply(); } else { this.lang = 'ru'; this.autoDetect(); }
        if (this.btn) this.btn.addEventListener('click', () => { this.lang = this.lang === 'ru' ? 'en' : 'ru'; localStorage.setItem('tp_lang', this.lang); this.apply(); });
        this.updateLabel();
    }
    async autoDetect() {
        try { const r = await fetch('https://ipapi.co/json/', {signal:AbortSignal.timeout(3000)}); const d = await r.json(); if (d.country_code && d.country_code !== 'RU') { this.lang = 'en'; this.apply(); } } catch(e) {}
    }
    apply() {
        document.querySelectorAll('[data-ru][data-en]').forEach(el => { const t = el.getAttribute('data-'+this.lang); if(t){if(el.childElementCount===0){el.textContent=t}else{const n=Array.from(el.childNodes).find(n=>n.nodeType===3&&n.textContent.trim());if(n)n.textContent=t}} });
        this.updateLabel();
    }
    updateLabel() { if (this.label) this.label.textContent = this.lang === 'ru' ? 'RU' : 'EN'; }
}

// ===== THEME (auto browser + manual toggle) =====
class ThemeManager {
    constructor() {
        this.btn = document.getElementById('themeToggle');
        const saved = localStorage.getItem('tp_theme');
        if (saved) { this.set(saved); } else { const mq = window.matchMedia('(prefers-color-scheme: light)'); this.set(mq.matches ? 'light' : 'dark'); }
        if (this.btn) this.btn.addEventListener('click', () => { const next = document.body.classList.contains('light') ? 'dark' : 'light'; localStorage.setItem('tp_theme', next); this.set(next); });
    }
    set(theme) {
        document.body.classList.toggle('light', theme === 'light');
        if (this.btn) { const sun = this.btn.querySelector('.icon-sun'); const moon = this.btn.querySelector('.icon-moon'); if(sun&&moon){sun.style.display=theme==='light'?'none':'block';moon.style.display=theme==='light'?'block':'none';} }
    }
}

// ===== ANTI-DOWNLOAD PROTECTION =====
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => {
    if (e.ctrlKey && (e.key === 's' || e.key === 'S' || e.key === 'u' || e.key === 'U')) e.preventDefault();
    if (e.ctrlKey && e.shiftKey && (e.key === 'i' || e.key === 'I' || e.key === 'j' || e.key === 'J')) e.preventDefault();
});

// ===== CONTACT FORM =====
function initContactForm() {
    const form = document.getElementById('contactForm');
    if (!form) return;
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const origHTML = btn.innerHTML;
        btn.disabled = true;
        const _l = localStorage.getItem('tp_lang') || 'ru';
        btn.innerHTML = '<span>' + (_l==='en'?'Sending...':'Отправка...') + '</span>';
        try {
            const res = await fetch('/api/v1/contact', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: form.querySelector('#name').value,
                    email: form.querySelector('#email').value,
                    message: form.querySelector('#message').value
                })
            });
            if (res.ok) {
                btn.innerHTML = '<span>✓ ' + (_l==='en'?'Sent':'Отправлено') + '</span>';
                form.reset();
                setTimeout(() => { btn.innerHTML = origHTML; btn.disabled = false; }, 3000);
            } else {
                btn.innerHTML = '<span>' + (_l==='en'?'Error':'Ошибка') + '</span>';
                setTimeout(() => { btn.innerHTML = origHTML; btn.disabled = false; }, 2000);
            }
        } catch(err) {
            window.location.href = 'mailto:info@tokenpay.space?subject=' + encodeURIComponent(_l==='en'?'Feedback':'Обратная связь') + '&body=' + encodeURIComponent(form.querySelector('#message').value);
            btn.innerHTML = origHTML; btn.disabled = false;
        }
    });
}

// ===== AUTH NAV CHECK =====
function _escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function updateNavAuth() {
    const token = localStorage.getItem('tpid_token') || sessionStorage.getItem('tpid_token');
    const refreshTok = localStorage.getItem('tpid_refresh') || sessionStorage.getItem('tpid_refresh');
    const user = (() => { try { return JSON.parse(localStorage.getItem('tpid_user') || sessionStorage.getItem('tpid_user') || 'null'); } catch(e) { return null; } })();
    if (!token && !refreshTok) return;

    const _lang = localStorage.getItem('tp_lang') || (navigator.language && navigator.language.startsWith('en') ? 'en' : 'ru');
    const label = _lang === 'en' ? 'Dashboard' : 'Личный кабинет';

    // Desktop .nav-auth
    const navAuth = document.querySelector('.nav-auth');
    if (navAuth) {
        navAuth.innerHTML = `<a href="/dashboard" class="nav-btn nav-btn-white" style="display:flex;align-items:center;gap:6px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span>${user ? _escHtml((user.name || '').split(' ')[0]) || label : label}</span>
        </a>`;
    }

    // Mobile .nav-mobile-auth
    const mobileAuth = document.querySelector('.nav-mobile-auth');
    if (mobileAuth) {
        mobileAuth.innerHTML = `<a href="/dashboard" class="btn btn-primary" style="width:100%;justify-content:center">${label}</a>`;
    }

    // Validate token silently; if invalid try refresh
    fetch('/api/v1/auth/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) })
        .then(r => r.json()).then(d => {
            if (d.valid) return;
            if (refreshTok) {
                fetch('/api/v1/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshTok }) })
                    .then(r => r.json()).then(data => {
                        if (data.accessToken) {
                            const store = sessionStorage.getItem('tpid_refresh') ? sessionStorage : localStorage;
                            store.setItem('tpid_token', data.accessToken);
                            if (data.refreshToken) store.setItem('tpid_refresh', data.refreshToken);
                        } else {
                            // Both invalid — clear and show login buttons
                            ['tpid_token','tpid_refresh','tpid_user','tp_token'].forEach(k => { localStorage.removeItem(k); sessionStorage.removeItem(k); });
                            if (navAuth) navAuth.innerHTML = `<a href="/login" class="nav-btn nav-btn-ghost" data-ru="Войти" data-en="Sign In">Войти</a><a href="/register" class="nav-btn nav-btn-white" data-ru="Регистрация" data-en="Sign Up">Регистрация</a>`;
                            if (mobileAuth) mobileAuth.innerHTML = `<a href="/login" class="btn btn-secondary" style="width:100%;justify-content:center">Войти</a><a href="/register" class="btn btn-primary" style="width:100%;justify-content:center">Регистрация</a>`;
                        }
                    }).catch(() => {});
            }
        }).catch(() => {});
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particles');
    if (canvas) new ParticleSystem(canvas);

    new ScrollAnimator();
    new CounterAnimator();
    new Navbar();
    new LanguageManager();
    new ThemeManager();
    initContactForm();
    updateNavAuth();
});

// ===== CSS for spin animation (injected) =====
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
