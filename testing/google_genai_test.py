from google import genai

client = genai.Client(api_key="AIzaSyC0YkeRjpEu4RfWNXsZHnTSyYWye6EyjrA")

response = client.models.generate_content(
  model='gemini-2.5-flash',
  contents='why is the sky blue?',
)

print(response.text) # output is often markdown