# Changelog

All notable changes to this project will be documented in this file.

## [v1.0.0] - 2026-06-24
นี่คือเวอร์ชันแรกสุดที่เป็นทางการของ GQOS Institutional Framework

### Added
- **GQOS Core Architecture (`gqos/`)**: สร้างโครงสร้างพื้นฐานระดับองค์กรสำหรับค้นหา Alpha
- **Shadow Validation Pipeline**: สร้างกระบวนการ 90 วันเพื่อดูผลงานของบอทเทรด
- **Telegram Notification System**: `telegram_notifier.py` พร้อมผูกติดเข้ากับการยิงออเดอร์และการเปิดปิดบอท
- **Baseline Edge Reports**: เอกสารแสดงผลการทดสอบ OOS
- **Documentation**: เพิ่ม `FOUNDING.md`, `MANIFESTO.md`, `RESEARCH_HANDBOOK.md`

### Changed
- **Market Memory Engine**: เวกเตอร์ถูกเซฟในฟอร์แมต `.npy` ทับของเก่า โหลดใหม่ได้อย่างมีประสิทธิภาพ
- **Execution Workflow**: อัพเกรด `Executor` ให้บันทึกข้อมูล `probability` และรายละเอียดอื่นๆ เข้าสู่ฐานข้อมูลควบคู่กับการส่ง Telegram

### Fixed
- **Market Memory Filename Bug**: ปัญหาโค้ดเรียกหา `*v*.csv` ทำให้ไม่เจอไฟล์ Dataset แก้ไขโดยปรับชื่อไฟล์ Dataset ให้ตรงกับที่ Glob ต้องการ 
- **MT5 Disconnection Crash**: บอทรันค้างแล้ว MT5 หลุด ไม่ยอมต่อใหม่ ถูกหยุดการทำงานและปรับการรันรอบใหม่ 

### Removed
- **Legacy Strategy V1**: นำ Strategy เก่าออก และหันมาใช้งาน AI/XGBoost เป็นตัวกรองหลัก

---

*ประวัติก่อนหน้าเวอร์ชันนี้เป็นการพัฒนาในชื่อ GoldBot ซึ่งเป็นช่วงสร้างโมเดล Machine Learning และการทำ Feature Engineering โดยมีการเพิ่ม Circuit Breakers, News Filters, Regime Detectors และ Indicators อย่างต่อเนื่อง*
