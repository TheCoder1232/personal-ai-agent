import requests
import json

response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": "Bearer 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",
    "Content-Type": "application/json",
  },
  data=json.dumps({
    "model": "z-ai/glm-4.5-air:free",
    "messages": [
      {
        "role": "user",
        "content": "Answer in one word; Example: 1+2=3; Question: 2+4=?"
      }
    ],
    
  })
)

res = json.loads(response.text)
print(res)
