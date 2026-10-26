FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --create-home blockclock

WORKDIR /app
COPY blockclock_backend /app/blockclock_backend

USER blockclock

EXPOSE 21021 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-m", "blockclock_backend.healthcheck"]

CMD ["python", "-m", "blockclock_backend"]

