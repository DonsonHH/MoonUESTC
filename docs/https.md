# 公网 HTTPS

容器提供 HTTP 8080，主机默认绑定 127.0.0.1:8088，由同机 Nginx 等代理提供公网 HTTPS。已有 IP 或域名证书均可使用。

1. 在 .env 填真实浏览器地址，例如 `https://192.0.2.10:8443` 或 `https://checkin.example.com`。非标准端口必须写入。
2. 保持 MOON_BIND_ADDRESS=127.0.0.1、MOON_ALLOW_INSECURE_HTTP=0。
3. 参考 deploy/nginx-https.conf.example，填写证书、私钥、监听端口和 server_name；保持 Host 转发为 `$http_host`，包含非标准端口。
4. 检查代理配置后平滑重载；宿主机防火墙只需放行实际 HTTPS 端口，后端 8088 无需向公网放行。
5. 从其他设备访问配置的地址，检查证书覆盖该 IP/域名。

证书放在代理主机的私有目录，续期后重载代理，不放入源码、镜像或公共部署包。代理与应用异机时应明确设置私有网络上游和防火墙，127.0.0.1 不能作为跨主机地址。

程序校验 Host 和写入请求 Origin；地址、协议和端口必须与 MOON_PUBLIC_URL 一致。公网 HTTP 不受支持；局域网 HTTP 只用于私有 IP、localhost 或 .local 地址。
