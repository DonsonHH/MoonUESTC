# 发布前隐私检查

发布检查覆盖源码工作区、拟推送提交的完整 Git 历史、所有 Release 资产、镜像配置和每个历史文件层。命中敏感内容、检查器不可用、生产隐私清单读取失败、格式不受支持或摘要不一致时，检查返回失败，后续上传停止。

## 本地推送和 Release 上传

维护者首次在自己的源码检出中执行：

    python scripts/release_guard.py install --host YOUR_SSH_HOST --container YOUR_CONTAINER

SSH 使用维护者自己的既有认证，命令不接收学校密码或 Cookie。配置仅写入本机仓库的 Git 配置，新的检出需要重新安装。安装后常规 git push 在传送对象前执行 pre-push 检查。

每次检查通过只读 SSH 和容器 exec 读取当前维护实例的数据库及加密密钥，在内存中解密学校账号和 Cookie 以生成本次匹配值；不调用应用存储初始化、不写数据库、不创建任务、不重启容器。网页模式的可选 CLI 配置文件存在时一并检查，未创建时无需生成。敏感值只经 SSH 加密会话进入本地检查进程内存，不写清单文件、报告或 GitHub Secrets。检查结束进程退出，下一次重新读取。

GitHub Release 创建、资产上传和发布应通过同一个受保护入口：

    python scripts/guarded-publish.py --ref vX.Y.Z --artifact-list /private/release/asset-list.json -- gh release upload vX.Y.Z FILES

asset-list.json 放在仓库外，是本次所有公开文件绝对路径的 JSON 数组，包含源码、部署包、镜像、校验文件、说明及验收报告。也可用多个 --artifact 参数。受保护入口检查通过后才运行实际上传命令；命中内容或无法检查时不会执行该命令。维护者既有发行 API 助手也使用此检查器，覆盖所有写请求及请求内容。

查看不含敏感值的检查结果：

    python scripts/release_guard.py check --ref HEAD --artifact-list /private/release/asset-list.json

生产实例不可访问、账号 Cookie 损坏或必需的数据库、密钥不可用时，发布停止；应先恢复检查条件，不要跳过检查继续上传。

## GitHub Actions 和 GHCR

Privacy checks 工作流在推送、PR 和手动触发时执行合成泄漏测试、源码及历史检查。这是推送后的补充检查，本机 pre-push 负责推送前拦截。

镜像发布分为两个有依赖关系的任务：

1. 只读任务测试检查器，检查版本历史，下载所有 Release 文件，验证每个文件的 SHA-256，检查所有压缩包及镜像各层。未列入校验目录的新增资产也会被拒绝。
2. 只有前一步通过，才执行具有 packages:write 权限的上传任务。上传任务重新下载镜像，并核对前一步固定的镜像摘要，然后校验提交标签、版本和架构后上传 GHCR。资产在两步之间被替换会导致摘要不一致并停止。

手动运行镜像工作流时可设置 audit_only=true，完整检查公开发行资产并跳过上传任务，用于验收发布检查本身。

GitHub 不读取生产数据库，不保存服务器 SSH 私钥或实时隐私匹配值；CI 使用通用规则，本地发布检查另外使用当前生产数据。正式镜像仍由 Linux 验证主机导出，Actions 不重建应用。

## 检查范围与例外

检查包括数据库魔数与路径、加密运行数据、Cookie 存储、用户数据导出、私钥、访问令牌、密码和指纹赋值、镜像环境变量及已知私有值的原文、URL 编码、JSON 转义、十六进制和 Base64。镜像按原始层逐层检查，即使后续层删除了文件也会检查；未引用的二进制文件、损坏或无法解析的归档会被拒绝。

报告只有规则、不可逆文件标识和检查数量，不输出匹配内容、凭据或真实文件名。已知真实值、数据库、运行目录和加密运行数据不能添加例外。

privacy-allowlist.json 仅记录人工复核过的合成测试输入、公开第三方自测密钥和上游构建信息，绑定具体路径和完整匹配内容的 SHA-256，并注明原因。不会自动放行 tests 目录；修改样例或加入新值必须重新检查。私钥例外绑定完整密钥块，片段例外绑定整个文件。

这些检查保护项目提供的推送与发布入口。另行绕过本地钩子、直接调用上传 API 或禁用工作流，不属于受保护流程。对新的文件格式和例外，需先补充检查规则及合成阻断测试。

## 隔离验收

    python3 -B -m unittest discover -s scripts/tests -v

测试只使用合成账号、凭据和本地临时 Git 远端，验证敏感内容在传送到远端前被阻止，以及发布命令在失败时不执行。不向学校发送请求，不修改生产数据。

依据：[Git pre-push 文档](https://git-scm.com/docs/githooks#_pre_push)、[GitHub Token 权限说明](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)。
