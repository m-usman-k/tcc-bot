import discord, os, sys
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Check if required environment variables are set
if not BOT_TOKEN:
    print("❌ Error: BOT_TOKEN not found in environment variables!")
    print("Please create a .env file with your Discord bot token.")
    sys.exit(1)

# Create bot instance with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    print(f"✅ LOGGED IN AS: {bot.user.name}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Load the Dashboard cog
    try:
        await bot.load_extension("cogs.Dashboard")
        print(f"✅ EXTENSION LOADED: Dashboard")
    except Exception as e:
        print(f"❌ ERROR LOADING EXTENSION: {e}")
        return

    # Sync slash commands
    try:
        await bot.tree.sync()
        print(f"✅ COMMANDS SYNCED")
    except Exception as e:
        print(f"❌ ERROR SYNCING COMMANDS: {e}")

    print(f"🚀 Bot is ready! Use /dashboard to create a market dashboard.")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    
    print(f"❌ Command error: {error}")
    
    embed = discord.Embed(
        title="❌ Error",
        description=f"An error occurred: {str(error)}",
        color=discord.Color.red()
    )
    
    try:
        await ctx.send(embed=embed)
    except:
        pass  # If we can't send the error message, just ignore it

@bot.event
async def on_guild_join(guild):
    """Called when the bot joins a new guild"""
    print(f"🎉 Joined new guild: {guild.name} (ID: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    """Called when the bot leaves a guild"""
    print(f"👋 Left guild: {guild.name} (ID: {guild.id})")

if __name__ == "__main__":
    print("🚀 Starting TCC Bot...")
    print("📋 Make sure you have:")
    print("   - Created a .env file with BOT_TOKEN and COINDESK_API_KEY")
    print("   - Invited the bot to your Discord server")
    print("   - Given the bot proper permissions")
    print("-" * 50)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid bot token! Please check your BOT_TOKEN in the .env file.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)