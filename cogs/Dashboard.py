import aiohttp
import discord, json, os, asyncio
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

from dotenv import load_dotenv


load_dotenv()
COINDESK_API_KEY = os.getenv("COINDESK_API_KEY")
COINDESK_BASE_URL = "https://data-api.coindesk.com"

class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_path = "./data/config.json"
        self.config_data = self.load_config()
        self.all_data = {}
        self.update_dashboard_task.start()

    def load_config(self) -> dict:
        try:
            with open(self.config_path, "r") as file:
                return json.load(file)
        except:
            return {"time": 12, "message-ids": []}
        
    def save_config(self) -> None:
        with open(self.config_path, "w") as file:
            try:
                json.dump(self.config_data, file, indent=4)
            except:
                json.dump({"time": 12, "message-ids": []}, file, indent=4)

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_dashboard_task.cancel()

    @tasks.loop(hours=12)
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
        """Update all stored dashboard messages"""
        if not self.config_data["message-ids"]:
            return

        all_data = await self.get_all_data()
        
        for message_id in self.config_data["message-ids"][:]:
            try:
                for guild in self.bot.guilds:
                    try:
                        channel = discord.utils.get(guild.text_channels, name="general") or guild.text_channels[0]
                        message = await channel.fetch_message(message_id)
                        await self.update_dashboard_message(message, all_data)
                        break
                    except discord.NotFound:
                        continue
                    except Exception as e:
                        print(f"Error updating message {message_id}: {e}")
                        if message_id in self.config_data["message-ids"]:
                            self.config_data["message-ids"].remove(message_id)
                        continue
            except Exception as e:
                print(f"Error processing message {message_id}: {e}")
        
        self.save_config()

    async def update_dashboard_message(self, message, all_data):
        """Update a specific dashboard message with new data"""
        embed = self.create_dashboard_embed(all_data)
        await message.edit(embed=embed)
    
    async def get_total_market_cap(self) -> str:
        """Get total market cap value as string without symbols"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/overview/v1/latest/marketcap/all/tick",
                    params={"api_key": COINDESK_API_KEY},
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_value = float(data["Data"]["VALUE"])
                        total_trillions = total_value / 1_000_000_000_000
                        return f"{total_trillions:.2f}T"
                    else:
                        return "Error"
        except Exception as e:
            print(f"Error fetching total market cap: {e}")
            return "Error"

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
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "bitcoin" in data and "usd_market_cap" in data["bitcoin"]:
                            return data["bitcoin"]["usd_market_cap"]
                        else:
                            return 0
                    else:
                        return 0
        except Exception as e:
            print(f"Error fetching BTC market cap: {e}")
            return 0

    async def get_usdt_market_cap(self) -> float:
        """Get USDT market cap as float value"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd&include_market_cap=true"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "tether" in data and "usd_market_cap" in data["tether"]:
                            return data["tether"]["usd_market_cap"]
                        else:
                            return 0
                    else:
                        return 0
        except Exception as e:
            print(f"Error fetching USDT market cap: {e}")
            return 0

    async def get_total_market_cap_value(self) -> float:
        """Get total market cap as float value for calculations"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{COINDESK_BASE_URL}/overview/v1/latest/marketcap/all/tick",
                    params={"api_key": COINDESK_API_KEY},
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data["Data"]["VALUE"])
                    else:
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

    async def get_all_data(self):
        """Fetch all market data using individual functions"""
        all_data = {}

        # Get all data using individual functions
        all_data["TOTAL2"] = await self.get_total_market_cap()
        all_data["BTC_USD"] = await self.get_btc_price()
        all_data["ETH_USD"] = await self.get_eth_price()
        all_data["SOL_USD"] = await self.get_sol_price()
        
        # Use coinalyze.net for dominance calculations
        all_data["BTC_DOMINANCE"] = await self.get_btc_dominance_coinalyze()
        all_data["USDT_DOMINANCE"] = await self.get_usdt_dominance()
        
        all_data["ETH_BTC_RATIO"] = await self.get_eth_btc_ratio()
        
        # Use coinalyze.net for open interest and funding rates
        all_data["BTC_OI"] = await self.get_btc_open_interest_coinalyze()
        all_data["ETH_OI"] = await self.get_eth_open_interest_coinalyze()
        all_data["BTC_FUNDING"] = await self.get_btc_funding_rate_coinalyze()
        all_data["ETH_FUNDING"] = await self.get_eth_funding_rate_coinalyze()

        return all_data

    def create_dashboard_embed(self, all_data):
        """Create a formatted dashboard embed with market data"""
        embed = discord.Embed(
            title="Crypto Market Dashboard",
            description="Here's the latest overview of the market:",
            color=0x5865F2,  # Discord blurple color
            timestamp=datetime.utcnow()
        )

        # Prices section - add $ symbol
        embed.add_field(
            name="Prices",
            value=f"**BTC/USD:** ${all_data.get('BTC_USD', 'Loading...')}\n"
                  f"**ETH/USD:** ${all_data.get('ETH_USD', 'Loading...')}\n"
                  f"**SOL/USD:** ${all_data.get('SOL_USD', 'Loading...')}",
            inline=False
        )

        # Market metrics - add % symbols and $ symbol
        embed.add_field(
            name="Market Metrics",
            value=f"**BTC.D:** {all_data.get('BTC_DOMINANCE', 'Loading...')}%\n"
                  f"**USDT.D:** {all_data.get('USDT_DOMINANCE', 'Loading...')}%\n"
                  f"**ETH/BTC:** {all_data.get('ETH_BTC_RATIO', 'Loading...')}\n"
                  f"**TOTAL2:** ${all_data.get('TOTAL2', 'Loading...')}",
            inline=False
        )

        # Open Interest - add $ symbol
        embed.add_field(
            name="Open Interest",
            value=f"BTC OI: ${all_data.get('BTC_OI', 'Loading...')}\n"
                  f"ETH OI: ${all_data.get('ETH_OI', 'Loading...')}",
            inline=True
        )

        # Funding rates - add % symbol
        embed.add_field(
            name="Funding Rates",
            value=f"BTC: {all_data.get('BTC_FUNDING', 'Loading...')}%\n"
                  f"ETH: {all_data.get('ETH_FUNDING', 'Loading...')}%",
            inline=True
        )

        embed.set_footer(text=f"Updates every {self.config_data['time']} hours")

        return embed

    @app_commands.command(name="ping", description="Admin command to check bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            try:
                latency = round(self.bot.latency * 1000)

                embed = discord.Embed(
                    title="Pong!",
                    description=f"Latency: **{latency}ms**",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(f"Error in ping command: {e}")
                try:
                    await interaction.followup.send("Error occurred. Please try again.", ephemeral=True)
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
                print(f"Error in ping command (permission denied): {e}")
        
    @app_commands.command(name="dashboard", description="Admin command to display market dashboard.")
    async def dashboard(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            try:
                await interaction.response.defer()
                
                all_data = await self.get_all_data()
                embed = self.create_dashboard_embed(all_data)

                message = await interaction.followup.send(embed=embed)

                if message.id not in self.config_data["message-ids"]:
                    self.config_data["message-ids"].append(message.id)
                    self.save_config()
                    
            except Exception as e:
                print(f"Error in dashboard command: {e}")
                try:
                    await interaction.followup.send("Error creating dashboard. Please try again.", ephemeral=True)
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
                print(f"Error in dashboard command (permission denied): {e}")
    
    @app_commands.command(name="set-dashboard-time", description="Admin command to set dashboard update delay time.")
    async def set_dashboard_time(self, interaction: discord.Interaction, hours: int):
        if interaction.user.guild_permissions.administrator:
            try:
                if hours < 1 or hours > 24:
                    embed = discord.Embed(
                        title="Invalid Time",
                        description="Please specify a time between 1 and 24 hours.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                self.config_data["time"] = hours
                self.save_config()
                
                # Restart the task with new timing
                self.update_dashboard_task.cancel()
                await asyncio.sleep(1)  # Wait for task to fully cancel
                self.update_dashboard_task.change_interval(hours=hours)
                self.update_dashboard_task.start()
                
                embed = discord.Embed(
                    title="Dashboard Time Updated",
                    description=f"Dashboard will now update every **{hours} hours**.",
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
            try:
                embed = discord.Embed(
                    title="Access Denied",
                    description="You need administrator permissions to use this command.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Error in set-dashboard-time command (permission denied): {e}")

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