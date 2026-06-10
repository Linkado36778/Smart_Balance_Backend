import os
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv()

print("Testing environment variable access...")
print(f"Production: {os.getenv("USERNAME")}")

# for chave, valor in os.environ.items():
#     print(f"{chave}: {valor}")
