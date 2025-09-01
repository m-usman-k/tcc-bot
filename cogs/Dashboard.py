import aiohttp
import discord, json, os, asyncio
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

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
        self.update_task = None
        self.start_auto_update()

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

    def start_auto_update(self):
        """Start the auto-update task for dashboard messages"""
        if self.update_task:
            self.update_task.cancel()
        self.update_task = self.bot.loop.create_task(self.auto_update_dashboard())

    async def auto_update_dashboard(self):
        """Automatically update dashboard messages every specified hours"""
        while True:
            try:
                await asyncio.sleep(self.config_data["time"] * 3600)  # Convert hours to seconds
                await self.update_all_dashboards()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in auto update: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    async def update_all_dashboards(self):
        """Update all stored dashboard messages"""
        if not self.config_data["message-ids"]:
            return

        all_data = await self.get_all_data()
        
        for message_id in self.config_data["message-ids"][:]:  # Copy list to avoid modification during iteration
            try:
                # Try to find the message in all guilds
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
                        # Remove invalid message IDs
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

    async def get_all_data(self):
        """Fetch all market data from CoinDesk API"""
        all_data = {}
        
        async with aiohttp.ClientSession() as session:
            # Get total market cap
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/overview/v1/latest/marketcap/all/tick",
                    params={"api_key": COINDESK_API_KEY},
                    headers={"Content-Type": "application/json; charset=UTF-8"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_value = float(data["Data"]["VALUE"])
                        total_trillions = total_value / 1_000_000_000_000
                        all_data["TOTAL2"] = f"${total_trillions:.2f}T"
                    else:
                        all_data["TOTAL2"] = "Error"
            except Exception as e:
                print(f"Error fetching total market cap: {e}")
                all_data["TOTAL2"] = "Error"

            # Get BTC price
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/v1/price/BTC-USD",
                    params={"api_key": COINDESK_API_KEY}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data["BTC_USD"] = f"${float(data['bpi']['USD']['rate_float']):,.2f}"
                    else:
                        all_data["BTC_USD"] = "Error"
            except Exception as e:
                print(f"Error fetching BTC price: {e}")
                all_data["BTC_USD"] = "Error"

            # Get ETH price
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/v1/price/ETH-USD",
                    params={"api_key": COINDESK_API_KEY}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data["ETH_USD"] = f"${float(data['bpi']['USD']['rate_float']):,.2f}"
                    else:
                        all_data["ETH_USD"] = "Error"
            except Exception as e:
                print(f"Error fetching ETH price: {e}")
                all_data["ETH_USD"] = "Error"

            # Get BTC dominance
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/overview/v1/latest/dominance/BTC/tick",
                    params={"api_key": COINDESK_API_KEY}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data["BTC_DOMINANCE"] = f"{float(data['Data']['VALUE']):.1f}%"
                    else:
                        all_data["BTC_DOMINANCE"] = "Error"
            except Exception as e:
                print(f"Error fetching BTC dominance: {e}")
                all_data["BTC_DOMINANCE"] = "Error"

            # Get USDT dominance
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/overview/v1/latest/dominance/USDT/tick",
                    params={"api_key": COINDESK_API_KEY}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data["USDT_DOMINANCE"] = f"{float(data['Data']['VALUE']):.1f}%"
                    else:
                        all_data["USDT_DOMINANCE"] = "Error"
            except Exception as e:
                print(f"Error fetching USDT dominance: {e}")
                all_data["USDT_DOMINANCE"] = "Error"

            # Get ETH/BTC ratio
            try:
                async with session.get(
                    f"{COINDESK_BASE_URL}/v1/price/ETH-BTC",
                    params={"api_key": COINDESK_API_KEY}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data["ETH_BTC_RATIO"] = f"{float(data['bpi']['BTC']['rate_float']):.4f}"
                    else:
                        all_data["ETH_BTC_RATIO"] = "Error"
            except Exception as e:
                print(f"Error fetching ETH/BTC ratio: {e}")
                all_data["ETH_BTC_RATIO"] = "Error"

        return all_data

    def create_dashboard_embed(self, all_data):
        """Create a formatted dashboard embed with market data"""
        embed = discord.Embed(
            title="🪙 Crypto Market Dashboard",
            description="Real-time cryptocurrency market overview",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        # Prices section
        embed.add_field(
            name="💰 Prices",
            value=f"**BTC/USD:** {all_data.get('BTC_USD', 'Loading...')}\n"
                  f"**ETH/USD:** {all_data.get('ETH_USD', 'Loading...')}",
            inline=True
        )

        # Market metrics
        embed.add_field(
            name="📊 Market Metrics",
            value=f"**BTC.D:** {all_data.get('BTC_DOMINANCE', 'Loading...')}\n"
                  f"**USDT.D:** {all_data.get('USDT_DOMINANCE', 'Loading...')}\n"
                  f"**ETH/BTC:** {all_data.get('ETH_BTC_RATIO', 'Loading...')}",
            inline=True
        )

        # Total market cap
        embed.add_field(
            name="🌐 Total Market Cap",
            value=f"**TOTAL2:** {all_data.get('TOTAL2', 'Loading...')}",
            inline=False
        )

        embed.set_footer(text=f"Updates every {self.config_data['time']} hours • Last updated")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/123456789/123456789/crypto-icon.png")

        return embed

    @app_commands.command(name="ping", description="Admin command to check bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            latency = round(self.bot.latency * 1000)

            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Latency: **{latency}ms**",
                color=discord.Color.green()
            )
            return await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="dashboard", description="Admin command to display market dashboard.")
    async def dashboard(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            await interaction.response.defer()
            
            all_data = await self.get_all_data()
            embed = self.create_dashboard_embed(all_data)

            message = await interaction.followup.send(embed=embed)

            if message.id not in self.config_data["message-ids"]:
                self.config_data["message-ids"].append(message.id)
                self.save_config()
            
        else:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="set-dashboard-time", description="Admin command to set dashboard update delay time.")
    async def set_dashboard_time(self, interaction: discord.Interaction, hours: int):
        if interaction.user.guild_permissions.administrator:
            if hours < 1 or hours > 24:
                embed = discord.Embed(
                    title="❌ Invalid Time",
                    description="Please specify a time between 1 and 24 hours.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            self.config_data["time"] = hours
            self.save_config()
            self.start_auto_update()  # Restart the auto-update task with new timing
            
            embed = discord.Embed(
                title="✅ Dashboard Time Updated",
                description=f"Dashboard will now update every **{hours} hours**.",
                color=discord.Color.green()
            )
            return await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="force-update", description="Admin command to force update all dashboard messages.")
    async def force_update(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            await interaction.response.defer()
            
            await self.update_all_dashboards()
            
            embed = discord.Embed(
                title="✅ Force Update Complete",
                description="All dashboard messages have been updated with the latest data.",
                color=discord.Color.green()
            )
            return await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear-dashboards", description="Admin command to clear all stored dashboard messages.")
    async def clear_dashboards(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            count = len(self.config_data["message-ids"])
            self.config_data["message-ids"] = []
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Dashboards Cleared",
                description=f"Cleared **{count}** stored dashboard messages.",
                color=discord.Color.green()
            )
            return await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))