# Facebook Marketplace Bot

Be the first to message sellers on Facebook Marketplace listings! This bot automatically monitors listings and sends messages to sellers for items matching your search criteria.

## Features

- Monitors Facebook Marketplace listings in real-time
- Automatically messages sellers for new listings
- Customizable search parameters (price, listing age, etc.)
- Saves listing data to prevent duplicate messages
- Random delays between checks to avoid detection

## Prerequisites

- Python 3.8 or higher
- Google Chrome browser
- Facebook account

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Chrome WebDriver setup is handled automatically by `webdriver_manager`

## Usage

Basic usage:
```bash
python bot.py --query "bicycle" --email "your_email@example.com" --password "your_password"
```

Advanced usage:
```bash
python bot.py --query "laptop" --email "your_email@example.com" --password "your_password" --max-price "500" --days-since-listed "7" --debug
```

### Arguments

- `--query`: Search term (required)
- `--email`: Facebook login email (required)
- `--password`: Facebook login password (required)
- `--max-price`: Maximum price (default: 400)
- `--days-since-listed`: Maximum listing age in days (default: 30)
- `--debug`: Enable debug logging
- `--sort-by`: Sort order (default: creation_time_descend)
- `--exact`: Enable exact match search (default: false)

## Important Notes

- When first running the bot, ensure you:
    1. Run the browser in full screen mode
    2. Complete any CAPTCHA if shown
    3. Close any Facebook popups
    4. Press ENTER when ready

## Legal Disclaimer

This bot is for educational purposes only. Use at your own risk and responsibility. Make sure to comply with Facebook's terms of service.

