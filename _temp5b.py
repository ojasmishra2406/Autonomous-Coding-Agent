
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
import datetime
import time
client = genai.Client()
for i in range(5):
    try:
        response = client.models.generate_content(model='gemini-3.7-flash', contents='Say hello')
        break
    except Exception as e:
        print(f"Attempt failed: {e}")
        if i == 4: raise
        time.sleep(10)
print(f"Model version: {response.model_version}")
print(f"Date: {datetime.date.today()}")
