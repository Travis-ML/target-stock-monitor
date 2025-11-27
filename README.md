# 🎯 Target Stock Monitor

A Python-based stock monitoring tool for Target.com products with Discord webhook integration. Built through reverse-engineering Target's Redsky API using HAR file analysis.

> ⚠️ **Disclaimer**: This tool is for educational and security research purposes only. Use responsibly and respect Target's terms of service.

## Features

- **Real-time Stock Monitoring** — Continuously monitors product availability with configurable check intervals
- **Discord Webhook Integration** — Rich embed notifications with color-coded alerts (green/yellow/red)
- **Change Detection** — Only alerts when stock status actually changes, reducing notification noise
- **Dual Fulfillment Tracking** — Monitors both shipping availability and store pickup status
- **Intelligent URL Generation** — Creates proper Target product URLs with SEO-friendly slugs
- **Rate Limit Awareness** — Built-in warnings and recommendations for sustainable polling
- **Cross-Platform Support** — Windows Unicode handling for proper emoji display in terminals
- **Comprehensive Logging** — File and console logging with session summaries

## How It Works

### API Discovery via HAR File Analysis

The API key and endpoints were discovered through browser HAR (HTTP Archive) file analysis (The script will not work until you obtain the API Key and set it in the TargetAPI class in the script):

1. **Open Developer Tools** in your browser (F12)
2. **Navigate to the Network tab** and enable "Preserve log"
3. **Visit any Target product page** and interact with it
4. **Export the HAR file** (Right-click → Save all as HAR)
5. **Analyze the requests** — Look for the `x-api-key` value in the header section of the JSON HAR file.

From the HAR file, we extracted:
- **API Base URL**: `https://redsky.target.com/redsky_aggregations/v1/web`
- **API Key**: A public/frontend key passed as a query parameter
- **Required Headers**: Browser-like headers to avoid bot detection
- **Endpoint Patterns**: `/pdp_client_v1` for product info, `/product_fulfillment_and_variation_hierarchy_v1` for stock data

### API Endpoints Used

| Endpoint                                          | Purpose                                             |
|---------------------------------------------------|-----------------------------------------------------|
| `/pdp_client_v1`                                  | Product details (title, price, description)         |
| `/product_fulfillment_and_variation_hierarchy_v1` | Stock availability, quantities, fulfillment options |

## Installation

```bash
# Clone the repository
git clone https://github.com/Travis-ML/target-stock-monitor.git
cd target-stock-monitor

# Install dependencies
pip install requests
```

## Usage

### Quick Availability Check

Check a product's current stock status once and exit:

```bash
python target-monitor.py 94681790 --check-once
```

### Continuous Monitoring

Monitor a product with default 2-minute intervals:

```bash
python target-monitor.py 94681790
```

### Monitor with Discord Alerts

```bash
python target-monitor.py 94681790 --discord-webhook "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
```

### Custom Configuration

```bash
python target-monitor.py 94681790 \
    --interval 180 \
    --duration 3600 \
    --store 874 \
    --zip 12345 \
    --discord-webhook "https://discord.com/api/webhooks/..."
```

### Test Discord Webhook

Verify your webhook is working before starting a monitoring session:

```bash
python target-monitor.py 94681790 --test-discord --discord-webhook "https://discord.com/api/webhooks/..."
```

## Command Line Arguments

| Argument           | Default    | Description                                   |
|--------------------|------------|-----------------------------------------------|
| `tcin`             | (required) | Target product ID (found in URL: `/p/A-TCIN`) |
| `--interval`       | 120        | Check interval in seconds                     |
| `--duration`       | ∞          | Total monitoring duration in seconds          |
| `--store`          | 874        | Target store ID for local inventory           |
| `--zip`            | 12345      | ZIP code for shipping availability            |
| `--check-once`     | —          | Single check mode, exit after one check       |
| `--discord-webhook`| —          | Discord webhook URL for notifications         |
| `--test-discord`   | —          | Test webhook and exit                         |

## Check Frequency Considerations

The default check interval is **120 seconds (2 minutes)**. Here's why:

| Interval  | Checks/Hour | Risk Level | Use Case              |
|-----------|-------------|------------|-----------------------|
| 30s       | 120         | ⚠️ High    | Brief monitoring only |
| 60s       | 60          | ⚠️ Moderate| Active restocks       |
| 120s      | 30          | ✅ Low     | Recommended default   |
| 180s      | 20          | ✅ Very Low| Extended monitoring   |
| 300s      | 12          | ✅ Minimal | Long-term tracking    |

**Recommendations:**
- Intervals below 30 seconds will trigger warnings and may result in rate limiting (HTTP 429)
- For extended monitoring sessions, use 180s+ intervals
- The script logs rate limit responses and handles them gracefully

## Discord Integration

### Webhook Setup

1. Open your Discord server settings
2. Navigate to **Integrations → Webhooks**
3. Click **New Webhook** and configure the channel
4. Copy the webhook URL

### Notification Features

The Discord notifications include:

- **Color-coded embeds**:
  - 🟢 Green — In stock
  - 🟡 Yellow — Pre-order available  
  - 🔴 Red — Out of stock
- **Product information**: Title, price, TCIN
- **Availability details**: Shipping quantity, store pickup status
- **Direct link**: Clickable URL to the product page
- **Timestamps**: When the status changed

### Example Discord Alert

```
🚨 STOCK ALERT! 🚨

🟢 Stock Alert: Pokémon TCG: Charizard Premium Collection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ Status: Available for purchase
💰 Price: $129.99
📦 Shipping Quantity: 10 available
🏪 Store Pickup: AVAILABLE
🔢 TCIN: 94681790
⏰ Timestamp: 2024-01-15T10:30:45
```

## Stock Status Codes

| Status                 | Description                 |
|------------------------|-----------------------------|
| `IN_STOCK`             | Available for purchase      |
| `OUT_OF_STOCK`         | Currently unavailable       |
| `PRE_ORDER_SELLABLE`.  | Pre-order available         |
| `PRE_ORDER_UNSELLABLE` | Pre-order not yet available |
| `UNAVAILABLE`          | Product discontinued        |

## Finding Product TCINs

The TCIN (Target Common Item Number) is the unique product identifier. Find it in the product URL:

```
https://www.target.com/p/pokemon-tcg-charizard/-/A-94681790
                                                    ^^^^^^^^
                                                    This is the TCIN
```

## Project Structure

```
target-stock-monitor/
├── target-monitor.py      # Main monitoring script
├── target_monitor.log     # Log file (auto-generated)
└── README.md              # This file
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Target Stock Monitor                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  TargetAPI   │───▶│ StockMonitor │───▶│   Discord    │   │
│  │              │    │              │    │   Webhook    │   │
│  │ • Product    │    │ • Change     │    │              │   │
│  │   Info       │    │   Detection  │    │ • Rich       │   │
│  │ • Fulfillment│    │ • Logging    │    │   Embeds     │   │
│  │   Status     │    │ • Callbacks  │    │ • Alerts     │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Target Redsky API                       │   │
│  │        redsky.target.com/redsky_aggregations         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Sample Output

```
2024-01-15 10:30:00 [INFO] ======================================================================
2024-01-15 10:30:00 [INFO] Starting Target Stock Monitor
2024-01-15 10:30:00 [INFO] TCIN: 94681790
2024-01-15 10:30:00 [INFO] Check Interval: 120s
2024-01-15 10:30:00 [INFO] Duration: Infinite
2024-01-15 10:30:00 [INFO] Discord Alerts: Enabled
2024-01-15 10:30:00 [INFO] ======================================================================
2024-01-15 10:30:01 [INFO] Product: Pokémon TCG: Charizard Premium Collection
2024-01-15 10:30:01 [INFO] Price: $129.99
2024-01-15 10:30:02 [INFO] Check #1: OUT_OF_STOCK | Qty: 0.0
2024-01-15 10:32:02 [INFO] Check #2: OUT_OF_STOCK | Qty: 0.0
2024-01-15 10:34:02 [WARNING] ⚠️  STATUS CHANGE #1: OUT_OF_STOCK → IN_STOCK
2024-01-15 10:34:02 [WARNING] 🚨 PRODUCT IN STOCK! 🚨
2024-01-15 10:34:03 [INFO] ✅ Discord notification sent successfully
```

## Technical Details

### Request Headers

The script mimics a real browser to avoid detection:

```python
{
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
    'Accept': 'application/json',
    'Origin': 'https://www.target.com',
    'sec-ch-ua': '"Chromium";v="142"',
    'sec-fetch-mode': 'cors',
    ...
}
```

### URL Slug Generation

Product URLs are generated with proper slugs for cleaner links:

```
Input:  "Pokémon TCG: Charizard Premium Collection"
Output: https://www.target.com/p/pokemon-tcg-charizard-premium-collection/-/A-94681790
```

The slug generator handles:
- Unicode normalization (é → e)
- HTML entity decoding
- Special character removal
- Length truncation at word boundaries

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

MIT License — See [LICENSE](LICENSE) for details.

## Acknowledgments

- Built through HAR file analysis and reverse engineering
- Discord webhook integration for real-time alerts
- Inspired by the need to catch limited product restocks

---

**Remember**: This tool is for educational purposes. Be respectful of Target's infrastructure and use reasonable check intervals.
