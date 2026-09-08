from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime
import os
from dotenv import load_dotenv
import anthropic
from jose import jwt

from app.database import engine, get_db, Base
from app.models import User, Conversation, Message
from app.auth import authenticate_ad, create_access_token

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SecBot - AI Security Assistant")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are SecBot, the official internal AI Security Assistant for the company SecProject.

Your role:
- Help employees and IT staff with cybersecurity questions
- Always answer in the context of our company security policies
- Be professional, clear, and helpful
- Never give advice that would violate security best practices

Company Security Policies (always follow these):
1. Passwords must be at least 12 characters, contain upper/lower case, numbers and symbols. Never share passwords.
2. Always report suspicious emails to security@secproject.local. Do not click links in unexpected emails.
3. If you clicked a suspicious link: disconnect from network, run full antivirus scan, change password immediately, notify IT.
4. MFA is mandatory for all accounts.
5. Never install unauthorized software.
6. USB devices are restricted.
7. Report any potential data breach immediately to the Security team.

When users ask about phishing, password resets, CVEs, or incidents, give practical step-by-step guidance based on the policies above.
Keep answers concise but complete.
"""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not authenticate_ad(username, password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid Active Directory credentials"},
            status_code=401
        )

    # Create or get user in local DB
    user = db.query(User).filter(User.username == username).first()
    if not user:
        is_admin = username.lower() == "admin"
        user = User(username=username, display_name=username, is_admin=is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(data={"sub": username})
    response = RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        return RedirectResponse(url="/")

    try:
        payload = jwt.decode(token[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return RedirectResponse(url="/")
    except:
        return RedirectResponse(url="/")

    conversations = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).all()
    return templates.TemplateResponse(request, "index.html", {
        "user": user,
        "conversations": conversations
    })

@app.post("/api/chat")
async def api_chat(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    data = await request.json()
    message = data.get("message", "").strip()
    conversation_id = data.get("conversation_id")

    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    # Get or create conversation
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(user_id=user.id, title=message[:50])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    # Get previous messages for context
    previous = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.created_at).all()
    messages_for_claude = [{"role": m.role, "content": m.content} for m in previous]

    # Call Claude
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages_for_claude
        )
        assistant_reply = response.content[0].text
    except Exception as e:
        assistant_reply = f"Sorry, I encountered an error contacting the AI service: {str(e)}"

    # Save assistant message
    bot_msg = Message(conversation_id=conversation.id, role="assistant", content=assistant_reply)
    db.add(bot_msg)
    conversation.updated_at = datetime.utcnow()
    db.commit()

    return {
        "reply": assistant_reply,
        "conversation_id": conversation.id,
        "title": conversation.title
    }

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401)

    try:
        payload = jwt.decode(token[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
    except:
        raise HTTPException(status_code=401)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id
    ).first()
    if not conversation:
        raise HTTPException(status_code=404)

    messages = [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in conversation.messages]
    return {"id": conversation.id, "title": conversation.title, "is_resolved": conversation.is_resolved, "messages": messages}

@app.post("/api/conversations/{conversation_id}/resolve")
async def mark_resolved(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401)

    try:
        payload = jwt.decode(token[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
    except:
        raise HTTPException(status_code=401)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id
    ).first()
    if conversation:
        conversation.is_resolved = True
        db.commit()
    return {"status": "ok"}

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/")

    try:
        payload = jwt.decode(token[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_admin:
            return HTMLResponse("<h1>Access Denied</h1>", status_code=403)
    except:
        return RedirectResponse(url="/")

    all_conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50).all()
    return templates.TemplateResponse(request, "admin.html", {
        "user": user,
        "conversations": all_conversations
    })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response
