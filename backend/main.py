from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Option Bazaar Test API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

positions = []
trades = []

class PaperOrder(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float
    order_type: str = "LIMIT"

@app.get("/api/health")
def health():
    return {"ok": True, "mode": "TEST", "live_orders": False}

@app.get("/api/market/summary")
def market_summary():
    return {
        "source": "TEST DATA",
        "indices": [
            {"symbol": "NIFTY 50", "ltp": 24812.65, "change_pct": 0.62},
            {"symbol": "BANK NIFTY", "ltp": 51236.90, "change_pct": 0.41},
            {"symbol": "INDIA VIX", "ltp": 12.45, "change_pct": -2.51},
        ],
    }

@app.get("/api/market/ladder")
def ladder(center: float = 24812.65, rows: int = 13):
    half = rows // 2
    return {"source": "TEST DATA", "rows": [round(center + i * 0.05, 2) for i in range(half, -half - 1, -1)]}

@app.get("/api/factor-j/signal")
def factor_j_signal():
    return {"source": "TEST DATA", "signal": "STRONG BUY", "confidence": 78, "trend": "Bullish", "risk_reward": 2.35, "reasons": ["Supertrend bullish", "RSI supportive", "VWAP alignment"]}

@app.post("/api/paper/orders")
def paper_order(order: PaperOrder):
    record = {"id": len(trades) + 1, "time": datetime.utcnow().isoformat() + "Z", **order.model_dump(), "mode": "PAPER"}
    trades.append(record)
    positions.append({"symbol": order.symbol, "side": order.side, "quantity": order.quantity, "avg": order.price, "ltp": order.price, "pnl": 0.0, "mode": "PAPER"})
    return {"ok": True, "order": record}

@app.get("/api/positions")
def get_positions():
    return {"positions": positions}

@app.get("/api/trades")
def get_trades():
    return {"trades": trades}

@app.get("/api/fyers/status")
def fyers_status():
    return {"configured": False, "authenticated": False, "live_orders_enabled": False, "message": "FYERS is intentionally disabled in the initial shared test build."}
