from openai import OpenAI
from config.config import OPENAI_API_KEY

import os
client = OpenAI(api_key=OPENAI_API_KEY)

response = client.embeddings.create(
    model="text-embedding-3-small",
    input="Hello from Chicago!"
)

print(response.data[0].embedding[:5])  # first 5 numbers
