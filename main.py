# main.py
from fastapi import FastAPI, Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import List, Optional, Dict, Any
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4
import httpx

SECRET_KEY = "6c9f08e2b99e4f6cae7a71c88e9d5f74447d7649d5c44d8f80a8a8e5e1c2579c"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

CEREBRASERV_URL = "https://galaxeservice.onrender.com/generate"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajustar en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "galaxeai.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Habilitar foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # users
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL
    )
    ''')
    # chats: one row per conversation
    c.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    # messages: messages linked to a chat
    c.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
    )
    ''')
    conn.commit()
    conn.close()

init_db()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Pydantic models ---
class UserRegister(BaseModel):
    username: str
    password: str

class User(BaseModel):
    username: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ChatCreateResponse(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str

class MessageIn(BaseModel):
    role: str
    content: str

class MessageOut(MessageIn):
    timestamp: str

class ChatSummary(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int

class ChatWithMessages(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    messages: List[MessageOut]

# --- Auth helpers ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(username: str) -> Optional[UserInDB]:
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if row:
        return UserInDB(username=row["username"], hashed_password=row["hashed_password"])
    return None

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return User(username=username)

# --- Endpoints ---

@app.post("/register", status_code=201)
def register(user: UserRegister):
    hashed_password = get_password_hash(user.password)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (user.username, hashed_password))
        conn.commit()
        return {"msg": "Usuario creado"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    finally:
        conn.close()

@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

# Create a new chat (explicitly used when pressing "Nuevo chat")
@app.post("/chats", response_model=ChatCreateResponse)
def create_chat(current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_id = user_row["id"]
    chat_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO chats (id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (chat_id, user_id, now, now)
    )
    conn.commit()
    conn.close()
    return ChatCreateResponse(id=chat_id, title=None, created_at=now, updated_at=now)

# Add messages to a chat and get assistant response (this does NOT create new chat)
@app.post("/chats/{chat_id}/messages")
async def add_messages_to_chat(
    chat_id: str = Path(..., description="ID del chat"),
    messages: List[MessageIn] = [],
    current_user: User = Depends(get_current_user)
):
    conn = get_db()
    c = conn.cursor()
    # verify chat exists and belongs to user
    chat_row = c.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    if not chat_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    # verify ownership
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row or chat_row["user_id"] != user_row["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="No tienes permiso para este chat")

    # Save incoming messages (if any)
    saved_any = False
    for msg in messages:
        if msg.role not in ("user", "assistant", "system"):
            continue
        c.execute(
            "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, msg.role, msg.content, datetime.utcnow().isoformat())
        )
        saved_any = True

    # If no messages were sent in payload, that's allowed; we may still call the model with full chat history
    # Build context: read all messages for this chat ordered by timestamp ASC
    rows = c.execute("SELECT role, content, timestamp FROM messages WHERE chat_id=? ORDER BY timestamp ASC", (chat_id,)).fetchall()
    chat_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

    # Call external generation service with the context
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(CEREBRASERV_URL, json={"messages": chat_messages}, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as exc:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Error conectando a servicio de IA: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Servicio de IA respondió con error: {exc.response.status_code}") from exc

    # Expect data["response"] to contain assistant text. Guardar en messages
    assistant_text = data.get("response", "")
    if assistant_text:
        c.execute(
            "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, "assistant", assistant_text, datetime.utcnow().isoformat())
        )
        # Update chat's updated_at and maybe title if not set (title = first user message)
        # If chat has no title, set it from the first user message
        if not chat_row["title"]:
            first_user = c.execute("SELECT content FROM messages WHERE chat_id=? AND role='user' ORDER BY timestamp ASC LIMIT 1", (chat_id,)).fetchone()
            title = first_user["content"][:255] if first_user else None
        else:
            title = chat_row["title"]
        now = datetime.utcnow().isoformat()
        c.execute("UPDATE chats SET title=?, updated_at=? WHERE id=?", (title, now, chat_id))
        conn.commit()
    else:
        conn.commit()

    # Return assistant response
    conn.close()
    return {"response": assistant_text}

# Get list of chats summaries for the current user
@app.get("/chats", response_model=List[ChatSummary])
def list_chats(current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_id = user_row["id"]

    rows = c.execute(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at,
               (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) as message_count
        FROM chats c
        WHERE c.user_id = ?
        ORDER BY c.updated_at DESC
        LIMIT 100
        """,
        (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append(ChatSummary(
            id=r["id"],
            title=r["title"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            message_count=r["message_count"]
        ))
    return result

# Get full chat with messages
@app.get("/chats/{chat_id}", response_model=ChatWithMessages)
def get_chat(chat_id: str, current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    chat_row = c.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    if not chat_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row or chat_row["user_id"] != user_row["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="No tienes permiso para este chat")

    msg_rows = c.execute("SELECT role, content, timestamp FROM messages WHERE chat_id=? ORDER BY timestamp ASC", (chat_id,)).fetchall()
    messages = [MessageOut(role=m["role"], content=m["content"], timestamp=m["timestamp"]) for m in msg_rows]
    conn.close()
    return ChatWithMessages(
        id=chat_row["id"],
        title=chat_row["title"],
        created_at=chat_row["created_at"],
        updated_at=chat_row["updated_at"],
        messages=messages
    )

# Delete a chat
@app.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    chat_row = c.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    if not chat_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row or chat_row["user_id"] != user_row["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="No tienes permiso para este chat")
    # Cascade delete messages thanks to FK with ON DELETE CASCADE
    c.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()
    return

# Convenience endpoint - get last N messages across all chats (if needed)
@app.get("/history")
def get_recent_messages(limit: int = 50, current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_id = user_row["id"]

    # Get messages joined with chat but only for this user
    rows = c.execute(
        """
        SELECT m.chat_id, m.role, m.content, m.timestamp
        FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ?
        ORDER BY m.timestamp DESC
        LIMIT ?
        """,
        (user_id, limit)
    ).fetchall()
    conn.close()
    history = [{"chat_id": r["chat_id"], "role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
    return {"history": history}
