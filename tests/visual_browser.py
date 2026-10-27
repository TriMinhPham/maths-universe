"""Browser acceptance checks for the public, browser-local curriculum."""
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARTIFACTS = ROOT / "test-data" / "visual-learning"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *_args):
        pass


class VisualLearningBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: QuietHandler(*a, directory=str(DOCS), **k))
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/index.html"
        ARTIFACTS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def _browser(self, pw, viewport=None):
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            self.skipTest(f"Playwright Chromium unavailable: {exc}")
        context = browser.new_context(viewport=viewport or {"width": 390, "height": 844}, reduced_motion="reduce")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        page.on("requestfailed", lambda req: errors.append(f"requestfailed: {req.url}: {req.failure}"))
        page.goto(self.base, wait_until="networkidle")
        page.locator("#discoveries [data-topic]").first.wait_for(state="visible", timeout=15000)
        self.assertTrue(page.locator("#error").is_hidden(), page.locator("#error-text").inner_text())
        self.assertEqual(errors, [], "load errors: " + "; ".join(errors))
        self.assertTrue(page.evaluate("document.body.scrollWidth <= innerWidth"))
        return browser, context, page, errors

    def test_discovery_library_switch_reset_and_layout(self):
        with sync_playwright() as pw:
            browser, context, page, errors = self._browser(pw)
            self.assertTrue(page.locator("#hero-play").is_visible())
            cards = page.locator("#discoveries [data-topic]")
            self.assertGreaterEqual(cards.count(), 6)
            before_stars = page.locator("#stars").inner_text()
            first = cards.nth(0)
            first_topic = first.get_attribute("data-topic")
            first_title = first.locator(".discovery-title").inner_text()
            first.click()
            self.assertEqual(page.locator("#lesson-title").inner_text(), first_title)
            play = page.locator("#lesson-playground")
            play.wait_for(state="visible")
            action = play.locator("button:not(:has-text('Reset'))").first
            self.assertTrue(action.is_visible(), "lesson must expose an actionable control")
            action.click()
            reset = play.get_by_role("button", name="Reset", exact=True)
            self.assertTrue(reset.is_visible(), "Reset control is required")
            self.assertEqual(play.locator("button[aria-pressed=true]").count(), 1)
            reset.click()
            self.assertEqual(play.locator(".mp-equation").inner_text(), "3 + 2 = ?")
            self.assertEqual(play.locator("button[aria-pressed=true]").count(), 0)
            self.assertEqual(page.locator("#stars").inner_text(), before_stars)

            page.locator("#lesson-back").click()
            second = page.locator("#discoveries [data-topic]").nth(1)
            self.assertTrue(second.is_visible(), "second discovery must be visible after returning")
            second_topic = second.get_attribute("data-topic")
            second_title = second.locator(".discovery-title").inner_text()
            self.assertNotEqual(first_topic, second_topic)
            second.click()
            self.assertEqual(page.locator("#lesson-title").inner_text(), second_title)
            self.assertNotEqual(page.locator("#lesson-title").inner_text(), first_title)

            page.locator("#lesson-back").click()
            page.locator("#browse-library").click()
            page.locator("#library").wait_for(state="visible")
            collected = set()
            while True:
                collected.update(page.locator("#library [data-topic]").evaluate_all("els => els.map(e => e.dataset.topic)"))
                more = page.locator("#more")
                if more.is_disabled():
                    break
                more.click()
            canonical = page.evaluate("fetch('./catalog.json').then(r => r.json()).then(c => c.domains.flatMap(d => d.topics.map(t => t.id)))")
            self.assertEqual(len(canonical), 576)
            self.assertEqual(len(collected), 576)
            self.assertEqual(collected, set(canonical))
            for width in (320, 390, 1280):
                page.set_viewport_size({"width": width, "height": 860})
                self.assertTrue(page.evaluate("document.body.scrollWidth <= innerWidth"), f"overflow at {width}px")
            self.assertEqual(errors, [], "runtime errors: " + "; ".join(errors))
            page.screenshot(path=str(ARTIFACTS / "visual-learning.png"), full_page=True)
            context.close()
            browser.close()

    def test_resume_restores_active_question_and_immutability(self):
        with sync_playwright() as pw:
            browser, context, page, errors = self._browser(pw)
            # Exercise the shipped module against frozen lesson/question snapshots;
            # mount and click real controls, then prove neither input was changed.
            result = page.evaluate("""() => {
              const freeze = o => { Object.freeze(o); for (const v of Object.values(o)) if (v && typeof v === 'object' && !Object.isFrozen(v)) freeze(v); return o; };
              const lesson = freeze({topic_id:'mt_OvyoRo47K-', title:'snapshot title', worked_example:{prompt:'p',steps:['s'],answer:'a'}});
              const active = freeze({topic_id:'mt_OvyoRo47K-', index:0, problem:{id:'frozen-question',prompt:'p',choices:['a','b'],visual:null}});
              const beforeLesson = JSON.stringify(lesson), beforeActive = JSON.stringify(active);
              const mount = document.createElement('div');
              const lessonOk = MathsPlay.mountLesson(mount, lesson);
              mount.querySelector('button:not([data-mp-key="reset"])').click();
              mount.querySelector('[data-mp-key="reset"]').click();
              const questionOk = MathsPlay.mountQuestion(mount, active);
              mount.querySelector('button:not([data-mp-key="reset"])').click();
              return {lessonOk,questionOk,unchanged:beforeLesson===JSON.stringify(lesson)&&beforeActive===JSON.stringify(active)};
            }""")
            self.assertTrue(result["lessonOk"] and result["questionOk"] and result["unchanged"], result)

            page.locator("#discoveries [data-topic='mt_OvyoRo47K-']").click()
            page.locator("#start").click()
            page.locator("#play").wait_for(state="visible", timeout=15000)
            page.locator("#prompt").wait_for(state="visible")
            engine_id = page.evaluate("MathsPublic.api('/api/quests/state').then(s=>s.active.problem.id)")
            prompt = page.locator("#prompt").inner_text()
            choices = page.locator("#choices .full-choice").all_inner_texts()
            self.assertTrue(prompt and len(choices) >= 2)
            page.reload(wait_until="networkidle")
            page.locator("#discoveries [data-topic]").first.wait_for(state="visible", timeout=15000)
            self.assertTrue(page.locator("#error").is_hidden(), page.locator("#error-text").inner_text())
            page.locator("#resume-button").click()
            page.locator("#play").wait_for(state="visible")
            self.assertEqual(page.locator("#prompt").inner_text(), prompt)
            self.assertEqual(page.locator("#choices .full-choice").all_inner_texts(), choices)
            self.assertEqual(page.evaluate("MathsPublic.api('/api/quests/state').then(s=>s.active.problem.id)"), engine_id)
            self.assertEqual(errors, [], "runtime errors: " + "; ".join(errors))
            page.screenshot(path=str(ARTIFACTS / "visual-learning-resume.png"), full_page=True)
            context.close()
            browser.close()


if __name__ == "__main__":
    unittest.main()
