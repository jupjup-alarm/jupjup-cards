"""흰 배경을 가장자리에서부터 지워 투명 PNG로 (옷 안쪽 흰색은 남김)."""
import sys
from PIL import Image, ImageDraw, ImageFilter
for p in sys.argv[1:]:
    im = Image.open(p).convert("RGBA"); w, h = im.size
    rgb = im.convert("RGB")
    mask = Image.new("L", (w, h), 0)
    # 테두리에서 시작하는 흰색 영역 채우기
    work = rgb.copy()
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0)]:
        ImageDraw.floodfill(work, seed, (255, 0, 255), thresh=28)
    px = work.load(); m = mask.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] != (255, 0, 255): m[x, y] = 255
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(mask)
    bbox = mask.point(lambda v: 255 if v > 20 else 0).getbbox()
    im.crop(bbox).save(p.replace(".png", "_cut.png"))
    print(p, "->", bbox)
