"""SQLAlchemy models for the Life Story application."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class User(Base):
    """User model representing a person whose life story is being collected."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    person_id = Column(String, unique=True, nullable=False, index=True)  # External person identifier
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    
    # OAuth2 fields
    oauth_provider = Column(String, nullable=True)  # e.g., "google"
    oauth_id = Column(String, nullable=True, index=True)  # OAuth provider's user ID
    picture = Column(String, nullable=True)  # Profile picture URL from OAuth provider
    
    # LLM Permission
    can_use_llm = Column(Boolean, default=False, nullable=False)  # Permission to make LLM API calls (costs money)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    answers = relationship("Answer", back_populates="user", cascade="all, delete-orphan")
    story_chapters = relationship("StoryChapter", back_populates="user", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="user", cascade="all, delete-orphan")


class Chapter(Base):
    """Chapter model representing predefined chapters in the life story."""
    
    __tablename__ = "chapters"
    
    id = Column(String, primary_key=True)  # e.g., "1", "2", etc.
    title = Column(String, nullable=False)
    order = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    answers = relationship("Answer", back_populates="chapter")
    story_chapters = relationship("StoryChapter", back_populates="chapter")


class Answer(Base):
    """Answer model representing a user's answer to a question."""
    
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint('user_id', 'chapter_id', 'question_id', name='uq_user_chapter_question'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String, nullable=False, index=True)  # e.g., "1-01", "2-05"
    text = Column(Text, nullable=False)
    audio_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="answers")
    chapter = relationship("Chapter", back_populates="answers")


class StoryChapter(Base):
    """StoryChapter model representing a generated narrative for a chapter."""
    
    __tablename__ = "story_chapters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    narrative = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)  # 100-200 word summary of the chapter
    style_guide = Column(Text, nullable=True)
    context_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="story_chapters")
    chapter = relationship("Chapter", back_populates="story_chapters")


class Story(Base):
    """Story model representing a compiled full life story book."""
    
    __tablename__ = "stories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    book_text = Column(Text, nullable=False)
    style_guide = Column(Text, nullable=True)
    chapters_used = Column(Integer, default=0, nullable=False)
    compiled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="stories")

