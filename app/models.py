from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(32), primary_key=True)
    filename = Column(String(255), nullable=False)
    feature_count = Column(Integer, nullable=False)
    crs = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    source_type = Column(String(32), nullable=False)
    features_json = Column(Text, nullable=False)
