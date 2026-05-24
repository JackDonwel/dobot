from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    llm_provider: Literal["openai", "ollama", "mock"] = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    account_balance: float = 10_000.0
    risk_per_trade: float = 0.01
    min_reward_ratio: float = 4.0

    london_session_start: str = "10:00"
    london_session_end: str = "18:00"

    chroma_persist_dir: str = "./data/chroma_db"
    trade_log_db: str = "./data/trades.db"
    fine_tuning_dataset_path: str = "./data/lessons.jsonl"

    major_pairs: list[str] = ["EUR/USD", "GBP/USD"]

    meta_api_token: str = ""
    meta_api_domain: str = "agiliumtrade.agiliumtrade.ai"
    meta_api_region: str = ""
    meta_api_account_id: str = ""
    data_provider: Literal["auto", "metaapi", "yfinance", "synthetic"] = "auto"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
