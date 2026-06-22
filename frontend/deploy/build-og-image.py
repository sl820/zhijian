"""
build-og-image.py — 生成 1200x630 OG 社交分享卡

设计：
- 1200x630（标准 OG 尺寸）
- 深靛蓝底（#0a0e1f，跟项目 BG_COLOR 一致）
- 一圈金色点模拟"星环"
- 中央标题「志鉴·家谱星图」+ 副标题「33 万先祖 · 3D 星系」
- 底部署名 sl820.github.io/zhijian/

用法：python deploy/build-og-image.py
输出：frontend/dist/og-image.png
"""
import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def font(size, bold=False):
    """跨平台尝试找中英文字体"""
    candidates = [
        # Windows
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def star_field(w, h, n, rng):
    """生成 n 个星点，返回 (x, y, r, alpha) 列表"""
    out = []
    for _ in range(n):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        # 中心区不放太多（让标题可读）
        if 250 < x < 950 and 200 < y < 430:
            continue
        r = rng.choice([1, 1, 1, 2, 2, 3])
        alpha = rng.randint(80, 255)
        out.append((x, y, r, alpha))
    return out


def main():
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), (10, 14, 31, 255))  # #0a0e1f
    draw = ImageDraw.Draw(img)

    # 1. 背景星点
    rng = random.Random(20260622)
    stars = star_field(W, H, 600, rng)
    for x, y, r, a in stars:
        # 颜色偏金 / 偏白 / 偏靛 三类
        choice = rng.random()
        if choice < 0.5:
            c = (240, 232, 212, a)  # 米白 #f0e8d4
        elif choice < 0.85:
            c = (212, 176, 112, a)  # 金 #d4b070
        else:
            c = (160, 175, 200, a)  # 冷
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

    # 2. 中央星系旋臂（4 臂螺旋）
    cx, cy = W / 2, H / 2 + 30
    for i in range(180):
        t = i / 180 * math.pi * 4  # 2 圈
        r = 8 + t * 28
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t) * 0.55  # 压扁成椭圆更像星系
        a = int(255 * (1 - i / 180) * 0.7)
        if a < 30:
            continue
        rr = 2 + (1 - i / 180) * 1.5
        draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(212, 176, 112, a))

    # 3. 核心 bulge（高斯模糊小亮点）
    bulge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bulge)
    for i in range(40):
        r = 80 - i * 1.6
        a = int(200 * (i / 40))
        if r <= 0 or a <= 0:
            break
        bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 232, 212, a))
    bulge = bulge.filter(ImageFilter.GaussianBlur(radius=12))
    img.alpha_composite(bulge)

    # 4. 标题
    title_font = font(76, bold=True)
    title = "志鉴·家谱星图"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((W - tw) / 2, 360),
        title,
        font=title_font,
        fill=(240, 232, 212, 255),
    )

    # 5. 副标题
    sub_font = font(28)
    sub = "33 万先祖 · 三维星系"
    bbox = draw.textbbox((0, 0), sub, font=sub_font)
    sw = bbox[2] - bbox[0]
    draw.text(
        ((W - sw) / 2, 450),
        sub,
        font=sub_font,
        fill=(212, 176, 112, 255),
    )

    # 6. 底部署名
    url_font = font(20)
    url = "sl820.github.io/zhijian"
    bbox = draw.textbbox((0, 0), url, font=url_font)
    uw = bbox[2] - bbox[0]
    draw.text(
        ((W - uw) / 2, 555),
        url,
        font=url_font,
        fill=(160, 160, 180, 255),
    )

    # 7. 边框装饰
    draw.rectangle([20, 20, W - 20, H - 20], outline=(212, 176, 112, 80), width=2)

    # 输出到 vite publicDir（项目根 public/），vite build 时自动 copy 到 dist/og-image.png
    # 路径：cwd 在 frontend/，所以 ../../public 就是 vite publicDir
    out = os.path.join(os.path.dirname(__file__), "..", "..", "public", "og-image.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    size_kb = os.path.getsize(out) / 1024
    print(f"[og-image] saved {out} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
