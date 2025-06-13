from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.requests import Request
from pydantic import BaseModel
from Crypto.Cipher import AES
from datetime import datetime
import pytz
import time
import urllib.parse
import binascii
import requests
import json
import yagmail
import hashlib
import requests

app = FastAPI()

# ✅ 加上這段：允許從 Framer Canvas 來的請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://framer.com",
        # "https://*.framercanvas.com",
        "https://ha-pp-y.kitchen",  # 改成你的 Framer 網域
    ],
    # allow_origins=["*"], # 測試開發中可以先允許所有網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 正式用密鑰
# HASH_KEY = "OKEaRtuSXR9pKozzvj4Fq3EYNc8W92jj"
# HASH_IV = "PSqcgIiqkWrLmppC"
# MERCHANT_ID = "MS3780269062"

# 測試用密鑰（請換成實際值）
HASH_KEY = "iypgxuabOx2fjI8zhSua1y4PQX0iU3WL"
HASH_IV = "CpgkDEc5fUm9tt4P"
MERCHANT_ID = "MS355719396"

class PaymentRequest(BaseModel):
    email: str
    amount: int
    companyName: str
    taxId: str
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


@app.get("/ip")
async def get_ip(request: Request):
    ip = request.client.host
    print(f"🌐 Client IP: {ip}")
    # https://happydraft4-newebpay.onrender.com/ip
    # {"ip":"111.243.102.121"}
    # {"ip":"111.243.89.57"} # 5/6 本機對外網路 public ip

    # https://api.ipify.org/
    return {"ip": ip}

@app.get("/my-egress-ip")
def get_my_egress_ip():
    try:
        ip = requests.get("https://api.ipify.org").text
        # https://happydraft4-newebpay.onrender.com/my-egress-ip
        # {"egress_ip":"34.211.200.85"}
        return {"egress_ip": ip}
    except Exception as e:
        return {"error": str(e)}

order_email_map = {}

@app.post("/create-payment")
def create_payment(req: PaymentRequest):
    timeStamp = str(int(time.time()))

    # Step 1: 生成請求字串
    # safe_email = req.email.replace("@", "_at_").replace(".", "_dot_")

    # 設定台北時區
    taipei_tz = pytz.timezone('Asia/Taipei')
    # 獲取當前UTC時間並轉換為台北時間
    taipei_time  = datetime.now(pytz.UTC).astimezone(taipei_tz)
    # 格式化為年月日時分秒
    date_str = taipei_time.strftime("%Y%m%d%H%M%S")
    taxId = req.taxId[0:4]
    order_id = f"{date_str}{taxId}"  # 把使用者 ID 放進去
    order_email_map[order_id] = {
        "email": req.email,
        "company": req.companyName
    }  # ✅ 儲存 Email
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
        "MerOrderNo": order_id,
        "ProdDesc": "訂閱方案",
        "PeriodAmt": str(req.amount),
        "PeriodType": "D",
        "PeriodPoint": "30",
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

    status = data.get("Status").lower()
    print("🔓 解密後status：", status)

    result = data.get("Result", {})

    gsheet_data = {
        "Status": status,                      # ✅ 主狀態
        "Message": data.get("Message", ""),    # ✅ 說明文字
        "Result": result                       # ✅ 內部交易欄位（你已解密）
    }

    # 👉 根據訂單號碼找 email
    order_no = result.get("MerchantOrderNo")
    # email = order_email_map.get(order_no, "無紀錄 Email")
    amt = result.get("PeriodAmt")

    # ✅ 從訂單記憶中找回 Email，若找不到就給預設值
    order = order_email_map.get(order_no, {})
    email = order.get("email", "")
    company = order.get("company", "")

    # ✅ 加入 email 到傳送資料中
    # result["Status"] = status
    result["PayerEmail"] = email
    result["CompanyName"] = company

    # ✅ 傳給 Google Apps Script
    try:
        gsheet_url = "https://script.google.com/macros/s/AKfycbzdlrJ3OS_Ao6CjjBfNZwgWLYVnoy4piCTGQWLBcVKByZtFXEhyhRJOn0FR0KP8ZoV3Ew/exec"
        gsheet_response = requests.post(gsheet_url, json=gsheet_data)
        print("📤 已送出至 Google Sheets:", gsheet_response.text)
    except Exception as e:
        print("⚠️ 發送 Google Sheets 失敗:", str(e))
    
    if email and status == "success":
        print("✉️ 收到付款通知email寄出")

        import textwrap
        contents = textwrap.dedent(f"""\
            您好，<br>
            您的訂閱編號 {order_no} 已成功付款 {amt} 元，<br>
            感謝您的訂閱！<br><br>
            本信件由系統自動發送，請勿直接回覆。<br>
            ha-pp-y™ Co.
        """)
        
        send_email(email, f"ha-pp-y™ Kitchen 訂閱成功 - {order_no}", contents)

    return "1|OK"


def generate_check_value(params: dict, hash_key: str, hash_iv: str) -> str:
    sorted_items = sorted(params.items())
    encoded_str = f"HashKey={hash_key}&" + urllib.parse.urlencode(sorted_items) + f"&HashIV={hash_iv}"
    encoded_str = encoded_str.lower()  # 根據藍新需全部轉小寫
    sha256 = hashlib.sha256()
    sha256.update(encoded_str.encode('utf-8'))
    return sha256.hexdigest().upper()

class AlterStatusRequest(BaseModel):
    order_id: str
    period_no: str
    action: str

@app.post("/alter-status")
def alter_status(req: AlterStatusRequest):  
    # action: suspend / terminate / restart
    print("📮 收到 POST /alter-status 請求")

    # ✅ Step 1: 準備 payload
    payload = {
        "RespondType": "JSON",
        "Version": "1.0",
        "TimeStamp": str(int(time.time())),
        "MerOrderNo": req.order_id,
        "PeriodNo": req.period_no,
        "AlterType": req.action.lower()
    }

    # ✅ Step 2: 加密 payload
    raw = urllib.parse.urlencode(payload)
    encrypted = aes_encrypt(raw)

    # ✅ Step 3: 建立簽章 CheckValue
    check_value = generate_check_value(payload, HASH_KEY, HASH_IV)

    post_data = {
        "MerchantID_": MERCHANT_ID,
        "PostData_": encrypted,
        "CheckValue": check_value
    }

    try:
        url = "https://ccore.newebpay.com/MPG/period/AlterStatus"  # ✅ 測試環境網址
        res = requests.post(url, data=post_data)
        print("🧾 藍新原始回傳:", res.text)
        try:
            res_data = res.json()
        except Exception:
            print("❌ 回傳不是 JSON，內容如下：")
            print(res.text)
            return {"error": "Non-JSON response", "raw": res.text}

        # 解密回傳
        if "period" in res_data:
            decrypted = aes_decrypt(res_data["period"])
            print("🔓 修改狀態結果:", decrypted)
            return json.loads(decrypted)
        else:
            print("⚠️ 未包含 period 欄位:", res_data)
            return {"error": "Missing period data in response"}

    except Exception as e:
        print("🔥 發生例外:", str(e))
        return {"error": str(e)}




@app.post("/newebpay-return")
async def newebpay_return(request: Request):
    # ✅ 付款成功導回此頁 → 自動轉 GET 頁面
    form = await request.form()
    print("🔁 回傳資料：", dict(form))
    
    # 從表單取出訂單編號（如有）
    order_no = form.get("MerchantOrderNo", "")

    # status = form.get("Status", "")
    # print("🔓 ReturnURL 解密 status 結果:", status)
    # period = form.get("Period", "")
    result = "unknown"
    
    # if status == "SUCCESS" and period:
    #     decrypted = aes_decrypt(period)
    #     print("🔓 ReturnURL 解密結果:", decrypted)

    #     try:
    #         data = json.loads(decrypted)
    #         result = "success"
    #     except:
    #         result = "error"
    # else:
    #     result = "fail"

    # 處理 Period 欄位 - 假設存在 Period 欄位就嘗試解密
    period_data = form.get("Period", "")
    if period_data:
        try:
            decrypted_period = aes_decrypt(period_data)
            print("🔓 ReturnURL 解密 Period 結果:", decrypted_period)
            
            try:
                data = json.loads(decrypted_period)
                print("✅ 解密成功並解析為 JSON:", data)

                # 檢查 Status 欄位
                if "Status" in data and data["Status"] == "SUCCESS":
                    result = "success"
                else:
                    result = "fail"
                
                # 從解密的資料中讀取訂單編號
                if "Result" in data and "MerchantOrderNo" in data["Result"]:
                    order_no = data["Result"]["MerchantOrderNo"]
                else:
                    print("⚠️ 找不到訂單編號")

            except json.JSONDecodeError:
                print("❌ JSON 解析失敗")
                result = "fail"
        except Exception as e:
            print(f"❌ Period 欄位解密失敗: {str(e)}")
            result = "fail"
    else:
        print("❌ 未找到 Period 欄位")
        result = "fail"


    redirect_url=f"https://ha-pp-y.kitchen/newebpay-return?status={result}&order={order_no}"
    print(f"🔄 重定向 URL: {redirect_url}")

    # ✅ 導回前端，帶參數
    return RedirectResponse(
        url=redirect_url,
        status_code=303
    )
    
    # return RedirectResponse(url="https://ha-pp-y.kitchen/account", status_code=303)







from fastapi import FastAPI, Request
from pydantic import BaseModel, EmailStr, constr
from fastapi.responses import JSONResponse
from typing import Literal, Optional
from urllib.parse import quote_plus
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import httpx
import os
from pydantic import Field
from datetime import datetime, timezone
from pydantic import field_validator
import re

# app = FastAPI()

class InvoiceRequest(BaseModel):
    merchantOrderNo: str
    invoiceType: Literal['B2C', 'B2B']
    buyerName: Optional[str] = ''
    # buyerUBN: Optional[constr(regex=r'^\d{8}$')] = ''
    # buyerUBN: Optional[str] = Field(default='', pattern=r'^\d{8}$')
    buyerUBN: Optional[str] = None
    email: EmailStr
    carrierType: Literal['', '1', '2']
    carrierNum: Optional[str] = ''
    donate: bool = False
    # loveCode: Optional[constr(regex=r'^\d{3,7}$')] = ''
    # loveCode: Optional[str] = Field(default='', pattern=r'^\d{3,7}$')
    loveCode: Optional[str] = None
    printFlag: bool = False
    address: Optional[str] = ''
    itemPrice: int
    itemAmt: int
    
    @field_validator('buyerUBN')
    def validate_buyerUBN(cls, v, info):
        if info.data.get('invoiceType') == 'B2B':
            if not v or not re.match(r'^\d{8}$', v):
                raise ValueError('統一編號需為 8 碼數字')
        return v

    @field_validator('loveCode')
    def validate_loveCode(cls, v, info):
        if info.data.get('donate'):
            if not v or not re.match(r'^\d{3,7}$', v):
                raise ValueError('捐贈碼需為 3~7 碼純數字')
        return v

def ezpay_aes_encrypt(data: str, key: str, iv: str) -> str:
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
    padded = pad(data.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode('utf-8')

@app.post("/api/invoice/issue")
async def issue_invoice(payload: InvoiceRequest):
    # MERCHANT_ID = os.getenv("EZP_MERCHANT_ID", "MS12345678")
    # HASH_KEY = os.getenv("EZP_HASH_KEY", "12345678901234567890123456789012")
    # HASH_IV = os.getenv("EZP_HASH_IV", "1234567890123456")

    MERCHANT_ID = "38090916"
    HASH_KEY = "qvEx2bToikTCD7Ia8D7bj8DyztGYFN7z"
    HASH_IV = "CqTeD1XWPVikNmUP"

    carrier_num_encoded = quote_plus(payload.carrierNum.strip()) if payload.carrierNum else ''

    now = int(datetime.now(timezone.utc).timestamp())
    is_b2b = payload.invoiceType == "B2B"

    post_data = {
        "MerchantID": MERCHANT_ID,
        "RespondType": "JSON",
        "Version": "1.5",
        "TimeStamp": str(now),
        "MerchantOrderNo": payload.merchantOrderNo,
        "Status": "1",
        "Category": payload.invoiceType,
        "BuyerName": payload.buyerName,
        "BuyerUBN": payload.buyerUBN,
        "BuyerEmail": payload.email,
        "CarrierType": payload.carrierType,
        "CarrierNum": carrier_num_encoded,
        "LoveCode": payload.loveCode,
        "PrintFlag": "Y" if payload.printFlag else "N",

        "TaxType": "1", # 應稅
        "TaxRate": 5, # 一般稅率/特種稅率？
        "Amt": 100, # 發票銷售額(未稅)
        "TaxAmt": 5, # 發票稅額
        "TotalAmt": 56614, # 發票總金額(含稅)

        "ItemName": "ha-pp-y™ Kitchen 訂閱",
        "ItemCount": "1",
        "ItemUnit": "月",
        "ItemPrice": payload.itemPrice,
        "ItemAmt": payload.itemAmt,
        "Comment": "感謝您的訂閱",
    }

    try:
        raw_data = "&".join(f"{k}={v}" for k, v in post_data.items() if v is not None)
        encrypted = ezpay_aes_encrypt(raw_data, HASH_KEY, HASH_IV)

        payload_to_send = {
            "MerchantID": MERCHANT_ID,
            "PostData_": encrypted
        }

        res = await httpx.post("https://cinv.ezpay.com.tw/Api/invoice_issue", data=payload_to_send)
        return res.json()

        print("模擬開立發票成功 (含 AES 加密)")

        return JSONResponse({
            "message": "模擬開立發票成功 (含 AES 加密)",
            "PostData_": encrypted,
            "RawData": raw_data
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})













# Linode proxy_main.py

# from fastapi import FastAPI
# import requests, urllib.parse, time
# from pydantic import BaseModel
# from Crypto.Cipher import AES
# import json
# import binascii
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI()

# # ✅ 加上這段 CORS 設定
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#     "https://framer.com",
##     "https://*.framercanvas.com",
#     "https://ha-pp-y.kitchen"
#     ],  # 或改成只允許 Framer 的網址，如 "https://framer.com"
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# 正式用密鑰
# HASH_KEY = "OKEaRtuSXR9pKozzvj4Fq3EYNc8W92jj"
# HASH_IV = "PSqcgIiqkWrLmppC"
# MERCHANT_ID = "MS3780269062"

# 測試用密鑰（請換成實際值）
# HASH_KEY = "iypgxuabOx2fjI8zhSua1y4PQX0iU3WL"
# HASH_IV = "CpgkDEc5fUm9tt4P"
# MERCHANT_ID = "MS355719396"

# class AlterStatusRequest(BaseModel):
#     order_id: str
#     period_no: str
#     action: str

# def pad(data: str):
#     pad_len = 32 - (len(data.encode('utf-8')) % 32)
#     return data + chr(pad_len) * pad_len

# def strip_padding(data: bytes) -> str:
#     """移除 PKCS7 Padding"""
#     padding_len = data[-1]
#     return data[:-padding_len].decode("utf-8")

# def aes_encrypt(data: str):
#     cipher = AES.new(HASH_KEY.encode('utf-8'), AES.MODE_CBC, HASH_IV.encode('utf-8'))
#     encrypted = cipher.encrypt(pad(data).encode('utf-8'))
#     return binascii.hexlify(encrypted).decode('utf-8')

# def aes_decrypt(encrypted_hex: str) -> str:
#     try:
#         # 將 hex 轉換為 bytes
#         encrypted_bytes = binascii.unhexlify(encrypted_hex)
        
#         # 建立 AES 解密器（使用 CBC 模式）
#         cipher = AES.new(HASH_KEY.encode('utf-8'), AES.MODE_CBC, HASH_IV.encode('utf-8'))
        
#         # 解密並去除 padding
#         decrypted_bytes = cipher.decrypt(encrypted_bytes)
#         decrypted_text = strip_padding(decrypted_bytes)

#         return decrypted_text
#     except Exception as e:
#         print("❌ 解密失敗：", str(e))
#         return "Decryption failed"


# @app.post("/alter-status")
# def proxy_alter_status(req: AlterStatusRequest):
#     print("📮 收到 POST /alter-status 請求")
#     payload = {
#         "RespondType": "JSON",
#         "Version": "1.0",
#         "TimeStamp": str(int(time.time())),
#         "MerOrderNo": req.order_id,
#         "PeriodNo": req.period_no,
#         "AlterType": req.action.lower()
#     }
#     print("📮 請求內容:", payload)

#     raw = urllib.parse.urlencode(payload)
#     encrypted = aes_encrypt(raw)  # 替換成你的加密函式
#     print("🔐 加密後:", encrypted)

#     post_data = {
#         "MerchantID_": MERCHANT_ID,
#         "PostData_": encrypted
#     }

#     try:
#         res = requests.post("https://core.newebpay.com/MPG/period/AlterStatus", data=post_data)
#         print("🧾 藍新原始回傳:", res.text)

#         try:
#             res_data = res.json()
#         except Exception:
#             print("❌ 回傳不是 JSON，內容如下：")
#             print(res.text)
#             return {"error": "Non-JSON response", "raw": res.text}

#         # 解密回傳
#         if "period" in res_data:
#             decrypted = aes_decrypt(res_data["period"])
#             print("🔓 修改狀態結果:", decrypted)
#             # 將解密後的資料轉為字典
#             result = json.loads(decrypted)
#             # ✅ 傳送到 Google Sheets（Apps Script URL）
#             try:
#                 gsheet_url = "https://script.google.com/macros/s/AKfycbzdlrJ3OS_Ao6CjjBfNZwgWLYVnoy4piCTGQWLBcVKByZtFXEhyhRJOn0FR0KP8ZoV3Ew/exec"
#                 gsheet_response = requests.post(gsheet_url, json=result)
#                 print("📤 已送出至 Google Sheets:", gsheet_response.text)
#             except Exception as e:
#                 print("⚠️ 發送 Google Sheets 失敗:", str(e))
#             return result

#         else:
#             print("⚠️ 未包含 period 欄位:", res_data)
#             return {"error": "Missing period data in response"}
#         # return {"status": res.status_code, "result": res.text}
#     except Exception as e:
#         print("🔥 發生例外:", str(e))
#         return {"error": str(e)}

# 修改狀態結果: {"Status":"PER10074","Message":"\u672cAPI\u9650\u5be9\u6838\u5f8c\u4f7f\u7528\uff0c\u5982\u9700\u4f7f\u7528\u8acb\u6d3d\u5ba2\u670d\u4eba\u54e1","Result":{"Version":"1.0","TimeStamp":"1747217829","MerOrderNo":"202505051256529025","PeriodNo":"P250505125718IMUM5i","RespondType":"JSON","AlterType":"suspend"}}











# 取得 SSL 憑證後
# server {
#     listen 443 ssl;
#     server_name api.ha-pp-y.kitchen;  # ✅ 改成你自己的網域或 Public IP

#     ssl_certificate /etc/letsencrypt/live/api.ha-pp-y.kitchen/fullchain.pem;       # 🔁 用 Let's Encrypt 憑證或自簽
#     ssl_certificate_key /etc/letsencrypt/live/api.ha-pp-y.kitchen/privkey.pem;

#     location / {
#         proxy_pass http://127.0.0.1:3000;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#     }
# }

# # Optional HTTP redirect
# server {
#     listen 80;
#     server_name api.ha-pp-y.kitchen;

#     return 301 https://$host$request_uri;
# }


# 取得 SSL 憑證前
# server {
#     listen 80;
#     server_name ha-pp-y.kitchen;

#     root /var/www/html;
#     index index.html;

#     location / {
#         try_files $uri $uri/ =404;
#     }
# }
