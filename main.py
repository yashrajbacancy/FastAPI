from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from schemas.User import UserCreate, UserResponse, UserUpdate,RefreshRequest,LoginSchema
from database import engine, get_db, Base
from models.User import User
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm,HTTPBasicCredentials,HTTPAuthorizationCredentials
from auth.hashing import hash_password, verify_password
from fastapi_mail import FastMail, MessageSchema
from email_config import conf
from models.Note import Note
from schemas.Note import NoteCreate, NoteResponse, NoteUpdate
from auth.dependencies import get_current_user
from auth.tokens import create_access_token,create_refresh_token
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import logging
from jose import jwt
from config import settings
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})


async def send_welcome_email(email: str, username: str):
    try:
        message = MessageSchema(
            subject="Welcome to Our App 🚀",
            recipients=[email],
            body=f"""
        Hello {username},

        Your account has been successfully created 🎉

        Thanks for joining us!
        """,
            subtype="plain",
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")


@app.get("/")
def home():
    return {"message": "Welcome to Notes"}


@app.post("/api/users/register", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(User).where(User.username == user.username))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )
    hashed_password = hash_password(user.password)
    new_user = User(username=user.username, email=user.email, password=hashed_password)

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    background_tasks.add_task(send_welcome_email, new_user.email, new_user.username)
    return new_user


@app.put("/api/users/{id}", response_model=UserResponse)
async def update_user(
    id: int,
    update_user: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(User).where(User.id == id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this resource",
        )

    if update_user.email:
        user.email = update_user.email
    if update_user.username:
        user.username = update_user.username

    await session.commit()
    await session.refresh(user)
    return user


from fastapi import Body

@app.post("/api/users/login")
async def user_login(
    # loginUser: LoginSchema,
    username: str,
    password: str,
    session: AsyncSession = Depends(get_db),
):
   

    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalars().first()

    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials",
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/refresh")
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt.decode(
            request.refresh_token,
            key=settings.SECRET_KEY, 
            algorithms=["HS256"],
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        new_access_token = create_access_token(
            data={"sub": user.username}
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    


@app.post("/api/notes", response_model=NoteResponse)
async def create_note(
    note: NoteCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    new_note = Note(title=note.title, content=note.content, user_id=current_user.id)

    session.add(new_note)
    await session.commit()
    await session.refresh(new_note)
    return new_note


@app.delete("/api/notes/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Note).where(Note.id == id))
    note = result.scalars().first()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not Found!"
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this note",
        )
    await session.delete(note)
    await session.commit()


@app.put("/api/notes/{id}", response_model=NoteResponse)
async def update_note(
    id: int,
    update_note: NoteUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Note).where(Note.id == id))
    note = result.scalars().first()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not Found!"
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not Authorized for this request",
        )
    if update_note.title is not None:
        note.title = update_note.title

    if update_note.content is not None:
        note.content = update_note.content

    await session.commit()
    await session.refresh(note)
    return note


@app.get("/api/notes", response_model=list[NoteResponse])
async def get_user_notes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Note).where(Note.user_id == current_user.id))
    notes = result.scalars().all()
    return notes


@app.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_user),
):
    return {"message": f"Hello {current_user.username}, you are authenticated!"}


@app.exception_handler(StarletteHTTPException)
async def global_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Invalid request data",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("Unexpected Error:", traceback.format_exc())

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "type": "ServerError",
                "message": "Something went wrong. Please try again later.",
            },
        },
    )
