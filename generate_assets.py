#!/usr/bin/env python3
"""Generate favicon.ico, BIMI SVG, and email header logo from existing assets."""
from PIL import Image, ImageDraw, ImageFont
import os

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')

# ===== 1. FAVICON.ICO from icon-512.png =====
def generate_favicon():
    print('[1] Generating favicon.ico from icon-512.png...')
    src = os.path.join(FRONTEND, 'icon-512.png')
    img = Image.open(src).convert('RGBA')
    
    # Create multiple sizes for favicon
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    icons = []
    for sz in sizes:
        resized = img.resize(sz, Image.LANCZOS)
        icons.append(resized)
    
    out = os.path.join(FRONTEND, 'favicon.ico')
    icons[0].save(out, format='ICO', sizes=[(s.width, s.height) for s in icons], append_images=icons[1:])
    print(f'  [+] {out} ({os.path.getsize(out):,} bytes)')

# ===== 2. FAVICON.SVG (proper SVG version of logo) =====
def generate_favicon_svg():
    print('[2] Generating favicon.svg...')
    # Create a proper SVG favicon with the head+orbit logo
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#000"/>
  <g transform="translate(56,56) scale(0.78)">
    <!-- Head silhouette -->
    <path d="M200 450 C120 450 60 380 60 290 C60 170 130 80 220 60 C250 52 270 55 290 65 C340 85 380 130 395 190 C410 250 400 320 370 370 C340 420 290 450 240 450 Z" fill="#fff"/>
    <!-- Face profile detail -->
    <path d="M180 350 C170 340 165 320 170 300 C175 280 185 265 200 255 C210 248 215 240 215 230 C215 215 205 200 195 195 C185 190 180 180 185 170" fill="none" stroke="#000" stroke-width="4" stroke-linecap="round"/>
    <!-- Orbit ring -->
    <ellipse cx="256" cy="256" rx="230" ry="90" fill="none" stroke="#fff" stroke-width="28" transform="rotate(-25,256,256)"/>
    <!-- Second ring line for depth -->
    <ellipse cx="256" cy="256" rx="210" ry="75" fill="none" stroke="#000" stroke-width="8" transform="rotate(-25,256,256)" opacity="0.3"/>
  </g>
</svg>'''
    out = os.path.join(FRONTEND, 'favicon.svg')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'  [+] {out}')

# ===== 3. BIMI logo (SVG Tiny PS format) =====
def generate_bimi_logo():
    print('[3] Generating bimi-logo.svg (SVG Tiny PS)...')
    # BIMI requires SVG Tiny 1.2 Portable/Secure profile
    # Must be square, no scripts, no external refs
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.2" baseProfile="tiny-ps" viewBox="0 0 512 512">
  <title>TOKEN PAY LLC</title>
  <rect width="512" height="512" rx="0" fill="#000"/>
  <g transform="translate(56,56) scale(0.78)">
    <path d="M200 450 C120 450 60 380 60 290 C60 170 130 80 220 60 C250 52 270 55 290 65 C340 85 380 130 395 190 C410 250 400 320 370 370 C340 420 290 450 240 450 Z" fill="#fff"/>
    <ellipse cx="256" cy="256" rx="230" ry="90" fill="none" stroke="#fff" stroke-width="28" transform="rotate(-25,256,256)"/>
  </g>
</svg>'''
    out = os.path.join(FRONTEND, 'bimi-logo.svg')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'  [+] {out}')

# ===== 4. Email header logo (tpid-logo-white.png) =====
def generate_email_logo():
    print('[4] Generating tpid-logo-white.png for email headers...')
    # Create "TOKEN PAY ID" text image on black background
    w, h = 320, 76
    img = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font
    text = 'TOKEN PAY ID'
    font_size = 28
    font = None
    for fpath in [
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf', 
        'C:/Windows/Fonts/segoeui.ttf',
    ]:
        if os.path.exists(fpath):
            font = ImageFont.truetype(fpath, font_size)
            break
    if not font:
        font = ImageFont.load_default()
    
    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2
    y = (h - th) // 2 - bbox[1]
    
    # Draw with letter spacing
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    
    out = os.path.join(FRONTEND, 'tpid-logo-white.png')
    img.save(out, 'PNG')
    print(f'  [+] {out} ({os.path.getsize(out):,} bytes)')

# ===== 5. Generate properly from the actual logo =====
def generate_email_logo_from_actual():
    print('[5] Checking if TOKEN PAY LLC logo can be used...')
    logo_path = r'C:\Users\user\Desktop\TPLOGO\TOKEN PAY LLC.png'
    if os.path.exists(logo_path):
        img = Image.open(logo_path).convert('RGBA')
        # Resize to email-friendly size (160px width)
        ratio = 160 / img.width
        new_h = int(img.height * ratio)
        img = img.resize((160, new_h), Image.LANCZOS)
        out = os.path.join(FRONTEND, 'email-avatar.png')
        img.save(out, 'PNG')
        print(f'  [+] {out} ({os.path.getsize(out):,} bytes)')
    else:
        print(f'  [!] Logo not found: {logo_path}')

if __name__ == '__main__':
    generate_favicon()
    generate_favicon_svg()
    generate_bimi_logo()
    generate_email_logo()
    generate_email_logo_from_actual()
    print('\n[+] All assets generated!')
