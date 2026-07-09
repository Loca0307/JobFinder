from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String


Base = declarative_base()


# Data ORM model for SQL database
class Job(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)