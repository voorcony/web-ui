import requests
import json
import time
import os
from playwright.async_api import async_playwright
from browser_use.browser.browser import Browser, BrowserConfig
from .adspower_config import AdspowerConfig

class AdspowerBrowser(Browser):
    def __init__(self, config: AdspowerConfig):
        super().__init__(BrowserConfig())
        self.adspower_config = config
        self._playwright = None
        
    def _check_service(self):
        """检查 Adspower API 服务是否可用"""
        try:
            response = requests.get(f"{self.adspower_config.api_host}/status")
            return response.status_code == 200
        except:
            return False
            
    def _check_browser_exists(self):
        """检查浏览器配置是否存在"""
        try:
            url = f"{self.adspower_config.api_host}/api/v1/user/list"
            response = requests.get(url).json()
            if response["code"] == 0:
                user_ids = [user["user_id"] for user in response["data"]["list"]]
                return self.adspower_config.user_id in user_ids
            return False
        except:
            return False

    async def launch_browser(self):
        try:
            # 1. 检查服务是否可用
            if not self._check_service():
                raise Exception("Adspower API service is not running. Please start the service first.")

            # 2. 检查浏览器配置是否存在
            if not self._check_browser_exists():
                raise Exception(f"Browser profile {self.adspower_config.user_id} not found in Adspower.")

            # 3. 先尝试关闭已存在的实例
            try:
                close_url = f"{self.adspower_config.api_host}/api/v1/browser/stop"
                close_params = {"user_id": self.adspower_config.user_id}
                close_response = requests.get(close_url, params=close_params).json()
                print(f"Stop existing browser response: {close_response}")
                time.sleep(3)  # 等待浏览器完全关闭
            except Exception as e:
                print(f"Warning when stopping existing browser: {e}")

            # 4. 启动新的浏览器实例
            start_url = f"{self.adspower_config.api_host}/api/v1/browser/start"
            
            # 修改启动参数格式
            launch_args = json.dumps([
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ])
            
            start_params = {
                "user_id": self.adspower_config.user_id,
                "headless": self.adspower_config.headless,
                "launch_args": launch_args  # 使用 JSON 字符串
            }
            
            print(f"Starting Adspower browser with params: {start_params}")
            start_response = requests.get(start_url, params=start_params).json()
            print(f"Start browser response: {start_response}")
            
            if start_response["code"] != 0:
                raise Exception(f"Failed to start browser: {start_response['msg']}")

            # 5. 获取连接信息
            ws_endpoint = start_response["data"]["ws"]["puppeteer"]  # 使用 puppeteer websocket URL
            print(f"WebSocket endpoint: {ws_endpoint}")

            # 6. 等待浏览器启动
            time.sleep(5)  # 增加等待时间

            # 7. 连接到浏览器
            self._playwright = await async_playwright().start()
            
            for attempt in range(3):
                try:
                    print(f"Attempt {attempt + 1} to connect to browser...")
                    browser = await self._playwright.chromium.connect_over_cdp(
                        endpoint_url=ws_endpoint,
                        timeout=30000,  # 30 秒超时
                        headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"
                        }
                    )
                    
                    # 8. 验证连接
                    contexts = await browser.contexts()
                    if not contexts:
                        context = await browser.new_context()
                        page = await context.new_page()
                        await page.goto("about:blank")
                        
                    print("Successfully connected to Adspower browser")
                    return browser
                    
                except Exception as e:
                    print(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(3)
                    else:
                        raise

        except Exception as e:
            error_msg = f"Failed to launch Adspower browser: {str(e)}"
            print(error_msg)
            if self._playwright:
                await self._playwright.stop()
            raise Exception(error_msg)

    async def close(self):
        """关闭浏览器"""
        try:
            # 1. 关闭 playwright
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            # 2. 关闭 Adspower 浏览器
            close_url = f"{self.adspower_config.api_host}/api/v1/browser/stop"
            params = {"user_id": self.adspower_config.user_id}
            response = requests.get(close_url, params=params).json()
            print(f"Close browser response: {response}")

        except Exception as e:
            print(f"Error when closing browser: {e}")
            raise 