import os
from datetime import datetime, timedelta
from database.repository import repository
from database.models import ShadowTrade
from mlops.registry import registry
import shutil

def run_auto_rollback():
    print("Checking Production Model Health for Auto-Rollback...")
    
    # Calculate PF over the last 3 days
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=3)
    
    with repository.get_session() as session:
        trades = session.query(ShadowTrade).filter(
            ShadowTrade.open_time >= start_time
        ).all()
        
    wins = sum([1 for t in trades if t.pnl is not None and t.pnl > 0])
    losses = sum([1 for t in trades if t.pnl is not None and t.pnl <= 0])
    win_sum = sum([t.pnl for t in trades if t.pnl is not None and t.pnl > 0])
    loss_sum = abs(sum([t.pnl for t in trades if t.pnl is not None and t.pnl <= 0]))
    
    pf = win_sum / loss_sum if loss_sum > 0 else (99.9 if win_sum > 0 else 0.0)
    
    print(f"Shadow Trades last 3 days: {len(trades)}")
    print(f"Shadow PF last 3 days: {pf:.3f}")
    
    if len(trades) >= 5 and pf < 1.0:
        print("🚨 CRITICAL: PF < 1.0 for 3 days. Initiating Auto-Rollback!")
        
        # Demote current
        prod_models = sorted(os.listdir(registry.production_dir))
        if len(prod_models) <= 1:
            print("Cannot rollback: Only one or zero production models exist.")
            return
            
        current_version = prod_models[-1]
        previous_version = prod_models[-2]
        
        print(f"Demoting {current_version} to archive...")
        registry.promote_model(current_version, "production", "archive")
        
        # In our registry, moving back from archive to production isn't officially in the 'forward flow'
        # But we can manually restore the previous version if it was archived, or it's still in production.
        # Since our registry keeps old versions in production until archived, the previous is now the active one!
        print(f"Rollback Complete. Active Production model is now {previous_version}")
    else:
        print("✅ Health Check Passed. No rollback required.")

if __name__ == "__main__":
    run_auto_rollback()
