from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from Crypto.Cipher import AES
import time
import urllib.parse
import binascii
import requests
import json
import yagmail
import hashlib

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
HASH_KEY = "iypgxuabOx2fjI8zhSua1y4PQX0iU3WL"
HASH_IV = "CpgkDEc5fUm9tt4P"
MERCHANT_ID = "MS355719396"

class PaymentRequest(BaseModel):
    email: str
    amount: int
    companyName: str
    # order_id: str

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
    try:
        # 將 hex 轉換為 bytes
        encrypted_bytes = binascii.unhexlify(encrypted_hex)
        
        # 建立 AES 解密器（使用 CBC 模式）
        cipher = AES.new(HASH_KEY.encode('utf-8'), AES.MODE_CBC, HASH_IV.encode('utf-8'))
        
        # 解密並去除 padding
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        decrypted_text = strip_padding(decrypted_bytes)

        return decrypted_text
    except Exception as e:
        print("❌ 解密失敗：", str(e))
        return "Decryption failed"

def send_email(email, subject, body):
    yag = yagmail.SMTP("happy.it.engineer@gmail.com", "kvxxurwgcihmsqca")  # 建議開啟 2FA
    # yag.send(to="jia@ha-pp-y.com", subject=subject, contents=body)
    yag.send(to=email, subject=subject, contents=body)


@app.get("/ping")
def ping():
    return {"status": "ok"}



order_email_map = {}

@app.post("/create-payment")
def create_payment(req: PaymentRequest):
    timeStamp = str(int(time.time()))
    order_email_map[timeStamp] = {
        "email": req.email,
        "company": req.companyName
    }  # ✅ 儲存 Email

    # Step 1: 生成請求字串
    # safe_email = req.email.replace("@", "_at_").replace(".", "_dot_")
    # order_id = f"ORDER_{int(time.time())}_{safe_email}"  # 把使用者 ID 放進去
    # payload = {
    #     "MerchantID": MERCHANT_ID,
    #     "RespondType": "JSON",
    #     "TimeStamp": timeStamp,
    #     "Version": "2.0",
    #     "LangType": "zh-tw",
    #     "MerchantOrderNo": timeStamp,
    #     "Amt": str(req.amount),
    #     "ItemDesc": "即時付款訂閱",
    #     "Email": req.email,
    #     "EmailModify": "1",
    #     "CREDIT": "1",
    #     "NotifyURL": "https://happydraft4-newebpay.onrender.com/payment/notify",
    #     "ReturnURL": "https://ha-pp-y.kitchen/success"
    # }
    payload = {
        "MerchantID": "MS355719396",
        "RespondType": "JSON",
        "TimeStamp": timeStamp,
        "Version": "1.5",
        "LangType": "zh-Tw",
        "MerOrderNo": timeStamp,
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
        "ReturnURL": "https://happydraft4-newebpay.onrender.com/newebpay-return",  # ✅ 自動跳轉
        
        # "ClientBackURL": "https://ha-pp-y.kitchen/account",  # ✅ 一般一次性交易顯示一個 「返回商店」按鈕，使用者手動跳轉

    }

    # 把「鍵值對的字典」轉換成「URL query string 形式」
    raw = urllib.parse.urlencode(payload)
    # print("🔍 加密前:", raw)

    # Step2: 將請求字串加密
    encrypted = aes_encrypt(raw)
    # print("🔒 加密後:",encrypted)
    # hashstr = f"HashKey={HASH_KEY}&{encrypted}&HashIV={HASH_IV}"
    # trade_sha = (hashlib.sha256(hashstr.encode("utf-8")).hexdigest()).upper()

    # Step3: 發布請求 
    # return {
    #     "MerchantID": MERCHANT_ID,
    #     "TradeInfo": encrypted,
    #     "TradeSha": trade_sha,
    #     "Version": "2.0",
    #     "ActionURL": "https://ccore.newebpay.com/MPG/mpg_gateway"
    # }
    return {
        "MerchantID_": MERCHANT_ID,
        "PostData_": encrypted,
        "ActionURL": "https://ccore.newebpay.com/MPG/period"
    }

# Step4: 結果
@app.post("/payment/notify")
async def payment_notify(request: Request):
    form = await request.form()
    print("📩 收到 Notify POST")
    print("📦 原始內容：", dict(form))
    
    # encrypted = form.get("TradeInfo")
    # ✅ 定期定額使用 Period 欄位
    encrypted = form.get("Period")
    if not encrypted:
        return "0|No Period"

    # Step5: 將加密字串進行解密
    decrypted = aes_decrypt(encrypted)
    print("🔓 解密後內容：", decrypted)

    data = json.loads(decrypted)
    result = data.get("Result", {})

    # 👉 根據訂單號碼找 email
    order_no = result.get("MerchantOrderNo")
    # email = order_email_map.get(order_no, "無紀錄 Email")
    amt = result.get("PeriodAmt")

    # ✅ 從訂單記憶中找回 Email，若找不到就給預設值
    order = order_email_map.get(order_no, {})
    email = order.get("email", "unknown@example.com")
    company = order.get("company", "未知公司")

    # ✅ 加入 email 到傳送資料中
    result["PayerEmail"] = email
    result["CompanyName"] = company

    # ✅ 傳給 Google Apps Script
    try:
        gsheet_url = "https://script.google.com/macros/s/AKfycbxJiz4ytGDaa9bi570MdJEALrpmrbD1bnWJVgO5FR1aaguRkDbsKLrPXi_5KxUKkp5Amg/exec"
        gsheet_response = requests.post(gsheet_url, json=result)
        print("📤 已送出至 Google Sheets:", gsheet_response.text)
    except Exception as e:
        print("⚠️ 發送 Google Sheets 失敗:", str(e))
    
    print("✉️ 收到付款通知email寄出")
    send_email(email, f"ha-pp-y™ Kitchen 訂閱通知 - {order_no}", f"您好，\n\n您的訂單 {order_no} 已成功付款 {amt} 元，\n\n感謝您的訂閱！")

    return "1|OK"




@app.post("/alter-status")
def alter_status(order_id: str, period_no: str, action: str):  
    # action: suspend / terminate / restart
    payload = {
        "RespondType": "JSON",
        "Version": "1.0",
        "TimeStamp": str(int(time.time())),
        "MerOrderNo": order_id,
        "PeriodNo": period_no,
        "AlterType": action.lower()
    }

    raw = urllib.parse.urlencode(payload)
    encrypted = aes_encrypt(raw)

    post_data = {
        "MerchantID_": MERCHANT_ID,
        "PostData_": encrypted
    }

    try:
        url = "https://ccore.newebpay.com/MPG/period/AlterStatus"  # ✅ 測試環境網址
        res = requests.post(url, data=post_data)
        res_data = res.json()

        # 解密回傳
        if "period" in res_data:
            decrypted = aes_decrypt(res_data["period"])
            print("🔓 修改狀態結果:", decrypted)
            return json.loads(decrypted)
        else:
            return {"error": "Missing period data in response"}

    except Exception as e:
        return {"error": str(e)}




@app.post("/newebpay-return")
async def newebpay_return(request: Request):
    # ✅ 付款成功導回此頁 → 自動轉 GET 頁面
    form = await request.form()
    print("🔁 回傳資料：", dict(form))

    # 從表單取出訂單編號（如有）
    order_no = form.get("MerchantOrderNo", "")
    status = form.get("Status", "")
    period = form.get("Period", "")
    result = "unknown"
    
    if status == "SUCCESS" and period:
        decrypted = aes_decrypt(period)
        print("🔓 ReturnURL 解密結果:", decrypted)

        try:
            data = json.loads(decrypted)
            result = "success"
        except:
            result = "error"
    else:
        result = "fail"

    # ✅ 導回前端，帶參數
    return RedirectResponse(
        url=f"https://ha-pp-y.kitchen/newebpay-return?status={result}&order={order_no}",
        status_code=303
    )
    
    # return RedirectResponse(url="https://ha-pp-y.kitchen/account", status_code=303)