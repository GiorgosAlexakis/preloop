"""Issue Duplicate model."""
from __future__ import annotations


from sqlalchemy import Column, DateTime, ForeignKey, String, func, Text
from sqlalchemy.orm import relationship

from .base import Base


class IssueDuplicate(Base):
    """Issue Duplicate model."""

    __tablename__ = "issue_duplicate"

    issue1_id = Column(String, ForeignKey("issue.id"), nullable=False)
    issue2_id = Column(String, ForeignKey("issue.id"), nullable=False)
    decision = Column(String, nullable=False)
    decision_at = Column(DateTime, server_default=func.now())
    llm_model_id = Column(String, ForeignKey("llm_model.id"), nullable=False)
    llm_model_name = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    issue1 = relationship("Issue", foreign_keys=[issue1_id])
    issue2 = relationship("Issue", foreign_keys=[issue2_id])
    llm_model = relationship("LLMModel", foreign_keys=[llm_model_id])
