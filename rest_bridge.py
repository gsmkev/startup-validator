"""
FastAPI server on port 8001.
Allows the Next.js frontend to call validate_idea without MCP protocol.
Run with: uvicorn rest_bridge:app --port 8001 --reload
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tools import validate_idea

app = FastAPI(title="Paraguay Idea Validator REST Bridge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class ValidateRequest(BaseModel):
    idea: str
    depth: str = "quick"


@app.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_idea(req.idea, req.depth)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "paraguay-idea-mcp"}
