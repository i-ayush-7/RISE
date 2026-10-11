import os
import re
import unittest
from pathlib import Path

class TestWebStatic(unittest.TestCase):
    def setUp(self):
        self.web_dir = Path(__file__).parent.parent / "web"

    def test_required_files_exist(self):
        required = [
            "index.html",
            "css/app.css",
            "js/dom.js",
            "js/icons.js",
            "js/api.js",
            "js/store.js",
            "js/scene.js",
            "js/views/home.js",
            "js/views/board.js",
            "js/views/alerts.js",
            "js/views/plan.js",
            "js/views/log.js",
            "js/views/more.js",
            "js/main.js",
            "assets/house-rain.jpg"
        ]
        for rel in required:
            path = self.web_dir / rel
            self.assertTrue(path.exists(), f"File {rel} does not exist at {path}")

    def test_jpeg_magic_bytes(self):
        jpg_path = self.web_dir / "assets" / "house-rain.jpg"
        self.assertTrue(jpg_path.exists())
        with open(jpg_path, "rb") as f:
            header = f.read(3)
        self.assertEqual(header, b"\xff\xd8\xff", "house-rain.jpg must start with JPEG magic bytes")

    def test_index_html_structure(self):
        html_path = self.web_dir / "index.html"
        content = html_path.read_text(encoding="utf-8")

        # exactly one <script>
        scripts = re.findall(r"<script\b[^>]*>", content, re.IGNORECASE)
        self.assertEqual(len(scripts), 1, f"index.html must have exactly one <script>, found {len(scripts)}")
        self.assertIn('type="module"', scripts[0])
        self.assertIn('src="/js/main.js"', scripts[0])

        self.assertIn('lang="en"', content.lower())
        self.assertIn('viewport-fit=cover', content)

        # no on*= attributes
        on_attrs = re.findall(r'\bon[a-zA-Z]+\s*=', content)
        self.assertEqual(on_attrs, [], f"index.html must not contain inline event handlers: {on_attrs}")

    def test_import_specifiers_resolve(self):
        js_files = list((self.web_dir / "js").rglob("*.js"))
        self.assertGreater(len(js_files), 5)
        for js_file in js_files:
            text = js_file.read_text(encoding="utf-8")
            import_matches = re.findall(r'''(?:import|export)\s+.*?from\s+['"](.*?)['"]''', text)
            for imp in import_matches:
                target = (js_file.parent / imp).resolve()
                self.assertTrue(target.exists(), f"Import {imp!r} in {js_file.name} does not resolve to existing file {target}")

    def test_no_forbidden_apis(self):
        forbidden_apis = [
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "document.write",
            "eval(",
            "new Function",
            "javascript:"
        ]
        for p in self.web_dir.rglob("*"):
            if p.is_file() and p.suffix in [".js", ".html", ".css"]:
                text = p.read_text(encoding="utf-8")
                for api in forbidden_apis:
                    self.assertNotIn(api, text, f"Forbidden API {api!r} found in {p.relative_to(self.web_dir)}")

    def test_no_forbidden_urls(self):
        url_re = re.compile(r'https?://[^\s\'"<>]+')
        allowed = "http://www.w3.org/2000/svg"
        for p in self.web_dir.rglob("*"):
            if p.is_file() and p.suffix in [".js", ".html", ".css"]:
                text = p.read_text(encoding="utf-8")
                found_urls = url_re.findall(text)
                for u in found_urls:
                    self.assertEqual(u, allowed, f"Forbidden URL {u!r} found in {p.relative_to(self.web_dir)}")

    def test_no_forbidden_copy(self):
        forbidden_copy = [
            "Your family is safe",
            "Send Reminder",
            "Last seen",
            "Mom",
            "Dad",
            "Sister"
        ]
        for p in self.web_dir.rglob("*"):
            if p.is_file() and p.suffix in [".js", ".html", ".css"]:
                text = p.read_text(encoding="utf-8")
                for copy in forbidden_copy:
                    self.assertNotIn(copy, text, f"Forbidden copy {copy!r} found in {p.relative_to(self.web_dir)}")

    def test_utf8_without_bom_and_newline(self):
        for p in self.web_dir.rglob("*"):
            if p.is_file() and p.suffix in [".js", ".html", ".css"]:
                with open(p, "rb") as f:
                    data = f.read()
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), f"File {p.name} contains UTF-8 BOM")
                self.assertTrue(data.endswith(b"\n") or data.endswith(b"\r\n"), f"File {p.name} must end with a newline")
                # decode test
                data.decode("utf-8")

    def test_css_requirements(self):
        css_path = self.web_dir / "css" / "app.css"
        text = css_path.read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn("prefers-color-scheme", text)

    def test_main_js_requirements(self):
        main_path = self.web_dir / "js" / "main.js"
        text = main_path.read_text(encoding="utf-8")
        self.assertIn("aria-live", text)
        self.assertIn("aria-current", text)

    def test_file_sizes(self):
        for p in self.web_dir.rglob("*"):
            if p.is_file() and "assets" not in p.parts:
                size_kb = p.stat().st_size / 1024
                self.assertLess(size_kb, 120, f"File {p.relative_to(self.web_dir)} exceeds 120 KB ({size_kb:.1f} KB)")

if __name__ == "__main__":
    unittest.main()
