import os
from datetime import datetime

import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
env = os.getenv

DATABASE_URL = f"postgresql+psycopg2://{env('AWS_RDS_USER')}:{env('AWS_RDS_PASS')}@{env('AWS_RDS_HOST')}:{env('AWS_RDS_PORT')}/{env('AWS_RDS_NAME')}"

engine = create_engine(DATABASE_URL)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=True) # Nullable for OAuth users
    email = Column(String, nullable=False, unique=True, index=True)
    first_name = Column(String, nullable=False)
    oauth_provider = Column(String, nullable=True) # "google", "facebook", "apple"
    oauth_provider_user_id = Column(String, nullable=True, unique=True)
    oauth_provider_user_access_token = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    last_login_at = Column(DateTime, default=datetime.now(), nullable=False)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    theme = Column(String,nullable=False) # "light", "dark", "gray"


class RDS:
    def __init__(self):
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

    # User table
    def create_user(
            self, 
            username: str, 
            email: str,
            first_name: str,
            oauth_provider: Optional[str] = None,
            oauth_provider_user_id: Optional[str] = None,
            oauth_provider_user_access_token: Optional[str] = None,
            password: Optional[str] = None, 
        ) -> int | bool:

        db = self.SessionLocal()

        try:
            if password:
                password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            db_user = User(
                username=username, 
                password=password,
                email=email, 
                first_name=first_name,
                oauth_provider=oauth_provider,
                oauth_provider_user_id=oauth_provider_user_id,
                oauth_provider_user_access_token=oauth_provider_user_access_token
            )

            db.add(db_user)
            db.commit()
            db.refresh(db_user)

            return db_user.id # store this in redis

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()

    def read_user(self, user_id: int) -> dict[str, str | int] | bool:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                return False

            return {
                "username": db_user.username,
                "email": db_user.email,
                "first_name": db_user.first_name,
                "oauth_provider": db_user.oauth_provider,
                "oauth_provider_user_id": db_user.oauth_provider_user_id,
                "oauth_provider_user_access_token": db_user.oauth_provider_user_access_token,
                "created_at": str(db_user.created_at),
                "last_login_at": str(db_user.last_login_at),
            }

        except Exception:
            return False

        finally:
            db.close()
                
    def update_user(
            self, 
            user_id: int, 
            username: Optional[str] = None, 
            password: Optional[str] = None, 
            email: Optional[str] = None, 
            first_name: Optional[str] = None,
            last_login_at: Optional[datetime] = None,
        ) -> bool:

        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                return False
            
            if username:
                db_user.username = username
            if password:
                db_user.password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            if email:
                db_user.email = email
            if first_name:
                db_user.first_name = first_name
            if last_login_at:
                db_user.last_login_at = last_login_at

            db.commit()
            db.refresh(db_user)
            
            return True

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()

    def delete_user(self, user_id: int) -> bool:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                return False

            db.delete(db_user)
            db.commit()

            return True

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()


    # UserPreferences table
    def create_user_preference(self, user_id: int, theme: str) -> bool:
        db = self.SessionLocal()

        try:
            db_user_preference = UserPreferences(user_id=user_id, theme=theme)

            db.add(db_user_preference)
            db.commit()
            db.refresh(db_user_preference)

            return True
        
        except Exception:
            db.rollback()
            return False
        
        finally:
            db.close()

    def read_user_preference(self, user_id: int) -> dict[str, str] | bool:
        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

            if not db_user_preference:
                return False

            return { "theme": db_user_preference.theme }
        
        except Exception:
            return False

        finally:
            db.close()

    def update_user_preference(
            self, 
            user_id: int, 
            theme: str, 
        ) -> bool:

        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
            
            if not db_user_preference:
                return False

            db_user_preference.theme = theme
            
            db.commit()
            db.refresh(db_user_preference)

            return True

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()

    def delete_user_preference(self, user_id: int) -> bool:
        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

            if not db_user_preference:
                return False

            db.delete(db_user_preference)
            db.commit()

            return True

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()

    # Authentication (for local accounts)
    def check_login_credentials(self, username_or_email: str, password: str) -> bool:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.username == username_or_email).first()

            if not db_user:
                db_user = db.query(User).filter(User.email == username_or_email).first()

            if not db_user:
                return False

            if not bcrypt.checkpw(password.encode("utf-8"), db_user.password.encode("utf-8")):
                return False

            return True

        except Exception:
            return False

        finally:
            db.close()

    def login_after_successful_2fa(self, username_or_email: str) -> int | bool: # in the route, call update_user to change the last login at to the current datetime
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.username == username_or_email).first()

            if not db_user:
                db_user = db.query(User).filter(User.email == username_or_email).first()

            db_user.last_login_at = datetime.now()

            db.commit()
            db.refresh(db_user)

            return db_user.id

        except Exception:
            db.rollback()
            return False

        finally:
            db.close()
