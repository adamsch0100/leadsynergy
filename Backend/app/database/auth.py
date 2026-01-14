import datetime
import os
from datetime import timedelta

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")
supabase = create_client(supabase_url=URL, supabase_key=KEY)

random_email: str = "adam@saahomes.com"
random_password: str = "Vitzer0100!"
original_email = "kenzakishiro123@gmail.com"
original_password = "Lansilotskey@123"
# response = supabase.auth.sign_up(
#     {
#         "email": "kenzakishiro123@gmail.com",
#         "password": "Lansilotskey@123",
#     }
# )
response = supabase.auth.sign_in_with_password({
    "email": original_email,
    "password": original_password
})

print(response.model_dump_json())