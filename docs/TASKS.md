# Task Management

## In Progress
### [P1] Multi-Market Scanner Readiness
- **Description**: อัพเกรดบอทให้สามารถรองรับหลายตลาดพร้อมกัน จากเดิมที่จับคู่เดียว (XAUUSDm) ใน settings 
- **Files Related**: `main.py`, `config/settings.py`, `market/scanner.py` (to be created)
- **Dependencies**: `symbol_config.yaml`
- **Expected Outcome**: บอทสามารถลูปตรวจสอบสภาวะตลาดหลายตัวพร้อมกันโดยไม่สะดุด
- **Status**: IN PROGRESS

## Backlog
### [P0] Shadow Validation Phase (90-Day passive monitoring)
- **Description**: ติดตามผลงานของ Champion Alphas 5 ตัวใน Shadow Ledger โดยห้าม Deploy จริงจนกว่าจะผ่านเกณฑ์ความเสถียร
- **Files Related**: `gqos/research/dashboard.py`
- **Dependencies**: None
- **Expected Outcome**: OOS Sharpe > 1.2 หลังจากผ่านไป 90 วัน
- **Status**: WAITING (DAY 1/90)

### [P1] Centralized Symbol Configuration
- **Description**: สร้าง `symbol_config.yaml` เพื่อใช้จัดการ parameters เฉพาะของแต่ละ Symbol เช่น XAUUSD, BTCUSD, EURUSD
- **Files Related**: `config/symbol_config.yaml`
- **Dependencies**: None
- **Expected Outcome**: ระบบเรียกการตั้งค่า Stoploss, Timeframe ตามค่าคอนฟิกของแต่ละคู่เงิน
- **Status**: BACKLOG

### [P2] Portfolio Risk Control
- **Description**: สร้างระบบคุมความเสี่ยงรวมของพอร์ตโฟลิโอ ป้องกันไม่ให้เกิด Correlation risk มากเกินไปเมื่อรันหลายตลาด
- **Files Related**: `risk/portfolio_manager.py`, `main.py`
- **Dependencies**: Multi-Market Scanner
- **Expected Outcome**: หากความเสี่ยงรวมเกินขีดจำกัด บอทจะหยุดยิงออเดอร์ในทิศทางเดียวกันชั่วคราว
- **Status**: BACKLOG

### [P3] Alternative Data Integration (M28)
- **Description**: การเริ่มพัฒนาฟีเจอร์ Edge Expansion แนะนำให้ดึงข้อมูล Sentiment, Order Flow มาช่วยโมเดล Machine Learning
- **Files Related**: `/features/alternative_data/`
- **Dependencies**: 90-Day Validation Completion
- **Expected Outcome**: โมเดลมี Feature สำคัญเพิ่มขึ้น เพิ่มความแม่นยำ (Probability)
- **Status**: BACKLOG

## Completed
### [P0] Fix Market Memory Filename Mismatch
- **Description**: แก้ปัญหา ML Predictor โหลด Market Memory ไม่ขึ้น เพราะตั้งชื่อไฟล์ Dataset ขาด Version
- **Files Related**: `ml/market_memory.py`, `/datasets/`
- **Dependencies**: None
- **Expected Outcome**: ระบบคำนวณ Similarity ได้และส่งค่าไปยังส่วนการประเมิน Risk
- **Status**: COMPLETED

### [P1] Add Telegram Notifications
- **Description**: เพิ่มระบบส่งแจ้งเตือนผ่าน Telegram เมื่อมีการเริ่มต้นบอท เปิดออเดอร์ และปิดออเดอร์
- **Files Related**: `notifications/telegram_notifier.py`, `main.py`, `execution/executor.py`, `positions/tracker.py`
- **Dependencies**: `python-telegram-bot`, `requests`
- **Expected Outcome**: ผู้ใช้ได้รับแจ้งเตือนทันที
- **Status**: COMPLETED
