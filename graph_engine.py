"""Plotting and numerical validation for Research Graph Studio.

Seaborn/Matplotlib create publication-style static figures. Plotly creates a
matching interactive chart for browser hover, zoom and pan interactions.
"""
from __future__ import annotations

import base64
import io
import math
import re
from functools import wraps
from threading import RLock
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Safe for Flask servers without a display.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import seaborn as sns

MAX_POINTS = 5000
MAX_SERIES = 8
_PLOT_LOCK = RLock()  # Matplotlib uses global state; serialize server-side rendering.


def _serialized_plot(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        with _PLOT_LOCK:
            return function(*args, **kwargs)
    return wrapper


sns.set_theme(style="whitegrid", context="notebook", font_scale=1.0)
PALETTE = "colorblind"


class InputValidationError(ValueError):
    """Raised when user-supplied numerical data is invalid."""


def parse_numeric_list(raw: str | None, field_name: str, *, min_items: int = 2,
                       max_items: int = MAX_POINTS) -> list[float]:
    """Parse comma-, semicolon-, whitespace- or newline-separated numbers."""
    if raw is None or not raw.strip():
        raise InputValidationError(f"Please enter values for {field_name}.")
    tokens = [t for t in re.split(r"[,;\s]+", raw.strip()) if t]
    if len(tokens) < min_items:
        raise InputValidationError(
            f"{field_name} needs at least {min_items} numerical values; received {len(tokens)}."
        )
    if len(tokens) > max_items:
        raise InputValidationError(
            f"{field_name} contains {len(tokens)} values. The maximum is {max_items}."
        )
    values: list[float] = []
    for index, token in enumerate(tokens, start=1):
        try:
            value = float(token)
        except ValueError as exc:
            raise InputValidationError(
                f"{field_name}: '{token}' at position {index} is not a valid number."
            ) from exc
        if not math.isfinite(value):
            raise InputValidationError(
                f"{field_name}: values must be finite numbers (NaN and infinity are not allowed)."
            )
        if abs(value) > 1e150:
            raise InputValidationError(
                f"{field_name}: {token} is outside the supported numerical range (absolute value must be at most 1e150)."
            )
        values.append(value)
    return values


def validate_matching_lengths(x_values: list[float], series: list[dict[str, Any]]) -> None:
    if not series:
        raise InputValidationError("Add at least one output series before generating the graph.")
    if len(series) > MAX_SERIES:
        raise InputValidationError(f"You can compare up to {MAX_SERIES} series on one graph.")
    for item in series:
        if len(item["values"]) != len(x_values):
            raise InputValidationError(
                f"'{item['label']}' contains {len(item['values'])} values, but the X-axis has "
                f"{len(x_values)}. Each series must have exactly the same number of values as X."
            )


def sort_x_and_series(x_values: list[float], series: list[dict[str, Any]]) -> tuple[list[float], list[dict[str, Any]]]:
    """Sort X values in ascending order while keeping each Y value paired with its X."""
    order = np.argsort(np.asarray(x_values, dtype=float), kind="stable")
    sorted_x = [float(x_values[i]) for i in order]
    sorted_series = [
        {"label": item["label"], "values": [float(item["values"][i]) for i in order]}
        for item in series
    ]
    return sorted_x, sorted_series


def series_from_form(form: Any) -> list[dict[str, Any]]:
    labels = form.getlist("series_label[]")
    raw_values = form.getlist("series_values[]")
    if len(labels) != len(raw_values):
        raise InputValidationError("Each series needs both a label and a corresponding values field.")
    if not labels:
        raise InputValidationError("Add at least one output series.")
    if len(labels) > MAX_SERIES:
        raise InputValidationError(f"You can compare up to {MAX_SERIES} series on one graph.")
    output = []
    for i, (label, raw) in enumerate(zip(labels, raw_values), start=1):
        # Strip angle brackets/control characters before embedding labels in Plotly's HTML.
        clean_label = re.sub(r"[<>\x00-\x1f\x7f]", "", (label or "")).strip()[:80]
        if not clean_label:
            clean_label = f"Series {i}"
        values = parse_numeric_list(raw, f"values for {clean_label}")
        output.append({"label": clean_label, "values": values})
    return output


def _validate_text(value: str | None, fallback: str, max_length: int = 120) -> str:
    value = (value or "").strip()
    # Plotly embeds text in an HTML/JavaScript fragment; remove markup delimiters.
    value = re.sub(r"[<>\x00-\x1f\x7f]", "", value)
    return (value or fallback)[:max_length]


def _fig_to_data_uri(fig: plt.Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _plotly_fragment(fig: go.Figure) -> str:
    fig.update_layout(
        template="plotly_white",
        font={"family": "Inter, Arial, sans-serif", "size": 13, "color": "#20304a"},
        margin={"l": 65, "r": 25, "t": 55, "b": 60},
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.22, "x": 0},
    )
    config = {"responsive": True, "displaylogo": False, "scrollZoom": True}
    return pio.to_html(fig, full_html=False, include_plotlyjs="cdn", config=config)


def _tidy_frame(x_values: list[float], series: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in series:
        rows.extend(
            {"x": x, "value": y, "series": item["label"]}
            for x, y in zip(x_values, item["values"])
        )
    return pd.DataFrame(rows)


def _trend_text(x_values: list[float], y_values: list[float]) -> str:
    start, end = y_values[0], y_values[-1]
    delta = end - start
    scale = max(abs(start), abs(end), 1e-12)
    if abs(delta) <= 0.01 * scale:
        direction = "changes only slightly between the first and last supplied points"
    elif delta > 0:
        direction = "increases from the first to the last supplied point"
    else:
        direction = "decreases from the first to the last supplied point"
    ymin, ymax = min(y_values), max(y_values)
    return (
        f"{direction}. It starts at {start:.5g} and ends at {end:.5g}; "
        f"the supplied range is {ymin:.5g} to {ymax:.5g}."
    )


def _profile_interpretation(config: dict[str, Any], x_values: list[float],
                            series: list[dict[str, Any]]) -> list[dict[str, str]]:
    notes = [{
        "heading": "What this graph shows",
        "text": config["meaning"]
    }]
    for item in series:
        notes.append({"heading": item["label"], "text": _trend_text(x_values, item["values"])})
    notes.append({
        "heading": "How to interpret it",
        "text": "Compare the curves at the same similarity-variable value. A difference between curves "
                "is evidence of a difference in the supplied cases; it represents the effect of one "
                "parameter only when the other model conditions were held fixed."
    })
    if config.get("paper_context"):
        notes.append({"heading": "Research-paper context", "text": config["paper_context"]})
    return notes


def _sensitivity_interpretation(config: dict[str, Any], x_values: list[float],
                                series: list[dict[str, Any]], fixed_conditions: str) -> list[dict[str, str]]:
    notes = [{
        "heading": "What this graph shows",
        "text": f"The graph compares {config['output_name']} with the selected independent parameter "
                "using the numerical values entered by the user."
    }]
    for item in series:
        trend = _trend_text(x_values, item["values"])
        if len(x_values) >= 2 and np.std(x_values) > 0 and np.std(item["values"]) > 0:
            r = float(np.corrcoef(np.asarray(x_values), np.asarray(item["values"]))[0, 1])
            trend += f" The linear correlation across these points is r = {r:.4f}."
        else:
            trend += " A correlation coefficient cannot be calculated for constant data."
        notes.append({"heading": item["label"], "text": trend})
    if fixed_conditions.strip():
        notes.append({"heading": "Other conditions stated by the user", "text": fixed_conditions.strip()[:500]})
    notes.append({
        "heading": "Scientific interpretation",
        "text": "A plotted association is not, by itself, proof of causation. Interpret the selected "
                "parameter as the cause of a change only when the other model parameters, boundary "
                "conditions and material properties are controlled consistently across cases."
    })
    if config.get("paper_context"):
        notes.append({"heading": "Research-paper context", "text": config["paper_context"]})
    return notes


@_serialized_plot
def create_profile_graph(config: dict[str, Any], form: Any) -> dict[str, Any]:
    x_values = parse_numeric_list(form.get("x_values"), config["x_axis"], min_items=2)
    series = series_from_form(form)
    validate_matching_lengths(x_values, series)
    x_values, series = sort_x_and_series(x_values, series)
    title = _validate_text(form.get("graph_title"), config["title"])
    x_label = _validate_text(form.get("x_label"), config["x_axis"], 100)
    y_label = _validate_text(form.get("y_label"), config["y_axis"], 100)
    fixed_conditions = _validate_text(form.get("fixed_conditions"), "", 500)

    df = _tidy_frame(x_values, series)
    fig, ax = plt.subplots(figsize=(9.8, 5.8), constrained_layout=True)
    sns.lineplot(data=df, x="x", y="value", hue="series", style="series", markers=True,
                 dashes=False, linewidth=2.5, markersize=7, palette=PALETTE, ax=ax,
                 sort=True, estimator=None, errorbar=None)
    ax.set(title=title, xlabel=x_label, ylabel=y_label)
    ax.set_axisbelow(True)
    ax.grid(True, which="major", alpha=0.24, linewidth=0.8)
    ax.legend(title="Comparison case", frameon=True, loc="best")
    sns.despine(ax=ax)
    png = _fig_to_data_uri(fig)

    pfig = go.Figure()
    for item in series:
        pfig.add_trace(go.Scatter(x=x_values, y=item["values"], mode="lines+markers",
                                  name=item["label"], line={"width": 3}, marker={"size": 8}))
    pfig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
    notes = _profile_interpretation(config, x_values, series)
    if fixed_conditions:
        notes.insert(1, {"heading": "Other conditions stated by the user", "text": fixed_conditions})
    return {"png": png, "interactive": _plotly_fragment(pfig), "notes": notes,
            "metrics": [{"label": "Data points per curve", "value": str(len(x_values))},
                        {"label": "Comparison curves", "value": str(len(series))}],
            "title": title}


@_serialized_plot
def create_sensitivity_graph(config: dict[str, Any], form: Any) -> dict[str, Any]:
    x_values = parse_numeric_list(form.get("x_values"), "independent parameter values", min_items=2)
    series = series_from_form(form)
    validate_matching_lengths(x_values, series)
    x_values, series = sort_x_and_series(x_values, series)
    title = _validate_text(form.get("graph_title"), config["title"])
    x_label = _validate_text(form.get("x_label"), "Parameter value", 100)
    fixed_conditions = _validate_text(form.get("fixed_conditions"), "", 500)

    df = _tidy_frame(x_values, series)
    fig, ax = plt.subplots(figsize=(9.8, 5.8), constrained_layout=True)
    sns.lineplot(data=df, x="x", y="value", hue="series", style="series", markers=True,
                 dashes=False, linewidth=2.5, markersize=7, palette=PALETTE, ax=ax,
                 sort=True, estimator=None, errorbar=None)
    ax.set(title=title, xlabel=x_label, ylabel=config["y_axis"])
    ax.grid(True, alpha=0.24, linewidth=0.8)
    ax.legend(title="Output series", frameon=True, loc="best")
    sns.despine(ax=ax)
    png = _fig_to_data_uri(fig)

    pfig = go.Figure()
    for item in series:
        pfig.add_trace(go.Scatter(x=x_values, y=item["values"], mode="lines+markers",
                                  name=item["label"], line={"width": 3}, marker={"size": 8}))
    pfig.update_layout(title=title, xaxis_title=x_label, yaxis_title=config["y_axis"])
    notes = _sensitivity_interpretation(config, x_values, series, fixed_conditions)
    metrics = [{"label": "Parameter values", "value": str(len(x_values))},
               {"label": "Output series", "value": str(len(series))}]
    return {"png": png, "interactive": _plotly_fragment(pfig), "notes": notes,
            "metrics": metrics, "title": title}


def _parse_actual_predicted(form: Any) -> tuple[list[float], list[float], np.ndarray]:
    actual = parse_numeric_list(form.get("actual_values"), "actual/target values", min_items=2)
    predicted = parse_numeric_list(form.get("predicted_values"), "predicted/output values", min_items=2)
    if len(actual) != len(predicted):
        raise InputValidationError(
            f"Actual values has {len(actual)} items but predicted values has {len(predicted)}. "
            "The two lists must have matching lengths."
        )
    errors = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return actual, predicted, errors


def _ann_metrics(actual: list[float], predicted: list[float], errors: np.ndarray) -> dict[str, str]:
    mse = float(np.mean(errors ** 2))
    mae = float(np.mean(np.abs(errors)))
    rmse = math.sqrt(mse)
    r = None
    if np.std(actual) > 0 and np.std(predicted) > 0:
        r = float(np.corrcoef(np.asarray(actual), np.asarray(predicted))[0, 1])
    return {
        "Observations": str(len(actual)),
        "MSE": f"{mse:.6g}",
        "MAE": f"{mae:.6g}",
        "RMSE": f"{rmse:.6g}",
        "Mean error (target − output)": f"{float(np.mean(errors)):.6g}",
        "Correlation R": "Not defined for constant data" if r is None else f"{r:.5f}",
    }


def _ann_target(form: Any) -> str:
    target = (form.get("ann_target") or "Cfx").strip()
    allowed = {"Cfx", "Cfy", "Nux", "Shx"}
    if target not in allowed:
        raise InputValidationError("Choose a valid ANN output quantity: Cfx, Cfy, Nux or Shx.")
    return target


@_serialized_plot
def create_error_histogram(form: Any) -> dict[str, Any]:
    actual, predicted, errors = _parse_actual_predicted(form)
    target = _ann_target(form)
    entered_title = _validate_text(form.get("graph_title"), "ANN Error Histogram")
    title = f"ANN Error Histogram — {target}" if entered_title.lower() == "ann error histogram" else entered_title
    fig, ax = plt.subplots(figsize=(9.8, 5.8), constrained_layout=True)
    sns.histplot(x=errors, bins="auto", color="#4776c7", edgecolor="white", linewidth=1.0, ax=ax)
    ax.axvline(0, color="#d1495b", linestyle="--", linewidth=2, label="Zero error")
    ax.set(title=title, xlabel="Prediction error (target − output)", ylabel="Number of observations")
    ax.legend(frameon=True)
    ax.grid(axis="y", alpha=0.22)
    sns.despine(ax=ax)
    png = _fig_to_data_uri(fig)

    pfig = go.Figure()
    pfig.add_trace(go.Histogram(x=errors, nbinsx=max(5, min(40, int(np.sqrt(len(errors)) * 2))),
                                name="Prediction error", marker_color="#4776c7"))
    pfig.add_vline(x=0, line_dash="dash", line_color="#d1495b", annotation_text="Zero error")
    pfig.update_layout(title=title, xaxis_title="Prediction error (target − output)",
                       yaxis_title="Number of observations", bargap=0.08)
    metrics = _ann_metrics(actual, predicted, errors)
    notes = [
        {"heading": "Selected ANN output", "text": f"This error analysis is labelled for {target}. Make sure the entered target and predicted values correspond to this same engineering quantity."},
        {"heading": "What this graph shows", "text": "The histogram shows how the differences between the supplied target values and ANN outputs are distributed. The error is calculated as target minus output, matching the convention used in the research paper."},
        {"heading": "How to read it", "text": "Bars concentrated near zero indicate small prediction errors. A wide distribution or a strong shift away from zero can indicate larger errors or systematic over/under-prediction."},
        {"heading": "Data limitation", "text": "This graph evaluates the actual/predicted pairs entered here. It does not train an ANN or independently verify the origin of those values."},
    ]
    return {"png": png, "interactive": _plotly_fragment(pfig), "notes": notes,
            "metrics": [{"label": k, "value": v} for k, v in metrics.items()], "title": title}


@_serialized_plot
def create_regression_graph(form: Any) -> dict[str, Any]:
    actual, predicted, errors = _parse_actual_predicted(form)
    target = _ann_target(form)
    entered_title = _validate_text(form.get("graph_title"), "ANN Regression")
    title = f"ANN Regression — {target}: Actual vs Predicted" if entered_title.lower() in {"ann regression", "ann regression plot"} else entered_title
    x = np.asarray(actual, dtype=float)
    y = np.asarray(predicted, dtype=float)
    low = float(min(np.min(x), np.min(y)))
    high = float(max(np.max(x), np.max(y)))
    pad = (high - low) * 0.06 if high > low else max(abs(high) * 0.06, 0.1)
    line_min, line_max = low - pad, high + pad
    r = None
    if np.std(x) > 0 and np.std(y) > 0:
        r = float(np.corrcoef(x, y)[0, 1])

    fig, ax = plt.subplots(figsize=(7.8, 7.0), constrained_layout=True)
    sns.scatterplot(x=x, y=y, s=65, color="#4776c7", edgecolor="white", linewidth=0.7, ax=ax,
                    label="Predictions")
    ax.plot([line_min, line_max], [line_min, line_max], color="#d1495b", linestyle="--",
            linewidth=2, label="Ideal agreement (Y = T)")
    if len(np.unique(x)) >= 2:
        sns.regplot(x=x, y=y, scatter=False, ci=None, color="#168a72", line_kws={"linewidth": 2}, ax=ax,
                    label="Linear fit")
    ax.set(xlim=(line_min, line_max), ylim=(line_min, line_max), title=title,
           xlabel="Actual target values", ylabel="ANN predicted output values")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=True, loc="best")
    sns.despine(ax=ax)
    png = _fig_to_data_uri(fig)

    pfig = go.Figure()
    pfig.add_trace(go.Scatter(x=x, y=y, mode="markers", name="Predictions",
                              marker={"size": 10, "color": "#4776c7"}))
    pfig.add_trace(go.Scatter(x=[line_min, line_max], y=[line_min, line_max], mode="lines",
                              name="Ideal agreement (Y = T)", line={"color": "#d1495b", "dash": "dash"}))
    if len(np.unique(x)) >= 2:
        slope, intercept = np.polyfit(x, y, 1)
        pfig.add_trace(go.Scatter(x=[line_min, line_max],
                                  y=[slope * line_min + intercept, slope * line_max + intercept],
                                  mode="lines", name="Linear fit", line={"color": "#168a72", "width": 2}))
    pfig.update_layout(title=title, xaxis_title="Actual target values",
                       yaxis_title="ANN predicted output values")
    pfig.update_xaxes(range=[line_min, line_max])
    pfig.update_yaxes(range=[line_min, line_max], scaleanchor="x", scaleratio=1)

    metrics = _ann_metrics(actual, predicted, errors)
    notes = [
        {"heading": "Selected ANN output", "text": f"This regression analysis is labelled for {target}. Make sure the entered target and predicted values correspond to this same engineering quantity."},
        {"heading": "What this graph shows", "text": "Each point represents one supplied pair: its horizontal position is the actual numerical target and its vertical position is the ANN prediction."},
        {"heading": "Ideal agreement", "text": "Points on the dashed Y = T line are exact predictions. Points close to this line have smaller differences; points above it are over-predictions and points below it are under-predictions."},
        {"heading": "Correlation is not the whole story", "text": "A correlation R close to 1 indicates a strong linear association, but should be considered together with MSE, MAE and the distance from the ideal-agreement line."},
    ]
    return {"png": png, "interactive": _plotly_fragment(pfig), "notes": notes,
            "metrics": [{"label": k, "value": v} for k, v in metrics.items()], "title": title}


@_serialized_plot
def create_performance_graph(form: Any) -> dict[str, Any]:
    target = _ann_target(form)
    epochs = parse_numeric_list(form.get("epochs"), "epoch values", min_items=2)
    training = parse_numeric_list(form.get("training_mse"), "training MSE", min_items=2)
    validation = parse_numeric_list(form.get("validation_mse"), "validation MSE", min_items=2)
    testing_raw = (form.get("testing_mse") or "").strip()
    testing = parse_numeric_list(testing_raw, "testing MSE", min_items=2) if testing_raw else None
    for name, values in (("training MSE", training), ("validation MSE", validation)):
        if len(values) != len(epochs):
            raise InputValidationError(f"{name} has {len(values)} values but epochs has {len(epochs)}. These lengths must match.")
        if any(v < 0 for v in values):
            raise InputValidationError(f"{name} cannot contain negative values.")
    if testing is not None:
        if len(testing) != len(epochs):
            raise InputValidationError(f"Testing MSE has {len(testing)} values but epochs has {len(epochs)}. These lengths must match.")
        if any(v < 0 for v in testing):
            raise InputValidationError("Testing MSE cannot contain negative values.")
    if any(v < 0 for v in epochs):
        raise InputValidationError("Epoch values must be zero or positive.")
    if any(b <= a for a, b in zip(epochs, epochs[1:])):
        raise InputValidationError("Epoch values must be strictly increasing with no duplicates.")

    entered_title = _validate_text(form.get("graph_title"), "ANN Training Performance")
    title = f"ANN Training Performance — {target}" if entered_title.lower() == "ann training performance" else entered_title
    rows = []
    for label, values in (("Training", training), ("Validation", validation), ("Testing", testing)):
        if values is not None:
            rows.extend({"epoch": epoch, "MSE": mse, "dataset": label} for epoch, mse in zip(epochs, values))
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9.8, 5.8), constrained_layout=True)
    sns.lineplot(data=df, x="epoch", y="MSE", hue="dataset", style="dataset", markers=True,
                 dashes=False, linewidth=2.5, markersize=7, palette="colorblind", ax=ax, sort=True)
    ax.set(title=title, xlabel="Training epoch", ylabel="Mean squared error (MSE)")
    all_mse = training + validation + (testing or [])
    if all(v > 0 for v in all_mse) and max(all_mse) / min(all_mse) > 100:
        ax.set_yscale("log")
        ax.set_ylabel("Mean squared error (MSE, logarithmic scale)")
    ax.grid(True, alpha=0.24)
    ax.legend(title="Dataset", frameon=True, loc="best")
    sns.despine(ax=ax)
    png = _fig_to_data_uri(fig)

    pfig = go.Figure()
    for label, values in (("Training", training), ("Validation", validation), ("Testing", testing)):
        if values is not None:
            pfig.add_trace(go.Scatter(x=epochs, y=values, mode="lines+markers", name=label,
                                      line={"width": 3}, marker={"size": 8}))
    pfig.update_layout(title=title, xaxis_title="Training epoch", yaxis_title="Mean squared error (MSE)")
    if all(v > 0 for v in all_mse) and max(all_mse) / min(all_mse) > 100:
        pfig.update_yaxes(type="log", title="Mean squared error (MSE, logarithmic scale)")

    best_idx = int(np.argmin(validation))
    best_epoch = epochs[best_idx]
    best_mse = validation[best_idx]
    notes = [
        {"heading": "Selected ANN output", "text": f"This training history is labelled for {target}. Use the MSE history for the same target quantity that the ANN was trained to predict."},
        {"heading": "What this graph shows", "text": "The curves show the MSE values the user supplied for training, validation and (when provided) testing sets across training epochs."},
        {"heading": "Best validation point", "text": f"The lowest supplied validation MSE is {best_mse:.6g} at epoch {best_epoch:g}. This is a useful checkpoint when assessing generalization."},
        {"heading": "Overfitting check", "text": "A warning pattern can occur when training MSE keeps falling while validation MSE starts rising. The plot helps reveal this pattern, but the supplied points and the model-training procedure should be checked before drawing a final conclusion."},
    ]
    metrics = [{"label": "Epochs supplied", "value": str(len(epochs))},
               {"label": "Best validation epoch", "value": f"{best_epoch:g}"},
               {"label": "Lowest validation MSE", "value": f"{best_mse:.6g}"},
               {"label": "Final training MSE", "value": f"{training[-1]:.6g}"},
               {"label": "Final validation MSE", "value": f"{validation[-1]:.6g}"}]
    return {"png": png, "interactive": _plotly_fragment(pfig), "notes": notes,
            "metrics": metrics, "title": title}
