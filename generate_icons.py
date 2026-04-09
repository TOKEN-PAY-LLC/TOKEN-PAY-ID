"""Generate favicon and icon assets from source icon + copy hero logos."""
import shutil
from pathlib import Path
from PIL import Image

SRC = Path(r"C:\Users\user\Desktop\TPLOGO")
DST = Path(r"C:\Users\user\Desktop\TokenPay-Website\frontend")

# --- 1. Load source icon (icon.svg.png is actually a PNG) ---
icon_src = SRC / "icon.svg.png"
print(f"Loading {icon_src} ({icon_src.stat().st_size} bytes)")
img = Image.open(icon_src)
print(f"  Original size: {img.size}, mode: {img.mode}")
if img.mode != "RGBA":
    img = img.convert("RGBA")

# --- 2. Generate PNG icons ---
sizes = {
    "icon-192.png": 192,
    "icon-512.png": 512,
    "apple-touch-icon.png": 180,
}
for name, sz in sizes.items():
    out = DST / name
    resized = img.resize((sz, sz), Image.LANCZOS)
    resized.save(out, "PNG", optimize=True)
    print(f"  Saved {name}: {sz}x{sz} ({out.stat().st_size} bytes)")

# --- 3. Generate favicon.ico (16 + 32 + 48) ---
ico_path = DST / "favicon.ico"
ico_sizes = [(16, 16), (32, 32), (48, 48)]
ico_images = [img.resize(s, Image.LANCZOS) for s in ico_sizes]
ico_images[0].save(ico_path, format="ICO", sizes=ico_sizes, append_images=ico_images[1:])
print(f"  Saved favicon.ico ({ico_path.stat().st_size} bytes)")

# --- 4. Copy hero logos ---
hero_white = SRC / "TOKEN PAY LLC WHITE.png"
hero_black = SRC / "TOKEN PAY LLC BLACK.png"

dst_white = DST / "hero-logo-white.png"
dst_black = DST / "hero-logo-black.png"

shutil.copy2(hero_white, dst_white)
print(f"  Copied hero-logo-white.png ({dst_white.stat().st_size} bytes)")

shutil.copy2(hero_black, dst_black)
print(f"  Copied hero-logo-black.png ({dst_black.stat().st_size} bytes)")

# Check dimensions of hero logos vs current tokenpay-icon.png
current_icon = DST / "tokenpay-icon.png"
if current_icon.exists():
    ci = Image.open(current_icon)
    print(f"\n  Current tokenpay-icon.png: {ci.size}")

wimg = Image.open(dst_white)
bimg = Image.open(dst_black)
print(f"  hero-logo-white.png: {wimg.size}")
print(f"  hero-logo-black.png: {bimg.size}")

print("\nDone! All assets generated.")
