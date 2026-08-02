FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RV32I_GUI_HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils-riscv64-unknown-elf \
        gcc-riscv64-unknown-elf \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 simulator

WORKDIR /app
COPY --chown=simulator:simulator . .
RUN python -m pip install --no-cache-dir .

USER simulator

EXPOSE 8080

CMD ["rv32i-gui"]
