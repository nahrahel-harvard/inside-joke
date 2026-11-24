"""The SVG backend renders model-written markup locally, so the sanitizer must
remove anything that can pull pixels, words or code from outside the document.
Cases come from the 2026-11-24 adversarial review, which got a local file's
pixels into a render through <feImage href> and a namespaced <s:image>."""
import unittest

from inside_joke.art import _sanitize_svg

HOSTILE = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:s="http://www.w3.org/2000/svg"
 xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
<filter id="f"><feImage href="/etc/secret.png"/></filter>
<s:image href='/abs/x.png' width="10" height="10"/>
<image xlink:href="https://evil.example/a.png"/>
<text x="1">hi</text><style>@import url(https://x.example)</style>
<rect fill="url(https://evil.example/p.svg#a)" filter="url(#f)" width="10" height="10"/>
<use href="#r"/><script>alert(1)</script></svg>"""


class SanitizerTest(unittest.TestCase):
    def setUp(self):
        self.out = _sanitize_svg(HOSTILE)

    def test_external_and_local_references_removed(self):
        for bad in ("feImage", "s:image", "evil.example", "secret", "/abs/x.png", "x.example"):
            self.assertNotIn(bad, self.out)

    def test_text_style_script_removed(self):
        for bad in ("<text", "<style", "<script", "alert"):
            self.assertNotIn(bad, self.out)

    def test_in_document_references_kept(self):
        self.assertIn('href="#r"', self.out)
        self.assertIn("url(#f)", self.out)

    def test_no_svg_raises(self):
        with self.assertRaises(ValueError):
            _sanitize_svg("no markup here")


if __name__ == "__main__":
    unittest.main()
