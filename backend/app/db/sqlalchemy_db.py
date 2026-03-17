from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
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


def init_db():
    Base.metadata.create_all(bind=engine)
