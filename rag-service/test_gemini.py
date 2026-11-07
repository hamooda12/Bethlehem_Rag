import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

result = client.models.embed_content(
    model="gemini-embedding-001",
    contents="ما هي شروط التسجيل في الجامعة؟",
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768
    )
)

vector = result.embeddings[0].values

print("Gemini connected successfully")
print("Embedding dimensions:", len(vector))