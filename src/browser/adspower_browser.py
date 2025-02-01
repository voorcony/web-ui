import requests
import json
import asyncio
from playwright.async_api import async_playwright, Browser as PlaywrightBrowser
from browser_use.browser.browser import Browser, BrowserConfig
from src.browser.custom_context import CustomBrowserContext
from browser_use.browser.context import BrowserContextConfig
from .adspower_config import AdspowerConfig

class AdspowerBrowser(Browser):
    def __init__(self, config: AdspowerConfig):
        super().__init__(BrowserConfig())
        self.adspower_config = config
        self._playwright = None
        self._browser: PlaywrightBrowser = None
        self._default_context = None

    async def get_playwright_browser(self) -> PlaywrightBrowser:
        """获取 Playwright 浏览器实例"""
        if not self._browser:
            self._browser = await self.launch_browser()
        return self._browser

    async def launch_browser(self) -> PlaywrightBrowser:
        """启动浏览器"""
        try:
            # 1. 启动新的浏览器实例
            start_url = f"{self.adspower_config.api_host}/api/v1/browser/start"
            
            # 根据 AdsPower 文档配置启动参数
            launch_args = json.dumps([
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--start-maximized",
                "--disable-notifications",  # 禁用通知
                "--ignore-certificate-errors"  # 忽略证书错误
            ])
            
            start_params = {
                "user_id": self.adspower_config.user_id,
                "headless": self.adspower_config.headless,
                "launch_args": launch_args,
                "enable_auto_refresh": True  # 启用自动刷新
            }
            
            print(f"Starting Adspower browser with params: {start_params}")
            start_response = requests.get(start_url, params=start_params).json()
            print(f"Start browser response: {start_response}")
            
            if start_response["code"] != 0:
                raise Exception(f"Failed to start browser: {start_response['msg']}")

            # 2. 获取连接信息
            ws_endpoint = start_response["data"]["ws"]["puppeteer"]
            print(f"WebSocket endpoint: {ws_endpoint}")

            # 3. 等待浏览器启动
            await asyncio.sleep(5)  # 使用异步等待

            # 4. 连接到浏览器
            if not self._playwright:
                self._playwright = await async_playwright().start()
            
            print("Connecting to browser...")
            browser = await self._playwright.chromium.connect_over_cdp(
                endpoint_url=ws_endpoint,
                timeout=60000,  # 增加超时时间
                headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"
                }
            )
            
            if not browser:
                raise Exception("Failed to connect to browser")
                
            print("Successfully connected to Adspower browser")
            await asyncio.sleep(2)
            
            # 5. 获取已有的上下文或创建新的
            contexts = browser.contexts
            if contexts:
                print("Using existing context")
                self._default_context = contexts[0]
            else:
                print("Creating new context")
                self._default_context = await browser.new_context(
                    viewport=None,
                    accept_downloads=True,
                    ignore_https_errors=True
                )
            
            if not self._default_context:
                raise Exception("Failed to get or create context")
            
            # 6. 设置默认上下文的超时
            await self._default_context.set_default_timeout(60000)
            await self._default_context.set_default_navigation_timeout(60000)
            
            self._browser = browser
            return self._browser

        except Exception as e:
            error_msg = f"Failed to launch Adspower browser: {str(e)}"
            print(error_msg)
            if self._playwright:
                await self._playwright.stop()
            raise Exception(error_msg)

    async def get_default_context(self) -> PlaywrightBrowserContext:
        """获取默认上下文"""
        if not self._default_context:
            browser = await self.get_playwright_browser()
            if not browser:
                raise Exception("Failed to get browser")
            
            # 获取已有的上下文或创建新的
            contexts = browser.contexts
            if contexts:
                print("Using existing context")
                self._default_context = contexts[0]
            else:
                print("Creating new context")
                self._default_context = await browser.new_context(
                    viewport=None,
                    accept_downloads=True,
                    ignore_https_errors=True
                )
            
            if not self._default_context:
                raise Exception("Failed to get or create context")
            
            await self._default_context.set_default_timeout(60000)
            await self._default_context.set_default_navigation_timeout(60000)
            
        return self._default_context

    async def new_context(self, config: BrowserContextConfig = None) -> CustomBrowserContext:
        """创建新的浏览器上下文"""
        if not config:
            config = BrowserContextConfig()
        
        # 确保有默认上下文
        await self.get_default_context()
        
        context = CustomBrowserContext(browser=self, config=config)
        return context

    async def close(self):
        """关闭浏览器"""
        try:
            # 不关闭默认上下文，让 AdsPower 管理它
            self._default_context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        except Exception as e:
            print(f"Error when closing browser: {e}")
            raise 