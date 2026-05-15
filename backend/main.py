from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime

from models import Chat, Message, create_tables, get_db
from agent import run_agent

app = FastAPI(title="Agente IA - Publicaciones Académicas")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


# ---------- Schemas Pydantic ----------

class ChatCreate(BaseModel):
    title: str = "Nuevo chat"


class ChatResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class AskRequest(BaseModel):
    question: str


# ---------- Endpoints de Chats ----------

@app.get("/chats", response_model=List[ChatResponse])
def list_chats(db: Session = Depends(get_db)):
    """Lista todos los chats ordenados por más reciente."""
    return db.query(Chat).order_by(Chat.created_at.desc()).all()


@app.post("/chats", response_model=ChatResponse)
def create_chat(body: ChatCreate, db: Session = Depends(get_db)):
    """Crea un nuevo chat."""
    chat = Chat(title=body.title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """Elimina un chat y todos sus mensajes."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    db.delete(chat)
    db.commit()
    return {"ok": True}


# ---------- Endpoints de Mensajes ----------

@app.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
def get_messages(chat_id: int, db: Session = Depends(get_db)):
    """Devuelve todos los mensajes de un chat."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()


@app.post("/chats/{chat_id}/messages", response_model=MessageResponse)
def send_message(chat_id: int, body: AskRequest, db: Session = Depends(get_db)):
    """
    Envía una pregunta al agente y guarda tanto la pregunta como la respuesta.
    Re-inyecta el historial completo del chat para mantener contexto.
    """
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")

    # Actualizar título del chat con la primera pregunta
    if chat.title == "Nuevo chat":
        chat.title = body.question[:60]
        db.commit()

    # Cargar historial completo para re-inyectar como contexto
    history_db = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at).all()

    history = [{"role": m.role, "content": m.content} for m in history_db]

    # Guardar pregunta del usuario
    user_msg = Message(chat_id=chat_id, role="user", content=body.question)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Llamar al agente con el historial completo
    answer = run_agent(user_question=body.question, history=history)

    # Guardar respuesta del agente
    assistant_msg = Message(chat_id=chat_id, role="assistant", content=answer)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg


@app.get("/health")
def health():
    return {"status": "ok"}