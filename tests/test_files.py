from slack_linear_ai_bot.files import (
    build_thread_images_block,
    image_mime_for_slack_download,
    is_probably_html_page,
    sniff_raster_image_mime,
)


def test_image_validation_rejects_html_and_sniffs_png() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 20
    assert sniff_raster_image_mime(png) == "image/png"
    assert image_mime_for_slack_download("text/plain", png) == "image/png"
    assert is_probably_html_page(b"<!doctype html><html></html>")
    assert image_mime_for_slack_download("image/png", b"<html>login</html>") is None


def test_thread_image_block_preserves_evidence_links_and_limit() -> None:
    messages = [
        {
            "files": [
                {
                    "mimetype": "image/png",
                    "name": f"shot-{index}.png",
                    "permalink": f"https://slack.test/files/{index}",
                    "url_private": f"https://files.slack.test/{index}",
                }
                for index in range(3)
            ]
        }
    ]
    block, urls = build_thread_images_block(messages, 2)
    assert "2 of 3 included" in block
    assert "https://slack.test/files/0" in block
    assert urls == ["https://files.slack.test/0", "https://files.slack.test/1"]
