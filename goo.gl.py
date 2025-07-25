#!/usr/bin/env python3
"""
Modern goo.gl URL Reader Script
Handles Google's shutdown warning page and extracts real URLs
"""

import requests
import itertools
import string
import re
import csv
import logging
import argparse
import time
import html
from typing import Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('goo_gl_scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GoogleShortenerScanner:
    def __init__(self, output_file: str = 'goo.gl_urls.csv', delay: float = 1.0, skip_404: bool = False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.output_file = Path(output_file)
        self.delay = delay
        self.skip_404 = skip_404
        self.processed_count = 0
        self.found_count = 0
        
        # Set up cookies to bypass the warning (simulate "Don't show this again")
        self.session.cookies.set('googol_warning_dismissed', 'true', domain='.goo.gl')
        
        # Initialize CSV file with headers
        self._initialize_csv()
    
    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not self.output_file.exists():
            with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['short_url', 'destination_url', 'status', 'timestamp'])
    
    def _find_last_processed_url(self, length: int) -> Optional[str]:
        """Find the last processed URL from the CSV file to resume from"""
        if not self.output_file.exists():
            return None
        
        try:
            with open(self.output_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                last_url = None
                for row in reader:
                    if len(row) >= 1:
                        short_url = row[0]
                        # Extract the suffix from the URL
                        if '/goo.gl/' in short_url:
                            suffix = short_url.split('/goo.gl/')[-1]
                            # Only consider URLs of the same length we're scanning
                            if len(suffix) == length:
                                last_url = suffix
                
                if last_url:
                    logger.info("Found last processed URL suffix (length %d): %s", length, last_url)
                    return last_url
                else:
                    logger.info("No previous URLs found for length %d", length)
                
        except Exception as e:
            logger.warning("Could not read existing CSV file: %s", e)
        
        return None
    
    def _extract_redirect_from_warning_page(self, html_content: str) -> Optional[str]:
        """Extract the actual redirect URL from Google's warning page"""
        # Look for the redirect URL in various possible locations
        patterns = [
            # JSON-style redirect URLs
            r'"redirect_url":"([^"]+)"',
            r'"url":"([^"]+)"',
            r'"target":"([^"]+)"',
            
            # Query parameter style
            r'redirect_url=([^&\s\'"]+)',
            r'url=([^&\s\'"]+)',
            r'continue=([^&\s\'"]+)',
            
            # HTML links and buttons - more specific
            r'href="(https?://[^"]+)"[^>]*>Continue',
            r'href="(https?://[^"]+)"[^>]*>\s*Continue',
            r'href="(https?://[^"]+)"[^>]*class="[^"]*continue[^"]*"',
            
            # JavaScript redirects
            r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
            
            # Meta refresh
            r'content="0;url=([^"]+)"',
            r'content="\d+;\s*url=([^"]+)"',
        ]
        
        def is_valid_redirect_url(url: str) -> bool:
            """Check if URL is a valid redirect destination"""
            if not url or len(url) < 10:
                return False
            
            # Skip Google's own services and resources
            skip_domains = [
                'google.com', 'goo.gl', 'googleapis.com', 'googleusercontent.com',
                'gstatic.com', 'googletagmanager.com', 'googlesyndication.com',
                'doubleclick.net', 'googlebots.com'
            ]
            
            url_lower = url.lower()
            for domain in skip_domains:
                if domain in url_lower:
                    return False
            
            # Must be a proper HTTP/HTTPS URL
            if not url.startswith(('http://', 'https://')):
                return False
                
            return True
        
        # Try specific patterns first
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = match.strip()
                # Decode URL if necessary
                url = url.replace('\\u003d', '=').replace('\\u0026', '&')
                url = url.replace('%3D', '=').replace('%26', '&')
                # Decode HTML entities
                url = html.unescape(url)
                
                if is_valid_redirect_url(url):
                    logger.debug("Found redirect URL in warning page: %s (pattern: %s)", url, pattern)
                    return url
        
        # Fallback: Look for any external URL in the HTML, but be more selective
        all_urls = re.findall(r'https?://[^\s<>"\']+', html_content, re.IGNORECASE)
        valid_urls = []
        
        for url in all_urls:
            if is_valid_redirect_url(url):
                # Clean up the URL
                url = html.unescape(url)
                valid_urls.append(url)
        
        if valid_urls:
            # Return the first valid URL found
            url = valid_urls[0]
            logger.debug("Found fallback redirect URL: %s", url)
            return url
        
        # Debug: Log some info about what we found
        logger.debug("Could not extract URL. HTML content length: %d", len(html_content))
        logger.debug("Found %d total URLs, %d valid ones", len(all_urls), len(valid_urls))
        
        # Save HTML for manual inspection in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            debug_filename = f"debug_html_{int(time.time())}.html"
            with open(debug_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.debug("Saved HTML content to %s for inspection", debug_filename)
            
            # Also log the first few URLs we found for debugging
            if all_urls:
                logger.debug("Sample URLs found: %s", all_urls[:5])
        
        return None
    
    def resolve_goo_gl_url(self, short_url: str) -> Tuple[str, str]:
        """
        Resolve a goo.gl URL, handling the warning page
        Returns: (destination_url, status)
        """
        try:
            # First request - might get warning page or direct redirect
            response = self.session.get(short_url, allow_redirects=False, timeout=10)
            
            if response.status_code == 200:
                # We got the warning page
                html_content = response.text
                
                # Check if it's the "Dynamic Link Not Found" page
                if "Dynamic Link Not Found" in html_content or "not found" in html_content.lower():
                    return "NOT_FOUND", "link_not_found"
                
                # Check if it's the warning page
                if "This link will no longer work" in html_content or "goo.gl links will no longer function" in html_content:
                    # Extract the real redirect URL from the warning page
                    redirect_url = self._extract_redirect_from_warning_page(html_content)
                    if redirect_url:
                        return redirect_url, "resolved_from_warning"
                    else:
                        logger.warning("Could not extract redirect from warning page for %s", short_url)
                        return "WARNING_PAGE_NO_EXTRACT", "warning_page_parse_failed"
                
                # If we get here, it's some other 200 response
                return response.url, "direct_200"
            
            elif response.status_code in [301, 302, 303, 307, 308]:
                # Direct redirect without warning page
                redirect_url = response.headers.get('Location', '')
                if redirect_url:
                    return redirect_url, "direct_redirect"
                else:
                    return "NO_LOCATION_HEADER", "redirect_without_location"
            
            elif response.status_code == 404:
                return "NOT_FOUND", "404_error"
            
            else:
                return f"HTTP_{response.status_code}", f"http_error_{response.status_code}"
                
        except requests.exceptions.Timeout:
            return "TIMEOUT", "request_timeout"
        except requests.exceptions.ConnectionError:
            return "CONNECTION_ERROR", "connection_failed"
        except requests.exceptions.RequestException as e:
            return f"REQUEST_ERROR: {str(e)}", "request_exception"
        except (ValueError, KeyError) as e:
            logger.error("Unexpected error processing %s: %s", short_url, e)
            return f"UNEXPECTED_ERROR: {str(e)}", "unexpected_error"
    
    def save_result(self, short_url: str, destination_url: str, status: str):
        """Save result to CSV file"""
        # Skip 404 results if flag is set
        if self.skip_404 and status in ['404_error', 'link_not_found']:
            return
        
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([short_url, destination_url, status, time.strftime('%Y-%m-%d %H:%M:%S')])
    
    def scan_url_combinations(self, length: int = 6, start_from: Optional[str] = None):
        """Scan goo.gl URL combinations"""
        chars = string.ascii_letters + string.digits
        logger.info("Starting scan with %d-character combinations", length)
        logger.info("Total possible combinations: %s", f"{len(chars)**length:,}")
        logger.info("Character order: %s", chars[:20] + "..." + chars[-10:])
        
        # Auto-resume: find where we left off if start_from is not specified
        if start_from is None:
            start_from = self._find_last_processed_url(length)
            if start_from:
                logger.info("Auto-resuming from: %s", start_from)
                # Move to the next URL after the last processed one
                start_from = self._get_next_url_suffix(start_from, chars, length)
                if start_from:
                    logger.info("Starting from next URL: %s", start_from)
                else:
                    logger.info("Reached end of combinations, starting from beginning")
                    start_from = None
        
        if self.skip_404:
            logger.info("Skipping 404 results (--no-404 flag enabled)")
        
        # Convert start_from to index for more reliable comparison
        start_index = None
        if start_from:
            start_index = self._url_suffix_to_index(start_from, chars, length)
            logger.info("Starting from index: %s (URL: %s)", start_index, start_from)
        
        found_start = start_from is None  # If no start_from, we start immediately
        
        try:
            current_index = 0
            for combo in itertools.product(chars, repeat=length):
                url_suffix = ''.join(combo)
                
                # Skip to start position - use exact string matching for reliability
                if not found_start:
                    if url_suffix == start_from:
                        found_start = True
                        logger.info("Found starting position: %s at index %d", url_suffix, current_index)
                    else:
                        current_index += 1
                        continue
                
                short_url = f"https://goo.gl/{url_suffix}"
                
                # Resolve the URL
                destination_url, status = self.resolve_goo_gl_url(short_url)
                
                # Save result (respects skip_404 flag)
                self.save_result(short_url, destination_url, status)
                
                # Update counters
                self.processed_count += 1
                if status not in ['link_not_found', '404_error']:
                    self.found_count += 1
                    logger.info("+ Found: %s -> %s (%s)", short_url, destination_url, status)
                
                # Progress logging (show all processed, even 404s)
                if self.processed_count % 100 == 0:
                    logger.info("Processed: %s | Found: %s | Current: %s (index: %s)", 
                               f"{self.processed_count:,}", f"{self.found_count:,}", url_suffix, current_index)
                
                current_index += 1
                
                # Rate limiting
                time.sleep(self.delay)
                
        except KeyboardInterrupt:
            logger.info("Scan interrupted. Processed: %s | Found: %s", 
                       f"{self.processed_count:,}", f"{self.found_count:,}")
            logger.info("Resume with --start-from %s (index: %s)", url_suffix, current_index)
    
    def _get_next_url_suffix(self, current_suffix: str, chars: str, length: int) -> Optional[str]:
        """Get the next URL suffix in sequence"""
        if len(current_suffix) != length:
            return None
        
        # Convert suffix to list for easier manipulation
        suffix_list = list(current_suffix)
        
        # Increment like a base-N number (right to left)
        carry = 1
        for i in range(length - 1, -1, -1):
            if carry == 0:
                break
            
            try:
                current_index = chars.index(suffix_list[i])
                new_index = current_index + carry
                
                if new_index < len(chars):
                    suffix_list[i] = chars[new_index]
                    carry = 0
                else:
                    suffix_list[i] = chars[0]
                    carry = 1
            except ValueError:
                # Character not found in chars, skip
                return None
        
        # If we still have carry, we've reached the end
        if carry == 1:
            return None
        
        return ''.join(suffix_list)
    
    def _url_suffix_to_index(self, suffix: str, chars: str, length: int) -> int:
        """Convert URL suffix to its index in the iteration sequence"""
        if len(suffix) != length:
            return 0
        
        index = 0
        base = len(chars)
        
        for i, char in enumerate(suffix):
            try:
                char_index = chars.index(char)
                # Calculate position using base conversion
                index += char_index * (base ** (length - 1 - i))
            except ValueError:
                # Character not found, return 0
                return 0
        
        return index

def main():
    parser = argparse.ArgumentParser(description='Modern goo.gl URL Scanner')
    parser.add_argument('--length', type=int, default=6, help='URL suffix length (default: 6)')
    parser.add_argument('--output', default='goo.gl_urls.csv', help='Output CSV file')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds')
    parser.add_argument('--start-from', help='Resume from specific URL suffix (overrides auto-resume)')
    parser.add_argument('--test-url', help='Test a specific goo.gl URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-404', action='store_true', help='Skip recording 404/not found results')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    scanner = GoogleShortenerScanner(args.output, args.delay, args.no_404)
    
    if args.test_url:
        # Test a specific URL
        logger.info("Testing URL: %s", args.test_url)
        destination, status = scanner.resolve_goo_gl_url(args.test_url)
        logger.info("Result: %s (Status: %s)", destination, status)
        scanner.save_result(args.test_url, destination, status)
    else:
        # Start scanning
        scanner.scan_url_combinations(args.length, args.start_from)

if __name__ == "__main__":
    main()
