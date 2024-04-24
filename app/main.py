from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from .models import User, Contact
from .schemas import UserCreate, UserInDB, ContactCreate, ContactInDB, Token
from .auth import create_access_token, create_refresh_token, decode_access_token, get_password_hash, verify_password
from .database import AsyncSessionLocal

from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

from pydantic import EmailStr, BaseModel

from slowapi import Limiter, limits
from slowapi.util import get_remote_address

from cloudinary.uploader import upload
from cloudinary.units import cloudinary_url

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(HTTPException, limiter.http_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conf = ConnectionConfig(
    MAIL_USERNAME="your-email@gmail.com",
    MAIL_PASSWORD="your-password",
    MAIL_FROM="your-email@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_TLS=True,
    MAIL_SSL=True,
)
fastapi_mail = FastAPI(conf)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

class UserBase(BaseModel):
    email: EmailStr

@app.post("/register/", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user with email and password.
    
    Args:
        user (UserCreate): User registration data.
        db (AsyncSession): Database session dependency.
        
    Returns:
        UserInDB: The registered user data.
    
    Raises:
        HTTPException: 409 conflict if the email is already registered.
    """
    async with db:
        existing_user = await db.get(User, user.email)
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")
        hashed_password = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_password, is_active=False)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        # Тут можна додати відправку email для верифікації
        # send_verification_email(new_user.email)
        return new_user

async def get_db():
    """
    Dependency that yields a database session from the session pool.
    """
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/users/", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new user record in the database.
    
    Args:
        user (UserCreate): User data to create.
        db (AsyncSession): Database session dependency.
        
    Returns:
        UserInDB: The created user data.
    
    Raises:
        HTTPException: 409 conflict if the email is already registered.
    """
    async with db:
        result = await db.execute(select(User).filter(User.email == user.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")
        hashed_password = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_password, is_active=True)
        db.add(new_user)
        await db.commit()
        return new_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and provide access and refresh JWT tokens.

    Args:
        form_data (OAuth2PasswordRequestForm): Form containing user credentials.
        db (AsyncSession): Dependency injection of the database session.

    Returns:
        Token: Object containing access and refresh tokens.
    
    Raises:
        HTTPException: 401 unauthorized if credentials are invalid.
    """
    async with db:
        user = await db.get(User, form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token({"sub": user.email})
        refresh_token = create_refresh_token({"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@app.get("/users/me/", response_model=UserInDB)
async def read_users_me(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Retrieve the user profile of the currently authenticated user.

    Args:
        token (str): OAuth2 token for current user session.
        db (AsyncSession): Database session dependency.

    Returns:
        UserInDB: User data of the authenticated user.

    Raises:
        HTTPException: 401 unauthorized if token is invalid or 404 if user not found.
    """
    email = decode_access_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    async with db:
        user = await db.get(User, email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

@app.post("/contacts/", response_model=ContactInDB, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_contact(contact: ContactCreate, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Create a new contact for the authenticated user with rate limiting.

    Args:
        contact (ContactCreate): Contact data to create.
        token (str): Authentication token of the user.
        db (AsyncSession): Database session dependency.

    Returns:
        ContactInDB: The newly created contact data.

    Raises:
        HTTPException: Various exceptions based on authentication and rate limits.
    """
    email = decode_access_token(token)
    async with db:
        user = await db.get(User, email)
        new_contact = Contact(**contact.dict(), user_id=user.id)
        db.add(new_contact)
        await db.commit()
        await db.refresh(new_contact)
        return new_contact

@app.get("/contacts/", response_model=List[ContactInDB])
async def read_contacts(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Retrieve all contacts associated with the authenticated user.

    Args:
        token (str): OAuth2 token for current user session.
        db (AsyncSession): Database session dependency.

    Returns:
        List[ContactInDB]: List of all contacts for the authenticated user.
    """
    email = decode_access_token(token)
    async with db:
        user = await db.get(User, email)
        result = await db.execute(select(Contact).filter(Contact.user_id == user.id))
        contacts = result.scalars().all()
        return contacts

@app.get("/contacts/{contact_id}", response_model=ContactInDB)
async def read_contact(contact_id: int, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Retrieve a list of all contacts for the authenticated user.

    Args:
        token (str): Access token for user authentication.
        db (AsyncSession): Database session dependency.

    Returns:
        List[ContactInDB]: A list of contact objects.
    """
    email = decode_access_token(token)
    async with db:
        user = await db.get(User, email)
        result = await db.execute(select(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id))
        contact = result.scalars().first()
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")
        return contact

@app.put("/contacts/{contact_id}", response_model=ContactInDB)
async def update_contact(contact_id: int, contact: ContactCreate, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Update details of a specific contact for the authenticated user.
    
    Args:
        contact_id (int): The unique identifier of the contact to update.
        contact (ContactCreate): Data to update the contact with.
        token (str): OAuth2 token for user authentication.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        ContactInDB: The updated contact data.
    """

    email = decode_access_token(token)
    async with db:
        user = await db.get(User, email)
        result = await db.execute(select(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id))
        existing_contact = result.scalars().first()
        if not existing_contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        for var, value in vars(contact).items():
            setattr(existing_contact, var, value) if value else None
        db.commit()
        return existing_contact

@app.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: int, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Delete a specific contact for the authenticated user.
    
    Args:
        contact_id (int): The unique identifier of the contact to delete.
        token (str): OAuth2 token for user authentication.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        None: Returns nothing but HTTP 204 on successful deletion.
    """
    email = decode_access_token(token)
    async with db:
        user = await db.get(User, email)
        result = await db.execute(select(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id))
        contact = result.scalars().first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        await db.delete(contact)
        await db.commit()

async def send_verification_mail(email: str):
    """
    Send a verification email to the newly registered user.

    Args:
        email (str): Email address to which the verification link will be sent.

    Returns:
        None: Sends an email through FastAPI Mail but does not return any value.
    """
    message = MessageSchema(
        subject="Verify your email",
        recipients=[email],
        body="Please verify your email by clicking on the link: http://127.0.0.1:8000/verify-email/token",
        subtype="html",
    )

    fm = FastMail(conf)
    await fastapi_mail.send(message)

@app.get('/verify/{token}')
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """
    Verify the user's email address.

    Args:
        token (str): Verification token used to identify the user.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        dict: A message indicating that the email has been successfully verified.
    """
    email = decode_token(token)
    async with db:
        user = await db.get(User, email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_active = True
        db.add(user)
        await db.commit()
        return {"message": "Email verified"}

@app.post("/users/{user_id}/avatar")
async def update_avatar(user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Update the avatar for a specific user.

    Args:
        user_id (int): Unique identifier for the user whose avatar is to be updated.
        file (UploadFile): The image file to be uploaded as the new avatar.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        dict: A dictionary containing the URL of the newly updated avatar.
    """
    async with db:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        upload_result = upload(file.file.read(), folder="user_avatars")
        user.avatar = upload_result.url("url")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {"avatar_url": user.avatar.url}
