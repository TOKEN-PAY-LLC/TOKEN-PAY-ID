// ===== STAR SKY BACKGROUND =====
class StarSky {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.stars = [];
        this._fc = 0;
        this._dpr = Math.min(window.devicePixelRatio || 1, 2);
        this._isLight = document.body && document.body.classList.contains('light');
        this._w = 0;
        this._h = 0;
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.draw();
    }

    resize() {
        const dpr = this._dpr;
        this._w = window.innerWidth;
        this._h = window.innerHeight;
        this.canvas.width = this._w * dpr;
        this.canvas.height = this._h * dpr;
        this.canvas.style.width = this._w + 'px';
        this.canvas.style.height = this._h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const n = Math.min(200, Math.floor(this._w * this._h / 6000));
        this.stars = [];
        for (let i = 0; i < n; i++) {
            this.stars.push({
                x: Math.random() * this._w,
                y: Math.random() * this._h,
                r: Math.random() * 1.2 + 0.2,
                o: Math.random() * 0.5 + 0.12,
                dx: (Math.random() - 0.5) * 0.18,
                dy: (Math.random() - 0.5) * 0.18,
                phase: Math.random() * Math.PI * 2
            });
        }
    }

    draw() {
        const ctx = this.ctx;
        const w = this._w, h = this._h;
        ctx.clearRect(0, 0, w, h);

        // Light theme: black stars; Dark theme: white stars
        const rgb = this._isLight ? '0,0,0' : '255,255,255';
        const alphaMultiplier = this._isLight ? 0.55 : 1;

        for (let i = 0; i < this.stars.length; i++) {
            const s = this.stars[i];
            s.x += s.dx;
            s.y += s.dy;
            if (s.x < 0 || s.x > w) s.dx *= -1;
            if (s.y < 0 || s.y > h) s.dy *= -1;

            s.phase += 0.006;
            const a = s.o * (0.85 + 0.15 * Math.sin(s.phase)) * alphaMultiplier;

            ctx.beginPath();
            ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(' + rgb + ',' + a + ')';
            ctx.fill();
        }

        if (++this._fc % 90 === 0) {
            this._isLight = document.body && document.body.classList.contains('light');
        }
        requestAnimationFrame(() => this.draw());
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
        this.overlay = document.getElementById('navOverlay');
        if (!this.navbar || !this.toggle || !this.links) return;
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
            if (this.overlay) this.overlay.classList.toggle('active');
            document.body.style.overflow = this.links.classList.contains('active') ? 'hidden' : '';
        });

        // Close on link click
        this.links.querySelectorAll('.nav-link').forEach((link) => {
            link.addEventListener('click', () => {
                this.links.classList.remove('active');
                this.toggle.classList.remove('active');
                if (this.overlay) this.overlay.classList.remove('active');
                document.body.style.overflow = '';
            });
        });

        // Close on overlay click
        if (this.overlay) {
            this.overlay.addEventListener('click', () => {
                this.links.classList.remove('active');
                this.toggle.classList.remove('active');
                this.overlay.classList.remove('active');
                document.body.style.overflow = '';
            });
        }

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

// ===== LANGUAGE (auto IP via server API + manual 3-way toggle: RU → EN → ZH) =====
// Centralized translation dictionary — maps CSS selectors to {en, zh} translations.
// Russian is the default in HTML, so only en/zh are needed here.
const _T = [
    // ── About section ──
    ['#about .section-tag', {en:'About Us',zh:'关于我们'}],
    ['#about .section-title', {en:'Who We Are',zh:'我们是谁'}],
    ['#about .section-subtitle', {en:'TOKEN PAY LLC is a technology company building its own products in AI, fintech, and network technologies',zh:'TOKEN PAY LLC 是一家科技公司，在人工智能、金融科技和网络技术领域开发自主产品'}],
    ['#about .about-card:nth-child(1) h3', {en:'Artificial Intelligence',zh:'人工智能'}],
    ['#about .about-card:nth-child(1) p', {en:'We build our own AI solutions: intelligent data processing, automation, and machine learning.',zh:'我们开发自主AI解决方案：智能数据处理、自动化和机器学习。'}],
    ['#about .about-card:nth-child(2) h3', {en:'Fintech & Crypto',zh:'金融科技与加密'}],
    ['#about .about-card:nth-child(2) p', {en:'We build our own solutions in cryptocurrency, blockchain, and digital financial instruments.',zh:'我们在加密货币、区块链和数字金融工具领域开发自主解决方案。'}],
    ['#about .about-card:nth-child(3) h3', {en:'Network Technologies',zh:'网络技术'}],
    ['#about .about-card:nth-child(3) p', {en:'We build our own network infrastructure: servers, secure access systems, and distributed architectures.',zh:'我们构建自主网络基础设施：服务器、安全访问系统和分布式架构。'}],
    ['#about .about-card:nth-child(4) p', {en:'Unified authentication with OAuth 2.0, REST API, and SDK. Third-party developers integrate via our open API.',zh:'统一认证系统，支持OAuth 2.0、REST API和SDK。第三方开发者通过开放API集成。'}],
    // ── Directions section ──
    ['#services .section-tag', {en:'Directions',zh:'业务方向'}],
    ['#services .section-title', {en:'What We Do',zh:'我们做什么'}],
    ['#services .section-subtitle', {en:'Three key directions where we build our own products and technologies',zh:'我们开发自主产品和技术的三个关键方向'}],
    ['#services .service-card:nth-child(1) h3', {en:'Artificial Intelligence',zh:'人工智能'}],
    ['#services .service-card:nth-child(1) > p', {en:'We research and implement AI in our products: NLP, computer vision, predictive analytics, and process automation.',zh:'我们研究并将AI应用于产品：自然语言处理、计算机视觉、预测分析和流程自动化。'}],
    ['#services .service-card:nth-child(2) h3', {en:'Fintech & Crypto',zh:'金融科技与加密'}],
    ['#services .service-card:nth-child(2) > p', {en:'Our own solutions in crypto, blockchain, digital identity, and authentication with open API.',zh:'加密货币、区块链、数字身份和开放API认证的自主解决方案。'}],
    ['#services .service-card:nth-child(3) h3', {en:'Network Technologies',zh:'网络技术'}],
    ['#services .service-card:nth-child(3) > p', {en:'We build and maintain server infrastructure: distributed systems, secure channels, monitoring, and fault tolerance.',zh:'构建和维护服务器基础设施：分布式系统、安全通信、监控和容错。'}],
    // ── Products section ──
    ['#products .section-tag', {en:'Products',zh:'产品'}],
    ['#products .section-title', {en:'Our Products',zh:'我们的产品'}],
    ['#products .section-subtitle', {en:'Flagship solutions we have built and continue to develop',zh:'我们打造并持续发展的旗舰产品'}],
    ['#products .product-card:nth-child(1) .product-tagline', {en:'Unified Authentication System',zh:'统一认证系统'}],
    ['#products .product-card:nth-child(1) .product-description', {en:'Open identity platform. OAuth 2.0, OpenID Connect, REST API, SDKs for JS/Python/Go, 2FA, webhooks, and monitoring. Get your API key in the dashboard.',zh:'开放身份平台。OAuth 2.0、OpenID Connect、REST API、JS/Python/Go SDK、双因素认证、Webhook和监控。在控制面板获取API密钥。'}],
    ['#products .product-card:nth-child(1) .product-feature:nth-child(2) span', {en:'Public REST API',zh:'公共REST API'}],
    ['#products .product-card:nth-child(1) .product-feature:nth-child(4) span', {en:'Two-Factor Protection',zh:'双因素认证'}],
    ['#products .product-card:nth-child(1) .btn', {en:'API Documentation',zh:'API 文档'}],
    ['#products .product-card:nth-child(2) .product-tagline', {en:'Secure Internet Access',zh:'安全互联网访问'}],
    ['#products .product-card:nth-child(2) .product-description', {en:'Our own VPN service with high-speed servers, modern encryption protocols, and full traffic protection.',zh:'自主VPN服务，配备高速服务器、现代加密协议和全面流量保护。'}],
    ['#products .product-card:nth-child(2) .product-feature:nth-child(3) span', {en:'NL & RU Servers',zh:'荷兰和俄罗斯服务器'}],
    ['#products .product-card:nth-child(2) .product-feature:nth-child(4) span', {en:'Telegram Bot Control',zh:'Telegram机器人管理'}],
    // ── Advantages section ──
    ['#advantages .section-tag', {en:'Advantages',zh:'优势'}],
    ['#advantages .section-title', {en:'Why Choose Us',zh:'为什么选择我们'}],
    ['#advantages .advantage-item:nth-child(1) .advantage-content h4', {en:'Own Products',zh:'自主产品'}],
    ['#advantages .advantage-item:nth-child(1) .advantage-content p', {en:'We don\'t take orders — we create our own technologies. Every product is born and developed by our team.',zh:'我们不接受外包——我们创造自己的技术。每个产品都由我们的团队打造和发展。'}],
    ['#advantages .advantage-item:nth-child(2) .advantage-content h4', {en:'Open API',zh:'开放API'}],
    ['#advantages .advantage-item:nth-child(2) .advantage-content p', {en:'Our authentication system is available for integration via public REST API and SDKs for JS, Python, and Go.',zh:'我们的认证系统可通过公共REST API和JS、Python、Go SDK进行集成。'}],
    ['#advantages .advantage-item:nth-child(3) .advantage-content h4', {en:'Independence',zh:'独立性'}],
    ['#advantages .advantage-item:nth-child(3) .advantage-content p', {en:'Our own infrastructure, our own authentication. We don\'t depend on third-party providers.',zh:'自主基础设施，自主认证系统。不依赖第三方供应商。'}],
    ['#advantages .advantage-item:nth-child(4) .advantage-content h4', {en:'Security',zh:'安全性'}],
    ['#advantages .advantage-item:nth-child(4) .advantage-content p', {en:'Data encryption, 2FA, brute-force protection, and full compliance with 152-FZ.',zh:'数据加密、双因素认证、暴力破解防护，完全符合152-FZ法规。'}],
    ['#advantages .advantage-item:nth-child(5) .advantage-content h4', {en:'99.9% Uptime',zh:'99.9% 正常运行'}],
    ['#advantages .advantage-item:nth-child(5) .advantage-content p', {en:'Highly available server infrastructure. 24/7 monitoring and automatic recovery.',zh:'高可用服务器基础设施。24/7监控和自动恢复。'}],
    ['#advantages .advantage-item:nth-child(6) .advantage-content h4', {en:'Documentation',zh:'文档'}],
    ['#advantages .advantage-item:nth-child(6) .advantage-content p', {en:'Detailed API documentation, integration examples, and ready-made SDKs — everything for quick integration.',zh:'详细的API文档、集成示例和现成SDK——快速集成所需的一切。'}],
    // ── Requisites section ──
    ['#requisites .section-tag', {en:'Requisites',zh:'公司信息'}],
    ['#requisites .section-title', {en:'Legal Information',zh:'法律信息'}],
    ['#requisites .section-subtitle', {en:'Full details of TOKEN PAY LLC',zh:'TOKEN PAY LLC 完整信息'}],
    ['#requisites .requisites-section:nth-child(1) h3', {en:'Company Information',zh:'公司信息'}],
    ['#requisites .requisites-section:nth-child(3) h3', {en:'Bank Details',zh:'银行信息'}],
    // ── Contact section ──
    ['#contact .section-tag', {en:'Contact',zh:'联系'}],
    ['#contact .section-title', {en:'Contact Us',zh:'联系我们'}],
    ['#contact .section-subtitle', {en:'Write to us — your message will be sent to info@tokenpay.space',zh:'写信给我们——您的消息将发送至 info@tokenpay.space'}],
    ['#contact .contact-item:nth-child(1) h4', {en:'Address',zh:'地址'}],
    ['#contact .contact-item:nth-child(1) p', {en:'Murino, Leningrad Region',zh:'穆里诺，列宁格勒州'}],
    // ── Footer ──
    ['.footer-bottom p', {en:'\u00A9 2025\u20132026 TOKEN PAY LLC. All rights reserved. INN 4706094495 OGRN 1254700021267',zh:'\u00A9 2025\u20132026 TOKEN PAY LLC. \u7248\u6743\u6240\u6709\u3002INN 4706094495 OGRN 1254700021267'}],
];
// Store Russian originals on first run
const _T_RU = {};

class LanguageManager {
    constructor() {
        this.langs = ['ru', 'en', 'zh'];
        this.lang = localStorage.getItem('tp_lang') || null;
        this.btn = document.getElementById('langToggle');
        this.label = this.btn ? this.btn.querySelector('.lang-label') : null;
        if (!this.lang) { this.lang = 'ru'; }
        this.apply();
        if (this.btn) this.btn.addEventListener('click', () => {
            const idx = this.langs.indexOf(this.lang);
            this.lang = this.langs[(idx + 1) % this.langs.length];
            localStorage.setItem('tp_lang', this.lang);
            document.cookie = 'tp_lang=' + this.lang + ';path=/;max-age=31536000;SameSite=Lax';
            this.apply();
        });
        this.updateLabel();
    }
    apply() {
        const lang = this.lang;
        // 1) Elements with data-ru/data-en/data-zh attributes (inline translations)
        document.querySelectorAll('[data-ru]').forEach(el => {
            const t = el.getAttribute('data-' + lang);
            if (t) {
                if (el.childElementCount === 0) { el.textContent = t; }
                else { const n = Array.from(el.childNodes).find(n => n.nodeType === 3 && n.textContent.trim()); if (n) n.textContent = t; }
            }
        });
        // 2) Centralized dictionary translations
        for (const [sel, tr] of _T) {
            const el = document.querySelector(sel);
            if (!el) continue;
            // Save Russian original on first encounter
            if (!_T_RU[sel]) _T_RU[sel] = el.textContent.trim();
            const text = lang === 'ru' ? _T_RU[sel] : (tr[lang] || _T_RU[sel]);
            if (el.childElementCount === 0) { el.textContent = text; }
            else {
                const n = Array.from(el.childNodes).find(n => n.nodeType === 3 && n.textContent.trim());
                if (n) n.textContent = text;
            }
        }
        document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
        // Update page title
        const titles = {ru:'TOKEN PAY LLC — AI, финтех и сетевые технологии', en:'TOKEN PAY LLC — AI, Fintech & Network Technologies', zh:'TOKEN PAY LLC — AI、金融科技和网络技术'};
        if (titles[lang]) document.title = titles[lang];
        this.updateLabel();
    }
    updateLabel() {
        const labels = { ru: 'RU', en: 'EN', zh: '中文' };
        if (this.label) this.label.textContent = labels[this.lang] || 'RU';
    }
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

    const _lang = localStorage.getItem('tp_lang') || 'ru';
    const label = _lang === 'en' ? 'Dashboard' : (_lang === 'zh' ? '\u63a7\u5236\u9762\u677f' : '\u041b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0431\u0438\u043d\u0435\u0442');

    // Desktop .nav-auth
    const navAuth = document.querySelector('.nav-auth');
    if (navAuth) {
        navAuth.innerHTML = `<a href="/dashboard" class="tpid-btn-icon" title="${label}"><img src="/tokenpay-icon.png" alt=""></a><a href="/dashboard" class="tpid-btn"><img src="/tokenpay-id-light.png" alt="TOKEN PAY ID" class="tpid-logo-light"><img src="/tokenpay-id-dark.png" alt="TOKEN PAY ID" class="tpid-logo-dark"></a>`;
        navAuth.style.cssText = 'display:flex;align-items:center;gap:8px';
    }

    // Mobile .nav-mobile-auth
    const mobileAuth = document.querySelector('.nav-mobile-auth');
    if (mobileAuth) {
        mobileAuth.innerHTML = `<a href="/dashboard" class="tpid-btn" style="width:100%;justify-content:center"><img src="/tokenpay-id-light.png" alt="TOKEN PAY ID" class="tpid-logo-light"><img src="/tokenpay-id-dark.png" alt="TOKEN PAY ID" class="tpid-logo-dark"></a>`;
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
                            if (navAuth) { navAuth.innerHTML = `<a href="/login" class="tpid-btn-icon" title="TOKEN PAY ID"><img src="/tokenpay-icon.png" alt=""></a><a href="/login" class="tpid-btn"><img src="/tokenpay-id-light.png" alt="TOKEN PAY ID" class="tpid-logo-light"><img src="/tokenpay-id-dark.png" alt="TOKEN PAY ID" class="tpid-logo-dark"></a>`; navAuth.style.cssText = 'display:flex;align-items:center;gap:8px'; }
                            if (mobileAuth) mobileAuth.innerHTML = `<a href="/login" class="tpid-btn" style="width:100%;justify-content:center"><img src="/tokenpay-id-light.png" alt="TOKEN PAY ID" class="tpid-logo-light"><img src="/tokenpay-id-dark.png" alt="TOKEN PAY ID" class="tpid-logo-dark"></a>`;
                        }
                    }).catch(() => {});
            }
        }).catch(() => {});
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particles');
    if (canvas) new StarSky(canvas);

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

// ===== GLOBAL TOAST NOTIFICATION SYSTEM =====
window.tpToast = (function() {
    let container = null;
    function getContainer() {
        if (!container || !document.body.contains(container)) {
            container = document.createElement('div');
            container.className = 'tp-toast-container';
            document.body.appendChild(container);
        }
        return container;
    }
    const icons = {
        success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>',
        error:   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
        info:    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
        warn:    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    };
    function show(msg, type, duration) {
        type = type || 'info';
        duration = duration == null ? 3500 : duration;
        const c = getContainer();
        const t = document.createElement('div');
        t.className = 'tp-toast tp-toast-' + type;
        t.innerHTML =
            '<span class="tp-toast-icon">' + (icons[type] || icons.info) + '</span>' +
            '<span class="tp-toast-text">' + msg + '</span>' +
            '<button class="tp-toast-close" onclick="this.parentNode.remove()">✕</button>';
        c.appendChild(t);
        if (duration > 0) {
            setTimeout(() => {
                t.classList.add('toast-hide');
                setTimeout(() => t.remove(), 350);
            }, duration);
        }
        return t;
    }
    return {
        success: (m, d) => show(m, 'success', d),
        error:   (m, d) => show(m, 'error', d),
        info:    (m, d) => show(m, 'info', d),
        warn:    (m, d) => show(m, 'warn', d),
        show
    };
})();

// ===== BUTTON RIPPLE EFFECT =====
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.auth-btn,.tp-btn,.nav-btn,.qa-btn,.tp-ripple,.dash-save-btn');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    const ripple = document.createElement('span');
    ripple.className = 'tp-ripple-effect';
    ripple.style.cssText = 'width:' + size + 'px;height:' + size + 'px;left:' + x + 'px;top:' + y + 'px';
    if (!btn.style.position || btn.style.position === 'static') btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
});
