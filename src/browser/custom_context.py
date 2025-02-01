import json
import logging
import os
import asyncio
from typing import List

from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.context import BrowserState
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
from playwright.async_api import Page
from src.browser.adspower_browser import AdspowerBrowser

logger = logging.getLogger(__name__)

class CustomBrowserContext(BrowserContext):
    def __init__(
        self,
        browser: "Browser",
        config: BrowserContextConfig = BrowserContextConfig()
    ):
        """初始化浏览器上下文"""
        super().__init__(browser=browser, config=config)
        self.browser = browser
        self.config = config
        self._context: PlaywrightBrowserContext = None
        self._page: Page = None
        self._state: BrowserState = None

    async def _initialize_context(self) -> PlaywrightBrowserContext:
        """初始化浏览器上下文"""
        try:
            # 1. 获取浏览器实例
            playwright_browser = await self.browser.get_playwright_browser()
            logger.info(f"Got playwright browser: {playwright_browser}")
            
            if not playwright_browser:
                raise Exception("Failed to get playwright browser")

            # 2. 获取或创建上下文
            if isinstance(self.browser, AdspowerBrowser):
                # 如果是 AdsPower 浏览器，使用默认上下文
                logger.info("Getting default context from AdsPower browser")
                self._context = await self.browser.get_default_context()
                if not self._context:
                    raise Exception("Failed to get default context from AdsPower browser")
            else:
                # 如果是其他浏览器，创建新的上下文
                logger.info("Creating new context for regular browser")
                self._context = await playwright_browser.new_context(
                    viewport=None,
                    accept_downloads=True,
                    ignore_https_errors=True
                )
                if not self._context:
                    raise Exception("Failed to create browser context")
                
                # 设置超时
                await self._context.set_default_timeout(60000)
                await self._context.set_default_navigation_timeout(60000)

            return self._context

        except Exception as e:
            logger.error(f"Error in _initialize_context: {str(e)}")
            if self._context:
                try:
                    await self._context.close()
                except:
                    pass
                self._context = None
            raise

    async def get_context(self) -> PlaywrightBrowserContext:
        """获取浏览器上下文"""
        if not self._context:
            logger.info("Getting browser context...")
            self._context = await self._initialize_context()
            if not self._context:
                raise Exception("Failed to get browser context")
            logger.info("Got browser context successfully")
        return self._context

    async def get_page(self) -> Page:
        """获取或创建页面"""
        try:
            if not self._page:
                # 1. 获取上下文
                context = await self.get_context()
                if not context:
                    raise Exception("Failed to get browser context")

                # 2. 获取所有页面
                pages = await context.pages()
                logger.info(f"Found {len(pages)} existing pages")

                if isinstance(self.browser, AdspowerBrowser):
                    # 如果是 AdsPower 浏览器，使用第一个页面或创建新页面
                    if pages:
                        logger.info("Using existing page from AdsPower browser")
                        self._page = pages[0]
                    else:
                        logger.info("Creating new page in AdsPower browser")
                        self._page = await context.new_page()
                else:
                    # 如果是其他浏览器，总是创建新页面
                    logger.info("Creating new page in regular browser")
                    self._page = await context.new_page()

                if not self._page:
                    raise Exception("Failed to get or create page")

                # 3. 设置页面属性
                await self._page.set_default_timeout(60000)
                await self._page.set_default_navigation_timeout(60000)
                
                # 4. 等待页面准备就绪
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=10000)
                except:
                    logger.warning("Page load state timeout, continuing anyway")

            return self._page

        except Exception as e:
            logger.error(f"Error in get_page: {e}")
            raise

    async def get_state(self, use_vision: bool = False) -> BrowserState:
        """获取浏览器状态"""
        try:
            if not self._state:
                logger.info("Getting page for browser state...")
                page = await self.get_page()
                if not page:
                    raise Exception("Failed to get page")
                
                # 等待页面加载完成
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    logger.warning("Network idle timeout, continuing anyway")
                
                self._state = BrowserState(page=page, use_vision=use_vision)
                logger.info("Browser state created")
                
            return self._state
        except Exception as e:
            logger.error(f"Error in get_state: {str(e)}")
            raise

    async def close(self):
        """关闭浏览器上下文"""
        # 检查是否是 AdsPower 浏览器
        from src.browser.adspower_browser import AdspowerBrowser
        if isinstance(self.browser, AdspowerBrowser):
            # 如果是 AdsPower 浏览器，只清除引用，不实际关闭
            self._page = None
            self._context = None
            self._state = None
        else:
            # 如果是其他浏览器，正常关闭
            if self._page:
                try:
                    await self._page.close()
                except:
                    pass
                self._page = None

            if self._context:
                try:
                    await self._context.close()
                except:
                    pass
                self._context = None

            self._state = None

    def __del__(self):
        """析构函数"""
        # 检查是否是 AdsPower 浏览器
        from src.browser.adspower_browser import AdspowerBrowser
        if not isinstance(self.browser, AdspowerBrowser):
            if self._context is not None:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.close())
                    else:
                        loop.run_until_complete(self.close())
                except:
                    pass