
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Database setup
DATABASE_URL = "sqlite:///./umrah_chat.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    preferences = Column(String)

Base.metadata.create_all(bind=engine)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str
    preferences: Optional[str] = None

# Routes
@app.post("/signup")
def signup(user: UserCreate):
    db = SessionLocal()
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    new_user = User(username=user.username, password=user.password, preferences=user.preferences)
    db.add(new_user)
    db.commit()
    db.close()
    return {"message": "User created successfully"}

@app.post("/login")
def login(user: UserCreate):
    db = SessionLocal()
    db_user = db.query(User).filter(User.username == user.username, User.password == user.password).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"message": "Login successful"}

# WebSocket for chat
connections = []

@app.websocket("/chat")
async def chat(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("AI:"):
                query = data[3:].strip()
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": query}]
                )
                answer = response.choices[0].message['content']
                await websocket.send_text(f"AI: {answer}")
            else:
                for conn in connections:
                    if conn != websocket:
                        await conn.send_text(data)
    except Exception as e:
        connections.remove(websocket)

# HTML for frontend testing
@app.get("/")
def get_chat():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Umrah Chat</title>
    </head>
    <body>
        <h1>Umrah Chat</h1>
        <input id="messageInput" type="text" placeholder="Type your message..."/>
        <button onclick="sendMessage()">Send</button>
        <div id="chat"></div>
        <script>
            const ws = new WebSocket("ws://localhost:8000/chat");
            ws.onmessage = (event) => {
                const chatDiv = document.getElementById('chat');
                chatDiv.innerHTML += `<p>${event.data}</p>`;
            };
            function sendMessage() {
                const input = document.getElementById('messageInput');
                ws.send(input.value);
                input.value = '';
            }
        </script>
    </body>
    </html>
    """)
