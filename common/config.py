"""
配置文件
定义各个服务的URL和端口
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # 脱敏算法服务地址
    DESENSITIVE_SERVICE_URL: str = "http://127.0.0.1:8888"
    
    # Word处理服务地址
    WORD_PROCESSOR_URL: str = "http://127.0.0.1:8002"
    
    # PDF解析API地址
    PDF_PARSE_API_URL: str = "http://127.0.0.1:8191"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
