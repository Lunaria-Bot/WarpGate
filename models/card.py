import uuid
import random
import string
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def generate_short_code(length=4) -> str:
    charset = string.ascii_lowercase + string.digits
    return ''.join(random.choices(charset, k=length))

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    character_name = Column(String, nullable=False)
    form = Column(Enum("base", "awakened", "event", name="card_form"), default="base", nullable=False)
    image_url = Column(String, nullable=False)
    series = Column(String, nullable=True)
    description = Column(Text)
    event_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def generate_code(self):
        """Generates a short randomized code like '7vst'."""
        return generate_short_code()
