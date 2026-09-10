import os
import asyncio
import aiohttp
import random
import logging
from pathlib import Path
from typing import List, Set
from urllib.parse import urlparse
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

logger = logging.getLogger(__name__)


class PinterestScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.temp_dir = Path("temp/pins")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
        ]

    async def _get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Add random delay between actions to mimic human behavior."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def _setup_browser(self):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=await self._get_random_user_agent(),
            locale="en-US,en;q=0.9",
        )
        page = await context.new_page()
        return playwright, browser, context, page

    async def _extract_image_urls(self, page) -> Set[str]:
        image_urls = set()
        try:
            await page.wait_for_selector('img[src*="pinimg.com"]', timeout=10000)
            await self._random_delay()

            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await self._random_delay(1.5, 2.5)

                images = await page.query_selector_all('img[src*="pinimg.com"]')
                for img in images:
                    src = await img.get_attribute("src")
                    if not src:
                        continue

                    src = src.split("?")[0]

                    if any(x in src for x in ["236x", "170x", "60x60"]):
                        continue

                    if "originals" not in src:
                        if "/736x/" in src:
                            src = src.replace("/736x/", "/originals/")
                        elif "/474x/" in src:
                            src = src.replace("/474x/", "/originals/")
                        elif "/236x/" in src:
                            src = src.replace("/236x/", "/originals/")
                        elif "/170x/" in src:
                            src = src.replace("/170x/", "/originals/")
                        else:
                            parts = src.split("/")
                            if len(parts) > 5:
                                parts.insert(5, "originals")
                                src = "/".join(parts)

                    image_urls.add(src)

                if len(image_urls) >= 30:
                    break

        except PlaywrightTimeoutError:
            logger.warning("Timeout while waiting for images to load")
        except Exception as e:
            logger.error(f"Error extracting image URLs: {str(e)}")

        return image_urls

    async def _download_image(
        self,
        session: aiohttp.ClientSession,
        url: str,
        save_path: Path,
        semaphore: asyncio.Semaphore,
    ) -> bool:
        headers = {
            "User-Agent": await self._get_random_user_agent(),
            "Referer": "https://www.pinterest.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with semaphore:
                    async with session.get(
                        url, headers=headers, timeout=30
                    ) as response:
                        if response.status == 200:
                            with open(save_path, "wb") as f:
                                f.write(await response.read())
                            logger.info(f"Downloaded: {save_path.name}")
                            return True
                        elif response.status == 429:
                            wait_time = (attempt + 1) * 5
                            logger.warning(
                                f"Rate limited. Waiting {wait_time} seconds..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                await asyncio.sleep(2**attempt)

        logger.error(f"Failed to download {url} after {max_retries} attempts")
        return False

    async def scrape_pinterest(self, query: str, max_images: int = 30) -> List[str]:
        """
        Scrape images from Pinterest based on a search query.
        """
        downloaded_files = []
        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright, browser, context, page = await self._setup_browser()
            search_url = (
                f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
            )

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await page.goto(
                        search_url, timeout=60000, wait_until="domcontentloaded"
                    )
                    await self._random_delay(2, 4)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to load page after {max_retries} attempts: {e}"
                        )
                        return []
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(2**attempt)

            try:
                accept_button = await page.query_selector(
                    'button[data-test-id="accept-cookie-button"]'
                )
                if accept_button:
                    logger.info("Accepting cookies...")
                    await accept_button.click()
                    await self._random_delay()
            except Exception as e:
                logger.debug(f"No cookie banner or error accepting cookies: {e}")

            image_urls = set()
            for _ in range(3):
                try:
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    await self._random_delay(1.5, 2.5)

                    try:
                        await page.wait_for_selector(
                            'img[src*="pinimg.com"]', timeout=10000
                        )
                    except Exception as e:
                        logger.warning(f"Timeout waiting for images: {e}")
                        continue

                    images = await page.query_selector_all('img[src*="pinimg.com"]')
                    for img in images:
                        src = await img.get_attribute("src")
                        if not src:
                            continue

                        src = src.split("?")[0]
                        if any(x in src for x in ["236x", "170x", "60x60"]):
                            continue

                        if "originals" not in src:
                            if "/736x/" in src:
                                src = src.replace("/736x/", "/originals/")
                            elif "/474x/" in src:
                                src = src.replace("/474x/", "/originals/")
                            elif "/236x/" in src:
                                src = src.replace("/236x/", "/originals/")
                            elif "/170x/" in src:
                                src = src.replace("/170x/", "/originals/")

                        image_urls.add(src)

                    if len(image_urls) >= max_images:
                        break

                except Exception as e:
                    logger.error(f"Error during image extraction: {e}")
                    continue

            if not image_urls:
                logger.warning("No image URLs found")
                return []

            image_urls = list(image_urls)[:max_images]
            logger.info(f"Found {len(image_urls)} unique image URLs")

            semaphore = asyncio.Semaphore(3)
            async with aiohttp.ClientSession() as session:
                tasks = []
                for i, url in enumerate(image_urls, 1):
                    try:
                        ext = os.path.splitext(urlparse(url).path)[1] or ".jpg"
                        ext = ".jpg" if not ext or len(ext) > 5 else ext
                        filename = f"{query.replace(' ', '_')}_{i}{ext}"
                        filepath = self.temp_dir / filename
                        task = self._download_image(session, url, filepath, semaphore)
                        tasks.append(task)
                    except Exception as e:
                        logger.error(f"Error creating download task for {url}: {e}")

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error downloading image {i+1}: {result}")
                    elif result:
                        downloaded_files.append(str(filepath))

            logger.info(f"Successfully downloaded {len(downloaded_files)} images")
            return downloaded_files

        except Exception as e:
            logger.error(f"An error occurred in scrape_pinterest: {e}", exc_info=True)
            return []

        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except:
                    pass


async def main():
    query = input("Enter Pinterest search query: ")
    max_images = (
        input("Enter maximum number of images to download (default: 30): ") or "30"
    )

    try:
        max_images = int(max_images)
        scraper = PinterestScraper(headless=True)
        await scraper.scrape_pinterest(query, max_images)
    except ValueError:
        print("Please enter a valid number for maximum images")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
