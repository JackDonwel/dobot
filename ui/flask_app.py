from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import error, parse, request

from flask import Flask, jsonify, render_template, request as flask_request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtester.backtest_engine import BacktestEngine
from backtester.data_loader import DataLoader
from backtester.results_analyzer import analyze_results
from backtester.strategies import BollingerBandsStrategy, RSIMACDStrategy

app = Flask(__name__, template_folder="templates", static_folder="static")

API_GATEWAY_BASE_URL = "http://api-gateway:4000"
LOCAL_API_GATEWAY_BASE_URL = "http://127.0.0.1:4000"


def get_api_gateway_base_url() -> str:
    return API_GATEWAY_BASE_URL if Path("/.dockerenv").exists() else LOCAL_API_GATEWAY_BASE_URL


def fetch_json(method: str, path: str, payload: dict | None = None) -> tuple[dict | None, str | None]:
    url = f"{get_api_gateway_base_url()}{path}"
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=5) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}, None
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8") or exc.reason
        return None, f"{exc.code}: {message}"
    except error.URLError as exc:
        return None, str(exc.reason)


def build_strategy(name: str, parameters: dict | None):
    normalized = (name or "RSIMACD").strip().upper()
    if normalized == "RSIMACD":
        return RSIMACDStrategy(parameters)
    if normalized == "BOLLINGER":
        return BollingerBandsStrategy(parameters)
    raise ValueError(f"Unsupported strategy '{name}'")


@app.get("/")
def index():
    return render_template("index.html", api_base_url=get_api_gateway_base_url())


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/dashboard")
def dashboard_data():
    symbol = flask_request.args.get("symbol", "BTCUSD")
    portfolio, portfolio_error = fetch_json("GET", "/api/portfolio")
    market, market_error = fetch_json("GET", f"/api/market/{parse.quote(symbol)}")

    return jsonify(
        {
            "portfolio": portfolio,
            "market": market,
            "symbol": symbol,
            "errors": {
                "portfolio": portfolio_error,
                "market": market_error,
            },
        }
    )


@app.post("/api/backtest")
def run_backtest():
    payload = flask_request.get_json(silent=True) or {}

    csv_path = payload.get("csv_path")
    symbol = payload.get("symbol", "BTCUSD")
    strategy_name = payload.get("strategy", "RSIMACD")
    parameters = payload.get("parameters") or {}
    initial_balance = float(payload.get("initial_balance", 10_000.0))
    risk_per_trade = float(payload.get("risk_per_trade", 0.01))
    commission = float(payload.get("commission", 0.001))

    if not csv_path:
        return jsonify({"error": "csv_path is required"}), 400

    try:
        loader = DataLoader()
        data = loader.load(csv_path, symbol)
        strategy = build_strategy(strategy_name, parameters)
        engine = BacktestEngine(
            initial_balance=initial_balance,
            strategy=strategy,
            risk_per_trade=risk_per_trade,
            commission=commission,
        )
        results = engine.run(data)

        if payload.get("save_plots", False):
            output_dir = payload.get("output_dir", str(PROJECT_ROOT / "backtester" / "plots"))
            analyze_results(results, save_plots=True, output_dir=output_dir)

        return jsonify(results)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
