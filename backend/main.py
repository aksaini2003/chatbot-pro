from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import json
import asyncio
import os
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage, ToolMessage

from database import get_db, create_tables, User, Conversation, Message, Document, PasswordResetToken
from auth import (
    UserCreate, Token, get_current_active_user,
    authenticate_user, create_access_token, get_user_by_username, get_user_by_email,
    get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
)
from email_utils import send_reset_password_email
from langgraph_backend import chatbot, ingest_pdf, thread_document_metadata, thread_has_document

app = FastAPI(title="Production Chatbot API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Production Chatbot API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/auth",
            "conversations": "/conversations"
        }
    }

# ==================== Auth Endpoints ====================

@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Basic Validation
    username = (user.username or "").strip()
    email = (user.email or "").strip()
    password = user.password
    
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    
    import re
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    # Check if user already exists
    if get_user_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/forgot-password")
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    user = get_user_by_email(db, email)
    if user:
        token = str(uuid.uuid4())
        expire_minutes = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "5"))
        expires_at = datetime.utcnow() + timedelta(minutes=expire_minutes)
        db_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            used=False,
        )
        db.add(db_token)
        db.commit()
        
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        reset_link = f"{frontend_url}/reset-password?token={token}"
        
        # Log to console for debugging
        print(f"DEBUG: Password reset link for {email}: {reset_link}")
        
        # Send actual email
        send_reset_password_email(email, reset_link)

    return {"message": "If the email exists, a password reset link has been generated."}


@app.post("/auth/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not reset_token or reset_token.used:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(new_password)
    reset_token.used = True
    db.commit()

    return {"message": "Password has been reset successfully"}

@app.post("/auth/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Basic input check
    username = (form_data.username or "").strip()
    password = form_data.password
    
    if not username:
        raise HTTPException(status_code=400, detail="Email is required")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
        
    result = authenticate_user(db, username, password)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A user with this Email was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if result == "INCORRECT_PASSWORD":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = result
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at
    }

# ==================== Conversation Endpoints ====================

@app.post("/conversations")
async def create_conversation(
    title: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    thread_id = str(uuid.uuid4())
    conversation = Conversation(
        thread_id=thread_id,
        title=title,
        user_id=current_user.id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return {
        "id": conversation.id,
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "created_at": conversation.created_at
    }

@app.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()
    
    return [
        {
            "id": conv.id,
            "thread_id": conv.thread_id,
            "title": conv.title,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": len(conv.messages)
        }
        for conv in conversations
    ]

@app.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at).all()
    
    documents = db.query(Document).filter(
        Document.conversation_id == conversation.id
    ).all()
    
    return {
        "id": conversation.id,
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": msg.id,
                "content": msg.content,
                "role": msg.role,
                "created_at": msg.created_at
            }
            for msg in messages
        ],
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "chunks_count": doc.chunks_count,
                "pages_count": doc.pages_count,
                "indexed_at": doc.indexed_at
            }
            for doc in documents
        ]
    }

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        db.query(Message).filter(Message.conversation_id == conversation.id).delete(synchronize_session=False)
        db.query(Document).filter(Document.conversation_id == conversation.id).delete(synchronize_session=False)
        db.delete(conversation)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

    return {"message": "Conversation deleted successfully"}

# ==================== Document Endpoints ====================

@app.post("/conversations/{conversation_id}/upload")
async def upload_document(
    conversation_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        print(f"Upload request received: conversation_id={conversation_id}, filename={file.filename}")
        
        # Verify conversation belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        print(f"File validation passed: {file.filename}")
        
        # Read file bytes
        file_bytes = await file.read()
        print(f"File read successfully: {len(file_bytes)} bytes")
        
        # Ingest PDF using existing LangGraph logic
        summary = ingest_pdf(
            file_bytes=file_bytes,
            thread_id=conversation.thread_id,
            filename=file.filename
        )
        print(f"PDF ingestion completed: {summary}")
        
        # Save document metadata to database
        document = Document(
            conversation_id=conversation.id,
            filename=file.filename,
            file_path="",  # We're not storing files permanently in this version
            chunks_count=summary["chunks"],
            pages_count=summary["documents"]
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        print(f"Document saved to database: {document.id}")
        
        return {
            "id": document.id,
            "filename": document.filename,
            "chunks_count": document.chunks_count,
            "pages_count": document.pages_count,
            "indexed_at": document.indexed_at
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ==================== Chat Endpoints ====================

@app.post("/conversations/{conversation_id}/chat")
async def chat(
    conversation_id: int,
    message: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify conversation belongs to user
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        content=message,
        role="user"
    )
    db.add(user_message)
    db.commit()
    
    # Update conversation title if it's the default "New Chat"
    if conversation.title == "New Chat":
        # Extract first few words from the message (max 50 characters)
        title = message[:50] + ("..." if len(message) > 50 else "")
        conversation.title = title
        db.commit()
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    db.commit()
    
    # Get conversation history from LangGraph
    
    CONFIG = {
        "configurable": {"thread_id": conversation.thread_id},
    }
    
    # Stream response from LangGraph
    async def generate_response():
        full_response = ""
        current_tool = None
        
        for message_chunk, _ in chatbot.stream(
            {"messages": [HumanMessage(content=message)]},
            config=CONFIG,
            stream_mode="messages",
        ):
            if hasattr(message_chunk, 'name') and message_chunk.name:
                # Tool execution
                current_tool = message_chunk.name
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': current_tool})}\n\n"
                
            elif isinstance(message_chunk, ToolMessage):
                # Tool result
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': current_tool, 'result': str(message_chunk.content)})}\n\n"
                
            elif hasattr(message_chunk, 'content') and message_chunk.content:
                # AI response chunk
                chunk = message_chunk.content
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # Save assistant message to database
        assistant_message = Message(
            conversation_id=conversation.id,
            content=full_response,
            role="assistant"
        )
        db.add(assistant_message)
        db.commit()
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
