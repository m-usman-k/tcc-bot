import asyncio
import os
import sys
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from cogs.Dashboard import Dashboard

load_dotenv()

async def diagnose_dashboard():
    print("Initializing Dashboard Diagnostics...")
    
    # Mock bot
    bot_mock = MagicMock()
    async def async_magic(): return None
    bot_mock.wait_until_ready = async_magic
    
    dashboard = Dashboard(bot_mock)
    dashboard.update_dashboard_task.cancel() # Stop loop

    print(f"CMC_KEY Present: {bool(os.getenv('CMC_API_KEY'))}")
    
    print("\n---------- 1. Testing Total Market Cap Value ----------")
    try:
        val = await dashboard.get_total_market_cap_value()
        print(f"Value: {val}")
        print(f"Type: {type(val)}")
    except Exception as e:
        print(f"EXCEPTION in get_total_market_cap_value: {e}")

    print("\n---------- 2. Testing Component Methods ----------")
    
    try:
        btc_mcap = await dashboard.get_btc_market_cap()
        print(f"BTC Market Cap: {btc_mcap}")
    except Exception as e:
        print(f"EXCEPTION in get_btc_market_cap: {e}")
        
    try:
        usdt_mcap = await dashboard.get_usdt_market_cap()
        print(f"USDT Market Cap: {usdt_mcap}")
    except Exception as e:
        print(f"EXCEPTION in get_usdt_market_cap: {e}")

    print("\n---------- 3. Testing Calculated Dominance ----------")
    
    try:
        btc_dom = await dashboard.get_btc_dominance()
        print(f"BTC Dominance Result: '{btc_dom}'")
    except Exception as e:
        print(f"EXCEPTION in get_btc_dominance: {e}")

    try:
        usdt_dom = await dashboard.get_usdt_dominance()
        print(f"USDT Dominance Result: '{usdt_dom}'")
    except Exception as e:
        print(f"EXCEPTION in get_usdt_dominance: {e}")

    print("\n---------- 4. Testing Full get_all_data() ----------")
    try:
        all_data = await dashboard.get_all_data()
        print("ALL DATA RESULT:")
        for k, v in all_data.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"EXCEPTION in get_all_data: {e}")


if __name__ == "__main__":
    asyncio.run(diagnose_dashboard())
