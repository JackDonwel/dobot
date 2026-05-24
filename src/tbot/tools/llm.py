"""LLM provider factory — returns a chat model for the configured provider."""


from langchain_core.language_models.chat_models import BaseChatModel

from tbot.models.config import settings


def get_llm(
    temperature: float = 0.2,
    model_override: str | None = None,
) -> BaseChatModel:
    provider = settings.llm_provider
    model = model_override or settings.ollama_model if provider == "ollama" else settings.openai_model

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            num_predict=4096,
        )

    msg = f"Unknown LLM provider: {provider} (use openai, ollama, or mock)"
    raise ValueError(msg)


def supports_structured_output(llm: BaseChatModel) -> bool:
    """Check if the LLM supports with_structured_output (function-calling)."""
    return hasattr(llm, "with_structured_output")
