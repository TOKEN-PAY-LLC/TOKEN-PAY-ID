#!/usr/bin/env python3
"""Generate ALL site assets from official TPLOGO source files."""
from PIL import Image
import shutil
import os

SRC = r'C:\Users\user\Desktop\TPLOGO'
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')

# Source files
LOGO_MAIN = os.path.join(SRC, 'TOKEN PAY LLC.png')        # white on black (square)
LOGO_BLACK = os.path.join(SRC, 'TOKEN PAY LLC BLACK.png')  # black on transparent
LOGO_WHITE = os.path.join(SRC, 'TOKEN PAY LLC WHITE.png')  # white on transparent
LOGO2 = os.path.join(SRC, 'TOKEN PAY LLC2.png')            # white on black (rounded)

def resize_png(src, dst, size, bg=None):
    """Resize image to square size, optionally with background color."""
    img = Image.open(src).convert('RGBA')
    if bg:
        canvas = Image.new('RGBA', img.size, bg)
        canvas.paste(img, (0, 0), img)
        img = canvas
    img = img.resize((size, size), Image.LANCZOS)
    img.save(dst, 'PNG')
    print(f'  [+] {os.path.basename(dst)} ({size}x{size}, {os.path.getsize(dst):,} bytes)')

def generate_ico(src, dst, sizes=(16, 32, 48, 64)):
    """Generate .ico with multiple sizes."""
    img = Image.open(src).convert('RGBA')
    icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    icons[0].save(dst, format='ICO', sizes=[(s, s) for s in sizes], append_images=icons[1:])
    print(f'  [+] {os.path.basename(dst)} (sizes: {sizes}, {os.path.getsize(dst):,} bytes)')

def main():
    print('='*60)
    print('Generating ALL assets from official TPLOGO')
    print('='*60)

    # === FAVICON ===
    print('\n--- Favicon ---')
    generate_ico(LOGO_MAIN, os.path.join(DST, 'favicon.ico'))

    # === Icons (for manifest, PWA, meta tags) ===
    print('\n--- App Icons ---')
    resize_png(LOGO_MAIN, os.path.join(DST, 'icon-192.png'), 192)
    resize_png(LOGO_MAIN, os.path.join(DST, 'icon-512.png'), 512)
    resize_png(LOGO_MAIN, os.path.join(DST, 'apple-touch-icon.png'), 180)

    # === Hero logos (for site header, dark/light theme) ===
    print('\n--- Hero Logos ---')
    resize_png(LOGO_BLACK, os.path.join(DST, 'hero-logo-black.png'), 512)
    resize_png(LOGO_WHITE, os.path.join(DST, 'hero-logo-white.png'), 512)

    # === Tokenpay icon (round button icon) ===
    print('\n--- Button Icon ---')
    resize_png(LOGO_MAIN, os.path.join(DST, 'tokenpay-icon.png'), 128)

    # === Email avatar (for BIMI / email sender) ===
    print('\n--- Email Avatar ---')
    resize_png(LOGO_MAIN, os.path.join(DST, 'email-avatar.png'), 256)

    # === Email header logo (TOKEN PAY ID white text on black) ===
    # Use the main logo resized for email header (160px wide)
    print('\n--- Email Header Logo ---')
    img = Image.open(LOGO_MAIN).convert('RGBA')
    # Make it 160x160 for email (square logo works in email headers)
    img = img.resize((160, 160), Image.LANCZOS)
    out = os.path.join(DST, 'tpid-logo-white.png')
    img.save(out, 'PNG')
    print(f'  [+] tpid-logo-white.png (160x160, {os.path.getsize(out):,} bytes)')

    # === BIMI logo (SVG Tiny PS — for email avatar in supported clients) ===
    # BIMI requires SVG Tiny 1.2 PS. We can't convert PNG to proper SVG path automatically.
    # But we can reference icon.svg if it exists
    print('\n--- BIMI SVG ---')
    svg_src = os.path.join(SRC, 'icon.svg')
    if os.path.exists(svg_src) and os.path.getsize(svg_src) < 50000:
        shutil.copy2(svg_src, os.path.join(DST, 'bimi-logo.svg'))
        print(f'  [+] Copied icon.svg -> bimi-logo.svg')
    else:
        # icon.svg is 3.6MB — too large. Keep the generated BIMI SVG.
        print(f'  [!] icon.svg too large ({os.path.getsize(svg_src):,} bytes), keeping generated bimi-logo.svg')

    # === OG Image (for social media sharing) ===
    print('\n--- OG Image ---')
    resize_png(LOGO_MAIN, os.path.join(DST, 'og-image.png'), 512)

    print('\n' + '='*60)
    print('ALL ASSETS GENERATED!')
    print('='*60)

if __name__ == '__main__':
    main()
