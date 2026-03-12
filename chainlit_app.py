import sqlite3
from pathlib import Path

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadDict

from agent import build_agent

# --- Database setup (SQLAlchemyDataLayer doesn't auto-create tables) ---

DB_PATH = Path(__file__).parent / "chainlit.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            identifier TEXT UNIQUE NOT NULL,
            metadata TEXT DEFAULT '{}',
            "createdAt" TEXT
        );

        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            "createdAt" TEXT,
            name TEXT,
            "userId" TEXT,
            "userIdentifier" TEXT,
            tags TEXT,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY ("userId") REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            "threadId" TEXT,
            "parentId" TEXT,
            name TEXT,
            type TEXT,
            streaming INTEGER DEFAULT 0,
            "waitForAnswer" INTEGER,
            "isError" INTEGER DEFAULT 0,
            input TEXT,
            output TEXT,
            metadata TEXT DEFAULT '{}',
            tags TEXT,
            "createdAt" TEXT,
            start TEXT,
            "end" TEXT,
            generation TEXT DEFAULT '{}',
            "showInput" TEXT,
            language TEXT,
            FOREIGN KEY ("threadId") REFERENCES threads(id)
        );

        CREATE TABLE IF NOT EXISTS elements (
            id TEXT PRIMARY KEY,
            "threadId" TEXT,
            type TEXT,
            name TEXT,
            display TEXT,
            url TEXT,
            "objectKey" TEXT,
            "chainlitKey" TEXT,
            size TEXT,
            language TEXT,
            page INTEGER,
            "forId" TEXT,
            mime TEXT,
            props TEXT DEFAULT '{}',
            "autoPlay" INTEGER,
            "playerConfig" TEXT,
            FOREIGN KEY ("threadId") REFERENCES threads(id)
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id TEXT PRIMARY KEY,
            "forId" TEXT,
            value INTEGER,
            comment TEXT,
            FOREIGN KEY ("forId") REFERENCES steps(id)
        );
    """)
    conn.close()


_init_db()


# --- Data layer (persistence for conversation history sidebar) ---


@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")


# --- Authentication (required for the conversation history sidebar to appear) ---


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    return cl.User(identifier=username, metadata={"role": "user"})


# --- Agent ---

agent = build_agent()


# --- Chat lifecycle ---


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("message_history", [])


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Rebuild in-memory message history so the agent has full context."""
    message_history = []
    for step in thread["steps"]:
        if step["type"] == "user_message":
            message_history.append(("user", step["output"]))
        elif step["type"] == "assistant_message":
            message_history.append(("assistant", step["output"]))
    cl.user_session.set("message_history", message_history)


@cl.on_message
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append(("user", message.content))

    response = cl.Message(content="")
    response.parent_id = None
    await response.send()

    full_response = ""
    async for chunk, metadata in agent.astream(
        {"messages": message_history},
        stream_mode="messages",
    ):
        if chunk.type == "AIMessageChunk" and not chunk.tool_call_chunks:
            content = ""
            if isinstance(chunk.content, str):
                content = chunk.content
            elif isinstance(chunk.content, list):
                for part in chunk.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        content += part.get("text", "")
            if content:
                full_response += content
                await response.stream_token(content)

    await response.update()
    message_history.append(("assistant", full_response))
    cl.user_session.set("message_history", message_history)