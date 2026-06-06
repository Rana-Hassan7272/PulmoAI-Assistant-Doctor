FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/root/.local/bin:$PATH
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --user \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --user packaging
RUN pip install --no-cache-dir --user -r requirements.txt

RUN pip cache purge || true
RUN rm -rf /tmp/* /var/tmp/* /root/.cache/pip || true

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY --from=builder /root/.local/lib/python3.11/site-packages /root/.local/lib/python3.11/site-packages
COPY --from=builder /root/.local/bin /root/.local/bin

RUN pip install --no-cache-dir --user packaging

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python3.11/site-packages:$PYTHONPATH

COPY backend/ .

RUN mkdir -p reports data/rag_index

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 7860

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"
