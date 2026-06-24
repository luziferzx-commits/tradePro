# Project Overview
- **Project Name**: GQOS (GoldBot Quant Research Operating System) / tradePro
- **Primary Objective**: สร้างระบบเทรดอัตโนมัติระดับสถาบันที่ไม่ได้มุ่งเน้นแค่ "บอทที่สมบูรณ์แบบ" แต่สร้าง "องค์กร/ระบบที่สามารถค้นหา ทดสอบ และทดแทน Alpha ได้อย่างต่อเนื่อง" (Platform > Product)
- **Supported Markets**: ปัจจุบันโฟกัสที่ **XAUUSD (Gold)** บน MT5 (Broker: Exness) แต่สถาปัตยกรรมถูกออกแบบมารองรับ Multi-Market 
- **Trading Strategy**: ใช้ Quant Scoring (Indicators + Regime) ผสมผสานกับ AI Prediction (XGBoost) และเช็คความคล้ายคลึงจากอดีต (Market Memory)

# Current Status
- **สิ่งที่ทำเสร็จแล้ว**: 
  - ระบบ Execution เชื่อมต่อ MT5 (V1)
  - โมดูล Market Memory (Rebuilt สำเร็จ โหลดเวกเตอร์ชัยชนะ 964 รูปแบบ)
  - Risk Manager & Circuit Breakers ป้องกันข่าวแรง
  - Telegram Notifications แจ้งเตือนเข้าและปิดออเดอร์
  - GQOS Architecture (Phase 0) สถาปัตยกรรมระดับองค์กร (Core, Accounting, Shadow Trading, Research Pipeline)
- **สิ่งที่กำลังพัฒนา**: 
  - การทำ Shadow Validation (เฝ้าดูผลงาน 90 วัน) ของ Champion Alphas
  - การรองรับหลายตลาด (Multi-Market Scanner)
- **สิ่งที่ยังไม่เริ่ม**: 
  - M28: Edge Expansion (การรวมข้อมูล Alternative Data, Order Flow เข้ามาในโมเดล)

# Important Decisions
- **Risk Management**: จำกัดความเสี่ยงเข้มงวด (เช่น 0.5% - 1% ของพอร์ต) มี Circuit Breaker คอยหยุดบอทช่วงข่าวแรง
- **Position Sizing**: คำนวณ Lot Size อัตโนมัติจาก Stoploss Points, ความมั่นใจของ ML (Probability) และคะแนนสุขภาพพอร์ต
- **AI Prediction**: ใช้ XGBoost ประเมิน Probability ของ Trade Setup ถ้าความน่าจะเป็นต่ำกว่าเกณฑ์จะ Reject ออเดอร์นั้นทิ้งทันที
- **Market Memory**: บันทึก Features ของไม้ที่ชนะในอดีตลงไฟล์ `.npy` เพื่อนำมาเปรียบเทียบ (Similarity) กับหน้าเทรดปัจจุบัน หากเหมือนไม้ได้กำไรในอดีตจะเพิ่มความมั่นใจ
- **Portfolio Rules**: ใช้แนวคิดการแบ่งทุนและเลื่อนขั้น (Staging) ออเดอร์ที่ผ่านการทดสอบเท่านั้นถึงจะได้ทุนจริง

# Repository Structure
- `/gqos/` - โครงสร้างใหม่ของ GQOS V2 (ประกอบด้วย accounting, alpha, backtest, execution, risk, portfolio, observability, research)
- `/ml/` - ระบบ Machine Learning, Dataset Builder, XGBoost Predictor และ Market Memory
- `/execution/` - ระบบส่งคำสั่งซื้อขายเข้า MT5 (Executor) และ Shadow Executor
- `/strategy/` - โลจิกดั้งเดิมของ V1, Indicator, Regime Detector และ Market Scorer
- `/risk/` & `/safety/` - กฎการคำนวณ Lot Size และ Circuit Breakers
- `/positions/` - Tracker ตรวจสอบสถานะและปิดออเดอร์
- `/notifications/` - ระบบแจ้งเตือน Telegram
- `/docs/` - เก็บเอกสารโครงสร้างระบบ การออกแบบ (ADR) และบันทึกต่างๆ
- `main.py` - จุดเริ่มต้นการรันบอทเทรดจริง

# Known Issues
- `symbol_config.yaml` ยังไม่ถูกสร้างเต็มรูปแบบเพื่อการสแกนหลายตลาดพร้อมกัน
- `Market Scanner` ปัจจุบันยังคงอิงกับ `settings.SYMBOL` เดี่ยวๆ ทำให้รันหลายคู่พร้อมกันใน 1 โปรเซสยังไม่สมบูรณ์

# Future Roadmap
- **Short-Term**: ปล่อยบอทรันเก็บผลแบบ Shadow Trading / Demo เพื่อให้แน่ใจว่า Market Memory และ ML โมเดลทำงานประสานกันได้เสถียร
- **Medium-Term**: เพิ่มระบบ Multi-Market Scanner, รันเทรด 10 ตลาดพร้อมกันด้วย Portfolio Risk Control
- **Long-Term**: พัฒนาไปสู่ M28 (Alternative Data) และสร้างระบบ Alpha Factory ที่ค้นหากลยุทธ์ใหม่ได้เองตลอด 24/7

# AI Handover Section
**ถึง AI ตัวใหม่ที่จะมารับช่วงต่อ (อ่านภายใน 2 นาที):**
โปรเจกต์นี้คือ **GQOS (tradePro)** บอทเทรด MT5 อัตโนมัติที่ผสาน Quant + ML + Market Memory ปัจจุบันบอทรันได้แล้วและเพิ่งแก้ไข Market Memory ให้โหลด `.npy` ได้สำเร็จ ระบบการแจ้งเตือน Telegram ก็เพิ่มเรียบร้อย 
**หน้าที่ต่อไปของคุณ**: ขยายขีดความสามารถจากบอทที่เทรดทองคำคู่เดียว ให้กลายเป็น Platform ที่สแกนและเทรดได้หลายตลาดพร้อมกัน (Multi-Market) อ้างอิงสิ่งที่ต้องทำต่อใน `/docs/TASKS.md` และ `/docs/AI_NEXT_SESSION.md` ห้ามไปยุ่งกับโมดูลแกนกลางที่ทำงานดีอยู่แล้วถ้าไม่จำเป็น!
