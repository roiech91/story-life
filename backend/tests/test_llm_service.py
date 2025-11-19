"""Unit tests for the LLM service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Settings
from app.llm import LifeStoryLLM


@pytest.fixture
def mock_settings():
    """Create a mock settings object."""
    settings = Settings(
        PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        ANTHROPIC_API_KEY=None,
        MODEL_NAME="gpt-4o-mini",
        TEMPERATURE=0.3,
        TIMEOUT_SEC=45,
        MAX_TOKENS=None,
    )
    return settings


@pytest.fixture
def mock_llm_service(mock_settings):
    """Create a LifeStoryLLM instance with mocked LLM."""
    with patch("app.llm.service.ChatOpenAI") as mock_chat:
        mock_llm_instance = MagicMock()
        mock_chat.return_value = mock_llm_instance
        
        service = LifeStoryLLM(mock_settings)
        service._llm = mock_llm_instance
        return service


@pytest.mark.asyncio
async def test_agenerate_chapter(mock_llm_service):
    """Test chapter generation."""
    # Mock the chain invocation
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value="Generated narrative text in Hebrew")
    
    mock_llm_service._get_chapter_chain = MagicMock(return_value=mock_chain)
    
    facts = [
        {"question_id": "1-01", "text": "נולדתי בתל אביב", "created_at": "2024-01-01"},
        {"question_id": "1-02", "text": "גדלתי במשפחה חמה", "created_at": "2024-01-02"},
    ]
    
    result = await mock_llm_service.agenerate_chapter(
        person_id="person-1",
        chapter_id="1",
        facts=facts,
        style_guide="סגנון חם וטבעי",
        context_summary="אין פרקים קודמים",
    )
    
    assert result == "Generated narrative text in Hebrew"
    assert mock_chain.ainvoke.called
    call_args = mock_chain.ainvoke.call_args[0][0]
    assert "chapter_title" in call_args
    assert "facts_bullets" in call_args
    assert "style_guide" in call_args
    assert "context_summary" in call_args


@pytest.mark.asyncio
async def test_acompile_book(mock_llm_service):
    """Test book compilation."""
    # Mock the chain invocation
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value="Compiled book text in Hebrew")
    
    mock_llm_service._get_compile_chain = MagicMock(return_value=mock_chain)
    
    chapters = [
        {
            "id": "1",
            "title": "שורשים ומשפחה מוקדמת",
            "narrative": "פרק על המשפחה...",
        },
        {
            "id": "2",
            "title": "ילדות",
            "narrative": "פרק על הילדות...",
        },
    ]
    
    result = await mock_llm_service.acompile_book(
        person_id="person-1",
        chapters=chapters,
        style_guide="סגנון חם וטבעי",
    )
    
    assert result == "Compiled book text in Hebrew"
    assert mock_chain.ainvoke.called
    call_args = mock_chain.ainvoke.call_args[0][0]
    assert "style_guide" in call_args
    assert "chapter_summaries" in call_args
    assert "timeline" in call_args


@pytest.mark.asyncio
async def test_agenerate_chapter_with_empty_facts(mock_llm_service):
    """Test chapter generation with empty facts."""
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value="Empty narrative")
    
    mock_llm_service._get_chapter_chain = MagicMock(return_value=mock_chain)
    
    result = await mock_llm_service.agenerate_chapter(
        person_id="person-1",
        chapter_id="1",
        facts=[],
    )
    
    # Should still call the chain with empty facts
    assert mock_chain.ainvoke.called


def test_estimate_tokens(mock_llm_service):
    """Test token estimation."""
    text = "This is a test text" * 10
    tokens = mock_llm_service._estimate_tokens(text)
    
    # Should return a positive integer
    assert isinstance(tokens, int)
    assert tokens > 0


def test_make_llm_openai(mock_settings):
    """Test LLM creation for OpenAI provider."""
    with patch("app.llm.service.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance
        
        service = LifeStoryLLM(mock_settings)
        llm = service._make_llm()
        
        assert llm == mock_instance
        mock_chat.assert_called_once()


def test_make_llm_anthropic():
    """Test LLM creation for Anthropic provider."""
    settings = Settings(
        PROVIDER="anthropic",
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY="test-key",
        MODEL_NAME="claude-3-5-sonnet-latest",
        TEMPERATURE=0.3,
        TIMEOUT_SEC=45,
        MAX_TOKENS=None,
    )
    
    with patch("app.llm.service.ChatAnthropic") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance
        
        service = LifeStoryLLM(settings)
        llm = service._make_llm()
        
        assert llm == mock_instance
        mock_chat.assert_called_once()


@pytest.mark.asyncio
async def test_retry_with_backoff_success(mock_llm_service):
    """Test retry mechanism with successful call."""
    async def success_coro():
        return "success"
    
    result = await mock_llm_service._retry_with_backoff(success_coro())
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_with_backoff_failure(mock_llm_service):
    """Test retry mechanism with failures."""
    call_count = 0
    
    async def failing_coro():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success after retries"
    
    result = await mock_llm_service._retry_with_backoff(failing_coro(), max_retries=3)
    assert result == "success after retries"
    assert call_count == 3

