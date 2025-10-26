from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserCard(Base):
    __tablename__ = "user_cards"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    card = relationship("Card")

    def get_code(self):
        """Returns the code of the linked card."""
        return self.card.code if self.card else None
