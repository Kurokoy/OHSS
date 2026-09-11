# Dockerfile 生产部署设计

**日期**: 2026-09-11
**项目**: OHSS 高蛋白饮食智能计算器

## 目标

为 OHSS 计算器创建生产级 Docker 镜像，支持容器化部署。

## 镜像方案

单阶段 `python:3.12-slim` 构建：

- **选型理由**: slim 镜像兼顾体积与兼容性；reportlab/Pillow 在 Alpine 上有 C 扩展编译问题
- **中文字体**: `fonts-noto-cjk`（思源黑体，开源，无版权问题），安装在 `/usr/share/fonts/opentype/noto/`
- **WSGI 服务器**: Gunicorn（生产级，非 Flask 自带的开发服务器）
- **用户**: 非 root 用户 `appuser` 运行

## 文件变更

### 新增文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 镜像构建定义 |
| `docker-compose.yml` | 一键部署编排 |
| `.dockerignore` | 构建排除文件 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `app.py` | 字体路径增加 Noto Sans CJK；数据库路径支持环境变量；debug 模式由环境变量控制 |

## app.py 修改点

1. **字体注册**（L124-125）: 增加 Noto Sans CJK 查找路径 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`
2. **数据库路径**（L38）: `DATABASE = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohss.db'))` — Docker 中通过 `DB_PATH=/data/ohss.db` 指向 volume
3. **启动参数**（L1174）: `debug=True` → `debug=os.environ.get('FLASK_DEBUG', '0') == '1'`

## 容器运行

```bash
# 构建
docker build -t ohss-calculator .

# 运行
docker run -d \
  -p 5000:5000 \
  -v ohss-data:/data \
  ohss-calculator:latest

# 或使用 docker-compose
docker-compose up -d
```

## 数据持久化

- SQLite 数据库 `/data/ohss.db` 通过 Docker volume `ohss-data` 挂载
- app.py 中数据库路径保持不变（`os.path.dirname(os.path.abspath(__file__))`），Dockerfile 中设置 `WORKDIR /data` 确保数据库文件落在 volume 挂载点

## 校验标准

- 镜像构建无报错
- 容器启动后访问 `http://localhost:5000` 可正常加载页面
- PDF 报告中文字体正常渲染