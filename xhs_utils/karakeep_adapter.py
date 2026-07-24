from datetime import datetime, timezone, timedelta


def _first_text(*values):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _image_url_from_value(value):
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""

    info_list = value.get("info_list")
    if isinstance(info_list, list):
        for item in reversed(info_list):
            if isinstance(item, dict):
                url = _first_text(item.get("url"), item.get("url_default"), item.get("url_pre"))
                if url:
                    return url

    return _first_text(value.get("url"), value.get("url_default"), value.get("url_pre"))


def _adapt_image_list(images):
    adapted = []
    if not isinstance(images, list):
        return adapted

    for image in images:
        url = _image_url_from_value(image)
        if url:
            adapted.append({"url": url})
    return adapted


def _note_type(note, card):
    note_type = _first_text(note.get("note_type"), card.get("type")).lower()
    if note_type in ("视频", "video"):
        return "video"
    if note_type in ("图集", "normal", "image"):
        return "image"
    return "unknown"


def _stats(note, card):
    interact = card.get("interact_info") if isinstance(card.get("interact_info"), dict) else {}
    return {
        "likedCount": note.get("liked_count", interact.get("liked_count", 0)) or 0,
        "collectedCount": note.get("collected_count", interact.get("collected_count", 0)) or 0,
        "commentCount": note.get("comment_count", interact.get("comment_count", 0)) or 0,
        "shareCount": note.get("share_count", interact.get("share_count", 0)) or 0,
    }


def _tags(note, card):
    if isinstance(note.get("tags"), list):
        return [str(tag) for tag in note["tags"] if str(tag).strip()]

    tag_list = card.get("tag_list")
    if not isinstance(tag_list, list):
        return []

    tags = []
    for tag in tag_list:
        if isinstance(tag, dict):
            name = _first_text(tag.get("name"))
            if name:
                tags.append(name)
    return tags


def _published_at(note, card):
    if note.get("upload_time"):
        value = str(note["upload_time"]).strip()
        if "T" in value:
            return value
        return value.replace(" ", "T") + "+08:00"

    timestamp = card.get("time")
    if timestamp is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000, timezone(timedelta(hours=8)))
        return dt.isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _video_url_from_raw(card):
    video_info = card.get("video") if isinstance(card.get("video"), dict) else {}
    streams = video_info.get("media", {}).get("stream", {}).get("h264", [])
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict):
                url = _first_text(stream.get("master_url"), stream.get("url"))
                if url:
                    return url

    consumer = video_info.get("consumer") if isinstance(video_info.get("consumer"), dict) else {}
    origin_key = _first_text(consumer.get("origin_video_key"))
    if origin_key:
        return f"https://sns-video-bd.xhscdn.com/{origin_key}"
    return ""


def _images(images):
    return [
        {"url": image["url"], "index": index, "width": None, "height": None}
        for index, image in enumerate(_adapt_image_list(images))
    ]


def _legacy_image_list(images):
    return [{"url": image["url"]} for image in _adapt_image_list(images)]


def _image_mime(url):
    lowered = url.lower().split("?", 1)[0]
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def adapt_note_for_karakeep(note, raw_note=None, include_raw=False):
    if not isinstance(note, dict):
        return None

    raw = raw_note if isinstance(raw_note, dict) else note
    card = raw.get("note_card") if isinstance(raw.get("note_card"), dict) else {}
    user = card.get("user") if isinstance(card.get("user"), dict) else {}

    title = _first_text(note.get("title"), card.get("title"))
    desc = _first_text(note.get("desc"), note.get("description"), note.get("content"), card.get("desc"))
    kind = _note_type(note, card)
    nickname = _first_text(
        note.get("nickname"),
        (note.get("user") or {}).get("nickname") if isinstance(note.get("user"), dict) else None,
        user.get("nickname"),
    )
    images = note.get("image_list") if "image_list" in note else card.get("image_list")
    adapted_images = _images(images)
    legacy_images = _legacy_image_list(images)
    cover_url = _first_text(note.get("video_cover"), adapted_images[0]["url"] if adapted_images else None)
    video_url = _first_text(note.get("video_addr"), note.get("video_url"), _video_url_from_raw(card))
    videos = []
    if kind == "video" and video_url:
        videos.append(
            {
                "url": video_url,
                "index": 0,
                "mimeType": "video/mp4",
                "coverUrl": cover_url or None,
            }
        )

    assets = []
    if kind == "video" and cover_url:
        assets.append(
            {
                "kind": "image",
                "url": cover_url,
                "index": 0,
                "role": "cover",
                "mimeType": _image_mime(cover_url),
            }
        )
    elif kind != "video":
        for image in adapted_images:
            assets.append(
                {
                    "kind": "image",
                    "url": image["url"],
                    "index": image["index"],
                    "role": "content",
                    "mimeType": _image_mime(image["url"]),
                }
            )

    for video in videos:
        asset = {
            "kind": "video",
            "url": video["url"],
            "index": len(assets),
            "role": "content",
            "mimeType": "video/mp4",
        }
        if video.get("coverUrl"):
            asset["coverUrl"] = video["coverUrl"]
        assets.append(asset)

    adapted = {
        "id": _first_text(note.get("note_id"), note.get("id")),
        "url": _first_text(note.get("note_url"), note.get("url")),
        "type": kind,
        "title": title,
        "desc": desc,
        "publishedAt": _published_at(note, card),
        "user": {
            "id": _first_text(note.get("user_id"), user.get("user_id")),
            "nickname": nickname,
            "avatar": _first_text(note.get("avatar"), user.get("avatar")),
        },
        "stats": _stats(note, card),
        "tags": _tags(note, card),
        "images": adapted_images,
        "videos": videos,
        "coverImageUrl": cover_url or None,
        "assets": assets,
        "raw": raw if include_raw else None,
        "image_list": legacy_images,
    }

    if video_url:
        adapted["video"] = {"url": video_url}

    return adapted
