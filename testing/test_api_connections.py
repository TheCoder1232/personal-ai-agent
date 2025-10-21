import litellm
# import os
# import pprint

# pprint.pprint(dict(os.environ))

output = litellm.completion(model="gemini/gemini-2.5-flash",
                messages=[{"role": "user", "content": "Hello how are you"}],
                max_tokens=1000)

print(output)

