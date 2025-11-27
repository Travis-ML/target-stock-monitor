#!/usr/bin/env python3
"""
Target Stock Monitor - Research Implementation
Based on HAR file analysis

Educational and security research purposes only.
"""

import requests
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, List
import hashlib
import sys
import os

# Fix Windows Unicode encoding issues
if sys.platform == 'win32':
    # Set stdout/stderr to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    # Set console to UTF-8 mode
    os.system('chcp 65001 >nul 2>&1')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('target_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TargetAPI:
    """Target.com Redsky API client"""
    
    # API key extracted from HAR file (public/frontend key)
    API_KEY = "3216aea83629371e321a7cc95a7814998tj83e69"
    BASE_URL = "https://redsky.target.com/redsky_aggregations/v1/web"
    
    AVAILABILITY_STATUS = {
        'IN_STOCK': 'Available for purchase',
        'OUT_OF_STOCK': 'Not available',
        'PRE_ORDER_SELLABLE': 'Pre-order available',
        'PRE_ORDER_UNSELLABLE': 'Pre-order not yet available',
        'UNAVAILABLE': 'Product discontinued',
        'UNKNOWN': 'Status unknown'
    }
    
    @staticmethod
    def generate_product_url(tcin: str, title: str = None) -> str:
        """
        Generate the proper Target product URL with slug
        
        Target URLs have format: /p/{slug}/-/A-{tcin}
        The slug is derived from the product title
        """
        if title:
            # Clean and convert title to URL slug
            import re
            import unicodedata
            
            # Decode HTML entities (e.g., &#233; -> é)
            import html
            title = html.unescape(title)
            
            # Convert to lowercase
            slug = title.lower()
            
            # Normalize Unicode characters to ASCII equivalents
            # NFD decomposes é to e + ́, then we filter out combining marks
            slug = unicodedata.normalize('NFD', slug)
            slug = ''.join(char for char in slug if unicodedata.category(char) != 'Mn')
            
            # Remove special characters except spaces and dashes
            slug = re.sub(r'[^\w\s-]', '', slug)
            
            # Replace spaces with dashes
            slug = re.sub(r'\s+', '-', slug)
            
            # Remove multiple consecutive dashes
            slug = re.sub(r'-+', '-', slug)
            
            # Remove leading/trailing dashes
            slug = slug.strip('-')
            
            # Truncate if too long (Target usually keeps it reasonable)
            if len(slug) > 100:
                slug = slug[:100].rsplit('-', 1)[0]  # Cut at word boundary
            
            return f"https://www.target.com/p/{slug}/-/A-{tcin}"
        else:
            # Fallback: simple URL without slug (still works but not as clean)
            return f"https://www.target.com/p/-/A-{tcin}"
    
    def __init__(self, store_id: str = "874", zip_code: str = "32738"):
        self.store_id = store_id
        self.zip_code = zip_code
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create session with realistic browser headers"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/142.0.0.0 Safari/537.36 '
                '(Research/Educational)'
            ),
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.target.com',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'DNT': '1'
        })
        return session
    
    def get_product_info(self, tcin: str) -> Optional[Dict]:
        """Get basic product information"""
        endpoint = f"{self.BASE_URL}/pdp_client_v1"
        
        params = {
            'key': self.API_KEY,
            'tcin': tcin,
            'store_id': self.store_id,
            'pricing_store_id': self.store_id,
            'channel': 'WEB',
            'page': f'/p/A-{tcin}',
            'is_bot': 'false'
        }
        
        self.session.headers['Referer'] = f'https://www.target.com/p/A-{tcin}'
        
        try:
            response = self.session.get(endpoint, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_product_info(data)
            elif response.status_code == 429:
                logger.warning("Rate limited on product info request")
                return None
            else:
                logger.error(f"Product info request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching product info: {e}")
            return None
    
    def _parse_product_info(self, data: Dict) -> Dict:
        """Parse basic product information"""
        try:
            product = data['data']['product']
            item = product.get('item', {})
            price = product.get('price', {})
            
            product_desc = item.get('product_description', {})
            title = product_desc.get('title', 'Unknown')
            tcin = product.get('tcin')
            
            return {
                'tcin': tcin,
                'title': title,
                'current_price': price.get('current_retail', 0),
                'reg_price': price.get('reg_retail', 0),
                'url': self.generate_product_url(tcin, title)
            }
        except Exception as e:
            logger.error(f"Error parsing product info: {e}")
            return None
    
    def get_fulfillment(self, tcin: str) -> Optional[Dict]:
        """Get product fulfillment and availability data"""
        endpoint = f"{self.BASE_URL}/product_fulfillment_and_variation_hierarchy_v1"
        
        params = {
            'key': self.API_KEY,
            'tcin': tcin,
            'store_id': self.store_id,
            'zip': self.zip_code,
            'channel': 'WEB',
            'page': f'/p/A-{tcin}',
            'is_bot': 'false'
        }
        
        self.session.headers['Referer'] = f'https://www.target.com/p/A-{tcin}'
        
        try:
            response = self.session.get(endpoint, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_fulfillment(data)
            elif response.status_code == 429:
                logger.warning("Rate limited on fulfillment request")
                return None
            else:
                logger.error(f"Fulfillment request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching fulfillment: {e}")
            return None
    
    def _parse_fulfillment(self, data: Dict) -> Dict:
        """Parse fulfillment data for availability"""
        try:
            product = data['data']['product']
            fulfillment = product.get('fulfillment', {})
            
            # Shipping options
            shipping = fulfillment.get('shipping_options', {})
            shipping_status = shipping.get('availability_status', 'UNKNOWN')
            shipping_qty = shipping.get('available_to_promise_quantity', 0)
            
            # Store options
            stores = fulfillment.get('store_options', [])
            store_pickup_status = 'UNKNOWN'
            store_qty = 0
            
            if stores:
                first_store = stores[0]
                order_pickup = first_store.get('order_pickup', {})
                store_pickup_status = order_pickup.get('availability_status', 'UNKNOWN')
                store_qty = first_store.get('location_available_to_promise_quantity', 0)
            
            # Determine overall stock status
            in_stock = shipping_status in ['IN_STOCK', 'PRE_ORDER_SELLABLE']
            sold_out = fulfillment.get('sold_out', True)
            
            return {
                'tcin': product.get('tcin'),
                'shipping_status': shipping_status,
                'shipping_status_desc': self.AVAILABILITY_STATUS.get(
                    shipping_status, 'Unknown'
                ),
                'shipping_quantity': float(shipping_qty),
                'store_pickup_status': store_pickup_status,
                'store_quantity': float(store_qty),
                'in_stock': in_stock,
                'sold_out': sold_out,
                'store_id': self.store_id
            }
            
        except Exception as e:
            logger.error(f"Error parsing fulfillment: {e}")
            return None


class TargetStockMonitor:
    """Monitor Target product availability with change detection"""
    
    def __init__(self, tcin: str, store_id: str = "874", zip_code: str = "32738"):
        self.tcin = tcin
        self.api = TargetAPI(store_id, zip_code)
        self.previous_status = None
        self.check_count = 0
        self.change_count = 0
        self.product_info = None
    
    def initialize(self):
        """Initialize by fetching product info"""
        logger.info(f"Initializing monitor for TCIN: {self.tcin}")
        self.product_info = self.api.get_product_info(self.tcin)
        
        if self.product_info:
            logger.info(f"Product: {self.product_info['title']}")
            logger.info(f"Price: ${self.product_info['current_price']}")
        else:
            logger.warning("Could not fetch product information")
    
    def check(self) -> Optional[Dict]:
        """Perform a single availability check"""
        fulfillment = self.api.get_fulfillment(self.tcin)
        
        if not fulfillment:
            return None
        
        self.check_count += 1
        
        # Combine with product info
        result = {
            'timestamp': datetime.now().isoformat(),
            'check_number': self.check_count,
            **fulfillment
        }
        
        if self.product_info:
            result.update({
                'title': self.product_info['title'],
                'price': self.product_info['current_price'],
                'url': self.product_info['url']
            })
        
        return result
    
    def monitor(self, check_interval: int = 120, duration: Optional[int] = None, 
                callback=None, discord_webhook: Optional[str] = None):
        """Monitor with change detection and alerts"""
        self.initialize()
        
        # Setup Discord webhook if provided
        discord = None
        if discord_webhook:
            discord = DiscordWebhook(discord_webhook)
            logger.info("Discord webhook configured")
            discord.send_simple_message(
                f"🎯 Started monitoring TCIN: {self.tcin}\n"
                f"Product: {self.product_info['title'] if self.product_info else 'Unknown'}\n"
                f"Check Interval: {check_interval}s"
            )
        
        start_time = time.time()
        
        logger.info("=" * 70)
        logger.info("Starting Target Stock Monitor")
        logger.info(f"TCIN: {self.tcin}")
        logger.info(f"Check Interval: {check_interval}s")
        logger.info(f"Duration: {duration if duration else 'Infinite'}")
        if discord:
            logger.info(f"Discord Alerts: Enabled")
        logger.info("=" * 70)
        
        try:
            while True:
                # Check duration limit
                if duration and (time.time() - start_time) > duration:
                    logger.info("Duration limit reached")
                    break
                
                # Perform check
                result = self.check()
                
                if result:
                    current_status = result['shipping_status']
                    
                    # Detect status changes
                    if current_status != self.previous_status:
                        self.change_count += 1
                        logger.warning(
                            f"⚠️  STATUS CHANGE #{self.change_count}: "
                            f"{self.previous_status} → {current_status}"
                        )
                        
                        if result['in_stock']:
                            logger.warning("🚨 PRODUCT IN STOCK! 🚨")
                            
                            if callback:
                                callback(result, discord)
                            elif discord:
                                discord.send_stock_alert(result)
                        
                        self.previous_status = current_status
                    else:
                        logger.info(
                            f"Check #{self.check_count}: {current_status} | "
                            f"Qty: {result['shipping_quantity']}"
                        )
                
                # Wait before next check
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user")
        
        finally:
            self._print_summary(time.time() - start_time)
    
    def _print_summary(self, elapsed: float):
        """Print monitoring session summary"""
        logger.info("\n" + "=" * 70)
        logger.info("MONITORING SUMMARY")
        logger.info("=" * 70)
        logger.info(f"TCIN: {self.tcin}")
        if self.product_info:
            logger.info(f"Product: {self.product_info['title']}")
        logger.info(f"Total Checks: {self.check_count}")
        logger.info(f"Status Changes: {self.change_count}")
        logger.info(f"Duration: {elapsed:.0f}s ({elapsed/60:.1f}m)")
        if self.check_count > 0:
            logger.info(f"Avg Interval: {elapsed/self.check_count:.1f}s")
        logger.info("=" * 70)


class DiscordWebhook:
    """Discord webhook notification system"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_stock_alert(self, result: Dict) -> bool:
        """Send stock alert to Discord"""
        
        # Determine embed color based on status
        if result['in_stock']:
            color = 0x00FF00  # Green for in stock
            status_emoji = "🟢"
        elif result['shipping_status'] == 'PRE_ORDER_SELLABLE':
            color = 0xFFFF00  # Yellow for pre-order
            status_emoji = "🟡"
        else:
            color = 0xFF0000  # Red for out of stock
            status_emoji = "🔴"
        
        # Build product URL (use stored URL if available, otherwise generate)
        product_url = result.get('url')
        if not product_url:
            product_url = TargetAPI.generate_product_url(
                result['tcin'], 
                result.get('title')
            )
        
        # Build the embed
        embed = {
            "title": f"{status_emoji} Stock Alert: {result.get('title', 'Unknown Product')}",
            "url": product_url,
            "description": f"**Status Changed!** Product availability has been updated.",
            "color": color,
            "fields": [
                {
                    "name": "🏷️ Status",
                    "value": result['shipping_status_desc'],
                    "inline": True
                },
                {
                    "name": "💰 Price",
                    "value": f"${result.get('price', 0):.2f}",
                    "inline": True
                },
                {
                    "name": "📦 Shipping Quantity",
                    "value": f"{int(result['shipping_quantity'])} available",
                    "inline": True
                },
                {
                    "name": "🏪 Store Pickup",
                    "value": result['store_pickup_status'],
                    "inline": True
                },
                {
                    "name": "🔢 TCIN",
                    "value": result['tcin'],
                    "inline": True
                },
                {
                    "name": "⏰ Timestamp",
                    "value": result['timestamp'],
                    "inline": True
                }
            ],
            "footer": {
                "text": "Target Stock Monitor | Educational Research"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Add thumbnail if product is in stock
        if result['in_stock']:
            embed["thumbnail"] = {
                "url": "https://corporate.target.com/_media/TargetCorp/about/logo_a.png"
            }
        
        payload = {
            "content": f"🚨 **STOCK ALERT!** 🚨" if result['in_stock'] else None,
            "embeds": [embed],
            "username": "Target Stock Monitor"
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info("✅ Discord notification sent successfully")
                return True
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False
    
    def send_simple_message(self, message: str) -> bool:
        """Send a simple text message to Discord"""
        payload = {
            "content": message,
            "username": "Target Stock Monitor"
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code in [200, 204]
        except:
            return False


def alert_callback(result: Dict, discord_webhook: Optional[DiscordWebhook] = None):
    """Alert callback with optional Discord integration"""
    
    # Get proper URL
    product_url = result.get('url')
    if not product_url:
        product_url = TargetAPI.generate_product_url(
            result['tcin'], 
            result.get('title')
        )
    
    print("\n" + "=" * 70)
    print("🚨 STOCK ALERT! 🚨")
    print("=" * 70)
    print(f"Product: {result.get('title', 'Unknown')}")
    print(f"TCIN: {result['tcin']}")
    print(f"Status: {result['shipping_status_desc']}")
    print(f"Price: ${result.get('price', 0)}")
    print(f"Shipping Qty: {result['shipping_quantity']}")
    print(f"Store Pickup: {result['store_pickup_status']}")
    print(f"URL: {product_url}")
    print("=" * 70 + "\n")
    
    # Send Discord notification if webhook provided
    if discord_webhook:
        discord_webhook.send_stock_alert(result)


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(
        description='Target Stock Monitor - Educational Research Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor a product (Charizard Pokemon)
  python target_monitor.py 94681790
  
  # Monitor with Discord alerts
  python target_monitor.py 94681790 --discord-webhook "https://discord.com/api/webhooks/..."
  
  # Test Discord webhook
  python target_monitor.py 94681790 --test-discord --discord-webhook "https://discord.com/api/webhooks/..."
  
  # Monitor with custom interval and duration
  python target_monitor.py 94681790 --interval 180 --duration 3600
  
  # Monitor with specific store and Discord alerts
  python target_monitor.py 94681790 --store 874 --zip 32738 --discord-webhook "https://discord.com/api/webhooks/..."
  
  # Quick availability check
  python target_monitor.py 94681790 --check-once

For research purposes only. Use responsibly.
        """
    )
    
    parser.add_argument('tcin', help='Target product TCIN (from URL: /p/A-TCIN)')
    parser.add_argument(
        '--interval',
        type=int,
        default=120,
        help='Check interval in seconds (default: 120). Lower values may trigger rate limiting.'
    )
    parser.add_argument(
        '--duration',
        type=int,
        help='Total monitoring duration in seconds'
    )
    parser.add_argument(
        '--store',
        default='874',
        help='Target store ID (default: 874)'
    )
    parser.add_argument(
        '--zip',
        default='32738',
        help='ZIP code (default: 32738)'
    )
    parser.add_argument(
        '--check-once',
        action='store_true',
        help='Check availability once and exit'
    )
    parser.add_argument(
        '--discord-webhook',
        help='Discord webhook URL for notifications'
    )
    parser.add_argument(
        '--test-discord',
        action='store_true',
        help='Test Discord webhook and exit'
    )
    
    args = parser.parse_args()
    
    # Test Discord webhook if requested
    if args.test_discord:
        if not args.discord_webhook:
            print("❌ Error: --discord-webhook required for testing")
            return
        
        print("Testing Discord webhook...")
        discord = DiscordWebhook(args.discord_webhook)
        
        test_result = {
            'tcin': '94681790',
            'title': 'Test Product - Pokémon TCG',
            'timestamp': datetime.now().isoformat(),
            'shipping_status': 'IN_STOCK',
            'shipping_status_desc': 'Available for purchase',
            'shipping_quantity': 10.0,
            'store_pickup_status': 'AVAILABLE',
            'price': 129.99,
            'in_stock': True
        }
        
        success = discord.send_stock_alert(test_result)
        if success:
            print("✅ Discord webhook test successful!")
        else:
            print("❌ Discord webhook test failed")
        return
    
    # Validate interval (warning only, no minimum enforced)
    if args.interval < 30 and not args.check_once:
        logger.warning(f"⚠️  Interval of {args.interval}s is very aggressive and may trigger rate limiting or blocking")
    
    # Create monitor
    monitor = TargetStockMonitor(
        tcin=args.tcin,
        store_id=args.store,
        zip_code=args.zip
    )
    
    # Single check mode
    if args.check_once:
        monitor.initialize()
        result = monitor.check()
        
        if result:
            print("\n" + "=" * 70)
            print("Product Availability Check")
            print("=" * 70)
            print(f"Product: {result.get('title', 'Unknown')}")
            print(f"TCIN: {result['tcin']}")
            print(f"Price: ${result.get('price', 0)}")
            print(f"Shipping Status: {result['shipping_status_desc']}")
            print(f"Shipping Quantity: {result['shipping_quantity']}")
            print(f"Store Pickup: {result['store_pickup_status']}")
            print(f"Store Quantity: {result['store_quantity']}")
            print(f"In Stock: {'✓ Yes' if result['in_stock'] else '✗ No'}")
            print(f"Sold Out: {'✓ Yes' if result['sold_out'] else '✗ No'}")
            print("=" * 70)
        else:
            print("Failed to check availability")
        
        return
    
    # Continuous monitoring mode
    monitor.monitor(
        check_interval=args.interval,
        duration=args.duration,
        callback=alert_callback,
        discord_webhook=args.discord_webhook
    )


if __name__ == '__main__':
    main()
