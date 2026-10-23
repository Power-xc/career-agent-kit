"""엔진 루트: harness 패키지가 있는 폴더. rules/, taxonomy/, templates/ 같은 엔진 자원은 여기서 읽는다."""
from __future__ import annotations

from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
