# 开源与上游关系

上游 [MoonUESTC](https://github.com/horoscope963852/MoonUESTC) 的 LICENSE 是 MIT，允许修改及再分发。分发源码或构建产物时保留原版权声明、完整 MIT 许可与免责文本，保留 THIRD_PARTY_NOTICES.md 和 third_party/ 中实际使用依赖的许可证。学校网页不属于本项目，不应将认证后的网页样本、校徽或学生资料随源码再分发。

当前仍大量延续原项目的协议、状态机、CLI 与后端结构，建议在 GitHub **fork 原仓库**，将此版本作为独立分支维护，README 清楚说明新增的学生端、私有管理员入口及部署差异。Fork 本身就是可独立维护的仓库，且保留 GitHub 上的上游关联，方便后续同步和回馈。若未来定位和代码均形成独立产品，也可建立独立仓库，但仍保留许可和来源说明；新建仓库不会消除 MIT 义务。

本地 Git 从导入上游 69ebe71 的源码快照开始，不具有完整的原仓库历史。后续真正发布 fork 时，应先创建/克隆 fork，再把经过检查的当前源码差异应用到发布分支，验证后推送；不要直接把含部署材料的整个 Jetson 工作区上传，也不要强推替换上游默认分支。维护者的 fork 位于 https://github.com/DonsonHH/MoonUESTC；发布分支基于真实上游历史导入清理后的源码，不混入含部署记录的本地开发历史。

发布范围仅限应用源码、构建配置、脱敏示例、测试、许可和文档。排除真实 .env、config/、data/、数据库、Cookie、key、备份、管理端专用 SSH 配置和密钥、.agents 证据/截图。`.gitignore` 不能清理已经进入 Git 历史的内容，所以需要同时检查当前文件和所有拟发布的历史对象。测试数据应明确为合成内容。

生产学号范围与地点范围来自私有环境变量；compose 示例不预填个人学号段。管理端桌面启动器可以分发通用脚本和配置示例，实际 `deploy/admin-ssh.config`、known_hosts 和私钥保留在部署者设备上。不要把公共 UI 中的校园名称或本地测试数据当成校方授权或官方背书。

参考：[上游许可](https://github.com/horoscope963852/MoonUESTC/blob/main/LICENSE)、[GitHub Fork 说明](https://docs.github.com/en/pull-requests/reference/forks)、[GitHub 仓库许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。
