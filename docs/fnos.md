# 飞牛 NAS 部署

当前镜像是 linux/amd64，适用于 x86-64 飞牛设备；其他架构应等待对应镜像及实际验证。

## SSH 向导

通过飞牛应用中心安装 Docker，开启本人管理的 SSH。把部署包解压到选定应用目录，进入目录执行 `bash install.sh`。普通用户可用自己的非 root UID/GID；root 首次安装时向导选择 10001:10001，并只准备专用 data/config 目录权限。

局域网浏览器地址填写 NAS 自己的私有 IP，如 `http://192.168.1.10:8088`。公网使用请按 HTTPS 文档设置代理，不直接映射 HTTP 后端。

## Compose 图形界面

1. 在 Docker 的 Compose 页面创建项目，将 compose.yaml 与填写后的 .env 放入工作目录。
2. MOON_DATA_DIR / MOON_CONFIG_DIR 指向明确的持久化目录，两者属于配置的非 root PUID/PGID，权限为 700。
3. 填真实访问地址。局域网 HTTP 使用 NAS 私有 IP，MOON_ALLOW_INSECURE_HTTP=1、MOON_BIND_ADDRESS=0.0.0.0；公网 HTTPS 保持回环绑定并设置代理。
4. 拉取镜像。首次启动前，在 NAS SSH 进入项目目录执行 `docker compose run --rm moonuestc init-admin`，交互创建管理员。
5. 启动项目，等待健康状态正常，打开配置的访问地址。

管理员在服务器终端初始化，没有默认密码。普通用户可自助注册（需要 HTTPS 或 localhost 的安全上下文），或由管理员创建；注册设置见 registration.md。学校学号、密码和可信浏览器指纹在登录网页后填写。保留数据目录及其加密密钥。
