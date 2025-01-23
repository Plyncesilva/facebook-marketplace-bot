import httpx
import re
import json
import logging
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from datetime import datetime
import os
import random

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

import time

def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def get_facebook_marketplace_data(query, debug=False):
    logger = logging.getLogger(__name__)
    
    # Request parameters
    params = {
        'maxPrice': '400',
        'daysSinceListed': '30',
        'sortBy': 'creation_time_descend',
        'query': query,
        'exact': 'false'
    }
    
    logger.info(f"Request parameters: {params}")

    # Generate current GMT epoch time in milliseconds
    current_utc_ms = int(time.time() * 1000)
    
    # Create presence cookie with current time
    presence_data = {
        "t3": [],
        "utc3": current_utc_ms,
        "v": 1
    }
    presence_cookie = f'C{json.dumps(presence_data).replace(" ", "")}'
    presence_encoded = urlencode({'': presence_cookie})[1:]  # Remove leading =
    
    logger.info(f"Presence cookie: {presence_cookie}")
    logger.info(f"Presence encoded: {presence_encoded}")

    # Headers updated for HTTP/2
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cookie': f'datr=dZ0JZ2QPh2NaJL_AkPmULUyd; sb=9Z0JZzeJKS6vKCMGzu-3HhrS; oo=v1; c_user=61551519951356; dpr=1.0909090909090908; xs=44%3Ae2L8PqAvdtnyuQ%3A2%3A1729987598%3A-1%3A-1%3AMNEUiaCZ8F_2-Q%3AAcX7ipadF5KA5k5awzRDf-tZPEi2en9RPuF-F6Az6Wo; b_user=61569826361938; wd=1220x912; fr=0BvFSnh6KN5FtmEQE.AWUjPEvm5_PvNC4X2fRkj9ASr-o.BngpPk..AAA.0.0.BnisQu.AWUd5uHHj1Y; presence={presence_encoded}',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none', 
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
        'Te': 'trailers'
    }

    url = f'https://www.facebook.com/marketplace/copenhagen/search?{urlencode(params)}'
    logger.debug(f"Request URL: {url}")

    try:
        logger.debug("Making HTTP/2 request...")
        # Use httpx with HTTP/2 support
        with httpx.Client(http2=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"HTTP version: {response.http_version}")
            # Add this inside the try block after the response
            logger.debug("Response headers:")
            for key, value in response.headers.items():
                logger.debug(f"{key}: {value}")

            # Update the response body logging to show first 1000 characters
            logger.debug(f"First 1000 chars of response: {response.text[:1000]}")

        # Parse HTML
        logger.debug("Parsing HTML response...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all script tags
        scripts = soup.find_all('script')
        logger.debug(f"Found {len(scripts)} script tags")
        
        # Pattern to find objects containing "marketplace_search"
        node_pattern = r'\{"marketplace_search"[^}]*(?:}[^}]*)*}'
        
        nodes = []
        for i, script in enumerate(scripts):
            if script.string:
                logger.debug(f"Processing script {i+1}/{len(scripts)}")
                # Find all matches of node objects in the script content
                matches = list(re.finditer(node_pattern, script.string))
                logger.debug(f"Found {len(matches)} matches in script {i+1}")
                if matches:
                    # Print the first match
                    logger.debug(f"First match in script {i+1}: {matches[0].group()}")
                for match in matches:
                    try:
                        # Clean the JSON string by extracting just the node data
                        json_str = match.group()
                        # Find the innermost object that contains 'node'
                        node_start = json_str.rfind('{"marketplace_search"')
                        if node_start != -1:
                            # Find the matching closing brace
                            brace_count = 0
                            node_end = node_start
                            for i in range(node_start, len(json_str)):
                                if json_str[i] == '{':
                                    brace_count += 1
                                elif json_str[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        node_end = i + 1
                                        break
                            
                            clean_json = json_str[node_start:node_end]
                            node_data = json.loads(clean_json)
                            if 'marketplace_search' in node_data:
                                nodes.append(node_data['marketplace_search']['feed_units']['edges'])
                                logger.debug(f"Found valid node data in script {i+1}")
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.debug(f"Failed to parse JSON in script {i+1}: {str(e)}")
                        continue

        logger.info(f"Total nodes found: {len(nodes)}")
        # Create a list to store all listings
        all_listings = []
        logger.debug("Starting to process node_sets")
        
        # First collect all listings
        for i, node_set in enumerate(nodes):
            logger.debug(f"Processing node_set {i+1}/{len(nodes)}")
            for j, inner_node in enumerate(node_set):
                try:
                    logger.debug(f"Processing inner_node {j+1} in node_set {i+1}")
                    listing = inner_node['node']['listing']
                    logger.debug(f"Got listing data: {json.dumps(listing, indent=2)}")
                    
                    listing_data = {
                        'story_key': inner_node['node']['story_key'],
                        'listing_id': listing['id'],
                        'price': listing['listing_price']['formatted_amount'],
                        'title': listing['marketplace_listing_title'],
                        'seller_name': listing['marketplace_listing_seller']['name'],
                        'seller_id': listing['marketplace_listing_seller']['id']
                    }
                    logger.debug(f"Created listing_data: {json.dumps(listing_data, indent=2)}")
                    all_listings.append(listing_data)
                except KeyError as e:
                    logger.error(f"KeyError processing listing: {e}")
                    logger.debug(f"Problem node content: {json.dumps(inner_node, indent=2)}")
                except Exception as e:
                    logger.error(f"Unexpected error processing listing: {e}")
        
        logger.debug(f"Total listings collected: {len(all_listings)}")
        
        # Create data directory if it doesn't exist
        listings_file = os.path.join('./data/listings.json')
        logger.debug(f"Using listings file path: {listings_file}")

        # Load existing listings from file
        if os.path.exists(listings_file):
            with open(listings_file, 'r') as file:
                existing_data = json.load(file)
                existing_listings = existing_data.get('listings', [])
                logger.info(f"Loaded {len(existing_listings)} existing listings from file")
        else:
            existing_listings = []
            logger.info("No existing listings file found, starting with an empty list")

        # Combine new listings with existing ones
        existing_listing_ids = {listing['listing_id'] for listing in existing_listings}
        new_listings = [listing for listing in all_listings if listing['listing_id'] not in existing_listing_ids]

        for i, listing_data in enumerate(new_listings, 1):
            logger.info("="*50)
            logger.info(f"Listing {i}")
            logger.info("="*50)
            logger.info("Listing Details:")
            logger.info("-"*30)
            logger.info(f"Story Key:     {listing_data['story_key']}")
            logger.info(f"Listing ID:    {listing_data['listing_id']}")
            logger.info(f"Price:         {listing_data['price']}")
            logger.info(f"Title:         {listing_data['title']}")
            logger.info("Seller Information:")
            logger.info("-"*30)
            logger.info(f"Name:          {listing_data['seller_name']}")
            logger.info(f"ID:            {listing_data['seller_id']}")
            logger.info("")

        # Log total new listings
        logger.info(f"Total new listings found: {len(new_listings)}")

        # Save all new listings to file if there are any new listings
        if new_listings:
            with open(listings_file, 'w') as file:
                existing_listings.extend(new_listings)
                data = {
                    'listings': existing_listings,
                    'last_updated': datetime.now().isoformat()
                }
                json.dump(data, file, indent=4)
                logger.info(f"Saved {len(new_listings)} new listings")

        return new_listings

    except httpx.RequestError as e:
        logger.error(f"Error making request: {e}")
    except Exception as e:
        logger.error(f"Error processing data: {e}")

from selenium.webdriver.common.by import By


def process_listings(driver, listings):
    for listing_data in listings:
        listing_url = f"https://www.facebook.com/marketplace/item/{listing_data['listing_id']}"
        driver.get(listing_url)
        time.sleep(5)

        # click message seller button
        try:
            logging.debug("Trying to click message seller button")
            message_seller_button = driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[2]/div/div[1]")
            logging.debug("Found message seller button -> ", message_seller_button)
            if message_seller_button:
                logging.debug("Message seller button found")
                message_seller_button.click()
                logging.debug("Clicked 'Message Seller' button")
                time.sleep(5)
            else:
                logging.error("'Message Seller' button not found")
            
            text_area = driver.find_element(By.XPATH, '/html/body/div[1]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div[3]/div[3]/div/label/div/div/textarea')
            
            if text_area:
                logging.debug("Found text area")
            else:
                logging.error("Text area not found")

            for _ in range(18):
                text_area.send_keys(Keys.BACK_SPACE)

            first_name = listing_data['seller_name'].split(' ')[0]
            message = f"Hi {first_name}! Is this still available?"
            text_area.send_keys(message)
            logging.debug(f"Entered message: {message}")
            time.sleep(5)

            send_button = driver.find_element(By.XPATH, '/html/body/div[1]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div[4]/div/div[2]/div/div[2]/div')
            if send_button:
                send_button.click()
                logging.debug("Clicked 'Send' button")
                time.sleep(10)
            else:
                logging.error("'Send' button not found")

        except Exception as e:
            logging.error(f"Error sending message to seller: {e}")

def driver_setup():
    options = Options()
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def login_to_facebook(driver, email, password):
    # Add your Facebook login credentials here
    driver.get('https://www.facebook.com/')

    # Find and click the "Decline optional cookies" button
    try:
        decline_button = driver.find_element(By.XPATH, '//*[@id="facebook"]/body/div[3]/div[2]/div/div/div/div/div[3]/div[2]/div/div[1]')
        if decline_button:
            logging.debug("'Decline optional cookies' button found")
            decline_button.click()
            logging.debug("Clicked 'Decline optional cookies' button")
            time.sleep(3)  # Adjust sleep time as needed for the action to complete
        else:
            logging.info("'Decline optional cookies' button not found")

        # Input email
        email_input = driver.find_element(By.XPATH, '//*[@id="email"]')
        email_input.send_keys(email)
        logging.debug("Entered email")

        # Input password
        password_input = driver.find_element(By.XPATH, '//*[@id="pass"]')
        password_input.send_keys(password)
        logging.debug("Entered password")

        # Click on the log in button
        login_button = driver.find_element(By.XPATH, '/html/body/div[1]/div[1]/div[1]/div/div/div/div[2]/div/div[1]/form/div[2]/button')
        if login_button:
            login_button.click()
            logging.debug("Clicked log in button")
            # Create a visually distinct message box
            print("\n" + "═"*80)
            print("║" + " "*78 + "║")
            print("║" + "🔴 IMPORTANT SETUP INSTRUCTIONS".center(77) + "║")
            print("║" + " "*78 + "║")
            print("║" + "1. Make sure the browser window is in FULL SCREEN mode".center(78) + "║")
            print("║" + "2. Complete the CAPTCHA if shown".center(78) + "║")
            print("║" + "3. Close any popups that appear".center(78) + "║")
            print("║" + "4. Press ENTER when ready to continue".center(78) + "║")
            print("║" + " "*78 + "║")
            print("═"*80 + "\n")
            logging.info("Waiting for user input...")
            input()  # Wait for user to press ENTER
        else:
            logging.error("Login button not found")

    except Exception as e:
        logging.error(f"Error logging in: {e}")

def create_data_directory():
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logging.info(f"Created data directory at {data_dir}")
    return data_dir

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Facebook Marketplace Bot",
        epilog="Example usage:\n"
               "  python bot.py --query 'bicycle' --email 'user@example.com' --password 'yourpass'\n"
               "  python bot.py --query 'laptop' --email 'user@example.com' --password 'yourpass' --debug",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--query', type=str, required=True, help='Search term for marketplace')
    parser.add_argument('--email', type=str, required=True, help='Facebook login email')
    parser.add_argument('--password', type=str, required=True, help='Facebook login password')
    parser.add_argument('--max-price', type=str, default='400', help='Maximum price (default: 400)')
    parser.add_argument('--days-since-listed', type=str, default='30', help='Days since listed (default: 30)')
    parser.add_argument('--sort-by', type=str, default='creation_time_descend', help='Sort order (default: creation_time_descend)')
    parser.add_argument('--exact', type=str, default='false', help='Exact match (default: false)')
    args = parser.parse_args()

    setup_logging(args.debug)
    logging.info("Logging setup complete")

    create_data_directory()
    logging.info("Data directory created")

    # Must happen only at startup
    driver = driver_setup()
    logging.info("Driver setup complete")
    login_to_facebook(driver=driver, email=args.email, password=args.password)
    logging.info("Login complete")

    try:
        logging.info("Starting main loop...")
        while True:
            logging.info("Checking Facebook Marketplace for new listings...")
            new_listings = get_facebook_marketplace_data(args.query, args.debug)
            logging.info(f"Found {len(new_listings)} new listings")
            if new_listings:
                logging.info("Processing new listings...")
                process_listings(driver=driver, listings=new_listings)
            
            # Random wait between 5 and 15 minutes
            wait_time = random.randint(300, 900)
            logging.info(f"Waiting {wait_time/60:.1f} minutes until next check...")
            
            # Countdown timer
            start_time = time.time()
            while (time.time() - start_time) < wait_time:
                remaining = wait_time - int(time.time() - start_time)
                mins, secs = divmod(remaining, 60)
                print(f"\033[1;32mTime remaining: {mins:02d}:{secs:02d}\033[0m", end='\r')
                time.sleep(1)
            print() # Clear the line
            
    except KeyboardInterrupt:
        logging.info("Received CTRL+C, shutting down...")

    driver.quit()