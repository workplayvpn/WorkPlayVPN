"""Persistent encrypted import address for each account subscription tier."""
from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class HappImportLink(Base):
    __tablename__ = "happ_import_links"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    access_tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_url: Mapped[str] = mapped_column(Text, nullable=False)
