# Research Graph Studio

A Flask website that lets a user enter numerical data directly in the browser and generate research-style scientific graphs. It does **not** require Excel or CSV files.

## What is included

### Physical profile pages
- `/graphs/primary-velocity` — primary velocity profile, f′(η)
- `/graphs/secondary-velocity` — secondary velocity profile, h(η)
- `/graphs/temperature` — temperature profile, θ(η)
- `/graphs/concentration` — concentration profile, χ(η)

### Engineering output sensitivity pages
- `/graphs/cfx` — primary skin-friction coefficient versus a selected parameter
- `/graphs/cfy` — secondary skin-friction coefficient versus a selected parameter
- `/graphs/nusselt` — Nusselt number versus a selected parameter
- `/graphs/sherwood` — Sherwood number versus a selected parameter

### ANN evaluation pages
- `/ann/error-histogram` — target-minus-output error histogram
- `/ann/regression` — actual-versus-predicted regression plot
- `/ann/performance` — training, validation and optional testing MSE versus epoch

Every page has its own URL and input form. The homepage links to all graph pages.

## Graph libraries

- **Seaborn + Matplotlib** produce the high-resolution, publication-style static PNG figure.
- **Plotly** produces a matching interactive chart in the browser (hover, zoom, pan and toolbar export).
- **NumPy + Pandas** validate and arrange values for graphing.
- **Flask** handles routes and form submissions.

> Seaborn is not an interactive chart library by itself. This project therefore uses Seaborn/Matplotlib for the paper-style export and Plotly for browser interactivity.

## Run on Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/ and enable **Add Python to PATH**.
2. Extract this folder.
3. (Optional) Copy `.env.example` to `.env` and set a private `SECRET_KEY`.
4. Double-click `run_windows.bat`.
5. When installation and startup finish, open **http://127.0.0.1:5000** in your browser.

The first launch creates a local `.venv` virtual environment and installs dependencies. An internet connection is required for that first dependency installation. The website itself then runs locally on your computer. A `.env` file is loaded automatically if present. The interactive Plotly chart loads its JavaScript library from a CDN, so the interactive preview needs an internet connection; the generated PNG remains available locally.

## Run manually (Windows, macOS or Linux)

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install and start:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

## Run the tests

After installing the dependencies, run:

```bash
python -m unittest discover -s tests -v
```

The graph-engine tests cover plotting, numerical parsing, invalid values and mismatched X/Y lengths. The Flask route smoke tests cover homepage/URL loading, form submission and CSRF validation.

## How to enter data

- Enter numbers separated by commas, spaces, semicolons or line breaks.
- X values and each matching Y series must have the same number of values.
- To compare several cases on a profile or sensitivity page, click **Add case** and enter a label plus its Y values. Each case becomes a separate coloured curve.
- ANN error histogram and regression pages need matching actual/target and predicted/output lists.
- ANN performance needs epoch numbers plus training and validation MSE histories. Testing MSE is optional. Each history must have the same length as the epoch list.
- Values must be finite numbers. NaN and infinity are rejected. Up to 5,000 points and 8 curves are accepted per chart.

The **Fill illustrative sample values** buttons are only to test the interface. They are fictional/demo values and must not be presented as research results.

## Interpreting the generated page

Each result page includes:
- a static PNG graph suitable for insertion into a report;
- an interactive Plotly chart;
- a numerical summary;
- an interpretation panel explaining what the plotted quantities represent and summarizing the entered values.

The automated interpretation describes the supplied values (for example, first-to-last change, range and correlation). It does not prove causality. When comparing the effect of one physical parameter, keep other model parameters and boundary conditions fixed and state that in the **Other conditions held fixed** field.

## Scope and scientific limitations

This is a visualization application. It plots user-entered results; it does not solve the governing PDE/ODE system, run MATLAB `bvp5c`, or train an ANN. The ANN pages evaluate numerical target/prediction pairs and MSE histories supplied by the user.

The reference research paper specifies 13 ANN input nodes but does not identify which 13 parameters are selected from its larger dimensionless parameter list. This project does not fabricate or assume that missing mapping.

The paper's Figure 3–5 profiles and Figures 7–10 ANN diagnostics are reflected in the page categories. The engineering output pages are built around Cfx, Cfy, Nux and Shx as described in the paper's tables and ANN section.

## Security before deployment

This project is intended for local use and development. Before publishing it online:

1. Set a long random `SECRET_KEY` environment variable.
2. Set `FLASK_DEBUG=0`.
3. If using HTTPS, set `COOKIE_SECURE=1`.
4. Run behind a production WSGI server (for example, Waitress on Windows or Gunicorn on Linux) and a properly configured HTTPS reverse proxy.
5. Add authentication and rate limiting if the site is public.

Do not expose Flask's development server or debug mode to the public internet.


## Research-paper reference

The scientific context notes in the interface are based on: A.B. Sadiya, G. Sucharitha, P. Lakshminarayana and S. Shaw, “Hall and cross-diffusion effects on ternary nanofluid flow over a rotating stretching surface under Coriolis force: An ANN approach,” *Results in Surfaces and Interfaces*, 24 (2026), article 100844. DOI: https://doi.org/10.1016/j.rsurfi.2026.100844.
