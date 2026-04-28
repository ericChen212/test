# FBS WebSocket 即時行情範本

這個範本依照富邦新一代 API（TradeAPI）文件整理，提供一個可直接改參數的 Python WebSocket 即時行情骨架程式：

- 先登入再建立行情連線
- 支援 `Mode.Speed` / `Mode.Normal`
- 支援 `trades` / `books` / `indices` 訂閱
- 具備 heartbeat / data / error / reconnect / resubscribe 的基本處理

## 檔案

- `fbs_ws_realtime_template.py`

## 安裝

```bash
pip install fubon-neo
```

## 執行

### 方式 1：命令列傳參

```bash
python fbs_ws_realtime_template.py \
  --id A123456789 \
  --password 'your_password' \
  --cert-path '/path/to/cert.pfx' \
  --cert-password 'your_cert_password' \
  --mode speed \
  --channels trades,books \
  --symbols 2330,2881
```

### 方式 2：環境變數

```bash
export FBS_ID='A123456789'
export FBS_PASSWORD='your_password'
export FBS_CERT_PATH='/path/to/cert.pfx'
export FBS_CERT_PASSWORD='your_cert_password'
export FBS_MODE='normal'
export FBS_CHANNELS='trades'
export FBS_SYMBOLS='2330'

python fbs_ws_realtime_template.py
```

## 注意事項

1. 此範本使用官方 SDK（`fubon-neo`）事件模式。
2. `Mode.Speed` 預設低延遲；`Mode.Normal` 提供較完整欄位。
3. 程式中已示範斷線後重連與重新訂閱，正式上線可再加上重試上限與告警。
