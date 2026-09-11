FROM python:3.12-slim

# 系统依赖：Noto Sans CJK 中文字体
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --no-log-init --create-home --shell /bin/bash appuser

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 数据持久化目录
RUN mkdir /data && chown appuser:appuser /data

# 生产环境变量
ENV DB_PATH=/data/ohss.db
ENV FLASK_DEBUG=0

# 入口点脚本（修复卷挂载时的所有权问题）
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

USER appuser
EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-120} app:app"]