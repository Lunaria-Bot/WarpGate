import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

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

    def __init__(self, character_name, form, image_url, series=None, description=None, event_name=None):
        self.character_name = character_name
        self.form = form
        self.image_url = image_url
        self.series = series
        self.description = description
        self.event_name = event_name
        self.created_at = datetime.utcnow()
        self.uuid = uuid.uuid4()
        self.code = self.generate_code()

    def generate_code(self):
        timestamp = int(self.created_at.timestamp())
        short = str(self.uuid).split("-")[0].upper()
        return f"{self.id}-{short}-{timestamp}"
