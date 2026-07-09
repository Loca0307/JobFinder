from pydantic import BaseModel



# Data schema used in app and noSQL database
class Job(BaseModel):
    name: str
    description: str
