from dotenv import load_dotenv
from google import genai

load_dotenv()  # Automatically loads GOOGLE_APPLICATION_CREDENTIALS, PROJECT, and LOCATION

# Initialize Vertex AI client (automatically reads your .env variables)
client = genai.Client(vertexai=True)

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Reply with 'Vertex AI is connected!' if you receive this."
)

print(response.text)