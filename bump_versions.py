import os, re
d = r'c:\Users\user\Desktop\TokenPay-Website\frontend'
for fn in os.listdir(d):
    if not fn.endswith('.html'): continue
    p = os.path.join(d, fn)
    c = open(p, encoding='utf-8').read()
    c2 = c.replace('styles.css?v=20260324','styles.css?v=20260325')\
          .replace('theme-init.js?v=20260324','theme-init.js?v=20260325')\
          .replace('script.js?v=20260316','script.js?v=20260325')\
          .replace('captcha.js?v=20260316d','captcha.js?v=20260325')
    if c2 != c:
        open(p,'w',encoding='utf-8').write(c2)
        print('bumped:', fn)
    else:
        print('no change:', fn)
