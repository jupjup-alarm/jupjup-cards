import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from char import gen
d = pathlib.Path(sys.argv[1]); ref = d / "base.png"
for name, pose, seed in [("point", "She is pointing up and to her right side with her index finger, as if presenting information.", 21),
                         ("phone", "She is holding a smartphone in front of her chest with both hands and looking at the viewer.", 31),
                         ("ok", "She is giving a cheerful thumbs up with one hand.", 41)]:
    try:
        gen(pose, d / f"{name}.png", ref=ref, seed=seed); print(name, "ok")
    except Exception as e:
        print(name, "ERR", e, getattr(e, "read", lambda: b"")()[:300])
