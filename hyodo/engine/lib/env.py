"""키 읽기: 환경변수가 있으면 그것을, 없으면 engine/.env 파일을 쓴다. 값은 절대 출력하지 않는다."""
import os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
KEYS = ("GOOGLE_TTS_KEY", "CF_ACCOUNT_ID", "CF_API_TOKEN", "DATA_GO_KR_KEY", "ANTHROPIC_API_KEY")


def load():
    d = {}
    f = ROOT / ".env"
    if f.exists():
        for l in f.read_text().splitlines():
            if "=" in l:
                k, v = l.split("=", 1); d[k.strip()] = v.strip()
    for k in KEYS:
        if os.environ.get(k):
            d[k] = os.environ[k]
    return d
