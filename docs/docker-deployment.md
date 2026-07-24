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

Tagged releases are built by GitHub Actions and pushed to GitHub Container Registry:

```text
ghcr.io/blueloverest/spider-xhs-http:<tag>
ghcr.io/blueloverest/spider-xhs-http:latest
```

For example:

```bash
docker pull ghcr.io/blueloverest/spider-xhs-http:latest
```

To publish a new image, push a `v*` tag:

```bash
git tag v0.1.0
git push origin feature/http-wrapper
git push origin v0.1.0
```

The workflow builds `linux/amd64` and `linux/arm64` images, then publishes a multi-arch manifest for both `<tag>` and `latest`.

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

Using the remote GHCR image:

```bash
docker run -d \
  --name spider-xhs \
  --restart unless-stopped \
  -p 18061:18061 \
  -e XHS_COOKIE_FILE=/run/secrets/xhs-cookie.txt \
  -e XHS_DOWNLOAD_DIR=/downloads \
  -v "$PWD/secrets/xhs-cookie.txt:/run/secrets/xhs-cookie.txt:ro" \
  -v "$PWD/data/xhs-downloads:/downloads" \
  ghcr.io/blueloverest/spider-xhs-http:latest
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

To use the remote GHCR image instead of building locally, edit `docker-compose.yml` and remove the `build` block:

```yaml
services:
  spider-xhs:
    image: ghcr.io/blueloverest/spider-xhs-http:latest
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
SPIDER_XHS_DOWNLOADER_ENDPOINT=http://spider-xhs:18061/api/xhs/download
```

If Karakeep runs outside that network, use the server host/IP:

```bash
XIAOHONGSHU_SPIDER_ENDPOINT=http://<server-ip>:18061/api/xhs/note
SPIDER_XHS_DOWNLOADER_ENDPOINT=http://<server-ip>:18061/api/xhs/download
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
