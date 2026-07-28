# Docker Deployment

This fork runs Spider_XHS as an HTTP service for Karakeep or other callers.

## Prerequisites

- Docker Engine with Compose support.
- A valid logged-in Xiaohongshu Cookie.
- A writable host directory for downloaded media.

## Files

- `Dockerfile`: Builds the HTTP service image.
- `docker-compose.example.yml`: Example Compose service.
- `secrets/xhs-cookie.txt`: Cookie file mounted into the container. Create this file locally; do not commit it.
- `data/xhs-downloads/`: Shared download directory mounted as `/downloads`.

## Build

```bash
docker build -t spider-xhs-http:latest .
```

## Remote Image

Current maintained remotes:

```text
origin   Gitea code archive and Gitea Actions image builds
github   GitHub fork: git@github.com:BLUELOVEREST/Spider_XHS.git
upstream original project
```

Keep development branches synchronized to both Gitea and the GitHub fork:

```bash
git push origin feature/http-wrapper
git push github feature/http-wrapper
```

Current image builds run on Gitea Actions and publish `linux/amd64` images to
the self-hosted Gitea registry:

```text
192.168.200.101:54453/zhangzhicheng/eric-xhs-spider:<tag>
192.168.200.101:54453/zhangzhicheng/eric-xhs-spider:latest
```

The `v3.0.0-eric.4` test tag was built successfully on Gitea in about 15
minutes, which is acceptable for this resolver. The Dockerfile uses the
Tsinghua Debian and PyPI mirrors plus the npmmirror npm registry during the
build. The remaining external risk is the Nodesource setup script used to
install Node.js 20:

```text
https://deb.nodesource.com/setup_20.x
```

If this step becomes slow or unstable, consider switching the Dockerfile to a
multi-stage setup that copies Node.js from `node:20-slim` or using a small
prebuilt runtime base image. For now, Gitea is the preferred image builder for
this repository.

To publish a new Gitea image, push the next `v*` tag to `origin`:

```bash
git tag v3.0.0-eric.5
git push origin v3.0.0-eric.5
```

Push tags to `github` only when you intentionally want the GitHub fork workflow
to build and publish GHCR multi-arch images.

## Run With Docker

Using a Cookie file:

```bash
mkdir -p secrets data/xhs-downloads
printf '%s' 'a1=...; webId=...; web_session=...' > secrets/xhs-cookie.txt

docker run -d \
  --name spider-xhs \
  --restart unless-stopped \
  -p 18061:18061 \
  -e XHS_COOKIE_FILE=/run/secrets/xhs-cookie.txt \
  -e XHS_DOWNLOAD_DIR=/downloads \
  -v "$PWD/secrets/xhs-cookie.txt:/run/secrets/xhs-cookie.txt:ro" \
  -v "$PWD/data/xhs-downloads:/downloads" \
  spider-xhs-http:latest
```

Using the remote Gitea image:

```bash
docker run -d \
  --name spider-xhs \
  --restart unless-stopped \
  -p 18061:18061 \
  -e XHS_COOKIE_FILE=/run/secrets/xhs-cookie.txt \
  -e XHS_DOWNLOAD_DIR=/downloads \
  -v "$PWD/secrets/xhs-cookie.txt:/run/secrets/xhs-cookie.txt:ro" \
  -v "$PWD/data/xhs-downloads:/downloads" \
  192.168.200.101:54453/zhangzhicheng/eric-xhs-spider:v3.0.0-eric.4
```

Using an environment variable directly:

```bash
docker run -d \
  --name spider-xhs \
  --restart unless-stopped \
  -p 18061:18061 \
  -e XHS_COOKIE='a1=...; webId=...; web_session=...' \
  -e XHS_DOWNLOAD_DIR=/downloads \
  -v "$PWD/data/xhs-downloads:/downloads" \
  spider-xhs-http:latest
```

## Run With Compose

```bash
mkdir -p secrets data/xhs-downloads
printf '%s' 'a1=...; webId=...; web_session=...' > secrets/xhs-cookie.txt
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

To use the remote Gitea image instead of building locally, edit `docker-compose.yml` and remove the `build` block:

```yaml
services:
  spider-xhs:
    image: 192.168.200.101:54453/zhangzhicheng/eric-xhs-spider:v3.0.0-eric.4
    container_name: spider-xhs
    restart: unless-stopped
    ports:
      - "18061:18061"
    environment:
      XHS_COOKIE_FILE: /run/secrets/xhs-cookie.txt
      XHS_DOWNLOAD_DIR: /downloads
      XHS_REQUEST_TIMEOUT_SECONDS: "30"
      XHS_DOWNLOAD_TIMEOUT_SECONDS: "120"
    volumes:
      - ./secrets/xhs-cookie.txt:/run/secrets/xhs-cookie.txt:ro
      - ./data/xhs-downloads:/downloads
```

Then run:

```bash
docker compose pull
docker compose up -d
```

## Verify

Health check:

```bash
curl -s http://127.0.0.1:18061/health
```

Expected:

```json
{"status":"ok"}
```

Resolve a note:

```bash
curl -s \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/<note-id>?xsec_token=<token>"}' \
  http://127.0.0.1:18061/api/xhs/note
```

Download media:

```bash
curl -s \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/<note-id>?xsec_token=<token>","mediaTypes":["image","video"]}' \
  http://127.0.0.1:18061/api/xhs/download
```

Downloaded files are written under:

```text
./data/xhs-downloads/<note-id>/
```

## Karakeep Worker Configuration

When Karakeep and Spider_XHS run in the same Compose network, point Karakeep at the service name:

```bash
XIAOHONGSHU_BACKEND=spider_xhs
XIAOHONGSHU_SPIDER_ENDPOINT=http://spider-xhs:18061/api/xhs/note
XIAOHONGSHU_SPIDER_DOWNLOAD_ENDPOINT=http://spider-xhs:18061/api/xhs/download
```

If Karakeep runs outside that network, use the server host/IP:

```bash
XIAOHONGSHU_SPIDER_ENDPOINT=http://<server-ip>:18061/api/xhs/note
XIAOHONGSHU_SPIDER_DOWNLOAD_ENDPOINT=http://<server-ip>:18061/api/xhs/download
```

## Environment Variables

- `XHS_COOKIE`: Cookie string. Highest priority.
- `XHS_COOKIE_FILE`: Path to a mounted Cookie file.
- `COOKIES`: Legacy Cookie environment variable.
- `XHS_DOWNLOAD_DIR`: Directory where downloaded media is written. Defaults to `/downloads`.
- `XHS_REQUEST_TIMEOUT_SECONDS`: Timeout for resolver requests. Defaults to `30`.
- `XHS_DOWNLOAD_TIMEOUT_SECONDS`: Timeout for media downloads. Defaults to `120`.
- `XHS_INCLUDE_RAW`: Set to `true` to include raw Xiaohongshu response data in `/api/xhs/note`.

Cookie priority is `XHS_COOKIE` > `XHS_COOKIE_FILE` > `COOKIES`.

## Troubleshooting

- `AUTH_REQUIRED`: Cookie is missing, expired, or invalid.
- `INVALID_URL`: The URL is not a supported Xiaohongshu note URL or short link.
- `NO_VIDEO`: `mediaTypes=["video"]` was requested for an image note.
- `NO_MEDIA`: The note parsed successfully but no downloadable assets were found.
- `DOWNLOAD_FAILED`: The media URL could not be downloaded or the download directory is not writable.

Check logs:

```bash
docker logs -f spider-xhs
```

Check Compose service status:

```bash
docker compose ps
```
