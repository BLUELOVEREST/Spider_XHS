import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

import server


class FakePcApi:
    def get_note_info(self, url, cookies):
        return True, "success", {
            "data": {
                "items": [
                    {
                        "id": "note123",
                        "url": url,
                        "note_card": {
                            "type": "normal",
                            "title": "note title",
                            "desc": "note body",
                            "user": {
                                "user_id": "user123",
                                "nickname": "author",
                                "avatar": "https://example.test/avatar.jpg",
                            },
                            "interact_info": {
                                "liked_count": 1,
                                "collected_count": 2,
                                "comment_count": 3,
                                "share_count": 4,
                            },
                            "image_list": [
                                {"info_list": [{"url": "https://example.test/low.jpg"}, {"url": "https://example.test/a.jpg"}]}
                            ],
                            "tag_list": [{"name": "tag1"}],
                            "time": 1784702400000,
                        },
                    }
                ]
            }
        }


class FakeVideoPcApi:
    def get_note_info(self, url, cookies):
        return True, "success", {
            "data": {
                "items": [
                    {
                        "id": "video123",
                        "url": url,
                        "note_card": {
                            "type": "video",
                            "title": "video title",
                            "desc": "video body",
                            "user": {
                                "user_id": "user456",
                                "nickname": "video author",
                                "avatar": "https://example.test/video-avatar.jpg",
                            },
                            "interact_info": {
                                "liked_count": 10,
                                "collected_count": 20,
                                "comment_count": 30,
                                "share_count": 40,
                            },
                            "image_list": [
                                {
                                    "info_list": [
                                        {"url": "https://example.test/cover-low.jpg"},
                                        {"url": "https://example.test/cover.jpg"},
                                    ]
                                }
                            ],
                            "video": {
                                "media": {
                                    "stream": {
                                        "h264": [
                                            {"master_url": "https://example.test/video.mp4"},
                                        ]
                                    }
                                }
                            },
                            "tag_list": [],
                            "time": 1784702400000,
                        },
                    }
                ]
            }
        }


class CapturingPcApi(FakePcApi):
    def __init__(self):
        self.urls = []

    def get_note_info(self, url, cookies):
        self.urls.append(url)
        return super().get_note_info(url, cookies)


class FakeRedirectResponse:
    def __init__(self, url):
        self.url = url

    def raise_for_status(self):
        return None


class ServerApiTest(unittest.TestCase):
    def test_note_endpoint_returns_karakeep_compatible_note(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=test"}, clear=True):
            with patch.object(server, "get_pc_api", return_value=FakePcApi()):
                body = server.get_note(
                    server.NoteRequest(url="https://www.xiaohongshu.com/explore/note123?xsec_token=token")
                )

        self.assertTrue(body["success"])
        self.assertEqual(body["msg"], "success")
        self.assertIsNone(body["errorCode"])
        self.assertEqual(body["note"]["type"], "image")
        self.assertEqual(body["note"]["title"], "note title")
        self.assertEqual(body["note"]["desc"], "note body")
        self.assertEqual(body["note"]["user"]["nickname"], "author")
        self.assertEqual(body["note"]["images"], [{"url": "https://example.test/a.jpg", "index": 0, "width": None, "height": None}])
        self.assertEqual(
            body["note"]["assets"],
            [
                {
                    "kind": "image",
                    "url": "https://example.test/a.jpg",
                    "index": 0,
                    "role": "content",
                    "mimeType": "image/jpeg",
                }
            ],
        )
        self.assertEqual(body["note"]["image_list"], [{"url": "https://example.test/a.jpg"}])

    def test_note_endpoint_returns_video_note_assets(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=test"}, clear=True):
            with patch.object(server, "get_pc_api", return_value=FakeVideoPcApi()):
                body = server.get_note(
                    server.NoteRequest(url="https://www.xiaohongshu.com/explore/video123?xsec_token=token")
                )

        self.assertTrue(body["success"])
        self.assertEqual(body["note"]["type"], "video")
        self.assertEqual(body["note"]["coverImageUrl"], "https://example.test/cover.jpg")
        self.assertEqual(
            body["note"]["videos"],
            [
                {
                    "url": "https://example.test/video.mp4",
                    "index": 0,
                    "mimeType": "video/mp4",
                    "coverUrl": "https://example.test/cover.jpg",
                }
            ],
        )
        self.assertEqual(body["note"]["video"], {"url": "https://example.test/video.mp4"})
        self.assertEqual(
            body["note"]["assets"],
            [
                {
                    "kind": "image",
                    "url": "https://example.test/cover.jpg",
                    "index": 0,
                    "role": "cover",
                    "mimeType": "image/jpeg",
                },
                {
                    "kind": "video",
                    "url": "https://example.test/video.mp4",
                    "index": 1,
                    "role": "content",
                    "mimeType": "video/mp4",
                    "coverUrl": "https://example.test/cover.jpg",
                },
            ],
        )

    def test_note_endpoint_returns_auth_required_without_cookie(self):
        with patch.dict(os.environ, {}, clear=True):
            body = server.get_note(server.NoteRequest(url="https://www.xiaohongshu.com/explore/note123"))

        self.assertFalse(body["success"])
        self.assertEqual(body["errorCode"], "AUTH_REQUIRED")
        self.assertIsNone(body["note"])

    def test_note_endpoint_rejects_invalid_url(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=test"}, clear=True):
            body = server.get_note(server.NoteRequest(url="https://example.com/not-xhs"))

        self.assertFalse(body["success"])
        self.assertEqual(body["errorCode"], "INVALID_URL")
        self.assertIsNone(body["note"])

    def test_note_endpoint_resolves_xhslink_without_cookie(self):
        final_url = (
            "http://www.xiaohongshu.com/discovery/item/6a534bdb000000000f02b2b9"
            "?xsec_token=CBeDhig1TzsewwS7_ToMAYUd8pyf4GwPtUKw290WAfD74=&xhsshare=CopyLink"
        )
        security_url = (
            "https://www.xiaohongshu.com/404/sec_ZjRRYBqw"
            f"?source=xhs_sec_server&originalUrl={quote(final_url, safe='')}"
        )
        pc_api = CapturingPcApi()

        with patch.dict(os.environ, {"XHS_COOKIE": "a1=test"}, clear=True):
            with patch.object(server, "get_pc_api", return_value=pc_api):
                with patch("server.requests.get", return_value=FakeRedirectResponse(security_url)) as request_get:
                    body = server.get_note(server.NoteRequest(url="http://xhslink.cn/o/9EVc7ZDTi74"))

        self.assertTrue(body["success"])
        self.assertEqual(pc_api.urls, [final_url])
        request_get.assert_called_once()
        kwargs = request_get.call_args.kwargs
        self.assertTrue(kwargs["allow_redirects"])
        self.assertNotIn("cookies", kwargs)
        self.assertNotIn("Cookie", kwargs["headers"])

    def test_download_endpoint_writes_media_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XHS_COOKIE": "a1=test", "XHS_DOWNLOAD_DIR": temp_dir}, clear=True):
                with patch.object(server, "get_pc_api", return_value=FakeVideoPcApi()):
                    with patch("server.download_media_url") as download_media_url:
                        download_media_url.side_effect = lambda url, path: path.write_bytes(url.encode("utf-8"))

                        body = server.download_note(
                            server.DownloadRequest(
                                url="https://www.xiaohongshu.com/explore/video123?xsec_token=token",
                                mediaTypes=["image", "video"],
                            )
                        )

        self.assertTrue(body["success"])
        self.assertIsNone(body["errorCode"])
        self.assertEqual(body["note"]["id"], "video123")
        self.assertEqual(
            [(item["kind"], item["role"], item["name"]) for item in body["files"]],
            [
                ("image", "cover", "cover.jpg"),
                ("video", "content", "video.mp4"),
            ],
        )
        for item in body["files"]:
            self.assertTrue(item["path"].startswith(temp_dir))
            self.assertGreater(item["sizeBytes"], 0)

    def test_download_endpoint_writes_image_note_files_with_stable_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XHS_COOKIE": "a1=test", "XHS_DOWNLOAD_DIR": temp_dir}, clear=True):
                with patch.object(server, "get_pc_api", return_value=FakePcApi()):
                    with patch("server.download_media_url") as download_media_url:
                        download_media_url.side_effect = lambda url, path: path.write_bytes(b"image-data")

                        body = server.download_note(
                            server.DownloadRequest(
                                url="https://www.xiaohongshu.com/explore/note123?xsec_token=token",
                                mediaTypes=["image"],
                            )
                        )

        self.assertTrue(body["success"])
        self.assertIsNone(body["errorCode"])
        self.assertEqual(body["note"]["type"], "image")
        self.assertEqual(
            [(item["kind"], item["role"], item["name"], item["index"]) for item in body["files"]],
            [
                ("image", "content", "image_0.jpg", 0),
            ],
        )

    def test_download_endpoint_returns_no_video_for_video_only_image_note(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=test"}, clear=True):
            with patch.object(server, "get_pc_api", return_value=FakePcApi()):
                body = server.download_note(
                    server.DownloadRequest(
                        url="https://www.xiaohongshu.com/explore/note123?xsec_token=token",
                        mediaTypes=["video"],
                    )
                )

        self.assertFalse(body["success"])
        self.assertEqual(body["errorCode"], "NO_VIDEO")
        self.assertEqual(body["files"], [])
        self.assertEqual(body["note"]["type"], "image")

    def test_download_endpoint_resolves_xhslink_before_download(self):
        final_url = (
            "https://www.xiaohongshu.com/explore/video123"
            "?xsec_token=token"
        )
        pc_api = CapturingPcApi()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XHS_COOKIE": "a1=test", "XHS_DOWNLOAD_DIR": temp_dir}, clear=True):
                with patch.object(server, "get_pc_api", return_value=pc_api):
                    with patch("server.requests.get", return_value=FakeRedirectResponse(final_url)):
                        with patch("server.download_media_url") as download_media_url:
                            download_media_url.side_effect = lambda url, path: path.write_bytes(b"image-data")

                            body = server.download_note(
                                server.DownloadRequest(
                                    url="https://xhslink.com/a/abc123",
                                    mediaTypes=["image"],
                                )
                            )

        self.assertTrue(body["success"])
        self.assertEqual(pc_api.urls, [final_url])
        self.assertEqual(body["files"][0]["name"], "image_0.jpg")


if __name__ == "__main__":
    unittest.main()
