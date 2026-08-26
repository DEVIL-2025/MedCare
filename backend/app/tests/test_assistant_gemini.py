import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.gemini_service import GeminiService
from backend.app.routers.assistant import assistant_chat, ChatRequest
from backend.app.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_gemini_service_phrasing_fallback_when_no_key():
    service = GeminiService(api_key="")
    result = await service.phrase_answer("What is the stock?", {"stock": 100}, "Inventory")
    assert result is None


@pytest.mark.asyncio
async def test_gemini_service_phrasing_with_mocked_client():
    service = GeminiService(api_key="mock-api-key")
    mock_response = MagicMock()
    mock_response.text = "There are 500 units of Paracetamol in stock."
    
    mock_generate = AsyncMock(return_value=mock_response)
    service._client.aio.models.generate_content = mock_generate

    result = await service.phrase_answer("What is stock?", {"stock": 500}, "Inventory")
    assert result == "There are 500 units of Paracetamol in stock."


@pytest.mark.asyncio
async def test_assistant_chat_endpoint_grounded():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="What is the stock of Paracetamol in MUM-01?")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Inventory"
        assert res.confidence >= 0.95
        assert res.data is not None
        assert "Paracetamol" in res.answer or "P-1042" in res.answer or "stock" in res.answer.lower()


@pytest.mark.asyncio
async def test_assistant_chat_demand_forecast_intent():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="What is the demand forecast for Paracetamol in BLR-01?")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Demand Forecast"
        assert res.confidence >= 0.95
        assert res.data is not None
        assert res.suggested_actions is not None
        assert len(res.suggested_actions) > 0
        assert "Paracetamol" in res.answer or "demand" in res.answer.lower() or "forecast" in res.answer.lower()
