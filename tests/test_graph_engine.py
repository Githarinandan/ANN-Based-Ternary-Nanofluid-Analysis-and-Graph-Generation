import unittest

from graph_engine import (
    InputValidationError,
    create_error_histogram,
    create_performance_graph,
    create_profile_graph,
    create_regression_graph,
    create_sensitivity_graph,
    parse_numeric_list,
)


class FormData:
    def __init__(self, values=None, lists=None):
        self.values = values or {}
        self.lists = lists or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def getlist(self, key):
        return self.lists.get(key, [])


class GraphEngineTests(unittest.TestCase):
    def test_numeric_parser_accepts_separators(self):
        self.assertEqual(parse_numeric_list("1, 2; 3\n4", "values"), [1.0, 2.0, 3.0, 4.0])

    def test_numeric_parser_rejects_nan(self):
        with self.assertRaises(InputValidationError):
            parse_numeric_list("1, nan, 3", "values")

    def test_numeric_parser_rejects_bad_token(self):
        with self.assertRaises(InputValidationError):
            parse_numeric_list("1, two, 3", "values")

    def test_profile_graph_generates_both_views(self):
        config = {"title": "Temperature", "x_axis": "eta", "y_axis": "theta",
                  "meaning": "Dimensionless temperature profile", "paper_context": "Context"}
        form = FormData(
            {"x_values": "0, 0.5, 1", "graph_title": "Test temperature", "x_label": "eta",
             "y_label": "theta", "fixed_conditions": "M=0.5"},
            {"series_label[]": ["Case A", "Case B"],
             "series_values[]": ["1, 0.6, 0.2", "1, 0.7, 0.3"]},
        )
        result = create_profile_graph(config, form)
        self.assertTrue(result["png"].startswith("data:image/png;base64,"))
        self.assertIn("plotly-graph-div", result["interactive"])
        self.assertGreaterEqual(len(result["notes"]), 3)

    def test_sensitivity_graph(self):
        config = {"title": "Cfx", "y_axis": "Cfx", "output_name": "Cfx", "paper_context": "Table context"}
        form = FormData(
            {"x_values": "1, 2, 3", "graph_title": "Cfx versus parameter", "x_label": "M",
             "fixed_conditions": "other parameters fixed"},
            {"series_label[]": ["Ternary"], "series_values[]": ["1.1, 1.2, 1.3"]},
        )
        result = create_sensitivity_graph(config, form)
        self.assertTrue(result["png"].startswith("data:image/png;base64,"))
        self.assertIn("Ternary", " ".join(note["heading"] for note in result["notes"]))

    def test_error_histogram(self):
        form = FormData({"actual_values": "1, 2, 3", "predicted_values": "1.1, 1.9, 3.2"})
        result = create_error_histogram(form)
        self.assertTrue(result["png"].startswith("data:image/png;base64,"))
        self.assertIn("MSE", [m["label"] for m in result["metrics"]])

    def test_regression_graph(self):
        form = FormData({"actual_values": "1, 2, 3, 4", "predicted_values": "1.1, 2.1, 2.9, 4.05"})
        result = create_regression_graph(form)
        self.assertTrue(result["png"].startswith("data:image/png;base64,"))
        self.assertIn("Ideal agreement", result["interactive"])

    def test_performance_graph(self):
        form = FormData({"epochs": "1, 2, 3, 4", "training_mse": "0.1, 0.05, 0.02, 0.01",
                         "validation_mse": "0.12, 0.06, 0.03, 0.04",
                         "testing_mse": "0.13, 0.07, 0.035, 0.045"})
        result = create_performance_graph(form)
        self.assertTrue(result["png"].startswith("data:image/png;base64,"))
        self.assertIn("Best validation epoch", [m["label"] for m in result["metrics"]])

    def test_rejects_mismatched_lengths(self):
        config = {"title": "Temperature", "x_axis": "eta", "y_axis": "theta", "meaning": "Meaning"}
        form = FormData({"x_values": "0, 1, 2"},
                        {"series_label[]": ["Case"], "series_values[]": ["1, 2"]})
        with self.assertRaises(InputValidationError):
            create_profile_graph(config, form)


if __name__ == "__main__":
    unittest.main()
