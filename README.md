# TCC Bot - Crypto Market Dashboard

A Discord bot that provides real-time cryptocurrency market data using the CoinDesk API. The bot displays market information including prices, dominance metrics, and total market capitalization in an auto-updating dashboard.

## Features

- **Real-time Market Data**: Fetches live cryptocurrency prices and market metrics
- **Auto-updating Dashboard**: Automatically updates dashboard messages at configurable intervals
- **Multiple Data Points**: BTC/USD, ETH/USD, SOL/USD, BTC dominance, USDT dominance, ETH/BTC ratio, total market cap, open interest, and funding rates
- **Admin Commands**: Full control over dashboard settings and updates
- **Error Handling**: Robust error handling for API failures and network issues

## Commands

### Admin Commands (Require Administrator permissions)

- `/ping` - Check bot latency
- `/dashboard` - Display current market dashboard
- `/set-dashboard-time <hours>` - Set dashboard update interval (1-24 hours)
- `/force-update` - Manually update all dashboard messages
- `/clear-dashboards` - Clear all stored dashboard messages

## Setup Instructions

### 1. Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- CoinDesk API Key

### 2. Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Environment Setup

Create a `.env` file in the root directory with your API keys:

```env
BOT_TOKEN=your_discord_bot_token_here
COINDESK_API_KEY=your_coindesk_api_key_here
```

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the bot token and add it to your `.env` file
5. Enable the following bot permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History
   - Manage Messages (for editing dashboard messages)

### 5. Invite Bot to Server

Use this URL format to invite your bot (replace `YOUR_BOT_CLIENT_ID` with your actual client ID):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=2147483648&scope=bot%20applications.commands
```

### 6. Test Setup (Optional)

Before running the bot, you can test your configuration:

```bash
# Linux/Mac
./test_setup.py

# Windows
python test_setup.py
```

### 7. Run the Bot

**Option 1: Direct execution**
```bash
python main.py
```

**Option 2: Using startup scripts**
```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

## Configuration

The bot automatically creates a `data/config.json` file to store:
- Dashboard update interval (default: 12 hours)
- Message IDs for auto-updating dashboards

## API Endpoints Used

The bot uses the following CoinDesk API endpoints:

- `/overview/v1/latest/marketcap/all/tick` - Total market capitalization
- `/v1/price/BTC-USD` - Bitcoin price in USD
- `/v1/price/ETH-USD` - Ethereum price in USD
- `/v1/price/SOL-USD` - Solana price in USD
- `/overview/v1/latest/dominance/BTC/tick` - Bitcoin dominance percentage
- `/overview/v1/latest/dominance/USDT/tick` - USDT dominance percentage
- `/v1/price/ETH-BTC` - ETH/BTC ratio
- `/overview/v1/latest/openinterest/BTC/tick` - Bitcoin open interest
- `/overview/v1/latest/openinterest/ETH/tick` - Ethereum open interest
- `/overview/v1/latest/fundingrate/BTC/tick` - Bitcoin funding rate
- `/overview/v1/latest/fundingrate/ETH/tick` - Ethereum funding rate

## Troubleshooting

### Common Issues

1. **Bot not responding to commands**: Ensure the bot has proper permissions and slash commands are enabled
2. **API errors**: Check your CoinDesk API key is valid and has proper permissions
3. **Dashboard not updating**: Verify the bot has "Manage Messages" permission to edit dashboard messages

### Logs

The bot prints status messages to the console:
- Bot login confirmation
- Extension loading status
- Command sync status
- API error messages

## License

This project is open source and available under the MIT License.
