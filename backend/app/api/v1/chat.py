from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


SYSTEM_PROMPT = """You are an expert CA Assistant for a UAE Chartered Accountant practice management platform called Clearbook.

You specialise in:
- UAE VAT (Value Added Tax) — Federal Decree-Law No. 8 of 2017
- UAE Corporate Tax — Federal Decree-Law No. 47 of 2022
- Accounting and bookkeeping for UAE businesses
- TallyPrime accounting software
- Financial statement preparation
- Document processing and voucher management

Always provide accurate, practical guidance. When discussing tax matters, remind the CA to verify against current FTA guidelines. Be concise and professional."""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        from openai import OpenAI
        from app.core.config import settings

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

        client = OpenAI(api_key=api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        return ChatResponse(reply=response.choices[0].message.content)

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=500, detail="Run: pip install openai")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")