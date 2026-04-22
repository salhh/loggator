from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.llm_registry import (
    list_llms, create_llm, update_llm, delete_llm, get_llm_raw, LLMNotFound
)
from loggator.llm.chain import LLMChain
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/llms", tags=["llms"])


class LLMIn(BaseModel):
    label: str
    provider: str          # ollama | anthropic | openai
    model: str
    base_url: str = ""
    api_key: str = ""
    is_default: bool = False


class LLMOut(BaseModel):
    id: str
    label: str
    provider: str
    model: str
    base_url: str
    api_key: str           # masked
    is_default: bool
    updated_at: str | None


@router.get("", response_model=list[LLMOut])
async def list_all(session: AsyncSession = Depends(get_session)):
    return await list_llms(session)


@router.post("", response_model=LLMOut, status_code=201)
async def create(body: LLMIn, session: AsyncSession = Depends(get_session)):
    return await create_llm(session, body.model_dump())


@router.put("/{id}", response_model=LLMOut)
async def update(id: str, body: LLMIn, session: AsyncSession = Depends(get_session)):
    try:
        return await update_llm(session, id, body.model_dump())
    except LLMNotFound:
        raise HTTPException(404, "LLM not found")


@router.delete("/{id}", status_code=204)
async def delete(id: str, session: AsyncSession = Depends(get_session)):
    try:
        await delete_llm(session, id)
    except LLMNotFound:
        raise HTTPException(404, "LLM not found")


@router.post("/{id}/test")
async def test_llm(id: str, session: AsyncSession = Depends(get_session)):
    try:
        config = await get_llm_raw(session, id)
    except LLMNotFound:
        raise HTTPException(404, "LLM not found")
    try:
        chain = LLMChain(config=config)
        answer = await chain.ainvoke([HumanMessage(content="Reply with exactly: ok")])
        return {"ok": True, "response": answer[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
