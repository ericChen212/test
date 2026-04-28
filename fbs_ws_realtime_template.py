#!/usr/bin/env python3
"""
Fubon Neo API WebSocket 即時行情範本（證券）

依據官方文件重點：
- 必須先 login，才有行情權限
- init_realtime 可選 Mode.Speed / Mode.Normal（預設 Speed）
- 可訂閱 channels: trades / books / indices（依模式與權限而定）
- 會收到 authenticated / heartbeat / data / error / subscribed / unsubscribed 等事件
"""

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fubon_neo.sdk import FubonSDK, Mode


@dataclass
class SubscribeTarget:
    channel: str
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    intraday_odd_lot: bool = False

    def to_payload(self) -> dict:
        payload = {"channel": self.channel}
        if self.symbol:
            payload["symbol"] = self.symbol
        if self.symbols:
            payload["symbols"] = self.symbols
        if self.intraday_odd_lot:
            payload["intradayOddLot"] = True
        return payload


@dataclass
class WSRuntime:
    sdk: FubonSDK
    stock: object
    subscriptions: List[SubscribeTarget]
    channel_id_map: Dict[str, dict] = field(default_factory=dict)
    keep_running: bool = True

    def on_message(self, message: str):
        data = self._parse_message(message)
        event = data.get("event")

        if event == "authenticated":
            print("[AUTH] authenticated")
        elif event == "heartbeat":
            print(f"[HEARTBEAT] {data.get('data', {}).get('time')}")
        elif event == "subscribed":
            self._remember_channel_ids(data.get("data"))
            print(f"[SUBSCRIBED] {json.dumps(data, ensure_ascii=False)}")
        elif event == "unsubscribed":
            print(f"[UNSUBSCRIBED] {json.dumps(data, ensure_ascii=False)}")
        elif event == "data":
            self._handle_market_data(data)
        elif event == "pong":
            print(f"[PONG] {json.dumps(data, ensure_ascii=False)}")
        elif event == "error":
            print(f"[ERROR] {json.dumps(data, ensure_ascii=False)}")
        else:
            print(f"[EVENT:{event}] {json.dumps(data, ensure_ascii=False)}")

    def on_connect(self):
        print("[CONNECT] market data connected")

    def on_disconnect(self, code, message):
        print(f"[DISCONNECT] code={code}, message={message}")
        if not self.keep_running:
            return

        time.sleep(1)
        print("[RECONNECT] reconnecting...")
        self.stock.connect()
        self.resubscribe_all()

    def on_error(self, error):
        print(f"[SOCKET_ERROR] {error}")

    def subscribe_all(self):
        for target in self.subscriptions:
            payload = target.to_payload()
            print(f"[SUBSCRIBE] {payload}")
            self.stock.subscribe(payload)

    def resubscribe_all(self):
        print("[RESUBSCRIBE] begin")
        self.subscribe_all()

    def close(self):
        self.keep_running = False
        if self.channel_id_map:
            ids = list(self.channel_id_map.keys())
            print(f"[UNSUBSCRIBE] ids={ids}")
            self.stock.unsubscribe({"ids": ids})
        self.stock.disconnect()

    @staticmethod
    def _parse_message(message: str) -> dict:
        if isinstance(message, str):
            return json.loads(message)
        return message

    def _remember_channel_ids(self, subscribed_data):
        if isinstance(subscribed_data, dict):
            cid = subscribed_data.get("id")
            if cid:
                self.channel_id_map[cid] = subscribed_data
            return

        if isinstance(subscribed_data, list):
            for item in subscribed_data:
                cid = item.get("id")
                if cid:
                    self.channel_id_map[cid] = item

    @staticmethod
    def _handle_market_data(data: dict):
        payload = data.get("data", {})
        channel = data.get("channel", "unknown")
        symbol = payload.get("symbol", "N/A")
        price = payload.get("price")
        volume = payload.get("volume")
        ts = payload.get("time")
        print(
            f"[DATA] channel={channel} symbol={symbol} price={price} volume={volume} time={ts}"
        )


def build_subscriptions(args) -> List[SubscribeTarget]:
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        raise ValueError("至少要提供一個股票代碼，例如 --symbols 2330,2881")

    channel_list = [c.strip() for c in args.channels.split(",") if c.strip()]
    subscriptions: List[SubscribeTarget] = []

    for channel in channel_list:
        if len(symbols) == 1:
            subscriptions.append(
                SubscribeTarget(
                    channel=channel,
                    symbol=symbols[0],
                    intraday_odd_lot=args.intraday_odd_lot,
                )
            )
        else:
            subscriptions.append(
                SubscribeTarget(
                    channel=channel,
                    symbols=symbols,
                    intraday_odd_lot=args.intraday_odd_lot,
                )
            )

    return subscriptions


def parse_args():
    parser = argparse.ArgumentParser(description="FBS WebSocket 即時行情範本")
    parser.add_argument("--id", default=os.getenv("FBS_ID", ""), help="身分證號")
    parser.add_argument("--password", default=os.getenv("FBS_PASSWORD", ""), help="登入密碼")
    parser.add_argument("--cert-path", default=os.getenv("FBS_CERT_PATH", ""), help="憑證路徑")
    parser.add_argument("--cert-password", default=os.getenv("FBS_CERT_PASSWORD", ""), help="憑證密碼")
    parser.add_argument("--mode", choices=["speed", "normal"], default=os.getenv("FBS_MODE", "speed"))
    parser.add_argument("--channels", default=os.getenv("FBS_CHANNELS", "trades"), help="逗號分隔，例如 trades,books")
    parser.add_argument("--symbols", default=os.getenv("FBS_SYMBOLS", "2330"), help="逗號分隔，例如 2330,2881")
    parser.add_argument("--intraday-odd-lot", action="store_true", help="是否訂閱盤中零股")
    return parser.parse_args()


def validate_credentials(args):
    required = {
        "id": args.id,
        "password": args.password,
        "cert_path": args.cert_path,
        "cert_password": args.cert_password,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"缺少必要參數: {', '.join(missing)}")


def main():
    args = parse_args()
    validate_credentials(args)

    mode = Mode.Speed if args.mode.lower() == "speed" else Mode.Normal
    subscriptions = build_subscriptions(args)

    sdk = FubonSDK()
    login_result = sdk.login(args.id, args.password, args.cert_path, args.cert_password)
    if not getattr(login_result, "is_success", False):
        raise RuntimeError(f"登入失敗: {login_result}")

    print("[LOGIN] success")

    sdk.init_realtime(mode)
    stock = sdk.marketdata.websocket_client.stock

    runtime = WSRuntime(sdk=sdk, stock=stock, subscriptions=subscriptions)

    stock.on("connect", runtime.on_connect)
    stock.on("disconnect", runtime.on_disconnect)
    stock.on("error", runtime.on_error)
    stock.on("message", runtime.on_message)

    def shutdown_handler(signum, frame):
        print(f"[SIGNAL] receive {signum}, shutdown")
        runtime.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    stock.connect()
    runtime.subscribe_all()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
