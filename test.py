import google.generativeai as genai

# Điền trực tiếp API Key của bạn vào đây (chỉ để test)
API_KEY = "AIzaSyCgWfCUPKKkF3Z5X2-ANgwJZR9NyihNLjk" 
genai.configure(api_key=API_KEY)

print("Đang quét danh sách các Model AI mà bạn có thể sử dụng...")
print("-" * 50)

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"👉 Dùng được: {m.name}")
except Exception as e:
    print("Lỗi:", e)