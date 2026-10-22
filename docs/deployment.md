# 部署与维护

## 准备

使用 Docker 和 Compose v2。先复制 `.env.example` 为 `.env`，设置学生端 HTTPS 地址，以及宿主机写入数据目录的用户与组 ID。Linux 可用 `id -u`、`id -g` 查询，填入 `PUID`、`PGID`；让 `data/` 属于对应用户。

`MOON_BROWSER_ASSIST_KEY` 使用至少 32 字节随机数据生成的密钥，保存在私有 `.env`。主应用和 helper 共用它，仅在 Docker 内网传递。学校账号由用户通过网页绑定，不写进配置文件。

## 构建与启动

```sh
mkdir -p data
docker build -t moonuestc-local:student-portal .
docker build -t moonuestc-browser:local browser_assist

docker compose -f compose.yaml -f compose.browser.yaml -f compose.admin.yaml run --rm moonuestc init-admin
docker compose -f compose.yaml -f compose.browser.yaml -f compose.admin.yaml up -d
```

helper 默认基于上一步主镜像；改用其他标签时传入 `--build-arg MOON_APP_IMAGE=实际主镜像标签`。首次初始化通过交互输入管理员密码。

学生端回环端口由 `MOON_PORT` 设置，默认 8088；HTTPS 代理只转发这个端口。`MOON_PUBLIC_URL` 必须与浏览器实际地址一致。只将已知反向代理网段填入 `MOON_TRUSTED_PROXY_CIDRS`。

管理端默认绑定 `127.0.0.1:4497`，通过 [私有管理转发](private-admin.md) 访问；不创建公开管理路由。helper 无宿主机公开端口。

## 用户范围与区域

`MOON_STUDENT_ID_PREFIX` 非空时，允许该前缀加两位数字的学号。管理员可在用户管理中单独增加授权；增加授权仍需本人学校验证。

`MOON_ALLOWED_PRESETS` 选择开放的组团，默认二、五组团。最终仍使用每个账号自己的校方围栏。`MOON_RUN_WINDOW` 默认为 `21:06,23:24`，与学校实时开放窗口共同生效。

## 更新与恢复

1. 确认没有排队或运行中的任务，停止两个应用服务。
2. 成对备份 `data/` 全目录与 `.env`、Compose 配置，包含数据库及 `dashboard.key`。密钥和密文必须来自同一快照。
3. 在新源码目录构建镜像，用备份副本在无网络容器中验证恢复与预期迁移。
4. 切换镜像并确认健康检查、学生登录页、私有管理端和数据摘要，保留旧镜像及成对备份。
5. 如需回滚，停服务后保留失败数据副本，再恢复配套数据、密钥和配置。

容器使用非 root 用户、只读根文件系统、临时目录和资源限制。公开端运行一个调度器，管理端不启动调度器。例行认证、密码、Cookie 与个人资料不进入公开日志。
