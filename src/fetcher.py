"""OKX 数据获取"""
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from dataclasses import dataclass, asdict


@dataclass
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    vol: float

    def to_dict(self) -> dict:
        return {
            "ts": self.ts.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "vol": self.vol,
        }


def fetch_candles(base_url: str, inst_id: str, bar: str, limit: int = 100) -> list[Candle]:
    """从 OKX 拉取 K 线数据"""
    url = f"{base_url}/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = Request(url, headers={"User-Agent": "crypto-analyzer/2.0"})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    if data["code"] != "0":
        raise RuntimeError(f"OKX API error: {data['msg']}")

    candles = []
    for c in reversed(data["data"]):
        candles.append(Candle(
            ts=datetime.fromtimestamp(int(c[0]) / 1000, tz=timezone.utc),
            open=float(c[1]),
            high=float(c[2]),
            low=float(c[3]),
            close=float(c[4]),
            vol=float(c[5]),
        ))
    return candles
