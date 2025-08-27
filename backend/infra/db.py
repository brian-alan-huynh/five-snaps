import os

import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
from typing import Optional

from backend.main import app

class RDSOperationError(Exception):
    "Exception for RDS operations"
    pass

class RDSFetchError(RDSOperationError):
    "Exception for RDS fetch operations"
    pass

load_dotenv()
env = os.getenv

def get_rds_db_url():
    user = env("AWS_RDS_DB_USER")
    password = env("AWS_RDS_DB_PASS")
    host = env("AWS_RDS_DB_HOST")
    port = env("AWS_RDS_DB_PORT")
    db_name = env("AWS_RDS_DB_NAME")
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}?sslmode=require"

engine = create_engine(
    get_rds_db_url(),
    poolclass=QueuePool,
    pool_size=25,
    max_overflow=50,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "application_name": "Snapthril Backend",
    },
)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True, default=None)
    password = Column(String, nullable=True, default=None)
    email = Column(String, nullable=True, unique=True, index=True, default=None)
    first_name = Column(String, nullable=False)
    oauth_provider = Column(String, nullable=True, default=None)
    oauth_provider_user_id = Column(String, nullable=True, unique=True, default=None)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_login_at = Column(DateTime, default=func.now(), nullable=False)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    theme = Column(String,nullable=False) # "light", "dark", "gray"

class RDS:
    def __init__(self):
        self.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=engine)
        
    def _raise_db_fetch_failure(self, func_name: str) -> None:
        error_message = f"Failed to fetch data from RDS database in {func_name}"
        app.state.logger.log_error(error_message)
        raise RDSFetchError(error_message)
        
    def _raise_db_operation_failure(self, func_name: str, error: Exception) -> None:
        error_message = f"Failed to fulfill RDS database operation in {func_name}: {error}"
        app.state.logger.log_error(error_message)
        raise RDSOperationError(error_message) from error

    # User table
    def create_user(
            self,
            first_name: str,
            username: Optional[str] = None, 
            password: Optional[str] = None, 
            email: Optional[str] = None,
            oauth_provider: Optional[str] = None,
            oauth_provider_user_id: Optional[str] = None,
        ) -> int:

        db = self.SessionLocal()

        try:
            if password:
                password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            db_user = None
            
            if username and password:
                db_user = User(
                    username=username, 
                    password=password,
                    email=email, 
                    first_name=first_name,
                )
            
            if oauth_provider and oauth_provider_user_id:
                db_user = User(
                    first_name=first_name,
                    oauth_provider=oauth_provider,
                    oauth_provider_user_id=oauth_provider_user_id,
                )

            db.add(db_user)
            db.commit()
            db.refresh(db_user)

            return db_user.id

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("create_user", e)

        finally:
            db.close()

    def read_user(self, user_id: int) -> dict[str, str | int]:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                self._raise_db_fetch_failure("read_user")

            if db_user.oauth_provider:
                return {
                    "is_oauth": True,
                    "account_type": f"Linked with {db_user.oauth_provider}",
                    "first_name": db_user.first_name,
                    "user_id": db_user.id,
                    "created_at": str(db_user.created_at),
                    "last_login_at": str(db_user.last_login_at),
                }
               
            return {
                "is_oauth": False,
                "account_type": "Normal (not linked)",
                "username": db_user.username,
                "email": db_user.email,
                "first_name": db_user.first_name,
                "user_id": db_user.id,
                "created_at": str(db_user.created_at),
                "last_login_at": str(db_user.last_login_at),
            }
            
        except RDSFetchError:
            raise

        except Exception as e:
            self._raise_db_operation_failure("read_user", e)

        finally:
            db.close()
                
    def update_user(
            self, 
            user_id: int, 
            username: Optional[str] = None, 
            password: Optional[str] = None, 
            email: Optional[str] = None, 
            first_name: Optional[str] = None,
        ) -> None:

        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                self._raise_db_fetch_failure("update_user")
            
            if username:
                db_user.username = username
            if password:
                db_user.password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            if email:
                db_user.email = email
            if first_name:
                db_user.first_name = first_name

            db.commit()
            db.refresh(db_user)
            
            return
        
        except RDSFetchError:
            raise

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("update_user", e)

        finally:
            db.close()

    def delete_user(self, user_id: int) -> None:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.id == user_id).first()

            if not db_user:
                self._raise_db_fetch_failure("delete_user")

            db.delete(db_user)
            db.commit()

            return

        except RDSFetchError:
            raise

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("delete_user", e)

        finally:
            db.close()

    # UserPreferences table
    def create_user_preference(self, user_id: int, theme: str) -> None:
        db = self.SessionLocal()

        try:
            db_user_preference = UserPreferences(user_id=user_id, theme=theme)

            db.add(db_user_preference)
            db.commit()
            db.refresh(db_user_preference)

            return
        
        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("create_user_preference", e)
        
        finally:
            db.close()

    def read_user_preference(self, user_id: int) -> dict[str, str]:
        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

            if not db_user_preference:
                self._raise_db_fetch_failure("read_user_preference")

            return { "theme": db_user_preference.theme }
        
        except RDSFetchError:
            raise

        except Exception as e:
            self._raise_db_operation_failure("read_user_preference", e)

        finally:
            db.close()

    def update_user_preference(
            self, 
            user_id: int, 
            theme: str, 
        ) -> None:

        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
            
            if not db_user_preference:
                self._raise_db_fetch_failure("update_user_preference")

            db_user_preference.theme = theme
            
            db.commit()
            db.refresh(db_user_preference)

            return
        
        except RDSFetchError:
            raise

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("update_user_preference", e)

        finally:
            db.close()

    def delete_user_preference(self, user_id: int) -> None:
        db = self.SessionLocal()

        try:
            db_user_preference = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

            if not db_user_preference:
                self._raise_db_fetch_failure("delete_user_preference")

            db.delete(db_user_preference)
            db.commit()

            return

        except RDSFetchError:
            raise

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("delete_user_preference", e)

        finally:
            db.close()

    # Authentication
    def check_normal_login_creds(self, username_or_email: str, password: str) -> bool | dict[str, str]:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.username == username_or_email).first()

            if not db_user:
                db_user = db.query(User).filter(User.email == username_or_email).first()

            if not db_user:
                return False

            if not bcrypt.checkpw(password.encode("utf-8"), db_user.password.encode("utf-8")):
                return False
            
            return {
                "email": db_user.email,
                "first_name": db_user.first_name,
            }

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("check_normal_login_creds", e)

        finally:
            db.close()
    
    def fetch_normal_user(self, username_or_email: str, password: str) -> int:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.username == username_or_email).first()

            if not db_user:
                db_user = db.query(User).filter(User.email == username_or_email).first()

            if not db_user:
                self._raise_db_fetch_failure("fetch_normal_user")

            if not bcrypt.checkpw(password.encode("utf-8"), db_user.password.encode("utf-8")):
                self._raise_db_fetch_failure("fetch_normal_user")
                
            db_user.last_login_at = func.now()

            db.commit()
            db.refresh(db_user)
            
            return db_user.id
        
        except RDSFetchError:
            raise
        
        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("fetch_normal_user", e)

        finally:
            db.close()
    
    def check_and_fetch_oauth_login_creds(self, oauth_user_id: str) -> bool | int:
        db = self.SessionLocal()

        try:
            db_user = db.query(User).filter(User.oauth_provider_user_id == oauth_user_id).first()

            if not db_user:
                return False
            
            db_user.last_login_at = func.now()

            db.commit()
            db.refresh(db_user)

            return db_user.id

        except Exception as e:
            db.rollback()
            self._raise_db_operation_failure("check_and_fetch_oauth_login_creds", e)

        finally:
            db.close()
