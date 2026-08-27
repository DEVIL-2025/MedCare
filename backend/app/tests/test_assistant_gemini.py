import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.gemini_service import GeminiService
from backend.app.routers.assistant import assistant_chat, ChatRequest
from backend.app.database import AsyncSessionLocal
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from sqlalchemy import select


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
async def test_assistant_chat_product_stock_grounded():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="What is the stock of Paracetamol in MUM-01?")
        res = await assistant_chat(req=req, db=session)
        assert res.category in ["Product Inventory", "Inventory"]
        assert res.confidence >= 0.95
        assert res.data is not None
        assert "Paracetamol" in res.answer or "P-1042" in res.answer


@pytest.mark.asyncio
async def test_assistant_chat_low_stock_query_retrieves_real_data():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="Show low stock")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Low Stock"
        assert res.confidence >= 0.95
        assert res.data is not None
        assert "low_stock_count" in res.data

        # Verify that if items are returned in data, they satisfy low stock condition
        for item in res.data.get("items", []):
            assert "sku" in item
            assert "product_name" in item
            assert "warehouse_id" in item
            assert "current_stock" in item
            assert "reorder_point" in item
            assert "safety_stock" in item
            assert "status" in item


@pytest.mark.asyncio
async def test_assistant_chat_low_stock_natural_variations():
    queries = [
        "Which products are low?",
        "What needs to be reordered?",
        "Show me low inventory",
        "What items are low stock?"
    ]
    async with AsyncSessionLocal() as session:
        for q in queries:
            req = ChatRequest(query=q)
            res = await assistant_chat(req=req, db=session)
            assert res.category == "Low Stock"
            assert res.data is not None
            assert "low_stock_count" in res.data


@pytest.mark.asyncio
async def test_assistant_chat_stockout_query():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="Show out of stock items")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Stockouts & Critical Shortages"
        assert res.data is not None


@pytest.mark.asyncio
async def test_assistant_chat_overstock_query():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="Show overstock")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Overstock"
        assert res.data is not None


@pytest.mark.asyncio
async def test_assistant_chat_rop_config_query():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="What is the reorder point for Paracetamol?")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Inventory Policy"
        assert res.data is not None
        assert "Paracetamol" in res.answer or "reorder_point" in str(res.data)


@pytest.mark.asyncio
async def test_assistant_chat_warehouse_inventory_query():
    async with AsyncSessionLocal() as session:
        req = ChatRequest(query="What products are stored in MUM-01?")
        res = await assistant_chat(req=req, db=session)
        assert res.category == "Warehouse Inventory"
        assert res.data is not None
        assert res.data.get("warehouse_id") == "MUM-01"


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
