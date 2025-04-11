from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from Crypto.Cipher import AES
import time
import urllib.parse
import binascii

app = FastAPI()

# ✅ 加上這段：允許從 Framer Canvas 來的請求
app.add_middleware(
    CORSMiddleware,
    # allow_origins=[
    #     "https://ha-pp-y.kitchen/",  # 改成你的 Framer 網域
    # ],
    allow_origins=["*"], # 測試開發中可以先允許所有網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 測試用密鑰（請換成實際值）
HASH_KEY = "OKEaRtuSXR9pKozzvj4Fq3EYNc8W92jj"
HASH_IV = "PSqcgIiqkWrLmppC"
MERCHANT_ID = "MS3780269062"

class PaymentRequest(BaseModel):
    email: str
    amount: int
    order_id: str

def pad(data: str):
    pad_len = 32 - (len(data.encode('utf-8')) % 32)
    return data + chr(pad_len) * pad_len

def aes_encrypt(data: str):
    cipher = AES.new(HASH_KEY.encode('utf-8'), AES.MODE_CBC, HASH_IV.encode('utf-8'))
    encrypted = cipher.encrypt(pad(data).encode('utf-8'))
    return binascii.hexlify(encrypted).decode('utf-8')

def strip_padding(data: bytes) -> str:
    """移除 PKCS7 Padding"""
    padding_len = data[-1]
    return data[:-padding_len].decode("utf-8")

def aes_decrypt(encrypted_hex: str) -> str:
    # 將 hex 轉換為 bytes
    encrypted_bytes = binascii.unhexlify(encrypted_hex)
    
    # 建立 AES 解密器（使用 CBC 模式）
    cipher = AES.new(HASH_KEY.encode('utf-8'), AES.MODE_CBC, HASH_IV.encode('utf-8'))
    
    # 解密並去除 padding
    decrypted_bytes = cipher.decrypt(encrypted_bytes)
    decrypted_text = strip_padding(decrypted_bytes)

    return decrypted_text

@app.post("/create-payment")
def create_payment(req: PaymentRequest):
    # Step 1: 生成請求字串
    payload = {
        "RespondType": "JSON",
        "TimeStamp": str(int(time.time())),
        "Version": "1.5",
        "LangType": "zh-Tw",
        "MerOrderNo": req.order_id,
        "ProdDesc": "訂閱方案",
        "PeriodAmt": str(req.amount),
        "PeriodType": "M",
        "PeriodPoint": "05",
        "PeriodStartType": "2",
        "PeriodTimes": "12",
        "PayerEmail": req.email,
        "PaymentInfo": "Y",
        "OrderInfo": "N",
        "EmailModify": "1",
        "NotifyURL": "https://happydraft4-newebpay.onrender.com/payment/notify",  # 改成你實際的網址
    }

    # 把「鍵值對的字典」轉換成「URL query string 形式」
    raw = urllib.parse.urlencode(payload)

    # Step2: 將請求字串加密
    encrypted = aes_encrypt(raw)
    # print("🔒encrypted:",encrypted)

    return {
        "MerchantID_": MERCHANT_ID,
        "PostData_": encrypted,
        "ActionURL": "https://ccore.newebpay.com/MPG/period"
    }

# Step4: 結果
@app.post("/payment/notify")
async def payment_notify(request: Request):
    form = await request.form()
    encrypted = form.get("TradeInfo")

    if not encrypted:
        return "0|No TradeInfo"

    # Step5: 將加密字串進行解密
    decrypted = aes_decrypt(encrypted)
    print("🔓 解密後內容：", decrypted)
    return "1|OK"