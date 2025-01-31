class AdspowerConfig:
    def __init__(self, 
                 api_host: str = "http://127.0.0.1:50325",
                 user_id: str = None,
                 headless: bool = False,
                 proxy: dict = None,
                 timeout: int = 30000):
        """
        初始化 Adspower 配置
        
        Args:
            api_host: Adspower API 服务器地址
            user_id: Adspower 浏览器配置 ID
            headless: 是否使用无头模式
            proxy: 代理配置
            timeout: 连接超时时间（毫秒）
        """
        if not user_id:
            raise ValueError("Adspower user_id is required")
            
        self.api_host = api_host.rstrip('/')  # 移除末尾的斜杠
        self.user_id = user_id
        self.headless = headless
        self.proxy = proxy
        self.timeout = timeout 