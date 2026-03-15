// Instant theme/lang apply on ALL pages (runs before DOMContentLoaded)
(function(){
    // Theme
    var saved = localStorage.getItem('tp_theme');
    if (saved === 'light') document.body.classList.add('light');
    else if (!saved) {
        if (window.matchMedia('(prefers-color-scheme: light)').matches) document.body.classList.add('light');
    }
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
