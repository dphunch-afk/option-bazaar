from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Option Bazaar Dev API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LOT_SIZES = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60, "SENSEX": 20}
positions: list[dict] = []
trades: list[dict] = []
logs: list[dict] = []
settings = {"mode": "PAPER", "max_lots": 4, "max_open_positions": 3, "daily_loss_limit": 5000.0, "live_orders_enabled": False}

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


def now():
    return datetime.now(timezone.utc).isoformat()


def add_log(event: str, detail: str):
    logs.insert(0, {"time": now(), "event": event, "detail": detail})
    del logs[200:]

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
    return {"configured": False, "authenticated": False, "live_orders_enabled": False, "message": "FYERS adapter is reserved for live verification. No real order route is enabled in this development build."}

@app.post("/api/live/orders")
def live_order_blocker():
    raise HTTPException(403, "LIVE ORDERS DISABLED: complete FYERS authentication and explicit safety verification first")
