try:
    import pandas
    print("pandas installed successfully")
except ImportError as e:
    print(f"Error importing pandas: {e}")

try:
    import openpyxl
    print("openpyxl installed successfully")
except ImportError as e:
    print(f"Error importing openpyxl: {e}")

try:
    import dotenv
    print("python-dotenv installed successfully")
except ImportError as e:
    print(f"Error importing dotenv: {e}")

try:
    import google.generativeai
    print("google-generativeai installed successfully")
except ImportError as e:
    print(f"Error importing google.generativeai: {e}")

try:
    import requests
    print("requests installed successfully")
except ImportError as e:
    print(f"Error importing requests: {e}")

try:
    from PIL import Image
    print("Pillow installed successfully")
except ImportError as e:
    print(f"Error importing Pillow: {e}")

try:
    from linkedin_api import Linkedin
    print("linkedin-api installed successfully")
except ImportError as e:
    print(f"Error importing linkedin-api: {e}")

try:
    import google.auth
    print("google-auth installed successfully")
except ImportError as e:
    print(f"Error importing google-auth: {e}") 