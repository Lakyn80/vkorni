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


class ExportRecord(Base):
    __tablename__ = "export_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    export_kind = Column(String(32), nullable=False, default="manual")
    status = Column(String(32), nullable=False, index=True)
    source_photo_path = Column(String(500), nullable=True)
    source_photo_url = Column(String(1000), nullable=True)
    image_origin = Column(String(64), nullable=True)
    attachment_id = Column(Integer, nullable=True, index=True)
    attachment_url = Column(String(1000), nullable=True)
    thread_id = Column(Integer, nullable=True, index=True)
    thread_url = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)


class StoredProfile(Base):
    __tablename__ = "stored_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=True)
    birth = Column(String(255), nullable=True)
    death = Column(String(255), nullable=True)
    selected_photo_url = Column(String(1000), nullable=True)
    selected_source_url = Column(String(1000), nullable=True)
    framed_image_path = Column(String(1000), nullable=True)
    frame_id = Column(Integer, nullable=True)
    attachment_id = Column(Integer, nullable=True, index=True)
    attachment_url = Column(String(1000), nullable=True)
    last_thread_id = Column(Integer, nullable=True, index=True)
    last_thread_url = Column(String(500), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    last_exported_at = Column(Float, nullable=False)

    photos = relationship("StoredProfilePhoto", back_populates="stored_profile", cascade="all, delete-orphan")
    export_attempts = relationship("ProfileExportAttempt", back_populates="stored_profile", cascade="all, delete-orphan")


class StoredProfilePhoto(Base):
    __tablename__ = "stored_profile_photos"

    id = Column(Integer, primary_key=True, index=True)
    stored_profile_id = Column(Integer, ForeignKey("stored_profiles.id"), nullable=False, index=True)
    photo_url = Column(String(1000), nullable=False)
    source_url = Column(String(1000), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_selected = Column(Integer, nullable=False, default=0)

    stored_profile = relationship("StoredProfile", back_populates="photos")


class ProfileExportAttempt(Base):
    __tablename__ = "profile_export_attempts"

    id = Column(Integer, primary_key=True, index=True)
    stored_profile_id = Column(Integer, ForeignKey("stored_profiles.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    export_kind = Column(String(32), nullable=False, default="manual")
    thread_id = Column(Integer, nullable=True, index=True)
    thread_url = Column(String(500), nullable=True)
    attachment_id = Column(Integer, nullable=True, index=True)
    attachment_url = Column(String(1000), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)

    stored_profile = relationship("StoredProfile", back_populates="export_attempts")


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
