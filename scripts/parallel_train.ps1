Write-Host "Starting parallel training..."

# Start Batch 1
Start-Process -FilePath "python" -ArgumentList "scripts/train_all_markets.py", "--candles", "1000000", "--symbols", "AUDCAD", "AUDUSD", "BTCUSD", "ETHUSD" -WindowStyle Hidden -RedirectStandardOutput "logs/train_batch1.log" -RedirectStandardError "logs/train_batch1_error.log"
# Start Batch 2
Start-Process -FilePath "python" -ArgumentList "scripts/train_all_markets.py", "--candles", "1000000", "--symbols", "EURGBP", "EURUSD", "GBPUSD", "GER40" -WindowStyle Hidden -RedirectStandardOutput "logs/train_batch2.log" -RedirectStandardError "logs/train_batch2_error.log"
# Start Batch 3
Start-Process -FilePath "python" -ArgumentList "scripts/train_all_markets.py", "--candles", "1000000", "--symbols", "NAS100", "NZDUSD", "SOLUSD", "US30" -WindowStyle Hidden -RedirectStandardOutput "logs/train_batch3.log" -RedirectStandardError "logs/train_batch3_error.log"
# Start Batch 4
Start-Process -FilePath "python" -ArgumentList "scripts/train_all_markets.py", "--candles", "1000000", "--symbols", "US500", "USDCAD", "USDJPY", "USOIL" -WindowStyle Hidden -RedirectStandardOutput "logs/train_batch4.log" -RedirectStandardError "logs/train_batch4_error.log"
# Start Batch 5
Start-Process -FilePath "python" -ArgumentList "scripts/train_all_markets.py", "--candles", "1000000", "--symbols", "XAGUSD", "XAUUSD", "XRPUSD" -WindowStyle Hidden -RedirectStandardOutput "logs/train_batch5.log" -RedirectStandardError "logs/train_batch5_error.log"

Write-Host "All 5 batches dispatched in background! Check the 'logs' folder for progress."
