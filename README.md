# MoonUESTC · 晚安成电自动打卡系统

本工作分支包含 **v0.5.1 日志修复**：持久化学校错误码和脱敏信息，并区分首次提交与仅复查，见 [诊断说明](docs/run-diagnostics.md)。公开发行镜像仍为 v0.5.0；本分支修复通过独立构建镜像部署。

带管理员 / 普通用户登录的自托管 dashboard，适用于飞牛 NAS 和 Linux VPS。当前版本 **v0.5.0**，提供 `linux/amd64` 镜像。

- 管理员管理所有用户及学校账号；普通用户只管理自己的账号。
- 每个账号选择学知一至八组团的常用位置，默认“学知三组团”，或手动填写、命名位置，支持 GCJ-02 / WGS-84。
- 支持用户自助注册，用户名和密码即可；使用完全自托管的 ALTCHA 注册验证。
- 提供只读诊断、位置检查、明确确认后的提交，以及首次确认成功后开启的每日计划。
- 学校凭据和学校 Cookie 使用 AES-GCM 加密保存；网页登录密码使用 Argon2id。
- 保存账号和打开网页不会提交打卡；结果不明确时保留状态并复查，不盲目重发。

仅用于本人或明确授权的账号。学校的认证、范围和时间要求仍由学校系统判定；可信浏览器可能被撤销，项目不会自动处理二次验证码。内置位置不是实时 GPS，填写位置时请确认自己位于允许范围内。海外网络和 ARM64 尚未列为本版本的已验证支持范围。

## 快速开始

先通过 NAS 应用中心或 Docker 官方渠道安装 Docker 和 Compose v2。下载本仓库，或从 [Releases](https://github.com/horoscope963852/MoonUESTC/releases) 下载部署包，进入包含 compose.yaml 的目录：

```sh
bash install.sh
```

首次运行会询问后端端口和浏览器访问地址，然后拉取镜像、准备私有目录、交互创建管理员并检查健康状态。登录后在网页添加学校账号；管理员可创建普通用户，也可由用户自助注册；没有默认密码，详情见 [注册配置](docs/registration.md)。

- **NAS 局域网**：访问地址可以是 `http://192.168.1.10:8088`，填写你自己的 NAS 私有 IP。
- **公网 VPS**：使用 `https://你的IP或域名:HTTPS端口`，并按 [HTTPS 配置](docs/https.md) 设置已有证书的反向代理。HTTPS 模式后端默认只绑定 127.0.0.1。
- **飞牛图形界面部署**：见 [飞牛部署说明](docs/fnos.md)。

完整配置见 `.env.example`。脚本保留已有 `.env` 和数据；升级时不会重新创建管理员。有任务正在排队或执行时，会要求任务完成后再更新。

## 手动使用 Compose

```sh
cp .env.example .env
# 编辑 .env，填写真实访问地址及数据目录、PUID/PGID。
mkdir -p data config
# 使两个目录归属于 .env 中的 PUID/PGID；使用非 root 用户运行容器。
docker compose pull
docker compose run --rm moonuestc init-admin
docker compose up -d --wait
```

默认镜像：`ghcr.io/horoscope963852/moonuestc:0.5.0`。升级前先备份数据，再选择固定版本，无需依赖 latest。

## 获取可信浏览器指纹

在浏览器打开 [学校统一认证](https://idas.uestc.edu.cn/authserver/login)，登录本人账号并按学校提示完成验证、信任该浏览器。按 F12，在 **Application / 应用程序 → Storage / 存储 → Cookies → https://idas.uestc.edu.cn** 找到：

```text
MULTIFACTOR_BROWSER_FINGERPRINT
```

复制该行的 **Value**（32 位十六进制），填入网页的“可信浏览器指纹”。它带 HttpOnly，不能用 document.cookie 读取。同一浏览器新建账号时自动填入 User-Agent；其他浏览器的值应与完成认证的浏览器对应。

保存后先运行“只读诊断”，再运行“位置检查”。需要打卡时在学校窗口内明确确认提交。只有回读学校记录确认成功，才解锁每日自动计划。密码和指纹直接填入自己的实例，不要提交到仓库或 Issue。

## 位置

内置学知一至八组团的高德 GCJ-02 坐标；默认学知三组团：经度 103.933849、纬度 30.754874，原样提交。旧版本已保存的 `xuezhi_group3` 及其名称引用在升级时统一更新为新的学知三组团坐标；用户、凭据、归属和运行计划保留。手动位置使用十进制度，并选择正确坐标系：GCJ-02 原样使用，WGS-84 做一次离线近似转换。

当你位于打卡范围内时，可在手机 Cellular-Z 软件中查看经纬度坐标。手动位置可自行命名，填写值按所选坐标系处理。学校的围栏与记录以接口为准。

## 更新、备份与离线安装

详见 [维护与离线安装](docs/maintenance.md)。`dashboard.sqlite3`、`dashboard.key`、`state.sqlite3` 应配对备份；密钥丢失无法恢复学校凭据。

```sh
bash install.sh --yes
```

此命令复用已有 .env，拉取其中指定版本并检查健康状态；首次管理员仍需交互创建。离线镜像导入后可使用 `bash install.sh --skip-pull`。

## 开发与发布

源码在 moonuestc/，测试在 tests/。默认 Compose 只拉取镜像，开发构建额外使用 compose.build.yaml：

```sh
docker compose -f compose.yaml -f compose.build.yaml build
```

维护者流程见 [发布说明](docs/releasing.md)。GitHub Actions 只上传已通过服务端验证的镜像，不保存部署服务器的 SSH 密钥。

## 许可与致谢

项目代码采用 [MIT](LICENSE)。参考 [GoodNight](https://github.com/beichenO2/GoodNight)、[UESTC-MoonCheck](https://github.com/richard297779/UESTC-MoonCheck)，使用 coordtransform 的 MIT 坐标转换公式。完整署名、MoonCheck 许可证格式说明及依赖许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
