"""Flask route smoke tests. Run after installing requirements.txt."""
import re
import unittest

from app import app


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = app.test_client()

    def csrf_token(self):
        response = self.client.get("/graphs/temperature")
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="_csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode("utf-8")

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Research Graph Studio", response.data)

    def test_all_graph_pages_load(self):
        paths = [
            "/graphs/primary-velocity", "/graphs/secondary-velocity",
            "/graphs/temperature", "/graphs/concentration",
            "/graphs/cfx", "/graphs/cfy", "/graphs/nusselt", "/graphs/sherwood",
            "/ann/error-histogram", "/ann/regression", "/ann/performance",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_profile_submission(self):
        token = self.csrf_token()
        response = self.client.post("/graphs/temperature", data={
            "_csrf_token": token,
            "graph_title": "Temperature test",
            "x_label": "eta",
            "y_label": "theta",
            "x_values": "0, 0.5, 1",
            "series_label[]": ["Case A"],
            "series_values[]": ["1, 0.6, 0.2"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Static graph preview", response.data)
        self.assertIn(b"Interactive exploration", response.data)

    def test_invalid_input_shows_validation_error(self):
        token = self.csrf_token()
        response = self.client.post("/graphs/temperature", data={
            "_csrf_token": token,
            "x_values": "0, 1, 2",
            "series_label[]": ["Case A"],
            "series_values[]": ["1, 2"],
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn(b"same number of values", response.data)

    def test_csrf_required(self):
        response = self.client.post("/graphs/temperature", data={"x_values": "0, 1"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
