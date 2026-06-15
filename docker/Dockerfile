# 志鉴后端 Docker 镜像
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖：OpenCV 需要 libgl 等
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（先 COPY 单独 pip 层以便缓存）
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 应用代码
COPY app/ ./app/
COPY data/ ./data/

EXPOSE 8000

# 单 worker：chroma + 模型在内存，单 worker 避免多份加载
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]