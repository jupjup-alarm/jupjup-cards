"""막내 표정 그림 추가 (2026-11-04 벤치마크 분석: 장면마다 표정 바꾸기). python3 lib/moods.py <폴더>  — 폴더에 base.png 필요."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from char import gen
MOODS = [("worried", "Her face looks worried with concerned eyebrows. Both of her hands are lowered and resting together at her waist. She is not waving.", 53),
         ("surprised", "She looks surprised with wide eyes and an open mouth, both hands raised near her face.", 61),
         ("happy", "She is smiling brightly with relief, both hands clasped together in front of her chest.", 71),
         ("thinking", "She is thinking, finger on her chin, looking slightly upward.", 81),
         ("ok", "She makes a fist with her right hand and raises it in front of her chest with the thumb pointing straight up (thumbs-up gesture). Her other arm is down. She is not waving.", 44)]
if __name__ == "__main__":
    d = pathlib.Path(sys.argv[1]); ref = d / "base.png"
    only = sys.argv[2:]
    for name, pose, seed in MOODS:
        if only and name not in only:
            continue
        try:
            gen(pose, d / f"{name}.png", ref=ref, seed=seed); print(name, "ok")
        except Exception as e:
            print(name, "ERR", e, getattr(e, "read", lambda: b"")()[:300])
