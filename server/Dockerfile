FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml .
COPY src ./src
# editable 安装，让 PROMPTS_DIR=/app/src/ai_engine/prompts 直接读到 .md prompt 文件
RUN uv pip install --system -e "."
# 非 root 运行，缩小一旦应用层失陷后的影响面
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "ai_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
