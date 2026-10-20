from google import genai

# Replace with your new 'mediskye' project ID!
client = genai.Client(vertexai=True, project="mediskye-backend", location="us-central1")

for m in client.models.list():
    if "gemini" in m.name:
        print(m.name)