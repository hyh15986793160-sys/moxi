# 部署 MoXi（与 XiangQ 同一台服务器）

> **正式线上改用「一个域名 + 子路径」**：导航页在 `/`，象棋在 `/xiangq/`，
> 默契在 `/moxi/`。完整步骤见根目录的 [`DEPLOY.md`](../../../DEPLOY.md)。
>
> 这份文档写的是"两个独立子域名并列"的老做法，作为备选保留：
> 好处是象棋完全不用改，坏处是要两个域名两张证书。
> 如果走新的子路径方案，第 1 步（起容器）仍然适用，第 2 步的域名配置不再需要。

两个项目完全并行：不同容器端口、不同静态目录、不同 compose 项目名。
部署 moxi 不会碰 xiangq 的任何文件。

```text
公网浏览器
    │  80 / 443
    ▼
宿主机 Nginx ─┬─ moxi.example.com/api/* → 127.0.0.1:8001
              └─ 其它                    → /opt/moxi/sites/moxi

Docker 容器只跑 FastAPI，镜像里没有任何前端文件。
```

## 端口占用一览

| 用途 | xiangq | moxi |
| --- | --- | --- |
| 宿主监听 | 127.0.0.1:8000 | 127.0.0.1:8001 |
| 容器内 | 8000 | 8000 |
| 静态目录 | /opt/xiangq/sites/xiangq | /opt/moxi/sites/moxi |
| 项目根 | /opt/xiangq | /opt/moxi |

`8001` 只绑 `127.0.0.1`，公网只需要放行 80 和 443。如果 8001 已被占用，
改 `docker-compose.yml` 里的 `MOXI_PORT`，并同步改 Nginx 的 `proxy_pass`。

## 1. 上传并启动容器

```bash
sudo mkdir -p /opt/moxi
# 把 release/moxi-<version>.zip 解压到 /opt/moxi
cd /opt/moxi
docker compose up -d --build
curl http://127.0.0.1:8001/api/health
```

预期返回：

```json
{"status":"ok","service":"moxi-api","version":"0.1.0"}
```

静态文件放在 `/opt/moxi/sites/moxi`，解压后应该已经就绪：

```bash
ls /opt/moxi/sites/moxi/index.html
```

## 2. 域名与证书

给 `moxi.example.com` 加一条 A 记录指向这台机器（与 xiangq 用同一台服务器也可以，
只是域名不同）。

先用 HTTP 配置申请证书：

```bash
sudo cp deploy/nginx/moxi.bootstrap.conf /etc/nginx/sites-available/moxi
sudo sed -i 's/moxi\.example\.com/你的域名/g' /etc/nginx/sites-available/moxi
sudo ln -sfn /etc/nginx/sites-available/moxi /etc/nginx/sites-enabled/moxi
sudo nginx -t && sudo systemctl reload nginx

sudo certbot certonly --webroot -w /var/www/certbot \
  -d 你的域名 --agree-tos -m 你的邮箱 --no-eff-email
```

签发成功后切正式配置：

```bash
sudo cp deploy/nginx/moxi.conf /etc/nginx/sites-available/moxi
sudo sed -i 's/moxi\.example\.com/你的域名/g' /etc/nginx/sites-available/moxi
sudo nginx -t && sudo systemctl reload nginx
```

访问 `https://你的域名` 检查：页面正常、`/api/health` 返回 200、能开一局。

## 3. 后续更新

只改了前端：替换静态目录，不用重启容器。

```bash
sudo rsync -a --delete 新版本/sites/moxi/ /opt/moxi/sites/moxi/
```

改了接口：重建容器。

```bash
cd /opt/moxi
docker compose up -d --build
```

## 如果想挂在同一个域名下的子路径

上面用的是独立子域名（推荐，最省事）。如果一定要放在 `xiangq.example.com/moxi/`，
需要两处一起改，缺一不可：

1. 构建前端时加 `--base=/moxi/`（或在 `vite.config.ts` 里设 `base: '/moxi/'`），
   否则 `/assets/*` 会 404。
2. Nginx 里把 `location /` 的 `root` 改到该子目录，并让 `try_files` 回落正确：

```nginx
location /moxi/ {
    alias /opt/xiangq/sites/xiangq-moxi/;
    try_files $uri $uri/ /moxi/index.html;
}

location /moxi/api/ {
    proxy_pass http://127.0.0.1:8001/api/;
    proxy_read_timeout 60s;
}
```

这种情况下前端要用 `VITE_API_BASE=/moxi/api` 构建，否则请求会打到 xiangq 的接口上。

## 排查

**页面上一直在等，房间码也变了** —— 容器重启过，房间在内存里，重启即丢。重新开一局。

**502** —— 先看容器：

```bash
curl http://127.0.0.1:8001/api/health
docker compose ps
docker compose logs -f app
```

**能开局但加不进去** —— 检查 `proxy_pass` 端口是否和 `MOXI_PORT` 一致。

**日志被轮询刷屏** —— Nginx 里 `/api/` 已设 `access_log off`；接口日志看
`docker compose logs -f app`。
