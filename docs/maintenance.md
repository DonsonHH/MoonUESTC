# 维护、备份与离线安装

## 更新

保管旧版本标签并备份数据，将 .env 的 MOON_IMAGE 改为目标版本，执行 `bash install.sh --yes`。脚本保留配置和管理员，任务排队或执行中时暂停更新，健康检查失败时尝试恢复旧镜像。不要同时运行旧 CLI daemon 和网页调度器。

## 备份

`dashboard.sqlite3` 保存用户、加密账号及会话，`dashboard.key` 是加密密钥，`state.sqlite3` 保存防重复提交及首次确认状态，应一并保管。在没有运行任务时暂停本项目容器，把整个数据目录复制到私人备份位置，再启动：

```sh
docker compose stop moonuestc
# 在宿主机私人备份数据目录，包含加密密钥。
docker compose start moonuestc
```

## 离线安装

下载 Release 的 `MoonUESTC-v0.5.0-linux-amd64.image.tar.gz`、部署包及 SHA256SUMS.release.txt，校验后在目标主机执行：

```sh
sha256sum --check --ignore-missing SHA256SUMS.release.txt
docker load --input MoonUESTC-v0.5.0-linux-amd64.image.tar.gz
bash install.sh --skip-pull
```

`--yes` 用于复用已有 .env，`--skip-admin` 仅用于明确要稍后执行 init-admin 的自动化场景。密码不通过命令参数或环境变量传入。

## 重置网页登录密码

```sh
docker compose exec moonuestc python -m moonuestc reset-password
```

按提示输入用户名和新密码，不修改学校密码。排查时查看 `docker compose ps` 和 `docker compose logs --tail 50 moonuestc`，不要清空 data/ 反复重试。

## 升级到 v0.5.0

先备份整个数据目录和加密密钥，确认没有排队或执行中的任务，再升级固定版本镜像。旧学知三组团位置会自动更新为高德 GCJ-02 经度 103.933849、纬度 30.754874。迁移为一次性事务；已有用户、学校账号凭据、所属用户、启用状态、自动计划、运行时间及防重复提交状态保留。回退旧版时应同时恢复升级前配套的数据与密钥备份。

此版默认开启普通用户自助注册；设置 `MOON_ALLOW_REGISTRATION=0` 可关闭，详见 [注册配置](registration.md)。
