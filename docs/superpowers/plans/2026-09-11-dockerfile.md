# Dockerfile 生产部署 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OHSS 计算器创建生产级 Docker 镜像（python:3.12-slim + gunicorn + Noto Sans CJK 字体）

**Architecture:** 单阶段构建，非 root 用户运行，SQLite 数据通过 volume 持久化

**Tech Stack:** Python 3.12, Flask, Gunicorn, SQLite, Noto Sans CJK

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `Dockerfile` | 镜像构建定义（system deps → python deps → app code → runtime） |
| `docker-compose.yml` | 一键部署编排，声明 volume 和端口映射 |
| `.dockerignore` | 排除 `__pycache__`、`.claude`、`screenshots`、`docs` 等 |
| `app.py` | 修改 3 处：DB_PATH 环境变量、Noto 字体路径、debug 环境变量控制 |
| `requirements.txt` | 增加 `gunicorn>=21` |

---

### Task 1: 修改 app.py — 数据库路径支持环境变量

**Files:**
- Modify: `app.py:38`

- [ ] **Step 1: 修改 DATABASE 定义**

```python
DATABASE = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohss.db'))
```

---

### Task 2: 修改 app.py — 增加 Noto Sans CJK 字体路径

**Files:**
- Modify: `app.py:124-125`

- [ ] **Step 1: 增加字体路径常量**

```python
FONT_PATH_WIN = 'C:/Windows/Fonts/msyh.ttc'
FONT_PATH_ALT = '/usr/share/fonts/truetype/msyh.ttc'
FONT_PATH_NOTO = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
```

- [ ] **Step 2: 更新 register_font 函数遍历所有路径**

```python
def register_font():
    for path in [FONT_PATH_WIN, FONT_PATH_ALT, FONT_PATH_NOTO]:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            return True
    return False
```

---

### Task 3: 修改 app.py — debug 模式由环境变量控制

**Files:**
- Modify: `app.py:1174`

- [ ] **Step 1: 修改 app.run 调用**

```python
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
```

---

### Task 4: 添加 gunicorn 依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 追加 gunicorn**

```
flask>=3.0
reportlab>=4.0
qrcode>=7.4
Pillow>=10.0
gunicorn>=21
```

---

### Task 5: 创建 .dockerignore

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: 写入排除规则**

```dockerignore
__pycache__
*.pyc
*.pyo
.claude
docs
screenshots
cloud-deployment-proposal.html
start.bat
*.db
.env
.git
```

---

### Task 6: 创建 Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: 写入完整 Dockerfile**

```dockerfile
FROM python:3.12-slim

# 系统依赖：Noto Sans CJK 中文字体
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser

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

USER appuser
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
```

---

### Task 7: 创建 docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: 写入编排文件**

```yaml
version: "3.8"

services:
  ohss-calculator:
    build: .
    image: ohss-calculator:latest
    container_name: ohss-calculator
    ports:
      - "5000:5000"
    volumes:
      - ohss-data:/data
    restart: unless-stopped
    environment:
      - DB_PATH=/data/ohss.db
      - FLASK_DEBUG=0

volumes:
  ohss-data:
```

---

### Task 8: 构建并验证

**Files:**
- 无新文件

- [ ] **Step 1: 构建镜像**

```bash
docker build -t ohss-calculator .
```
Expected: 构建成功，无报错

- [ ] **Step 2: 启动容器**

```bash
docker-compose up -d
```
Expected: 容器启动，状态 healthy

- [ ] **Step 3: 验证服务可访问**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000
```
Expected: 200

- [ ] **Step 4: 清理**

```bash
docker-compose down
```