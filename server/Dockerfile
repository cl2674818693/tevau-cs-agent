FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml .
COPY src ./src
# editable 安装，让 PROMPTS_DIR=/app/src/ai_engine/prompts 直接读到 .md prompt 文件
RUN uv pip install --system -e "."
CMD ["uvicorn", "ai_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
