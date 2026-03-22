from sqlalchemy import create_engine, Column, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:////app/app/data/vkorni.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Biography(Base):
    __tablename__ = "biographies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    text = Column(Text, nullable=True)

    photos = relationship("Photo", back_populates="biography", cascade="all, delete")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    biography_id = Column(Integer, ForeignKey("biographies.id"), nullable=False)

    wiki_url = Column(String(500), nullable=False)
    local_path = Column(String(500), nullable=True)

    biography = relationship("Biography", back_populates="photos")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    reset_token = Column(String(100), nullable=True)
    reset_token_expires = Column(Float, nullable=True)  # unix timestamp


def init_db():
    import os
    from passlib.context import CryptContext

    Base.metadata.create_all(bind=engine)

    # Seed default admin if none exists
    with SessionLocal() as db:
        if db.query(AdminUser).count() == 0:
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            username = os.getenv("ADMIN_USERNAME", "admin")
            password = os.getenv("ADMIN_PASSWORD", "admin123")
            db.add(AdminUser(
                username=username,
                hashed_password=pwd.hash(password),
            ))
            db.commit()
            import logging
            logging.getLogger(__name__).info("Default admin user '%s' created.", username)
