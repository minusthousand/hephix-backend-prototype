import logging
import re
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from mcp.server.fastmcp import FastMCP

# Try to use BeautifulSoup if available, otherwise fall back to regex
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Try to use Playwright for JavaScript-rendered pages
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Initialize FastMCP server
mcp = FastMCP("depo-store")

# Set up logging to stderr (important for stdio servers)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEPO_BASE_URL = "https://online.depo.lv"
DEPO_SEARCH_URL = f"{DEPO_BASE_URL}/search"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def make_request_with_browser(url: str, wait_for_selector: str | None = None, wait_timeout: int = 10000) -> str | None:
    """Make a request using a headless browser to handle JavaScript-rendered content."""
    if not HAS_PLAYWRIGHT:
        logger.warning("Playwright not available, falling back to regular HTTP request")
        return None
    
    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            # Navigate to URL
            logger.info(f"Loading page with browser: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=wait_timeout)
                except:
                    logger.warning(f"Selector {wait_for_selector} not found, continuing anyway")
            
            # Wait a bit more for dynamic content
            await page.wait_for_timeout(2000)
            
            # Get page content
            content = await page.content()
            
            await browser.close()
            return content
    except Exception as e:
        logger.error(f"Browser request failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def make_request(url: str, params: dict[str, Any] | None = None) -> httpx.Response | None:
    """Make a request to online.depo.lv with proper headers and error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "lv,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": DEPO_BASE_URL,
    }
    
    # httpx automatically handles decompression, but let's be explicit
    async with httpx.AsyncClient(
        follow_redirects=True, 
        timeout=30.0,
        headers=headers
    ) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            # Log response info for debugging
            logger.info(f"Response status: {response.status_code}, Content-Type: {response.headers.get('content-type', 'unknown')}")
            logger.info(f"Response length: {len(response.content)} bytes, Text length: {len(response.text)} chars")
            
            # Check if response is HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type and len(response.text) < 500:
                logger.warning(f"Response may not be HTML or is very short. Content-Type: {content_type}")
            
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            try:
                logger.error(f"Response preview: {e.response.text[:500]}")
            except:
                logger.error(f"Could not read response text")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


def extract_product_links(html_content: str) -> list[str]:
    """Extract product links from search results page."""
    product_links = []
    
    # First, try regex to find product links (works even if HTML is malformed/compressed)
    # Look for /product/ followed by digits
    product_pattern = r'href=["\']([^"\']*\/product\/\d+[^"\']*)["\']'
    matches = re.finditer(product_pattern, html_content, re.IGNORECASE)
    for match in matches:
        href = match.group(1)
        # Clean up the href - remove any query parameters or fragments for now
        href = href.split('?')[0].split('#')[0]
        if href.startswith('/product/'):
            full_url = urljoin(DEPO_BASE_URL, href)
            if full_url not in product_links:
                product_links.append(full_url)
        elif DEPO_BASE_URL in href and '/product/' in href:
            if href not in product_links:
                product_links.append(href)
    
    # Also try BeautifulSoup if available (more robust for well-formed HTML)
    if HAS_BS4 and len(product_links) == 0:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all links that point to product pages
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                # Match product URL pattern: /product/123456
                if href and '/product/' in href and re.search(r'/product/\d+', href):
                    # Extract the product path
                    href = href.split('?')[0].split('#')[0]  # Remove query params
                    if href.startswith('/product/'):
                        full_url = urljoin(DEPO_BASE_URL, href)
                        if full_url not in product_links:
                            product_links.append(full_url)
                    elif DEPO_BASE_URL in href and '/product/' in href:
                        if href not in product_links:
                            product_links.append(href)
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}, using regex results")
    
    logger.info(f"Extracted {len(product_links)} product links")
    if product_links:
        logger.info(f"Sample links: {product_links[:3]}")
    
    return product_links


async def fetch_product_details(product_url: str) -> dict[str, Any] | None:
    """Fetch detailed product information from a product page."""
    # Try browser first (for JavaScript-rendered content)
    html_content = None
    if HAS_PLAYWRIGHT:
        logger.info(f"Fetching product details with browser: {product_url}")
        html_content = await make_request_with_browser(
            product_url,
            wait_for_selector='h1, [class*="product"], [class*="price"]',  # Wait for product content
            wait_timeout=10000
        )
    
    # Fallback to regular HTTP request
    if not html_content:
        logger.info(f"Falling back to HTTP request for: {product_url}")
        response = await make_request(product_url)
        
        if not response:
            logger.error(f"Failed to fetch product page: {product_url}")
            return None
        
        html_content = response.text
    
    if HAS_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        product = {'url': product_url}
        
        # Try to extract product name from various locations
        name = None
        
        # Try h1 first (common for product titles)
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
        
        # Try meta tags
        if not name:
            meta_title = soup.find('meta', property='og:title')
            if meta_title:
                name = meta_title.get('content', '').strip()
        
        if not name:
            title_tag = soup.find('title')
            if title_tag:
                name = title_tag.get_text(strip=True)
                # Remove common suffixes
                name = name.replace(' - DEPO Online', '').replace(' | DEPO Online', '').strip()
        
        # Try common product name selectors
        if not name:
            name_selectors = [
                '.product-name', '.product-title', '.name', '.title',
                '[class*="product-name"]', '[class*="product-title"]',
                '[data-product-name]', '[data-name]'
            ]
            for sel in name_selectors:
                elem = soup.select_one(sel)
                if elem:
                    name = elem.get_text(strip=True)
                    if name:
                        break
        
        if name:
            product['name'] = name
        
        # Try to extract price
        price = None
        
        # Try data attributes
        price_elem = soup.find(attrs={'data-price': True})
        if price_elem:
            price = price_elem.get('data-price')
        
        # Try common price selectors
        if not price:
            price_selectors = [
                '.price', '.product-price', '.price-current', '.price-value',
                '.current-price', '[class*="price"]', '[class*="cost"]',
                '[data-price]', '[data-product-price]'
            ]
            for sel in price_selectors:
                price_elem = soup.select_one(sel)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Extract numeric price
                    price_match = re.search(r'([\d,]+\.?\d*)', price_text.replace(',', '.').replace(' ', ''))
                    if price_match:
                        price = f"€{price_match.group(1)}"
                        break
        
        # Try to find price in text content
        if not price:
            body_text = soup.get_text()
            price_match = re.search(r'€\s*([\d,]+\.?\d*)|([\d,]+\.?\d*)\s*€', body_text)
            if price_match:
                price_val = price_match.group(1) or price_match.group(2)
                if price_val:
                    price = f"€{price_val.replace(',', '.')}"
        
        product['price'] = price or "Price not available"
        
        # Try to extract description
        description = None
        desc_selectors = [
            '.product-description', '.description', '.product-details',
            '[class*="description"]', '[class*="details"]'
        ]
        for sel in desc_selectors:
            desc_elem = soup.select_one(sel)
            if desc_elem:
                description = desc_elem.get_text(strip=True)
                if description and len(description) > 10:
                    break
        
        if description:
            product['description'] = description[:300] + ('...' if len(description) > 300 else '')
        
        # Check availability
        availability_text = soup.get_text().lower()
        if any(word in availability_text for word in ['pieejams', 'ir noliktavā', 'in stock']):
            product['availability'] = 'Available'
        elif any(word in availability_text for word in ['nav pieejams', 'nav noliktavā', 'out of stock']):
            product['availability'] = 'Out of Stock'
        
        if product.get('name'):
            return product
    
    return None


def extract_product_info(html_content: str) -> list[dict[str, Any]]:
    """Extract product information from HTML content."""
    products = []
    
    if HAS_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Strategy 1: Look for JSON-LD structured data (common in e-commerce)
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') == 'ItemList' and 'itemListElement' in data:
                        for item in data['itemListElement']:
                            if isinstance(item, dict) and 'item' in item:
                                item_data = item['item']
                                if isinstance(item_data, dict):
                                    product = {}
                                    if 'name' in item_data:
                                        product['name'] = item_data['name']
                                    if 'url' in item_data:
                                        product['url'] = item_data['url']
                                    if 'offers' in item_data and 'price' in item_data['offers']:
                                        product['price'] = f"€{item_data['offers']['price']}"
                                    if product.get('name'):
                                        products.append(product)
            except:
                pass
        
        # Strategy 2: Try common product container selectors
        product_selectors = [
            '[data-product-id]',
            '[data-product]',
            '.product-item',
            '.product-card',
            '.product-tile',
            '.product',
            '[class*="product-item"]',
            '[class*="product-card"]',
            '[class*="product-tile"]',
            '[class*="catalog-item"]',
            '[class*="item-card"]',
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                product_elements = elements
                logger.info(f"Found {len(elements)} products using selector: {selector}")
                break
        
        # Strategy 3: Look for links that contain product-like paths
        if not product_elements:
            # Find all links that might be products
            all_links = soup.find_all('a', href=True)
            product_links = []
            for link in all_links:
                href = link.get('href', '')
                # Common product URL patterns
                if any(pattern in href.lower() for pattern in ['/product/', '/p/', '/item/', '/catalog/', '/goods/']):
                    # Check if parent looks like a product container
                    parent = link.parent
                    if parent:
                        product_links.append(parent)
            
            if product_links:
                product_elements = product_links[:50]
                logger.info(f"Found {len(product_links)} potential products via link analysis")
        
        # Extract data from found elements
        for element in product_elements[:50]:
            product = {}
            
            # Try to find product name - multiple strategies
            name = None
            
            # Try data attributes first
            name = element.get('data-name') or element.get('data-product-name') or element.get('data-title')
            
            # Try heading elements
            if not name:
                for tag in ['h1', 'h2', 'h3', 'h4']:
                    name_elem = element.find(tag)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name and len(name) > 3:  # Valid product name
                            break
            
            # Try common class names
            if not name:
                name_selectors = [
                    '.product-name', '.name', '.title', '.product-title',
                    '[class*="name"]', '[class*="title"]', '[class*="product-name"]'
                ]
                for sel in name_selectors:
                    name_elem = element.select_one(sel)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name and len(name) > 3:
                            break
            
            # Try link text if it's substantial
            if not name:
                link_elem = element.find('a', href=True)
                if link_elem:
                    link_text = link_elem.get_text(strip=True)
                    if link_text and len(link_text) > 3 and len(link_text) < 200:
                        name = link_text
            
            if name:
                product['name'] = name.strip()
            
            # Try to find product link
            link_elem = element.find('a', href=True)
            if link_elem:
                href = link_elem.get('href', '')
                if href:
                    product['url'] = urljoin(DEPO_BASE_URL, href)
            
            # Try to find price - multiple strategies
            price = None
            
            # Try data attributes
            price = element.get('data-price') or element.get('data-product-price')
            
            # Try common price selectors
            if not price:
                price_selectors = [
                    '.price', '.product-price', '.price-current', '.price-value',
                    '[class*="price"]', '[class*="cost"]', '[data-price]'
                ]
                for sel in price_selectors:
                    price_elem = element.select_one(sel)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        # Extract numeric price
                        price_match = re.search(r'([\d,]+\.?\d*)', price_text.replace(',', '.').replace(' ', ''))
                        if price_match:
                            price = f"€{price_match.group(1)}"
                            break
            
            # Try to find price in text content
            if not price:
                text = element.get_text()
                # Look for price patterns like €X.XX or X.XX€
                price_match = re.search(r'€\s*([\d,]+\.?\d*)|([\d,]+\.?\d*)\s*€', text)
                if price_match:
                    price_val = price_match.group(1) or price_match.group(2)
                    if price_val:
                        price = f"€{price_val.replace(',', '.')}"
            
            if product.get('name'):
                product['price'] = price or "Price not available"
                products.append(product)
    else:
        # Fallback to regex parsing
        # Look for product links with names
        product_pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]{10,200})</a>'
        matches = re.finditer(product_pattern, html_content, re.IGNORECASE)
        
        seen_urls = set()
        for match in matches:
            href = match.group(1)
            text = match.group(2).strip()
            
            # Filter out navigation/header links
            if any(skip in href.lower() for skip in ['/category/', '/catalog/', '/search', '/login', '/register', '/cart', '/account']):
                continue
            
            # Check if it looks like a product URL
            if any(pattern in href.lower() for pattern in ['/product/', '/p/', '/item/', '/goods/']) or '/lv/' in href:
                if href not in seen_urls and len(text) > 5:
                    seen_urls.add(href)
                    # Find price near this link
                    context = html_content[max(0, match.start()-500):match.end()+500]
                    price_match = re.search(r'€\s*([\d,]+\.?\d*)|([\d,]+\.?\d*)\s*€', context)
                    price = f"€{price_match.group(1) or price_match.group(2)}" if price_match else "Price not available"
                    
                    products.append({
                        "name": text,
                        "url": urljoin(DEPO_BASE_URL, href),
                        "price": price,
                    })
    
    # Remove duplicates based on URL
    seen = set()
    unique_products = []
    for product in products:
        url = product.get('url', '')
        if url and url not in seen:
            seen.add(url)
            unique_products.append(product)
        elif not url and product.get('name') not in [p.get('name') for p in unique_products]:
            unique_products.append(product)
    
    return unique_products


@mcp.tool()
async def search_products(query: str, limit: int = 10) -> str:
    """Search for products on online.depo.lv.
    
    Note: This tool accesses public information from online.depo.lv. Please ensure compliance with their terms of service.
    
    Args:
        query: Search query (product name, category, etc.)
        limit: Maximum number of results to return (default: 10, max: 50)
    """
    if not query or not query.strip():
        return "Error: Search query cannot be empty."
    
    limit = min(max(1, limit), 50)  # Clamp between 1 and 50
    
    # Build search URL - use path-based format: /search/query
    query_encoded = quote(query.strip())
    search_url = f"{DEPO_SEARCH_URL}/{query_encoded}"
    
    # Try browser first (for JavaScript-rendered content)
    html_content = None
    if HAS_PLAYWRIGHT:
        logger.info("Attempting to fetch page with headless browser...")
        html_content = await make_request_with_browser(
            search_url,
            wait_for_selector='a[href*="/product/"]',  # Wait for product links
            wait_timeout=15000
        )
    
    # Fallback to regular HTTP request if browser failed or not available
    if not html_content:
        logger.info("Falling back to regular HTTP request...")
        response = await make_request(search_url)
        
        if not response:
            return f"Error: Unable to search online.depo.lv for '{query}'. The website may be temporarily unavailable or there may be a network issue."
        
        html_content = response.text
    
    # Log HTML snippet for debugging
    logger.info(f"HTML response length: {len(html_content)} characters")
    
    # First, extract product links from search results
    product_links = extract_product_links(html_content)
    logger.info(f"Found {len(product_links)} product links")
    
    # If we found product links, fetch details from each product page
    products = []
    if product_links:
        # Limit to avoid too many requests
        product_links = product_links[:limit]
        
        for link in product_links:
            product = await fetch_product_details(link)
            if product:
                products.append(product)
    else:
        # Fallback to old extraction method
        products = extract_product_info(html_content)
    
    logger.info(f"Extracted {len(products)} products with details")
    
    if not products:
        # Check if the page might have products but our parser missed them
        # Look for common indicators that products exist
        has_product_indicators = any([
            'product' in html_content.lower()[:2000],
            'item' in html_content.lower()[:2000],
            'catalog' in html_content.lower()[:2000],
            'search' in html_content.lower()[:2000],
        ])
        
        if has_product_indicators:
            return f"Products may exist for '{query}' but couldn't be extracted automatically.\n\nDirect search URL: {search_url}\n\nPlease visit the link above to see results manually.\n\nNote: The website structure may have changed. You can also try:\n- More specific search terms\n- Using Latvian product names\n- Browsing categories instead"
        else:
            return f"No products found for '{query}' on online.depo.lv.\n\nDirect search URL: {search_url}\n\nTry:\n- A different search term\n- Checking the website directly using the link above\n- Using more general terms or Latvian product names"
    
    # Limit results
    products = products[:limit]
    
    # Format results
    lines = [f"Search results for '{query}' on online.depo.lv:", ""]
    for i, product in enumerate(products, 1):
        lines.append(f"{i}. {product.get('name', 'Unknown Product')}")
        lines.append(f"   Price: {product.get('price', 'Price not available')}")
        if product.get('availability'):
            lines.append(f"   Availability: {product['availability']}")
        if product.get('description'):
            lines.append(f"   Description: {product['description']}")
        if product.get('url'):
            lines.append(f"   URL: {product['url']}")
        if i != len(products):
            lines.append("")
    
    if len(products) == limit:
        lines.extend(["", f"(Showing {limit} results. Visit {search_url} for more results.)"])
    
    lines.extend(["", "Note: For the most up-to-date information, visit online.depo.lv directly."])
    
    return "\n".join(lines).strip()


@mcp.tool()
async def get_product_info(product_url: str) -> str:
    """Get detailed information about a specific product from online.depo.lv.
    
    Args:
        product_url: Full URL of the product page on online.depo.lv
    """
    if not product_url or not product_url.strip():
        return "Error: Product URL cannot be empty."
    
    # Ensure URL is from online.depo.lv
    url = product_url.strip()
    if not url.startswith(DEPO_BASE_URL):
        return f"Error: URL must be from online.depo.lv domain ({DEPO_BASE_URL})"
    
    response = await make_request(url)
    
    if not response:
        return f"Error: Unable to fetch product information from {url}. The page may not exist or the website may be temporarily unavailable."
    
    html_content = response.text
    
    # Extract product details (simplified - would need actual HTML structure inspection)
    # Common elements to extract:
    # - Product name/title
    # - Price
    # - Description
    # - Specifications
    # - Availability
    # - Images
    
    # Try to extract title
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html_content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "Product"
    
    # Try to extract price
    price_match = re.search(r'(?:€|EUR)\s*([\d,]+\.?\d*)', html_content)
    price = f"€{price_match.group(1)}" if price_match else "Price not available"
    
    # Try to extract description
    desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)</div>', html_content, re.IGNORECASE | re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else "Description not available"
    
    result = f"Product Information from online.depo.lv:\n\n"
    result += f"Title: {title}\n"
    result += f"Price: {price}\n"
    result += f"Description: {description[:200]}{'...' if len(description) > 200 else ''}\n"
    result += f"URL: {url}\n"
    result += f"\nNote: For complete details, visit the product page directly."
    
    return result


@mcp.tool()
async def get_categories() -> str:
    """Get available product categories from online.depo.lv.
    
    Returns a list of main product categories available on the website.
    """
    response = await make_request(DEPO_BASE_URL)
    
    if not response:
        return "Error: Unable to fetch categories from online.depo.lv. The website may be temporarily unavailable."
    
    html_content = response.text
    
    # Extract category links (simplified - would need actual HTML structure)
    # Common patterns: navigation menus, category links
    
    # Try to find category links
    category_pattern = r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*category[^"]*"[^>]*>([^<]+)</a>'
    categories = []
    
    matches = re.finditer(category_pattern, html_content, re.IGNORECASE)
    for match in matches:
        url = match.group(1)
        name = match.group(2).strip()
        if name and url:
            categories.append({"name": name, "url": urljoin(DEPO_BASE_URL, url)})
    
    if not categories:
        # Return common categories for online.depo.lv (hardware store)
        common_categories = [
            "Būvmateriāli",
            "Instrumenti",
            "Dekorācijas",
            "Elektroinstalācija",
            "Santehnika",
            "Krāsas un līmes",
            "Dārza preces",
            "Apkure un ventilācija",
        ]
        result = "Available categories on online.depo.lv:\n\n"
        for cat in common_categories:
            result += f"- {cat}\n"
        result += f"\nVisit {DEPO_BASE_URL} to browse all categories."
        return result
    
    result = "Available categories on online.depo.lv:\n\n"
    for cat in categories[:20]:  # Limit to 20
        result += f"- {cat['name']}\n"
        if cat.get('url'):
            result += f"  URL: {cat['url']}\n"
    
    return result


@mcp.tool()
async def check_product_availability(product_url: str) -> str:
    """Check if a product is available in stock on online.depo.lv.
    
    Args:
        product_url: Full URL of the product page on online.depo.lv
    """
    if not product_url or not product_url.strip():
        return "Error: Product URL cannot be empty."
    
    url = product_url.strip()
    if not url.startswith(DEPO_BASE_URL):
        return f"Error: URL must be from online.depo.lv domain ({DEPO_BASE_URL})"
    
    response = await make_request(url)
    
    if not response:
        return f"Error: Unable to check availability for {url}. The page may not exist or the website may be temporarily unavailable."
    
    html_content = response.text
    
    # Check for availability indicators
    # Common patterns: "In stock", "Out of stock", "Available", etc.
    
    availability_patterns = [
        (r'(?:in stock|pieejams|ir noliktavā)', 'Available'),
        (r'(?:out of stock|nav pieejams|nav noliktavā)', 'Out of Stock'),
        (r'(?:pre-order|pasūtīšana)', 'Pre-order'),
    ]
    
    html_lower = html_content.lower()
    
    for pattern, status in availability_patterns:
        if re.search(pattern, html_lower):
            return f"Product Availability: {status}\n\nURL: {url}\n\nNote: For the most accurate availability, please check the product page directly or contact online.depo.lv customer support."
    
    return f"Availability status could not be determined automatically.\n\nURL: {url}\n\nPlease visit the product page directly to check availability or contact online.depo.lv customer support."


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
