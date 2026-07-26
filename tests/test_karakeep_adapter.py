import unittest

from xhs_utils.karakeep_adapter import adapt_note_for_karakeep


class KarakeepAdapterTest(unittest.TestCase):
    def test_adapts_handled_spider_note_to_karakeep_shape(self):
        spider_note = {
            "note_type": "视频",
            "title": "note title",
            "desc": "note body",
            "user_id": "user123",
            "nickname": "author",
            "avatar": "https://example.test/avatar.jpg",
            "image_list": ["https://example.test/a.jpg", "https://example.test/b.jpg"],
            "video_cover": "https://example.test/cover.jpg",
            "video_addr": "https://example.test/video.mp4",
            "note_id": "note123",
            "note_url": "https://www.xiaohongshu.com/explore/note123",
            "liked_count": 1,
            "collected_count": 2,
            "comment_count": 3,
            "share_count": 4,
            "tags": ["tag1"],
            "upload_time": "2026-07-22 12:00:00",
        }

        note = adapt_note_for_karakeep(spider_note)

        self.assertEqual(note["type"], "video")
        self.assertEqual(note["title"], "note title")
        self.assertEqual(note["desc"], "note body")
        self.assertEqual(note["user"], {"id": "user123", "nickname": "author", "avatar": "https://example.test/avatar.jpg"})
        self.assertEqual(note["stats"]["likedCount"], 1)
        self.assertEqual(note["tags"], ["tag1"])
        self.assertEqual(
            note["images"],
            [
                {"url": "https://example.test/a.jpg", "index": 0, "width": None, "height": None},
                {"url": "https://example.test/b.jpg", "index": 1, "width": None, "height": None},
            ],
        )
        self.assertEqual(note["coverImageUrl"], "https://example.test/cover.jpg")
        self.assertEqual(
            note["videos"],
            [
                {
                    "url": "https://example.test/video.mp4",
                    "index": 0,
                    "mimeType": "video/mp4",
                    "coverUrl": "https://example.test/cover.jpg",
                }
            ],
        )
        self.assertEqual(
            note["assets"],
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
        self.assertEqual(note["image_list"], [{"url": "https://example.test/a.jpg"}, {"url": "https://example.test/b.jpg"}])
        self.assertEqual(note["video"], {"url": "https://example.test/video.mp4"})
        self.assertEqual(note["id"], "note123")
        self.assertEqual(note["url"], "https://www.xiaohongshu.com/explore/note123")

    def test_adapts_raw_spider_feed_item_to_karakeep_shape(self):
        raw_note = {
            "id": "raw123",
            "url": "https://www.xiaohongshu.com/explore/raw123",
            "note_card": {
                "type": "normal",
                "title": "raw title",
                "desc": "raw body",
                "user": {"user_id": "raw-user", "nickname": "raw author", "avatar": "https://example.test/raw-avatar.jpg"},
                "interact_info": {
                    "liked_count": 5,
                    "collected_count": 6,
                    "comment_count": 7,
                    "share_count": 8,
                },
                "tag_list": [{"name": "raw-tag"}],
                "time": 1784702400000,
                "image_list": [
                    {"info_list": [{"url": "https://example.test/low.jpg"}, {"url": "https://example.test/high.jpg"}]},
                    {"url": "https://example.test/fallback.jpg"},
                ],
            },
        }

        note = adapt_note_for_karakeep(raw_note)

        self.assertEqual(note["type"], "image")
        self.assertEqual(note["title"], "raw title")
        self.assertEqual(note["desc"], "raw body")
        self.assertEqual(note["user"]["nickname"], "raw author")
        self.assertEqual(
            note["images"],
            [
                {"url": "https://example.test/high.jpg", "index": 0, "width": None, "height": None},
                {"url": "https://example.test/fallback.jpg", "index": 1, "width": None, "height": None},
            ],
        )
        self.assertEqual(note["videos"], [])
        self.assertEqual(
            note["assets"],
            [
                {
                    "kind": "image",
                    "url": "https://example.test/high.jpg",
                    "index": 0,
                    "role": "content",
                    "mimeType": "image/jpeg",
                },
                {
                    "kind": "image",
                    "url": "https://example.test/fallback.jpg",
                    "index": 1,
                    "role": "content",
                    "mimeType": "image/jpeg",
                },
            ],
        )
        self.assertEqual(note["image_list"], [{"url": "https://example.test/high.jpg"}, {"url": "https://example.test/fallback.jpg"}])
        self.assertEqual(note["id"], "raw123")
        self.assertEqual(note["url"], "https://www.xiaohongshu.com/explore/raw123")

    def test_marks_xiaohongshu_webp_transform_urls_as_webp(self):
        raw_note = {
            "id": "webp123",
            "url": "https://www.xiaohongshu.com/explore/webp123",
            "note_card": {
                "type": "normal",
                "image_list": [
                    {
                        "url": (
                            "https://sns-webpic-qc.xhscdn.com/path/image"
                            "!nd_dft_wlteh_webp_3"
                        )
                    }
                ],
            },
        }

        note = adapt_note_for_karakeep(raw_note)

        self.assertEqual(note["assets"][0]["mimeType"], "image/webp")

    def test_adapts_live_photo_images_with_video_asset(self):
        raw_note = {
            "id": "live123",
            "url": "https://www.xiaohongshu.com/explore/live123",
            "note_card": {
                "type": "normal",
                "image_list": [
                    {
                        "live_photo": True,
                        "url_default": "https://example.test/live-cover!nd_dft_wlteh_webp_3",
                        "stream": {
                            "h264": [
                                {"master_url": "https://example.test/live.mp4"},
                            ]
                        },
                    }
                ],
            },
        }

        note = adapt_note_for_karakeep(raw_note)

        self.assertEqual(note["images"][0]["liveVideoUrl"], "https://example.test/live.mp4")
        self.assertEqual(
            note["assets"],
            [
                {
                    "kind": "image",
                    "url": "https://example.test/live-cover!nd_dft_wlteh_webp_3",
                    "index": 0,
                    "role": "content",
                    "mimeType": "image/webp",
                },
                {
                    "kind": "video",
                    "url": "https://example.test/live.mp4",
                    "index": 0,
                    "role": "live",
                    "mimeType": "video/mp4",
                    "coverUrl": "https://example.test/live-cover!nd_dft_wlteh_webp_3",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
