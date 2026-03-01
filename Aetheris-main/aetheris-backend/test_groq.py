import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
try:
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    completion = client.chat.completions.create(
        model='llama3-70b-8192',
        messages=[{'role': 'user', 'content': 'test'}]
    )
    print("Success:", completion.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
