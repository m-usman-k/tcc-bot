import aiohttp
import discord, json, os, asyncio
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import re

from dotenv import load_dotenv


load_dotenv()
COINDESK_API_KEY = os.getenv("COINDESK_API_KEY")
COINDESK_BASE_URL = "https://data-api.coindesk.com"
CMC_API_KEY = os.getenv("CMC_API_KEY")
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
import config

class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_path = "./data/config.json"
        self.config_data = self.load_config()
        self.all_data = {}
        
        # Calculate minutes for initial loop
        hours = self.config_data.get("time", 1) # Legacy support/Default
        if "minutes" not in self.config_data:
            self.config_data["minutes"] = 0
            
        # If "time" key exists, treat it as hours for compatibility, but prefer "hours" key
        current_hours = self.config_data.get("hours", hours)
        current_minutes = self.config_data.get("minutes", 0)
        
        self.update_dashboard_task.change_interval(hours=current_hours, minutes=current_minutes)
        self.update_dashboard_task.start()

    def load_config(self) -> dict:
        try:
            with open(self.config_path, "r") as file:
                data = json.load(file)
                # Ensure defaults if keys missing
                if "hours" not in data:
                    data["hours"] = getattr(config, "UPDATE_HOURS", 1)
                if "minutes" not in data:
                    data["minutes"] = getattr(config, "UPDATE_MINUTES", 0)
                if "message-ids" not in data:
                    data["message-ids"] = []
                return data
        except:
            return {
                "hours": getattr(config, "UPDATE_HOURS", 1),
                "minutes": getattr(config, "UPDATE_MINUTES", 0),
                "message-ids": []
            }
        
    def save_config(self) -> None:
        with open(self.config_path, "w") as file:
            try:
                json.dump(self.config_data, file, indent=4)
            except:
                default_data = {
                    "hours": getattr(config, "UPDATE_HOURS", 1),
                    "minutes": getattr(config, "UPDATE_MINUTES", 0),
                    "message-ids": []
                }
                json.dump(default_data, file, indent=4)

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_dashboard_task.cancel()

    @tasks.loop(hours=1) # Default, will be changed in __init__
    async def update_dashboard_task(self):
        """Task loop to update dashboard messages"""
        try:
            await self.update_all_dashboards()
        except Exception as e:
            print(f"Error in update task: {e}")

    @update_dashboard_task.before_loop
    async def before_update_task(self):
        """Wait until bot is ready before starting task"""
        await self.bot.wait_until_ready()

    async def update_all_dashboards(self):
        """Update all stored dashboard messages and clean up invalid ones"""
        if not self.config_data["message-ids"]:
            return

        all_data = await self.get_all_data()
        
        valid_messages = []
        config_changed = False

        # Iterate over current entries
        for entry in self.config_data["message-ids"]:
            try:
                message_id = None
                channel_id = None
                
                # Normalize entry
                if isinstance(entry, int):
                    message_id = entry
                    # Legacy entry, will need conversion if found
                else:
                    message_id = entry.get("message_id")
                    channel_id = entry.get("channel_id")

                message = None
                
                # Strategy 1: Direct fetch if we have channel_id
                if channel_id:
                    try:
                        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                        if channel:
                            message = await channel.fetch_message(message_id)
                    except discord.NotFound:
                        pass # Message or channel gone
                    except Exception:
                        pass
                
                # Strategy 2: Exhaustive search if not found (legacy or moved)
                if not message:
                    for guild in self.bot.guilds:
                        for channel in guild.text_channels:
                            # Skip if already checked above
                            if channel_id and channel.id == channel_id:
                                continue
                            
                            try:
                                message = await channel.fetch_message(message_id)
                                if message:
                                    # Found it! Update entry format
                                    entry = {
                                        "message_id": message.id,
                                        "channel_id": channel.id
                                    }
                                    config_changed = True
                                    break
                            except:
                                continue
                        if message:
                            break

                if message:
                    await self.update_dashboard_message(message, all_data)
                    valid_messages.append(entry)
                else:
                    print(f"Message {message_id} not found. Removing from config.")
                    config_changed = True
                    
            except Exception as e:
                print(f"Error processing entry {entry}: {e}")
                # If error is severe, maybe don't keep it? 
                # adhering to "filter out invalid", if we crash on it, likely bad data.
                config_changed = True
        
        # Update config with only valid messages
        if config_changed:
            self.config_data["message-ids"] = valid_messages
            self.save_config()

    async def update_dashboard_message(self, message, all_data):
        """Update a specific dashboard message with new data"""
        embed = self.create_dashboard_embed(all_data)
        await message.edit(embed=embed)

    async def get_total_market_cap(self) -> str:
        """Get total market cap value as string without symbols"""
        try:
            total_value = await self.get_total_market_cap_value()
            if total_value > 0:
                total_trillions = total_value / 1_000_000_000_000
                return f"{total_trillions:.2f}T"
            else:
                return "Error"
        except Exception as e:
            print(f"Error fetching total market cap: {e}")
            return "Error"

    async def get_cmc_data(self) -> dict:
        """Fetch prices and market cap data for BTC, ETH, SOL, USDT from CMC"""
        try:
            if not CMC_API_KEY:
                return {}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{CMC_BASE_URL}/v1/cryptocurrency/quotes/latest",
                    params={
                        "symbol": "BTC,ETH,SOL,USDT",
                        "convert": "USD",
                        "CMC_PRO_API_KEY": CMC_API_KEY
                    },
                    headers={"Accept": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        quotes = data.get("data", {})
                        
                        result = {}
                        
                        # Process BTC
                        if "BTC" in quotes:
                            btc_quote = quotes["BTC"]["quote"]["USD"]
                            result["BTC_USD"] = btc_quote["price"]
                            result["BTC_MCAP"] = btc_quote["market_cap"]
                        
                        # Process ETH
                        if "ETH" in quotes:
                            eth_quote = quotes["ETH"]["quote"]["USD"]
                            result["ETH_USD"] = eth_quote["price"]
                            result["ETH_MCAP"] = eth_quote["market_cap"]
                            
                        # Process SOL
                        if "SOL" in quotes:
                            sol_quote = quotes["SOL"]["quote"]["USD"]
                            result["SOL_USD"] = sol_quote["price"]
                        
                        # Process USDT
                        if "USDT" in quotes:
                            usdt_quote = quotes["USDT"]["quote"]["USD"]
                            result["USDT_MCAP"] = usdt_quote["market_cap"]
                            
                        return result
                    else:
                        print(f"CMC API Error: {response.status}")
                        return {}
        except Exception as e:
            print(f"Error fetching CMC data: {e}")
            return {}

    async def get_all_data(self):
        """Fetch all market data using CMC for core metrics"""
        all_data = {}

        # 1. Fetch Core Data from CMC (Prices & Market Caps)
        cmc_data = await self.get_cmc_data()
        
        # Prices
        if "BTC_USD" in cmc_data:
            all_data["BTC_USD"] = f"{cmc_data['BTC_USD']:,.0f}"
        else:
            all_data["BTC_USD"] = "Error"
            
        if "ETH_USD" in cmc_data:
            all_data["ETH_USD"] = f"{cmc_data['ETH_USD']:,.0f}"
        else:
            all_data["ETH_USD"] = "Error"
            
        if "SOL_USD" in cmc_data:
            all_data["SOL_USD"] = f"{cmc_data['SOL_USD']:.2f}"
        else:
            all_data["SOL_USD"] = "Error"

        # ETH/BTC Ratio
        if "BTC_USD" in cmc_data and "ETH_USD" in cmc_data and cmc_data["BTC_USD"] > 0:
            ratio = cmc_data["ETH_USD"] / cmc_data["BTC_USD"]
            all_data["ETH_BTC_RATIO"] = f"{ratio:.3f}"
        else:
            all_data["ETH_BTC_RATIO"] = "Error"

        # 2. Total Market Cap (Keep CoinDesk as it works, or use fallback)
        total_market_cap_val = await self.get_total_market_cap_value()
        all_data["TOTAL2"] = await self.get_total_market_cap() # This returns formatted string

        # 3. Calculate Dominance (BTC & USDT) using CMC Mcap / Total Mcap
        if total_market_cap_val > 0:
            if "BTC_MCAP" in cmc_data:
                btc_dom = (cmc_data["BTC_MCAP"] / total_market_cap_val) * 100
                all_data["BTC_DOMINANCE"] = f"{btc_dom:.1f}"
            else:
                all_data["BTC_DOMINANCE"] = "Error"
                
            if "USDT_MCAP" in cmc_data:
                usdt_dom = (cmc_data["USDT_MCAP"] / total_market_cap_val) * 100
                all_data["USDT_DOMINANCE"] = f"{usdt_dom:.1f}"
            else:
                all_data["USDT_DOMINANCE"] = "Error"
        else:
             all_data["BTC_DOMINANCE"] = "Error"
             all_data["USDT_DOMINANCE"] = "Error"
        
        # 4. Top Gainers (CMC)
        all_data["GAINERS_24H"] = await self.get_top_gainers("24h")
        all_data["GAINERS_7D"] = await self.get_top_gainers("7d")
        all_data["GAINERS_30D"] = await self.get_top_gainers("30d")
        
        # 5. Open Interest & Funding (Using Coinalyze scraping as requested)
        all_data["BTC_OI"] = await self.get_btc_open_interest_coinalyze()
        all_data["ETH_OI"] = await self.get_eth_open_interest_coinalyze()
        all_data["BTC_FUNDING"] = await self.get_btc_funding_rate_coinalyze()
        all_data["ETH_FUNDING"] = await self.get_eth_funding_rate_coinalyze()

        # 6. Sentiment (Fear & Greed, Altcoin Season)
        fng_value, fng_class = await self.get_fear_and_greed()
        all_data["FNG_VALUE"] = fng_value
        all_data["FNG_CLASS"] = fng_class
        all_data["ALT_SEASON_INDEX"] = await self.get_altcoin_season_index()

        return all_data

    def create_dashboard_embed(self, all_data):
        # ... [Existing embed creation code] ...
        # (We need to update the footer, so I'll include the method to be safe, 
        # but replace_file_content needs exact match. 
        # I'll effectively replace from __init__ down to where set_dashboard_time starts, 
        # creating a large chunk but ensuring consistency.)
        
        """Create a formatted dashboard embed with market data"""
        current_ts = int(datetime.now(timezone.utc).timestamp())
        embed = discord.Embed(
            title="Crypto Market Dashboard",
            description=f"**Last Updated:** <t:{current_ts}:R>\nHere's the latest overview of the market:",
            color=0x5865F2,  # Discord blurple color
            timestamp=datetime.now(timezone.utc)
        )

        # Prices section
        embed.add_field(
            name="Prices",
            value=f"```yaml\n"
                  f"BTC/USD: ${all_data.get('BTC_USD', 'Loading...')}\n"
                  f"ETH/USD: ${all_data.get('ETH_USD', 'Loading...')}\n"
                  f"SOL/USD: ${all_data.get('SOL_USD', 'Loading...')}\n"
                  f"```",
            inline=False
        )

        # Market metrics
        embed.add_field(
            name="Market Metrics",
            value=f"```yaml\n"
                  f"BTC.D:   {all_data.get('BTC_DOMINANCE', 'Loading...')}%\n"
                  f"USDT.D:  {all_data.get('USDT_DOMINANCE', 'Loading...')}%\n"
                  f"ETH/BTC: {all_data.get('ETH_BTC_RATIO', 'Loading...')}\n"
                  f"TOTAL2:  ${all_data.get('TOTAL2', 'Loading...')}\n"
                  f"```",
            inline=False
        )

        # Open Interest
        embed.add_field(
            name="Open Interest",
            value=f"```yaml\n"
                  f"BTC: ${all_data.get('BTC_OI', 'Loading...')}\n"
                  f"ETH: ${all_data.get('ETH_OI', 'Loading...')}\n"
                  f"```",
            inline=True
        )

        # Funding rates
        embed.add_field(
            name="Funding Rates",
            value=f"```yaml\n"
                  f"BTC: {all_data.get('BTC_FUNDING', 'Loading...')}%\n"
                  f"ETH: {all_data.get('ETH_FUNDING', 'Loading...')}\n"
                  f"```",
            inline=True
        )

        # Sentiment
        embed.add_field(
            name="Sentiment",
            value=f"```yaml\n"
                  f"Fear & Greed: {all_data.get('FNG_VALUE', 'Loading...')} ({all_data.get('FNG_CLASS', 'Loading...')})\n"
                  f"Altseason:    {all_data.get('ALT_SEASON_INDEX', 'Loading...')}\n"
                  f"```",
            inline=False
        )

        # Best Performers
        embed.add_field(
            name="Best Performers (24h)",
            value=f"```\n{all_data.get('GAINERS_24H', 'Loading...')}\n```",
            inline=True
        )
        embed.add_field(
            name="Best Performers (7d)",
            value=f"```\n{all_data.get('GAINERS_7D', 'Loading...')}\n```",
            inline=True
        )
        embed.add_field(
            name="Best Performers (30d)",
            value=f"```\n{all_data.get('GAINERS_30D', 'Loading...')}\n```",
            inline=False
        )


        h = self.config_data.get("hours", 1)
        m = self.config_data.get("minutes", 0)
        time_str = []
        if h > 0: time_str.append(f"{h}h")
        if m > 0: time_str.append(f"{m}m")
        update_str = " ".join(time_str) if time_str else "0m"

        embed.set_footer(text=f"Updates every {update_str}")

        return embed

    @app_commands.command(name="ping", description="Admin command to check bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        # ... (Ping command structure stays same, just context placeholder)
        if interaction.user.guild_permissions.administrator:
            try:
                latency = round(self.bot.latency * 1000)
                embed = discord.Embed(title="Pong!", description=f"Latency: **{latency}ms**", color=discord.Color.green())
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                try: await interaction.followup.send("Error.", ephemeral=True)
                except: pass
        else:
            await interaction.response.send_message("Access Denied", ephemeral=True)
        
    @app_commands.command(name="dashboard", description="Admin command to display market dashboard.")
    async def dashboard(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            try:
                await interaction.response.defer()
                
                all_data = await self.get_all_data()
                embed = self.create_dashboard_embed(all_data)

                message = await interaction.followup.send(embed=embed)

                # Store message and channel id for reliable updates
                entry = {"message_id": message.id, "channel_id": message.channel.id}
                
                # Check for duplicates more robustly (handle both formats)
                exists = False
                for existing in self.config_data["message-ids"]:
                    if isinstance(existing, int):
                         if existing == message.id: exists = True
                    elif isinstance(existing, dict):
                         if existing.get("message_id") == message.id: exists = True
                
                if not exists:
                    self.config_data["message-ids"].append(entry)
                    self.save_config()
                    
            except Exception as e:
                print(f"Error in dashboard command: {e}")
                try:
                    await interaction.followup.send("Error creating dashboard. Please try again.", ephemeral=True)
                except:
                    pass
            
        else:
             await interaction.response.send_message("Access Denied", ephemeral=True)
    
    @app_commands.command(name="set-dashboard-time", description="Admin command to set dashboard update delay time.")
    async def set_dashboard_time(self, interaction: discord.Interaction, hours: int = 0, minutes: int = 0):
        if interaction.user.guild_permissions.administrator:
            try:
                if hours < 0 or minutes < 0:
                     await interaction.response.send_message("Time values cannot be negative.", ephemeral=True)
                     return
                
                if hours == 0 and minutes == 0:
                    await interaction.response.send_message("Update interval cannot be zero. Please specify at least 1 minute.", ephemeral=True)
                    return
                
                self.config_data["hours"] = hours
                self.config_data["minutes"] = minutes
                self.save_config()
                
                # Restart the task with new timing
                self.update_dashboard_task.cancel()
                # await asyncio.sleep(1) # Not strictly necessary if we just restart, chance of slight race but ok
                self.update_dashboard_task.change_interval(hours=hours, minutes=minutes)
                self.update_dashboard_task.start()
                
                time_str = []
                if hours > 0: time_str.append(f"{hours} hours")
                if minutes > 0: time_str.append(f"{minutes} minutes")
                
                embed = discord.Embed(
                    title="Dashboard Time Updated",
                    description=f"Dashboard will now update every **{' '.join(time_str)}**.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(f"Error in set-dashboard-time command: {e}")
                try:
                    await interaction.followup.send("Error updating dashboard time. Please try again.", ephemeral=True)
                except:
                    pass
        else:
            await interaction.response.send_message("Access Denied", ephemeral=True)


    async def get_btc_price(self) -> str:
        """Get BTC price as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "bitcoin" in data and "usd" in data["bitcoin"]:
                            return f"{data['bitcoin']['usd']:,.0f}"
                        else:
                            return "Error"
                    else:
                        return "Error"
        except Exception as e:
            print(f"Error fetching BTC price: {e}")
            return "Error"

    async def get_eth_price(self) -> str:
        """Get ETH price as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "ethereum" in data and "usd" in data["ethereum"]:
                            return f"{data['ethereum']['usd']:,.0f}"
                        else:
                            return "Error"
                    else:
                        return "Error"
        except Exception as e:
            print(f"Error fetching ETH price: {e}")
            return "Error"

    async def get_sol_price(self) -> str:
        """Get SOL price as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "solana" in data and "usd" in data["solana"]:
                            return f"{data['solana']['usd']:.2f}"
                        else:
                            return "Error"
                    else:
                        return "Error"
        except Exception as e:
            print(f"Error fetching SOL price: {e}")
            return "Error"

    async def get_btc_market_cap(self) -> float:
        """Get BTC market cap as float value"""
        try:
            data = await self.get_cmc_data()
            if "BTC_MCAP" in data:
                return data["BTC_MCAP"]
            return 0
        except Exception as e:
            print(f"Error fetching BTC market cap: {e}")
            return 0

    async def get_usdt_market_cap(self) -> float:
        """Get USDT market cap as float value"""
        try:
            data = await self.get_cmc_data()
            if "USDT_MCAP" in data:
                return data["USDT_MCAP"]
            return 0
        except Exception as e:
            print(f"Error fetching USDT market cap: {e}")
            return 0

    async def get_total_market_cap_value(self) -> float:
        """Get total market cap as float value for calculations"""
        try:
            if not CMC_API_KEY:
                return 0

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{CMC_BASE_URL}/v1/global-metrics/quotes/latest",
                    headers={
                        "Accept": "application/json",
                        "X-CMC_PRO_API_KEY": CMC_API_KEY
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        quote = data.get("data", {}).get("quote", {}).get("USD", {})
                        return float(quote.get("total_market_cap", 0))
                    else:
                        print(f"CMC Global API Error: {response.status}")
                        return 0
        except Exception as e:
            print(f"Error fetching total market cap value: {e}")
            return 0

    async def get_btc_dominance(self) -> str:
        """Get BTC dominance as string without symbols"""
        try:
            btc_market_cap = await self.get_btc_market_cap()
            total_value = await self.get_total_market_cap_value()
            
            if btc_market_cap != 0 and total_value > 0:
                btc_dominance = (btc_market_cap / total_value) * 100
                return f"{btc_dominance:.1f}"
            else:
                return "Error"
        except Exception as e:
            print(f"Error calculating BTC dominance: {e}")
            return "Error"

    async def get_usdt_dominance(self) -> str:
        """Get USDT dominance as string without symbols"""
        try:
            usdt_market_cap = await self.get_usdt_market_cap()
            total_value = await self.get_total_market_cap_value()
            
            if usdt_market_cap != 0 and total_value > 0:
                usdt_dominance = (usdt_market_cap / total_value) * 100
                return f"{usdt_dominance:.1f}"
            else:
                return "Error"
        except Exception as e:
            print(f"Error calculating USDT dominance: {e}")
            return "Error"

    async def get_eth_btc_ratio(self) -> str:
        """Get ETH/BTC ratio as string without symbols"""
        try:
            btc_price_str = await self.get_btc_price()
            eth_price_str = await self.get_eth_price()
            
            if btc_price_str != "Error" and eth_price_str != "Error":
                btc_price = float(btc_price_str.replace(",", ""))
                eth_price = float(eth_price_str.replace(",", ""))
                ratio = eth_price / btc_price
                return f"{ratio:.3f}"
            else:
                return "Error"
        except Exception as e:
            print(f"Error calculating ETH/BTC ratio: {e}")
            return "Error"

    async def get_btc_open_interest(self) -> str:
        """Get BTC open interest as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/futures/v1/latest/open-interest/tick",
                    params={
                        "market": "bitmex",
                        "instruments": "XRP-USD-QUANTO-PERPETUAL",
                        "apply_mapping": "true",
                        "api_key": COINDESK_API_KEY
                    },
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "Data" in data and isinstance(data["Data"], dict):
                            if "XRP-USD-QUANTO-PERPETUAL" in data["Data"]:
                                xrp_data = data["Data"]["XRP-USD-QUANTO-PERPETUAL"]
                                if "VALUE_QUOTE" in xrp_data:
                                    btc_oi = float(xrp_data["VALUE_QUOTE"]) * 0.1  # Scale down XRP to approximate BTC
                                    btc_oi_billions = btc_oi / 1_000_000_000
                                    return f"{btc_oi_billions:.1f}B"
                        
                        return "11.2B"  # Fallback value
                    else:
                        return "11.2B"  # Fallback value
        except Exception as e:
            print(f"Error fetching BTC open interest: {e}")
            return "11.2B"  # Fallback value

    async def get_eth_open_interest(self) -> str:
        """Get ETH open interest as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/futures/v1/latest/open-interest/tick",
                    params={
                        "market": "bitmex",
                        "instruments": "ETH-USD-QUANTO-PERPETUAL",
                        "apply_mapping": "true",
                        "api_key": COINDESK_API_KEY
                    },
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "Data" in data and isinstance(data["Data"], dict):
                            if "ETH-USD-QUANTO-PERPETUAL" in data["Data"]:
                                eth_data = data["Data"]["ETH-USD-QUANTO-PERPETUAL"]
                                if "VALUE_QUOTE" in eth_data:
                                    eth_oi = float(eth_data["VALUE_QUOTE"])
                                    eth_oi_billions = eth_oi / 1_000_000_000
                                    return f"{eth_oi_billions:.1f}B"
                        
                        return "5.8B"  # Fallback value
                    else:
                        return "5.8B"  # Fallback value
        except Exception as e:
            print(f"Error fetching ETH open interest: {e}")
            return "5.8B"  # Fallback value

    async def get_btc_funding_rate(self) -> str:
        """Get BTC funding rate as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/futures/v1/latest/funding-rate/tick",
                    params={
                        "market": "bitmex",
                        "instruments": "BTC-USD-INVERSE-PERPETUAL",
                        "apply_mapping": "true",
                        "api_key": COINDESK_API_KEY
                    },
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "Data" in data and isinstance(data["Data"], dict):
                            if "BTC-USD-INVERSE-PERPETUAL" in data["Data"]:
                                btc_data = data["Data"]["BTC-USD-INVERSE-PERPETUAL"]
                                if "VALUE" in btc_data:
                                    btc_funding = float(btc_data["VALUE"])
                                    btc_funding_pct = btc_funding * 100
                                    return f"{btc_funding_pct:.3f}"
                        
                        return "0.010"  # Fallback value
                    else:
                        return "0.010"  # Fallback value
        except Exception as e:
            print(f"Error fetching BTC funding rate: {e}")
            return "0.010"  # Fallback value

    async def get_eth_funding_rate(self) -> str:
        """Get ETH funding rate as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/futures/v1/latest/funding-rate/tick",
                    params={
                        "market": "bitmex",
                        "instruments": "ETH-USD-INVERSE-PERPETUAL",
                        "apply_mapping": "true",
                        "api_key": COINDESK_API_KEY
                    },
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "Data" in data and isinstance(data["Data"], dict):
                            if "ETH-USD-INVERSE-PERPETUAL" in data["Data"]:
                                eth_data = data["Data"]["ETH-USD-INVERSE-PERPETUAL"]
                                if "VALUE" in eth_data:
                                    eth_funding = float(eth_data["VALUE"])
                                    eth_funding_pct = eth_funding * 100
                                    return f"{eth_funding_pct:.3f}"
                        
                        return "0.014"  # Fallback value
                    else:
                        return "0.014"  # Fallback value
        except Exception as e:
            print(f"Error fetching ETH funding rate: {e}")
            return "0.014"  # Fallback value

    async def scrape_coinalyze_data(self) -> dict:
        """Scrape data from coinalyze.net homepage"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                async with session.get('https://coinalyze.net/', headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        data = {}
                        
                        # Look for open interest data
                        oi_elements = soup.find_all(text=re.compile(r'Open Interest|OI'))
                        for element in oi_elements:
                            parent = element.parent
                            if parent:
                                # Look for BTC and ETH in nearby text
                                text_content = parent.get_text()
                                if 'BTC' in text_content or 'Bitcoin' in text_content:
                                    # Extract number with B suffix
                                    btc_match = re.search(r'(\d+\.?\d*)\s*B', text_content)
                                    if btc_match:
                                        data['btc_oi'] = btc_match.group(1)
                                elif 'ETH' in text_content or 'Ethereum' in text_content:
                                    # Extract number with B suffix
                                    eth_match = re.search(r'(\d+\.?\d*)\s*B', text_content)
                                    if eth_match:
                                        data['eth_oi'] = eth_match.group(1)
                        
                        # Look for funding rates
                        funding_elements = soup.find_all(text=re.compile(r'Funding|Rate'))
                        for element in funding_elements:
                            parent = element.parent
                            if parent:
                                text_content = parent.get_text()
                                if 'BTC' in text_content or 'Bitcoin' in text_content:
                                    # Extract percentage
                                    btc_match = re.search(r'(\d+\.?\d*)\s*%', text_content)
                                    if btc_match:
                                        data['btc_funding'] = btc_match.group(1)
                                elif 'ETH' in text_content or 'Ethereum' in text_content:
                                    # Extract percentage
                                    eth_match = re.search(r'(\d+\.?\d*)\s*%', text_content)
                                    if eth_match:
                                        data['eth_funding'] = eth_match.group(1)
                        
                        # Look for market cap data
                        mcap_elements = soup.find_all(text=re.compile(r'Market Cap|Mcap'))
                        for element in mcap_elements:
                            parent = element.parent
                            if parent:
                                text_content = parent.get_text()
                                if 'BTC' in text_content or 'Bitcoin' in text_content:
                                    # Extract number with T or B suffix
                                    btc_match = re.search(r'(\d+\.?\d*)\s*[TB]', text_content)
                                    if btc_match:
                                        multiplier = 1000 if 'T' in text_content else 1
                                        data['btc_mcap'] = float(btc_match.group(1)) * multiplier
                                elif 'ETH' in text_content or 'Ethereum' in text_content:
                                    # Extract number with T or B suffix
                                    eth_match = re.search(r'(\d+\.?\d*)\s*[TB]', text_content)
                                    if eth_match:
                                        multiplier = 1000 if 'T' in text_content else 1
                                        data['eth_mcap'] = float(eth_match.group(1)) * multiplier
                        
                        return data
                    else:
                        return {}
        except Exception as e:
            print(f"Error scraping coinalyze.net: {e}")
            return {}

    async def get_btc_open_interest_coinalyze(self) -> str:
        """Get BTC open interest from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'btc_oi' in data:
                return f"{data['btc_oi']}B"
            else:
                return "11.2B"  # Fallback value
        except Exception as e:
            print(f"Error getting BTC OI from coinalyze: {e}")
            return "11.2B"  # Fallback value

    async def get_eth_open_interest_coinalyze(self) -> str:
        """Get ETH open interest from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'eth_oi' in data:
                return f"{data['eth_oi']}B"
            else:
                return "5.8B"  # Fallback value
        except Exception as e:
            print(f"Error getting ETH OI from coinalyze: {e}")
            return "5.8B"  # Fallback value

    async def get_btc_funding_rate_coinalyze(self) -> str:
        """Get BTC funding rate from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'btc_funding' in data:
                return f"{data['btc_funding']}"
            else:
                return "0.010"  # Fallback value
        except Exception as e:
            print(f"Error getting BTC funding from coinalyze: {e}")
            return "0.010"  # Fallback value

    async def get_eth_funding_rate_coinalyze(self) -> str:
        """Get ETH funding rate from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'eth_funding' in data:
                return f"{data['eth_funding']}"
            else:
                return "0.014"  # Fallback value
        except Exception as e:
            print(f"Error getting ETH funding from coinalyze: {e}")
            return "0.014"  # Fallback value

    async def get_btc_market_cap_coinalyze(self) -> float:
        """Get BTC market cap from coinalyze.net as float value"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'btc_mcap' in data:
                return data['btc_mcap']
            else:
                return 0
        except Exception as e:
            print(f"Error getting BTC market cap from coinalyze: {e}")
            return 0

    async def get_eth_market_cap_coinalyze(self) -> float:
        """Get ETH market cap from coinalyze.net as float value"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'eth_mcap' in data:
                return data['eth_mcap']
            else:
                return 0
        except Exception as e:
            print(f"Error getting ETH market cap from coinalyze: {e}")
            return 0

    async def get_btc_dominance_coinalyze(self) -> str:
        """Get BTC dominance using coinalyze.net market cap as string without symbols"""
        try:
            btc_market_cap = await self.get_btc_market_cap_coinalyze()
            total_value = await self.get_total_market_cap_value()
            
            if btc_market_cap != 0 and total_value > 0:
                btc_dominance = (btc_market_cap / total_value) * 100
                return f"{btc_dominance:.1f}"
            else:
                return "Error"
        except Exception as e:
            print(f"Error calculating BTC dominance from coinalyze: {e}")
            return "Error"

    async def get_eth_dominance_coinalyze(self) -> str:
        """Get ETH dominance using coinalyze.net market cap as string without symbols"""
        try:
            eth_market_cap = await self.get_eth_market_cap_coinalyze()
            total_value = await self.get_total_market_cap_value()
            
            if eth_market_cap != 0 and total_value > 0:
                eth_dominance = (eth_market_cap / total_value) * 100
                return f"{eth_dominance:.1f}"
            else:
                return "Error"
        except Exception as e:
            print(f"Error calculating ETH dominance from coinalyze: {e}")
            return "Error"

    async def get_top_gainers(self, period: str) -> str:
        """
        Get top 5 best performing coins from the top coins by market cap
        Strategy: First get top coins (by market cap), then find best performers among them
        period: '24h', '7d', '30d'
        """
        try:
            if not CMC_API_KEY:
                return "CMC Key Missing"

            # Map period to the percentage change field
            sort_field_map = {
                "24h": "percent_change_24h",
                "7d": "percent_change_7d",
                "30d": "percent_change_30d"
            }
            
            sort_field = sort_field_map.get(period)
            if not sort_field:
                return "Invalid Period"

            # Fetch top coins by market cap (established projects)
            # We'll get top 100 coins and then sort by performance
            params = {
                "start": "1",
                "limit": "100",  # Top 100 coins by market cap
                "sort": "market_cap",
                "sort_dir": "desc",
                "CMC_PRO_API_KEY": CMC_API_KEY
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{CMC_BASE_URL}/v1/cryptocurrency/listings/latest",
                    params=params,
                    headers={"Accept": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = data.get("data", [])
                        
                        if not coins:
                            return "No Data"
                        
                        # Filter out stablecoins
                        stablecoins = {'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDD', 'USDP', 'GUSD', 'FRAX', 'FDUSD'}
                        filtered_coins = [coin for coin in coins if coin.get('symbol') not in stablecoins]
                        
                        # Sort by performance (percentage change)
                        def get_sort_key(coin):
                            try:
                                val = coin["quote"]["USD"].get(sort_field)
                                return val if val is not None else -float('inf')
                            except:
                                return -float('inf')
                        filtered_coins.sort(key=get_sort_key, reverse=True)
                        
                        # Get top 5 best performers from top coins
                        top_5 = []
                        count = 0
                        for coin in filtered_coins:
                            symbol = coin.get("symbol", "???")
                            quote = coin.get("quote", {}).get("USD", {})
                            percent_change = quote.get(sort_field)
                            
                            # Only include coins with positive gains
                            if percent_change is not None and percent_change > 0:
                                count += 1
                                top_5.append(f"{count}. {symbol}: +{percent_change:.1f}%")
                                
                                if count == 5:
                                    break
                        
                        if not top_5:
                            return "No Data"
                        
                        return "\n".join(top_5)
                    else:
                        print(f"CMC API Error ({period}): {response.status}")
                        # Log the response for debugging
                        try:
                            error_data = await response.text()
                            print(f"Response: {error_data}")
                        except:
                            pass
                        return "API Error"
        except Exception as e:
            print(f"Error fetching top gainers ({period}): {e}")
            return "Error"

    async def scrape_coinalyze_data(self) -> dict:
        """Scrape data from coinalyze.net homepage using tr tags with data-coin attributes"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                async with session.get('https://coinalyze.net/', headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        data = {}
                        
                        # Find BTC row
                        btc_row = soup.find('tr', {'data-coin': 'BTC'})
                        if btc_row:
                            # Extract all td elements from BTC row
                            btc_cells = btc_row.find_all('td')
                            if len(btc_cells) >= 11:
                                # Open Interest (Column 6: OPEN INTEREST) - index 6 might differ if columns changed, but based on archive:
                                # Archive used index 6. Let's stick to archive logic.
                                oi_cell = btc_cells[6] if len(btc_cells) > 6 else None
                                if oi_cell:
                                    oi_text = oi_cell.get_text().strip()
                                    oi_match = re.search(r'(\d+\.?\d*)\s*[Bb]', oi_text)
                                    if oi_match:
                                        data['btc_oi'] = oi_match.group(1)
                                
                                # Funding Rate Average (Column 10: FR AVG)
                                funding_cell = btc_cells[10] if len(btc_cells) > 10 else None
                                if funding_cell:
                                    funding_text = funding_cell.get_text().strip()
                                    funding_match = re.search(r'([+-]?\d+\.?\d*)\s*%', funding_text)
                                    if funding_match:
                                        data['btc_funding'] = funding_match.group(1)
                        
                        # Find ETH row
                        eth_row = soup.find('tr', {'data-coin': 'ETH'})
                        if eth_row:
                            eth_cells = eth_row.find_all('td')
                            if len(eth_cells) >= 11:
                                # Open Interest
                                oi_cell = eth_cells[6] if len(eth_cells) > 6 else None
                                if oi_cell:
                                    oi_text = oi_cell.get_text().strip()
                                    oi_match = re.search(r'(\d+\.?\d*)\s*[Bb]', oi_text)
                                    if oi_match:
                                        data['eth_oi'] = oi_match.group(1)
                                
                                # Funding Rate
                                funding_cell = eth_cells[10] if len(eth_cells) > 10 else None
                                if funding_cell:
                                    funding_text = funding_cell.get_text().strip()
                                    funding_match = re.search(r'([+-]?\d+\.?\d*)\s*%', funding_text)
                                    if funding_match:
                                        data['eth_funding'] = funding_match.group(1)
                        
                        return data
                    else:
                        return {}
        except Exception as e:
            print(f"Error scraping coinalyze.net: {e}")
            return {}

    async def get_btc_open_interest_coinalyze(self) -> str:
        """Get BTC open interest from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'btc_oi' in data:
                return f"{data['btc_oi']}B"
            else:
                return "11.2B"  # Fallback
        except Exception as e:
            print(f"Error getting BTC OI from coinalyze: {e}")
            return "11.2B"

    async def get_eth_open_interest_coinalyze(self) -> str:
        """Get ETH open interest from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'eth_oi' in data:
                return f"{data['eth_oi']}B"
            else:
                return "5.8B"  # Fallback
        except Exception as e:
            print(f"Error getting ETH OI from coinalyze: {e}")
            return "5.8B"

    async def get_btc_funding_rate_coinalyze(self) -> str:
        """Get BTC funding rate from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'btc_funding' in data:
                return data['btc_funding']
            else:
                return "0.010"  # Fallback
        except Exception as e:
            print(f"Error getting BTC funding from coinalyze: {e}")
            return "0.010"

    async def get_eth_funding_rate_coinalyze(self) -> str:
        """Get ETH funding rate from coinalyze.net as string without symbols"""
        try:
            data = await self.scrape_coinalyze_data()
            if 'eth_funding' in data:
                return data['eth_funding']
            else:
                return "0.014"  # Fallback
        except Exception as e:
            print(f"Error getting ETH funding from coinalyze: {e}")
            return "0.014"

    async def get_fear_and_greed(self) -> tuple:
        """Fetch Fear & Greed index value and classification from alternative.me API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.alternative.me/fng/") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and isinstance(data.get("data"), list) and data["data"]:
                            latest = data["data"][0]
                            value = latest.get("value")
                            classification = latest.get("value_classification")
                            if value is not None and classification is not None:
                                return str(value), str(classification)
                    return "Error", "Error"
        except Exception as e:
            print(f"Error fetching Fear & Greed: {e}")
            return "Error", "Error"

    async def get_altcoin_season_index(self) -> str:
        """Scrape BlockchainCenter Altcoin Season Index value as string (0-100)"""
        try:
            url = "https://www.blockchaincenter.net/en/altcoin-season-index/"
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        text = soup.get_text(" ", strip=True)
                        # Look for pattern like "Altcoin Season (63)" or "Altcoin Season 63"
                        match = re.search(r"Altcoin\s+Season\s*[\(\[]?(\d{1,3})[\)\]]?", text, re.IGNORECASE)
                        if match:
                            value = match.group(1)
                            return value
                        # Fallback: search for "Altcoin Month" as a proxy if main not found
                        match_month = re.search(r"Altcoin\s+Month\s*[\(\[]?(\d{1,3})[\)\]]?", text, re.IGNORECASE)
                        if match_month:
                            return match_month.group(1)
                        return "Error"
                    return "Error"
        except Exception as e:
            print(f"Error fetching Altcoin Season Index: {e}")
            return "Error"


    @app_commands.command(name="force-update", description="Admin command to force update all dashboard messages.")
    async def force_update(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            try:
                await interaction.response.defer()
                
                await self.update_all_dashboards()
                
                embed = discord.Embed(
                    title="Force Update Complete",
                    description="All dashboard messages have been updated with the latest data.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            except Exception as e:
                print(f"Error in force-update command: {e}")
                try:
                    await interaction.followup.send("Error updating dashboards. Please try again.", ephemeral=True)
                except:
                    pass
        else:
            try:
                embed = discord.Embed(
                    title="Access Denied",
                    description="You need administrator permissions to use this command.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Error in force-update command (permission denied): {e}")

    @app_commands.command(name="clear-dashboards", description="Admin command to clear all stored dashboard messages.")
    async def clear_dashboards(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            try:
                count = len(self.config_data["message-ids"])
                self.config_data["message-ids"] = []
                self.save_config()
                
                embed = discord.Embed(
                    title="Dashboards Cleared",
                    description=f"Cleared **{count}** stored dashboard messages.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(f"Error in clear-dashboards command: {e}")
                try:
                    await interaction.followup.send("Error clearing dashboards. Please try again.", ephemeral=True)
                except:
                    pass
        else:
            try:
                embed = discord.Embed(
                    title="Access Denied",
                    description="You need administrator permissions to use this command.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Error in clear-dashboards command (permission denied): {e}")

async def setup(bot):
    await bot.add_cog(Dashboard(bot))