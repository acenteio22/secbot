from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

load_dotenv()

LDAP_SERVER = os.getenv("LDAP_SERVER")
DOMAIN = os.getenv("DOMAIN")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def authenticate_ad(username: str, password: str) -> bool:
    """Try to bind to Active Directory. Fallback for lab/demo if AD is locked down."""
    
    # First try real Active Directory
    try:
        server = Server(LDAP_SERVER, get_info=ALL, connect_timeout=5)
        
        # Try NTLM
        try:
            user_dn = f"{DOMAIN}\\{username}"
            conn = Connection(server, user=user_dn, password=password, authentication=NTLM, auto_bind=True)
            conn.unbind()
            return True
        except Exception:
            pass

        # Try SIMPLE
        try:
            user_dn = f"{username}@{DOMAIN}"
            conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True)
            conn.unbind()
            return True
        except Exception:
            pass
    except Exception:
        pass

    # ===== LAB / DEMO FALLBACK =====
    # This lets you log in for the project demonstration
    # while Windows security is blocking LDAP
    lab_users = {
        "student1": "Anildo20!",
        "student2": "Anildo20!",
        "admin": "Anildo20!"
    }
    
    if username in lab_users and lab_users[username] == password:
        return True

    return False

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
