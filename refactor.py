import os

replacements = {
    'ExecuteTradeCommand(symbol="AAPL", quantity=Decimal(\'10\'), estimated_value=Decimal(\'500.0\'), strategy_id="strat_cb")':
    'ExecuteTradeCommand(symbol="AAPL", direction=TradeDirection.BUY, quantity=Decimal(\'10\'), estimated_value=Decimal(\'500.0\'), strategy_id="strat_cb")',
    
    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'85.0\'), "strat_limit")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'85.0\'), "strat_limit")',

    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'10.0\'), "strat_limit")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'10.0\'), "strat_limit")',
    
    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'50.0\'), "strat_comp")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'50.0\'), "strat_comp")',

    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'91.0\'), "strat_hyst")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'91.0\'), "strat_hyst")',

    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'2.0\'), "strat_hyst")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'2.0\'), "strat_hyst")',

    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'7.0\'), "strat_hyst")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'7.0\'), "strat_hyst")',

    'TradeExecutedEvent("s1", "TSLA", Decimal(\'100\'), Decimal(\'10.0\'))':
    'TradeExecutedEvent("s1", "TSLA", TradeDirection.BUY, Decimal(\'100\'), Decimal(\'10.0\'))',

    'TradeExecutedEvent("s1", "TSLA", Decimal(\'50\'), Decimal(\'16.0\'))':
    'TradeExecutedEvent("s1", "TSLA", TradeDirection.BUY, Decimal(\'50\'), Decimal(\'16.0\'))',

    'TradeExecutedEvent("s1", "TSLA", Decimal(\'-100\'), Decimal(\'20.0\'))':
    'TradeExecutedEvent("s1", "TSLA", TradeDirection.SELL, Decimal(\'100\'), Decimal(\'20.0\'))',

    'TradeExecutedEvent("s1", "TSLA", Decimal(\'-100\'), Decimal(\'15.0\'))':
    'TradeExecutedEvent("s1", "TSLA", TradeDirection.SELL, Decimal(\'100\'), Decimal(\'15.0\'))',

    'ExecuteTradeCommand("AAPL", Decimal(\'1\'), Decimal(\'100.0\'), "s1")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'100.0\'), "s1")',

    'TradeExecutedEvent("s1", "BTC", Decimal(\'2\'), Decimal(\'50000.0\'))':
    'TradeExecutedEvent("s1", "BTC", TradeDirection.BUY, Decimal(\'2\'), Decimal(\'50000.0\'))',

    'TradeExecutedEvent("s1", "BTC", Decimal(\'-1\'), Decimal(\'60000.0\'))':
    'TradeExecutedEvent("s1", "BTC", TradeDirection.SELL, Decimal(\'1\'), Decimal(\'60000.0\'))',

    'ExecuteTradeCommand("AAPL", Decimal(\'10\'), Decimal(\'200.0\'), "s1")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'200.0\'), "s1")',

    'ExecuteTradeCommand("AAPL", Decimal(\'10\'), Decimal(\'400.0\'), "strat_1")':
    'ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'400.0\'), "strat_1")',

    'TradeExecutedEvent(strategy_id="strat_1", symbol="AAPL", quantity=Decimal(\'10\'), execution_price=Decimal(\'40.0\'))':
    'TradeExecutedEvent(strategy_id="strat_1", symbol="AAPL", direction=TradeDirection.BUY, quantity=Decimal(\'10\'), execution_price=Decimal(\'40.0\'))',

    'ExecuteTradeCommand("TSLA", Decimal(\'10\'), Decimal(\'200.0\'), "strat_1")':
    'ExecuteTradeCommand("TSLA", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'200.0\'), "strat_1")',

    'ExecuteTradeCommand("TSLA", Decimal(\'-10\'), Decimal(\'200.0\'), "strat_1")':
    'ExecuteTradeCommand("TSLA", TradeDirection.SELL, Decimal(\'10\'), Decimal(\'200.0\'), "strat_1")',

    'TradeExecutedEvent(strategy_id="strat_1", symbol="TSLA", quantity=Decimal(\'-10\'), execution_price=Decimal(\'20.0\'))':
    'TradeExecutedEvent(strategy_id="strat_1", symbol="TSLA", direction=TradeDirection.SELL, quantity=Decimal(\'10\'), execution_price=Decimal(\'20.0\'))',

    'ExecuteTradeCommand("TSLA", Decimal(\'-30\'), Decimal(\'600.0\'), "strat_1")':
    'ExecuteTradeCommand("TSLA", TradeDirection.SELL, Decimal(\'30\'), Decimal(\'600.0\'), "strat_1")',

    'ExecuteTradeCommand("NVDA", Decimal(\'10\'), Decimal(\'200.0\'), "s1")':
    'ExecuteTradeCommand("NVDA", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'200.0\'), "s1")',

    'TradeExecutedEvent("s1", "NVDA", Decimal(\'10\'), Decimal(\'20.0\'))':
    'TradeExecutedEvent("s1", "NVDA", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'20.0\'))',

    'ExecuteTradeCommand("NVDA", Decimal(\'1\'), Decimal(\'20.0\'), "s1")':
    'ExecuteTradeCommand("NVDA", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'20.0\'), "s1")',

    'ExecuteTradeCommand("AMD", Decimal(\'5\'), Decimal(\'100.0\'), "s1")':
    'ExecuteTradeCommand("AMD", TradeDirection.BUY, Decimal(\'5\'), Decimal(\'100.0\'), "s1")',

    'TradeExecutedEvent("s1", "AMD", Decimal(\'5\'), Decimal(\'20.0\'))':
    'TradeExecutedEvent("s1", "AMD", TradeDirection.BUY, Decimal(\'5\'), Decimal(\'20.0\'))',

    'ExecuteTradeCommand("AMD", Decimal(\'1\'), Decimal(\'20.0\'), "s1")':
    'ExecuteTradeCommand("AMD", TradeDirection.BUY, Decimal(\'1\'), Decimal(\'20.0\'), "s1")',

    'ExecuteTradeCommand("UNKNOWN_COIN", Decimal(\'10\'), Decimal(\'100.0\'), "strat_1")':
    'ExecuteTradeCommand("UNKNOWN_COIN", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'100.0\'), "strat_1")',

    'ExecuteTradeCommand(symbol="AAPL", quantity=10, estimated_value=500.0, strategy_id="strat_1")':
    'ExecuteTradeCommand(symbol="AAPL", direction=TradeDirection.BUY, quantity=10, estimated_value=500.0, strategy_id="strat_1")',

    'ExecuteTradeCommand(decision)':
    'ExecuteTradeCommand(decision.symbol, TradeDirection.BUY, decision.quantity, decision.estimated_value, decision.strategy_id)',

    'TradeExecutedEvent("s1", symbol, Decimal(\'100\'), Decimal(\'10.0\'))':
    'TradeExecutedEvent("s1", symbol, TradeDirection.BUY, Decimal(\'100\'), Decimal(\'10.0\'))',

    'ExecuteTradeCommand("SYM_5000", Decimal(\'10\'), Decimal(\'100.0\'), "s1")':
    'ExecuteTradeCommand("SYM_5000", TradeDirection.BUY, Decimal(\'10\'), Decimal(\'100.0\'), "s1")'
}

directories = ['tests/gqos/risk', 'tests/gqos/execution', 'scripts']
for d in directories:
    for root, dirs, files in os.walk(d):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                original_content = content
                for old, new in replacements.items():
                    content = content.replace(old, new)
                
                if content != original_content:
                    if 'TradeDirection' not in content:
                        content = 'from gqos.common.enums import TradeDirection\n' + content
                    with open(path, 'w', encoding='utf-8') as file:
                        file.write(content)
                    print(f'Updated {path}')
