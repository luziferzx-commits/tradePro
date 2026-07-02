"""
scripts/migrate_add_session_label.py
 
Migration — เพิ่ม columns ใหม่ใน trades table
  - session    (String 20)
  - pattern_id (String 100)
  - strategy   (String 50)
 
รันครั้งเดียวก่อน restart บอท:
  python scripts/migrate_add_session_label.py
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
 
from sqlalchemy import create_engine, text
from config.settings import settings
 
engine = create_engine(settings.DATABASE_URL)
 
MIGRATIONS = [
    "ALTER TABLE trades ADD COLUMN session     VARCHAR(20)  DEFAULT NULL",
    "ALTER TABLE trades ADD COLUMN pattern_id  VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE trades ADD COLUMN strategy    VARCHAR(50)  DEFAULT NULL",
]
 
def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"OK: {sql[:60]}...")
            except Exception as e:
                # Column อาจมีอยู่แล้ว → ข้ามไป
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"SKIP Already exists: {sql.split('ADD COLUMN')[1].strip()[:30]}")
                else:
                    print(f"FAILED: {e}")
        print("\nMigration complete.")
 
if __name__ == "__main__":
    run()
