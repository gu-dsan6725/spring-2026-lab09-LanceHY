"""
FastAPI wrapper for the memory-enabled Agent.

Provides multi-tenant REST endpoints with session-based agent caching,
enabling user isolation and cross-session memory recall via Mem0.
"""

import os
import uuid
import logging
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import Agent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Memory Agent API",
    description="Multi-tenant conversational agent with semantic memory",
    version="1.0.0",
)

# Session cache: run_id -> Agent instance
_session_cache: Dict[str, Agent] = {}

api_key = os.getenv("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class InvocationRequest(BaseModel):
    user_id: str = Field(..., description="User identifier for memory isolation")
    run_id: Optional[str] = Field(None, description="Session ID (auto-generated if omitted)")
    query: str = Field(..., description="User's message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional context/tags")


class InvocationResponse(BaseModel):
    user_id: str
    run_id: str
    response: str


class PingResponse(BaseModel):
    status: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_agent(user_id: str, run_id: str) -> Agent:
    """Return existing Agent for the session or create a new one."""
    if run_id in _session_cache:
        logger.info(f"Reusing agent for run_id={run_id}")
        return _session_cache[run_id]

    logger.info(f"Creating new agent for user_id={user_id}, run_id={run_id}")
    agent = Agent(user_id=user_id, run_id=run_id, api_key=api_key)
    _session_cache[run_id] = agent
    return agent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/ping", response_model=PingResponse)
def ping():
    """Health check endpoint."""
    return PingResponse(status="ok", message="Memory Agent API is running")


@app.post("/invocation", response_model=InvocationResponse)
def invocation(request: InvocationRequest):
    """Main conversation endpoint with session-aware memory."""
    run_id = request.run_id or str(uuid.uuid4())[:8]

    try:
        agent = _get_or_create_agent(request.user_id, run_id)
        response_text = agent.chat(request.query)
    except Exception as e:
        logger.error(f"Error during invocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return InvocationResponse(
        user_id=request.user_id,
        run_id=run_id,
        response=response_text,
    )
