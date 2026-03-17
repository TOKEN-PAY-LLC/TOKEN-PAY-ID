// Instant theme/lang apply on ALL pages (runs before DOMContentLoaded)
(function(){
    // Read URL params first (from external apps like CUPOL)
    try {
        var params = new URLSearchParams(window.location.search);
        var urlTheme = params.get('theme') || params.get('color_scheme');
        var urlLang = params.get('lang') || params.get('locale');
        if (urlTheme === 'light' || urlTheme === 'dark') localStorage.setItem('tp_theme', urlTheme);
        if (urlLang === 'ru' || urlLang === 'en') localStorage.setItem('tp_lang', urlLang);
    } catch(e) {}
    // Theme
    var saved = localStorage.getItem('tp_theme');
    if (saved === 'light') { try { document.documentElement.classList.add('light-html'); } catch(e) {} }
    document.addEventListener('DOMContentLoaded', function(){
        if (saved === 'light' && document.body) document.body.classList.add('light');
        else if (!saved && document.body) {
            if (window.matchMedia('(prefers-color-scheme: light)').matches) document.body.classList.add('light');
        }
    });
    // Language
    var lang = localStorage.getItem('tp_lang');
    if (lang) {
        document.addEventListener('DOMContentLoaded', function(){
            document.querySelectorAll('[data-ru][data-en]').forEach(function(el){
                var t = el.getAttribute('data-' + lang);
                if (t) {
                    if (el.childElementCount === 0) el.textContent = t;
                    else {
                        var n = Array.from(el.childNodes).find(function(n){ return n.nodeType === 3 && n.textContent.trim(); });
                        if (n) n.textContent = t;
                    }
                }
            });
        });
    }
})();
