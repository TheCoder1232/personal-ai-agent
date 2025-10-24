# print a simple completion
import litellm
# import os
# import pprint

# pprint.pprint(dict(os.environ))

# output = litellm.completion(model="gemini/gemini-2.5-flash",
#                 messages=[{"role": "user", "content": "Hello how are you"}],
#                 max_tokens=1000)

# print(output)


# list openrouter litellm supported models

# models = litellm.openrouter_models

# free_models = set()
# for model in models:
#     if "free" in model:
#         free_models.add(model)
# print(free_models)


import litellm
import os

messages = [
    {
        "role": "user",
        "content": "Hello! Write a three-line poem about a computer."
    }
]
try:
    response = litellm.completion(
        model="openrouter/meta-llama/llama-3-8b-instruct",
        messages=messages,
        api_key="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"
    )
    print("\n--- Full Response Object ---")
    print(response)

  
except Exception as e:
    print(f"\nAn error occurred: {e}")