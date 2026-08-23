from datetime import datetime, timezone
from typing import Literal
import hashlib
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Option Bazaar Dev API", version="0.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LOT_SIZES = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60, "SENSEX": 20}
FYERS_INDEX_SYMBOLS = {
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "INDIA VIX": "NSE:INDIAVIX-INDEX",
}
positions: list[dict] = []
trades: list[dict] = []
logs: list[dict] = []
settings = {"mode": "PAPER", "max_lots": 4, "max_open_positions": 3, "daily_loss_limit": 5000.0, "live_orders_enabled": False}
fyers = {
    "app_id": "",
    "secret_id": "",
    "redirect_uri": "",
    "state": "",
    "access_token": "",
    "refresh_token": "",
    "profile": None,
}
FYERS_API = "https://api-t1.fyers.in/api/v3"
FYERS_DATA_API = "https://api-t1.fyers.in/data"

class PaperOrder(BaseModel):
    symbol: str = "NIFTY"
    product: str = "NIFTY 24800 CE"
    side: Literal["BUY", "SELL"]
    lots: int = Field(default=1, ge=1, le=50)
    price: float = Field(gt=0)
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    stop_loss: float | None = None
    take_profit: float | None = None

class RiskSettings(BaseModel):
    max_lots: int = Field(ge=1, le=50)
    max_open_positions: int = Field(ge=1, le=20)
    daily_loss_limit: float = Field(gt=0)

class FyersConfig(BaseModel):
    app_id: str = Field(min_length=4)
    secret_id: str = Field(min_length=4)
    redirect_uri: str = Field(min_length=8)

class FyersAuthCode(BaseModel):
    auth_code: str = Field(min_length=8)


def now():
    return datetime.now(timezone.utc).isoformat()


def add_log(event: str, detail: str):
    logs.insert(0, {"time": now(), "event": event, "detail": detail})
    del logs[200:]


def _fyers_headers(auth: bool = False):
    headers = {"Content-Type": "application/json"}
    if auth:
        if not fyers["app_id"] or not fyers["access_token"]:
            raise HTTPException(400, "FYERS access token is not available")
        headers["Authorization"] = f'{fyers["app_id"]}:{fyers["access_token"]}'
    return headers


def _request_json(url: str, method: str = "GET", payload: dict | None = None, auth: bool = False):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers=_fyers_headers(auth), method=method)
    try:
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode())
            if isinstance(result, dict) and result.get("s") == "error":
                raise HTTPException(400, f"FYERS: {result.get('message') or 'request failed'}")
            return result
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            detail = json.loads(body).get("message") or body
        except Exception:
            detail = body
        raise HTTPException(e.code, f"FYERS: {detail}")
    except URLError as e:
        raise HTTPException(502, f"Could not reach FYERS: {e.reason}")


def fyers_request(path: str, method: str = "GET", payload: dict | None = None, auth: bool = False):
    return _request_json(FYERS_API + path, method, payload, auth)


def fyers_data_request(path: str, params: dict | None = None):
    query = "?" + urlencode(params or {}) if params else ""
    return _request_json(FYERS_DATA_API + path + query, auth=True)

@app.get("/api/health")
def health():
    return {"ok": True, "mode": settings["mode"], "live_orders": settings["live_orders_enabled"], "version": app.version}

@app.get("/api/instruments")
def instruments():
    return {"source": "TEST CONFIG", "lot_sizes": LOT_SIZES}

@app.get("/api/market/summary")
def market_summary():
    return {"source": "TEST DATA", "indices": [
        {"symbol": "NIFTY 50", "ltp": 24812.65, "change_pct": 0.62},
        {"symbol": "BANK NIFTY", "ltp": 51236.90, "change_pct": 0.41},
        {"symbol": "INDIA VIX", "ltp": 12.45, "change_pct": -2.51},
    ]}

@app.get("/api/market/ladder")
def ladder(center: float = 24812.65, rows: int = 15, tick: float = 0.05):
    rows = max(5, min(rows, 51))
    half = rows // 2
    values = [round(center + i * tick, 2) for i in range(half, -half - 1, -1)]
    return {"source": "TEST DATA", "tick": tick, "center": center, "rows": values}

@app.get("/api/market/candles")
def candles(symbol: str = "NIFTY", count: int = 120):
    count = max(20, min(count, 500))
    base = 24800.0 if symbol == "NIFTY" else 51200.0
    out = []
    price = base
    for i in range(count):
        move = ((i * 17) % 13 - 6) * 1.8
        op = price
        cl = op + move
        hi = max(op, cl) + 5 + (i % 4)
        lo = min(op, cl) - 5 - (i % 3)
        out.append({"t": i, "open": round(op,2), "high": round(hi,2), "low": round(lo,2), "close": round(cl,2), "volume": 100000 + (i*7919)%700000})
        price = cl
    return {"source": "TEST DATA", "symbol": symbol, "candles": out}

@app.get("/api/market/option-chain")
def option_chain(spot: float = 24812.65, strikes: int = 13):
    atm = round(spot / 50) * 50
    half = strikes // 2
    rows = []
    for i in range(-half, half + 1):
        strike = atm + i * 50
        ce = max(4.0, 128 - i * 17.5)
        pe = max(4.0, 118 + i * 17.0)
        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "ce": {"ltp": round(ce,2), "bid": round(ce-.5,2), "ask": round(ce+.5,2), "oi": 125000 + abs(i)*18000},
            "pe": {"ltp": round(pe,2), "bid": round(pe-.5,2), "ask": round(pe+.5,2), "oi": 132000 + abs(i)*16000},
        })
    return {"source": "TEST DATA", "spot": spot, "expiry": "TEST WEEKLY", "rows": rows}

@app.get("/api/indicators/registry")
def indicator_registry():
    return {"indicators": [
        {"id":"supertrend","name":"Supertrend","group":"Trend","defaults":{"period":10,"multiplier":3}},
        {"id":"ema","name":"EMA","group":"Trend","defaults":{"period":20}},
        {"id":"sma","name":"SMA","group":"Trend","defaults":{"period":20}},
        {"id":"vwap","name":"VWAP","group":"Trend","defaults":{}},
        {"id":"bb","name":"Bollinger Bands","group":"Volatility","defaults":{"period":20,"stddev":2}},
        {"id":"rsi","name":"RSI","group":"Momentum","defaults":{"period":14}},
        {"id":"macd","name":"MACD","group":"Momentum","defaults":{"fast":12,"slow":26,"signal":9}},
        {"id":"stochastic","name":"Stochastic","group":"Momentum","defaults":{"period":14}},
        {"id":"adx","name":"ADX","group":"Momentum","defaults":{"period":14}},
        {"id":"atr","name":"ATR","group":"Volatility","defaults":{"period":14}},
        {"id":"volume","name":"Volume","group":"Volume","defaults":{}},
    ]}

@app.get("/api/factor-j/signal")
def factor_j_signal():
    return {"source": "TEST DATA", "signal": "STRONG BUY", "confidence": 78, "trend": "Bullish", "risk_reward": 2.35,
            "reasons": ["Price above Supertrend", "RSI supportive", "VWAP alignment", "Volume confirmation"],
            "safety": {"mode": "PAPER", "live_action_allowed": False}}

@app.post("/api/paper/orders")
def paper_order(order: PaperOrder):
    lot_size = LOT_SIZES.get(order.symbol.upper())
    if not lot_size:
        raise HTTPException(400, "Unknown symbol")
    if order.lots > settings["max_lots"]:
        raise HTTPException(400, f"Risk rule: max lots is {settings['max_lots']}")
    if len(positions) >= settings["max_open_positions"]:
        raise HTTPException(400, "Risk rule: maximum open positions reached")
    quantity = order.lots * lot_size
    record = {"id": len(trades)+1, "time": now(), **order.model_dump(), "lot_size": lot_size, "quantity": quantity, "mode": "PAPER", "status": "FILLED"}
    trades.insert(0, record)
    positions.insert(0, {"id": record["id"], "symbol": order.symbol, "product": order.product, "side": order.side, "lots": order.lots, "lot_size": lot_size, "quantity": quantity, "avg": order.price, "ltp": order.price, "pnl": 0.0, "stop_loss": order.stop_loss, "take_profit": order.take_profit, "mode": "PAPER"})
    add_log("PAPER_ORDER", f"{order.side} {order.product} x {quantity} @ {order.price}")
    return {"ok": True, "order": record}

@app.post("/api/paper/reset")
def paper_reset():
    positions.clear(); trades.clear(); add_log("PAPER_RESET", "Paper account reset")
    return {"ok": True}

@app.get("/api/positions")
def get_positions():
    return {"positions": positions}

@app.get("/api/trades")
def get_trades():
    return {"trades": trades}

@app.get("/api/logs")
def get_logs():
    return {"logs": logs}

@app.get("/api/risk")
def get_risk():
    return settings

@app.put("/api/risk")
def update_risk(payload: RiskSettings):
    settings.update(payload.model_dump())
    add_log("RISK_UPDATE", str(payload.model_dump()))
    return {"ok": True, "risk": settings}

@app.get("/api/reports/summary")
def report_summary():
    wins = sum(1 for p in positions if p.get("pnl",0) > 0)
    losses = sum(1 for p in positions if p.get("pnl",0) < 0)
    net = round(sum(p.get("pnl",0) for p in positions),2)
    total = wins + losses
    return {"mode":"PAPER","trades":len(trades),"open_positions":len(positions),"wins":wins,"losses":losses,"win_rate":round(wins/total*100,2) if total else 0,"net_pnl":net}

@app.get("/api/fyers/status")
def fyers_status():
    configured = bool(fyers["app_id"] and fyers["secret_id"] and fyers["redirect_uri"])
    authenticated = bool(fyers["access_token"])
    return {
        "configured": configured,
        "authenticated": authenticated,
        "live_data_enabled": authenticated,
        "live_orders_enabled": False,
        "app_id": fyers["app_id"],
        "redirect_uri": fyers["redirect_uri"],
        "profile": fyers["profile"],
        "message": "FYERS authenticated — live market data available" if authenticated else ("FYERS credentials saved in backend memory" if configured else "Enter FYERS App ID, Secret ID and Redirect URL in Settings")
    }

@app.put("/api/fyers/config")
def fyers_config(payload: FyersConfig):
    fyers.update({"app_id": payload.app_id.strip(), "secret_id": payload.secret_id.strip(), "redirect_uri": payload.redirect_uri.strip(), "access_token": "", "refresh_token": "", "profile": None})
    add_log("FYERS_CONFIG", f"Configured app {fyers['app_id']} with redirect URI {fyers['redirect_uri']}")
    return {"ok": True, "configured": True, "app_id": fyers["app_id"], "redirect_uri": fyers["redirect_uri"]}

@app.get("/api/fyers/login-url")
def fyers_login_url():
    if not (fyers["app_id"] and fyers["secret_id"] and fyers["redirect_uri"]):
        raise HTTPException(400, "Save FYERS credentials first")
    fyers["state"] = secrets.token_urlsafe(18)
    query = urlencode({"client_id": fyers["app_id"], "redirect_uri": fyers["redirect_uri"], "response_type": "code", "state": fyers["state"]})
    return {"ok": True, "url": f"{FYERS_API}/generate-authcode?{query}", "state": fyers["state"]}

@app.post("/api/fyers/token")
def fyers_token(payload: FyersAuthCode):
    if not (fyers["app_id"] and fyers["secret_id"]):
        raise HTTPException(400, "Save FYERS credentials first")
    app_hash = hashlib.sha256(f'{fyers["app_id"]}:{fyers["secret_id"]}'.encode()).hexdigest()
    result = fyers_request("/validate-authcode", "POST", {"grant_type": "authorization_code", "appIdHash": app_hash, "code": payload.auth_code.strip()})
    token = result.get("access_token")
    if not token:
        raise HTTPException(400, result.get("message") or "FYERS did not return an access token")
    fyers["access_token"] = token
    fyers["refresh_token"] = result.get("refresh_token", "")
    add_log("FYERS_TOKEN", "FYERS access token generated")
    try:
        profile = fyers_request("/profile", auth=True)
        fyers["profile"] = profile.get("data") or profile
    except HTTPException:
        fyers["profile"] = None
    return {"ok": True, "authenticated": True, "profile": fyers["profile"]}

@app.get("/api/fyers/profile")
def fyers_profile():
    result = fyers_request("/profile", auth=True)
    fyers["profile"] = result.get("data") or result
    return result

@app.get("/api/fyers/quotes")
def fyers_quotes(symbols: str = "NSE:NIFTY50-INDEX,NSE:NIFTYBANK-INDEX,NSE:INDIAVIX-INDEX"):
    result = fyers_data_request("/quotes", {"symbols": symbols})
    return {"source": "FYERS LIVE", "received_at": now(), "raw": result}

@app.get("/api/fyers/market-summary")
def fyers_market_summary():
    result = fyers_data_request("/quotes", {"symbols": ",".join(FYERS_INDEX_SYMBOLS.values())})
    rows = result.get("d") or []
    by_symbol = {}
    for row in rows:
        key = row.get("n") or row.get("symbol")
        values = row.get("v") or {}
        if key:
            by_symbol[key] = values
    indices = []
    for display, broker_symbol in FYERS_INDEX_SYMBOLS.items():
        values = by_symbol.get(broker_symbol, {})
        indices.append({
            "symbol": display,
            "broker_symbol": broker_symbol,
            "ltp": values.get("lp", 0),
            "change": values.get("ch", 0),
            "change_pct": values.get("chp", 0),
            "open": values.get("open_price"),
            "high": values.get("high_price"),
            "low": values.get("low_price"),
            "prev_close": values.get("prev_close_price"),
        })
    add_log("FYERS_LIVE_QUOTES", "Fetched live index quote snapshot from FYERS")
    return {"source": "FYERS LIVE", "received_at": now(), "indices": indices}

@app.get("/api/fyers/depth")
def fyers_depth(symbol: str = "NSE:NIFTY50-INDEX"):
    result = fyers_data_request("/depth", {"symbol": symbol, "ohlcv_flag": "1"})
    return {"source": "FYERS LIVE", "received_at": now(), "raw": result}

@app.get("/api/fyers/option-chain")
def fyers_option_chain(symbol: str = "NSE:NIFTY50-INDEX", strikecount: int = 8):
    result = fyers_data_request("/options-chain-v3", {"symbol": symbol, "strikecount": max(1, min(strikecount, 50))})
    return {"source": "FYERS LIVE", "received_at": now(), "raw": result}

@app.post("/api/fyers/disconnect")
def fyers_disconnect():
    fyers.update({"access_token": "", "refresh_token": "", "profile": None})
    add_log("FYERS_DISCONNECT", "FYERS local session cleared")
    return {"ok": True}

@app.get("/api/fyers/callback")
def fyers_callback(auth_code: str = "", state: str = ""):
    if not auth_code:
        raise HTTPException(400, "auth_code missing from FYERS callback")
    return {"ok": True, "auth_code": auth_code, "state": state, "message": "Copy this auth_code and paste it into Option Bazaar Settings → FYERS"}

@app.post("/api/live/orders")
def live_order_blocker():
    raise HTTPException(403, "LIVE ORDERS DISABLED: FYERS live data may be tested, but order placement remains locked until explicit broker verification")
