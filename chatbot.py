from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
import sqlite3
import os
from dotenv import load_dotenv
import mimetypes

# Tải các biến môi trường từ file .env
load_dotenv()
gemini_api_key = os.getenv('GEMINI_API_KEY') # Đảm bảo file .env của bạn ghi: GEMINI_API_KEY="AIzaSy..."

app = Flask(__name__)
CORS(app)

# Khởi tạo Client theo thư viện google.genai MỚI NHẤT
client = genai.Client(api_key=gemini_api_key)
MODEL_ID = 'gemini-2.5-flash' # Sử dụng model xịn nhất trong danh sách của bạn

# ==========================================
# CẤU HÌNH DATABASE SQLITE
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ChatHistory (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            UserId INTEGER,
            UserMessage TEXT,
            BotReply TEXT,
            CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# CÁC HÀM XỬ LÝ LOGIC CHAT
# ==========================================
def is_unwanted_topic(message):
    unwanted_keywords = [
        'lập trình', 'code', 'thời trang', 'quần áo', 'giày dép', 'game', 'nấu ăn', 'thể thao'
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in unwanted_keywords)

def is_greeting(message):
    greetings = ['xin chào', 'chào', 'hello', 'hi', 'alo', 'ê', 'cho hỏi']
    message_lower = message.lower()
    return any(message_lower.startswith(g) for g in greetings)

def is_finance_related(message):
    finance_keywords = [
        'vay', 'tiền mặt', 'trả góp', 'thẻ tín dụng', 'jcb', 'lãi suất', 'nợ xấu', 
        'giải ngân', 'hồ sơ', 'cccd', 'thẩm định', 'hạn mức', 'phí', 'đáo hạn', 
        'tài chính', 'fe credit', 'tín chấp', 'cà vẹt', 'mua xe', 'mua điện thoại'
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in finance_keywords)

# ==========================================
# API ENDPOINT CHÍNH
# ==========================================
@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.form.get('message', '').strip()
    image_file = request.files.get('image')
    user_id_raw = request.form.get("user_id", "0")

    user_id = int(user_id_raw)

    if not user_message and not image_file:
        return jsonify({'error': 'Message or image is required'}), 400

    try:
        # 1. Lấy lịch sử hội thoại từ SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT UserMessage, BotReply
            FROM ChatHistory
            WHERE UserId = ?
            ORDER BY CreatedAt DESC
            LIMIT 10
        """, (user_id,))
        history = cursor.fetchall()
        
        # Format lịch sử chat cho SDK mới
        chat_history_list = []
        for h in reversed(history):
            chat_history_list.append(
                types.Content(role="user", parts=[types.Part.from_text(text=h['UserMessage'])])
            )
            chat_history_list.append(
                types.Content(role="model", parts=[types.Part.from_text(text=h['BotReply'])])
            )
        
        # 2. Xử lý trường hợp khách gửi Ảnh
        if image_file:
            os.makedirs("uploads", exist_ok=True)
            image_path = os.path.join("uploads", image_file.filename)
            image_file.save(image_path)

            mime_type, _ = mimetypes.guess_type(image_path)
            with open(image_path, "rb") as f:
                image_data = f.read()

            image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
            prompt_text = f"Khách hàng gửi ảnh này và hỏi: '{user_message}'. Hãy trả lời dưới tư cách là trợ lý tư vấn tài chính FE Credit."

            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[image_part, prompt_text]
            )
            reply = response.text.strip()

        # 3. Xử lý trường hợp chỉ có Tin nhắn văn bản
        else:
            if is_greeting(user_message) and not is_finance_related(user_message):
                reply = "Xin chào! Mình là trợ lý AI của chuyên viên Tô Văn Tới. Bạn đang quan tâm đến gói Vay tiền mặt, Mở thẻ tín dụng hay Mua trả góp bên FE Credit ạ?"
            elif is_unwanted_topic(user_message):
                reply = "Dạ, mình là trợ lý chuyên tư vấn các giải pháp tài chính và vay vốn tại FE Credit. Rất tiếc mình không thể hỗ trợ chủ đề này. Bạn có nhu cầu tìm hiểu về các gói vay không ạ?"
            else:
                # Kiến trúc System Prompt cho SDK mới
                system_instruction_text = """
                Bạn là trợ lý ảo xuất sắc của Tô Văn Tới - Chuyên Viên Tư Vấn Tài Chính tại FE Credit.
                Thông tin liên hệ của Tô Văn Tới: SĐT/Zalo: 0359272229.
                Nhiệm vụ của bạn là tư vấn nhiệt tình, lịch sự, xưng "mình" và gọi khách là "bạn/anh/chị". 
                Dưới đây là thông tin các gói dịch vụ bạn cần nắm rõ để tư vấn:
                1. Vay Tiền Mặt: Hỗ trợ 3-100 triệu, chỉ cần CCCD gắn chip, không giữ giấy tờ gốc, giải ngân 24h.
                2. Thẻ Tín Dụng JCB PLUS: Đặc quyền 5 KHÔNG (Không phí thường niên, không phí rút ATM, không chờ thẻ cứng, không rườm rà giấy tờ, không giới hạn ưu đãi).
                3. Góp Xe Máy: Trả trước từ 20%, nhận ngay Cà vẹt gốc, duyệt 15 phút.
                4. Góp Điện Thoại/Điện Máy: Lãi suất từ 0.99%, duyệt siêu tốc.
                5. Nợ xấu: Nợ chú ý (nhóm 1, 2) đã tất toán có thể xem xét. Nhóm 3 trở lên chưa hỗ trợ.
                Quy tắc trả lời:
                - Rất ngắn gọn, súc tích, đi thẳng vào vấn đề khách hỏi.
                - Nếu khách hỏi điều kiện, thủ tục phức tạp hoặc muốn làm hồ sơ, luôn điều hướng khách liên hệ trực tiếp Zalo Tô Văn Tới (0359272229) để được hỗ trợ lên hồ sơ nhanh nhất.
                - Trả lời bằng định dạng dễ đọc (gạch đầu dòng nếu cần).
                """
                
                # Khởi tạo phiên chat với lịch sử và System Prompt
                chat = client.chats.create(
                    model=MODEL_ID,
                    history=chat_history_list,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction_text,
                        temperature=0.7
                    )
                )
                
                response = chat.send_message(user_message)
                reply = response.text.strip()

        # 4. Lưu lịch sử hội thoại mới vào SQLite
        cursor.execute(
            "INSERT INTO ChatHistory (UserMessage, BotReply, UserId) VALUES (?, ?, ?)",
            (user_message, reply, user_id)
        )
        conn.commit()
        conn.close()

        return jsonify({'reply': reply})

    except Exception as e:
        import traceback
        print("Lỗi API:", e)
        traceback.print_exc()
        return jsonify({'reply': '❌ Lỗi kết nối đến máy chủ AI. Bạn vui lòng liên hệ trực tiếp Zalo 0359272229 để được hỗ trợ nhé.'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5050)