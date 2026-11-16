from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db.database import Base


class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(100), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    specs = relationship("Spec", back_populates="phone", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="phone", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Phone(id={self.id}, model='{self.model}')>"


class Spec(Base):
    __tablename__ = "specs"

    id = Column(Integer, primary_key=True, index=True)
    phone_id = Column(Integer, ForeignKey("phones.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    key = Column(String(150), nullable=False)
    value = Column(Text, nullable=False)

    phone = relationship("Phone", back_populates="specs")

    def __repr__(self):
        return f"<Spec(phone_id={self.phone_id}, category='{self.category}', key='{self.key}')>"


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    phone_id = Column(Integer, ForeignKey("phones.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)

    phone = relationship("Phone", back_populates="embeddings")

    def __repr__(self):
        return f"<Embedding(phone_id={self.phone_id}, category='{self.category}')>"
