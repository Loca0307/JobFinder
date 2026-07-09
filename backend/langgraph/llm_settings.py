import os

from langchain_openai import ChatOpenAI



def get_model() -> ChatOpenAI:
  return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL"),
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY"),
        )