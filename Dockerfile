# oh-my-robo-advisor — 2-stage 빌드
# 정본: 설계 01 §7.2 / 계획 01 §1.6
#
# app 과 tools 는 **같은 이미지**를 쓴다. 격리의 실체는 이미지가 아니라
# 자격증명 배치(.env vs .env.tools)와 기동 셀프체크 SC-13이다 —
# 이미지를 나누면 "테스트 환경에서만 다른 코드 경로"가 생긴다.

# [확인 필요] uv 바이너리 공급 이미지의 버전 고정 태그 — uv 공식 문서로 확정한다
# (설계 01 §11-2). 현재는 재현성을 위해 명시 버전을 박아 둔다.
ARG UV_VERSION=0.12.1
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ARG UV_VERSION
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 의존성 레이어를 소스와 분리해 캐시한다 — 소스 변경이 재설치를 유발하지 않게.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev


FROM python:${PYTHON_VERSION}-slim
# non-root 고정 UID/GID — compose의 `user: "1000:1000"` 및 named volume 소유권과 일치한다
# (정본: 계획 01 §7-6).
RUN groupadd -g 1000 omra && useradd -u 1000 -g 1000 -m omra
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
# 기본값만 굽는다 — 런타임에는 `./config:/app/config:ro` 마운트가 덮는다.
COPY config/ /app/config/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER omra

# 호출 형식의 정본은 계획 01 §1.6 — `python -m omra.cli <명령>`.
CMD ["python", "-m", "omra.cli", "run"]
