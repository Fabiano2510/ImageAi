from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import List
import httpx
import sqlite3
from datetime import datetime, timedelta

# CONFIGURA TU SECRET_KEY JWT AQUÍ (usa clave segura)
SECRET_KEY = "6c9f08e2b99e4f6cae7a71c88e9d5f74447d7649d5c44d8f80a8a8e5e1c2579c"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

CEREBRASERV_URL = "https://galaxeservice.onrender.com/generate"  # Tu backend IA

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "galaxeai.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    conn.commit()
    conn.close()

init_db()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# MODELOS

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

class ChatMessage(BaseModel):
    role: str
    content: str

# FUNCIONES DE SEGURIDAD

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(username: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return UserInDB(username=row["username"], hashed_password=row["hashed_password"])
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
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
    return user

# RUTAS

@app.post("/register")
def register(user: UserRegister):
    hashed_password = get_password_hash(user.password)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, hashed_password) VALUES (?,?)", (user.username, hashed_password))
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

@app.post("/chat")
async def chat(messages: List[ChatMessage], current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    user_id = user_row["id"]
    # Guardar mensajes usuario
    for msg in messages:
        c.execute("INSERT INTO chats (user_id, role, content) VALUES (?, ?, ?)", (user_id, msg.role, msg.content))
    conn.commit()

    # Llamar al backend de IA
    async with httpx.AsyncClient() as client:
        resp = await client.post(CEREBRASERV_URL, json={"messages": [msg.dict() for msg in messages]})
        resp.raise_for_status()
        data = resp.json()

    # Guardar respuesta IA
    c.execute("INSERT INTO chats (user_id, role, content) VALUES (?, ?, ?)", (user_id, "assistant", data["response"]))
    conn.commit()
    conn.close()

    return {"response": data["response"]}

@app.get("/history")
def get_history(current_user: User = Depends(get_current_user)):
    conn = get_db()
    c = conn.cursor()
    user_row = c.execute("SELECT id FROM users WHERE username=?", (current_user.username,)).fetchone()
    user_id = user_row["id"]
    rows = c.execute(
        "SELECT role, content, timestamp FROM chats WHERE user_id=? ORDER BY timestamp DESC LIMIT 50", (user_id,)
    ).fetchall()
    conn.close()
    history = [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
    return {"history": history}
