# MoonUESTC · 晚安成电学生门户

基于 [horoscope963852/MoonUESTC](https://github.com/horoscope963852/MoonUESTC) 的 MIT 开源代码，增加面向学生的登录与每日计划，以及仅限私有连接的管理端。原版权、许可和第三方声明保留在 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

当前版本：**0.5.1+donson.15**。本分支从源码构建；上游 v0.5.1 镜像不包含这些功能。原版文档保留在 [README.upstream.md](README.upstream.md)。

## 功能

- 学号及学校密码登录，首次或校方要求时在学校原页面完成验证；不用安装扩展或复制 Cookie。
- 学校密码、学校 Cookie 与可信设备资料加密托管，本站登录密码哈希使用 Argon2id。首次使用前明确告知保存哪些信息、用途与删除边界，并保存版本化确认记录。
- 每位已绑定账号预留独立计划发起时段，靠近偏好时间；时段内小幅错峰，位置可在本人确认的实际范围内浮动。始终校验该账号的校方围栏和实时开放时段。
- 自动任务失败约两分钟后在预留的重试时段再试一次；已发送的签到只复查结果，绝不盲目重发。再次失败在页面报错。验证码、二次验证或后台重登限制出现时，可在用户端重新验证学校登录，验证成功后恢复；后台不会反复尝试验证码。本版本不接 QQbot。
- 管理端只在回环端口提供，通过 Tailscale/SSH 转发访问；公网没有管理员入口或管理 API。管理员可授权额外学号、管理用户与托管账号。
- 一个后台 HTTP worker 顺序处理任务，不为每日签到启动浏览器。临时浏览器只用于人工校方验证，同时最多两个隔离会话。

学生端与私有管理端均支持浅色、深色和跟随系统，默认跟随系统。运行记录默认从北京时间今天及前两天读取，每批最多 30 条，点击“加载更多记录”继续向前查看全部历史。托管说明已精简，信息处理范围及已有同意记录保持一致。

## 从源码部署

需要 Docker、Compose v2，及学生端域名的 HTTPS 反向代理。只使用本人或明确授权的账号，不绕过学校的定位、时间或二次验证要求。

1. 复制 `.env.example` 为私有 `.env`，填写 `MOON_PUBLIC_URL` 为实际学生端 HTTPS 地址，设置宿主机对应的 `PUID`/`PGID`，生成并填入随机辅助服务密钥 `MOON_BROWSER_ASSIST_KEY`（至少32字节随机数据）。按需设置学号段、开放位置和执行窗口，详见 [用户端说明](docs/donson-portal.md)。不要将真实学校密码写入配置示例。
2. 在有 Docker 权限的环境构建并创建数据目录：

```sh
mkdir -p data config
docker build -t moonuestc-local:student-portal .
docker build -t moonuestc-browser:local browser_assist
```

辅助浏览器默认基于上一步构建的 `moonuestc-local:student-portal`；若主镜像使用其他标签，在辅助浏览器构建时传入 `--build-arg MOON_APP_IMAGE=实际主镜像标签`。

3. 初始化管理员（交互输入，不保存明文初始化密码文件），再启动服务：

```sh
docker compose -f compose.yaml -f compose.browser.yaml -f compose.admin.yaml run --rm moonuestc init-admin
docker compose -f compose.yaml -f compose.browser.yaml -f compose.admin.yaml up -d
```

4. 仅将学生服务的回环端口配置到 HTTPS 入口。管理端 `127.0.0.1:4497` 不创建公网路由，按照 [私有管理说明](docs/private-admin.md) 配置专用 SSH 密钥和本地转发。Windows 可用 `deploy/launch-admin.mjs` 和实际私有 SSH 配置创建快捷方式。

5. 在管理端授权学生范围；学生阅读托管说明、完成学校验证，选择实际地点与时间。只有完成一次经学校确认的手动签到后才能开启自动计划。时段满时不能开启新计划；关闭计划不删除资料，删除用户/账号及备份的边界见登录告知。

## 运行边界

专属时段约束的是计划发起；网络延迟、学校认证和服务中断仍可能使任务转入重试或失败，不保证签到成功。学校要求的验证码、MFA 必须本人完成。位置是用户配置的实际区域，不是服务器测得的实时 GPS；拒绝地点不会被挪进围栏。登录不会提交签到，确认托管说明也不会自动开启每日计划。

数据目录及其密钥必须配套备份。不要上传 `.env`、数据库、Cookie、SSH 私钥、真实管理 SSH 配置或部署截图。发布前保留 [隐私检查](docs/privacy-release.md)，同时检查源码和拟推送的历史。贡献及与上游关系见 [开源说明](docs/open-source.md)。

## 开发与验证

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s scripts/tests -v
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

浏览器 helper 的原生回归位于 `browser_assist/tests/test_navigation.py`，须在对应 Chromium helper 镜像内执行。普通应用测试不访问真实学校账号，不应把合成测试当成真实签到证明。
