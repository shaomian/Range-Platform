# 功能改动点 Checklist（部署与运维）

> 本文件记录已实现的功能与改动点，便于后续查看与维护。勾选状态代表当前仓库已落地的能力。

## 一、部署脚本（一键部署）

- [x] **`deploy.sh`（Linux / macOS 一键部署）**
  - [x] 用 `uname` 识别系统；Linux 读取 `/etc/os-release` 识别发行版
  - [x] Linux 覆盖主流发行版并选择对应安装方式：
        Debian/Ubuntu/Kali/Mint（apt）、Fedora/CentOS/RHEL/Rocky/Alma/Oracle（dnf|yum）、
        Amazon Linux、openSUSE/SLES（zypper）、Arch/Manjaro（pacman）、Alpine（apk），
        未知发行版回退到 `get.docker.com`
  - [x] macOS 依赖 Docker Desktop，缺失时经 Homebrew `brew install --cask docker` 安装并启动
  - [x] 校验并按需补齐 `docker compose` v2 插件（按架构从 GitHub Releases 下载）
  - [x] 兼容 systemd 与 OpenRC（Alpine）启动/自启 Docker 守护进程
  - [x] 自动生成 `.env`：随机 `SECRET_KEY`、随机管理员密码、本机 IP 作为 `SERVER_HOST`、vulhub 同路径挂载
  - [x] 幂等：已存在 `.env` 不覆盖；结束时一次性打印本次管理员账号密码
  - [x] 打印访问地址、健康检查命令、防火墙/SELinux 提示

- [x] **`deploy.ps1`（Windows / PowerShell 一键部署）**
  - [x] 缺失 Docker 时经 `winget install -e --id Docker.DockerDesktop` 安装
  - [x] 启动 Docker Desktop 并等待守护进程就绪
  - [x] 生成 `.env`（随机 `SECRET_KEY`/管理员密码、本机 IPv4、vulhub 挂载，路径用正斜杠）
  - [x] 与 `deploy.sh` 行为一致：幂等、一次性打印凭据、防火墙放行提示

## 二、运维管理脚本（本次新增）

- [x] **`manage.sh`（Linux / macOS）** 与 **`manage.ps1`（Windows）**，封装 `docker compose`：
  - [x] `start`：启动平台（容器不存在则创建，幂等）
  - [x] `stop`：停止平台容器（保留容器与数据卷）
  - [x] `restart`：重启平台容器
  - [x] `status` / `ps`：查看容器状态
  - [x] `logs`：跟随平台日志（`--tail=200`）
  - [x] `rebuild` / `update`：重建镜像并重启（代码变更后使用）
  - [x] `down`：移除平台容器（保留 `range-data` 数据卷）
  - [x] `destroy`：移除容器并删除 `range-data` 卷（**会清空数据库，需输入 yes 二次确认**）
  - [x] Linux 自动加 `sudo`，macOS/Windows 不加；无 docker/compose 时报错退出
  - [x] 说明：以上命令仅作用于**平台容器**；运行中的 vulhub 靶场为独立 compose 项目，不受影响

## 三、Docker 打包与编排

- [x] **`Dockerfile`** 多阶段构建：
  - [x] Stage 1（`node:20-alpine`）`npm ci` + `npm run build` 编译前端
  - [x] 从 `docker:27-cli` 复制 docker CLI 与 compose 插件（供后端 DooD 驱动宿主机守护进程）
  - [x] Stage 2（`python:3.12-slim`）安装依赖、拷贝后端与前端产物、`/data` 持久化目录
  - [x] `uvicorn app.main:app` 监听 `0.0.0.0:8000`
- [x] **`docker-compose.yml`** 单容器编排：
  - [x] `restart: unless-stopped`、端口 `${PLATFORM_PORT:-8000}:8000`
  - [x] 环境变量全部支持 `.env` 覆盖（SECRET_KEY / SERVER_HOST / ADMIN_* / 端口范围等）
  - [x] 挂载 `/var/run/docker.sock`（DooD）、vulhub 目录、`range-data` 卷持久化 SQLite

## 四、平台核心功能（后端 / 前端）

- [x] 后端 FastAPI + SQLAlchemy(SQLite) + JWT 鉴权，前端 Vue3 + Vite + Element Plus + Pinia
- [x] 后端同源提供 API 与前端静态资源（无需 CORS）
- [x] 多用户鉴权与用户管理（创建/编辑/禁用、管理员查看全部实例）
- [x] 靶场目录检索（名称 / CVE / 应用 / 标签），README 与 compose 预览
- [x] 一键启停靶场：每次启动生成唯一 compose 项目名，端口重映射到
      `PORT_RANGE_START`~`PORT_RANGE_END` 随机空闲端口，支持多用户/多实例并发不冲突
- [x] 实时端口/访问地址、容器日志查看
- [x] 每用户并发实例数限制（`MAX_INSTANCES_PER_USER`）
- [x] 停止实例执行 `docker compose down -v`，清理容器/网络/卷不残留
- [x] 目录热重载：管理员「刷新目录」按钮 = `POST /api/environments/reload`（仅管理员）
- [x] 首次启动、数据库为空时按 `.env` 的 `ADMIN_PASSWORD` 创建管理员
- [x] Windows 下 `docker` 子进程输出统一 UTF-8 解码，避免 GBK 报错

## 四之二、实例超时自动停止与续期（本次新增）

- [x] **数据模型**：`Instance` 新增 `expires_at`（自动停止时刻，UTC）；新增 `AppSetting` 键值表存管理员可调配置；`database.py` 迁移为已有库追加列与表
- [x] **启动即赋过期时间**：启动实例时 `expires_at = now + 默认 TTL`
- [x] **后台清理任务（reaper）**：`auto_stop_loop()` 每 15s 扫描 `expires_at<=now` 的运行中实例，`compose down -v` 后标记已停止；阻塞子进程经 `asyncio.to_thread` 不阻塞事件循环；失败留待下轮重试；在 `lifespan` 中启动、关闭时取消
- [x] **续期接口** `POST /api/instances/{id}/renew`（body `{"minutes":N}`，0/缺省=默认 TTL）：重置 `expires_at = now + N`；普通用户受最大续期时长约束、管理员不限；已停止实例返回 400
- [x] **管理员可配置** `GET/PUT /api/settings`（GET 任意登录用户可读、PUT 仅管理员）：默认超时时间、最大续期时长，存数据库即时生效；启动时 seed 默认值；`INSTANCE_DEFAULT_TTL_MINUTES` / `INSTANCE_MAX_TTL_MINUTES` 仅作初始 seed
- [x] **前端倒计时**：「我的实例」新增「剩余时长」列，按秒刷新（<5m 橙、<1m 红），每 30s 自动刷新列表反映自动停止
- [x] **前端续期**：运行中实例「续期」按钮弹窗选分钟数，普通用户上限取自配置、管理员不限
- [x] **系统设置页**（`SettingsView.vue`，仅管理员）：调整默认超时 / 最大续期；侧边栏新增「系统设置」菜单与路由

## 五、跨平台注意事项（维护要点）

- [ ] **bind mount 路径一致性**：使用相对 bind mount 的靶场需容器内路径 == 宿主机绝对路径
  - [x] Linux/macOS：`VULHUB_HOST_PATH = VULHUB_MOUNT = <绝对路径>`（脚本已处理）
  - [ ] Windows：`C:\...` 无法等同容器内 Linux 路径，相对 bind mount 靶场可能无法启动（仅端口映射的靶场正常）
- [ ] 行尾必须为 LF（`deploy.sh` 与 vulhub 的 `docker-compose.yml`）
- [ ] SELinux enforcing 下按需 `chcon -Rt container_file_t <vulhub 绝对路径>`
- [ ] 防火墙放行平台端口 8000 与各靶场端口
- [ ] 生产环境务必修改 `.env` 的 `SECRET_KEY`、`ADMIN_PASSWORD`

## 六、常用命令速查

```bash
# Linux / macOS
./deploy.sh                 # 一键部署
./manage.sh restart         # 重启平台
./manage.sh stop            # 停止平台
./manage.sh logs            # 查看日志
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\deploy.ps1     # 一键部署
powershell -ExecutionPolicy Bypass -File .\manage.ps1 restart
powershell -ExecutionPolicy Bypass -File .\manage.ps1 stop
powershell -ExecutionPolicy Bypass -File .\manage.ps1 logs
```
