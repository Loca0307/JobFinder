from pydantic import Basemodel



# Data schema used in app and noSQL database
class Job(Basemodel):
    name: str
    description: str