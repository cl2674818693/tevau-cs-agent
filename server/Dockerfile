FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml .
# 先用最小 stub 包安装全部第三方依赖：本层只依赖 pyproject.toml，
# 源码改动不再使该层失效。（原来 COPY src 在依赖安装之前，改任何一行源码
# 都会让依赖层缓存失效、连带全量重装依赖，构建奇慢。）
RUN mkdir -p src/ai_engine && touch src/ai_engine/__init__.py \
    && uv pip install --system -e "." \
    && rm -rf src
# 真实源码；再做一次 editable 安装（依赖已满足，仅重注册本地包，秒级）。
# editable 让 PROMPTS_DIR=/app/src/ai_engine/prompts 直接读到 .md prompt 文件。
COPY src ./src
RUN uv pip install --system -e "."
# 非 root 运行，缩小一旦应用层失陷后的影响面
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser
# UVICORN_WORKERS env 可在 compose / k8s 注入；默认 2，按容器 CPU 配（一般 = nproc 或 2×nproc+1）。
# 多 worker → 进程内状态（_cancel_signals dict、_c_user_id_cache）各自一份；cancel DELETE 偶尔
# 命中不到正在 stream 的 worker，靠 _watch_disconnect 的 TCP 断开兜底（spec §3.3）。
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "exec uvicorn ai_engine.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
