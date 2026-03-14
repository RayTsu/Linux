from flask import Flask, request, jsonify
import requests
import json
import logging
import datetime
import os

app = Flask(__name__)

# ======================
# 日志配置
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(funcName)s:%(lineno)s] %(message)s"
)

# ======================
# 接口配置
# ======================
# Token 获取接口（使用 Basic 认证）
TOKEN_API = "http://test.7ieis.com/api/identity/Account/Simulate"
TOKEN_CODE = "10004"
AUTH_HEADER = "Basic VE9PTDpscUAjMTIz"  # 固定的 Base64 凭证

# 文件上传接口
UPLOAD_API = "http://test.7ieis.com/api/object-storage/FileUpDown/UploadFileByStream"

# 邮件发送接口
MAIL_API = "http://test.7ieis.com/api/email/AppMails/LQ_Mail_SaveSystemMail"

# 通知接口（邮件发送成功后调用）
NOTIFY_API = "http://test.7ieis.com/api/im-server/MessageExchange/NotifyEmail"

TENANT_ID = 16
MAIL_RECIPIENTS = "E69819,E16307"
NOTIFY_RECIPIENT_IDS = ["69819", "16307"]

# 固定的 Excel 文件名（需放在脚本同目录下）
EXCEL_FILENAME = "数据库及中间件磁盘巡检20260313.xlsx"


def get_token():
    """
    使用固定的 Basic 凭证获取 Bearer Token
    根据用户反馈，token 位于返回 JSON 的 Data 字段中
    """
    headers = {"Authorization": AUTH_HEADER}
    params = {"code": TOKEN_CODE}
    try:
        # 发送 GET 请求，与用户提供的脚本完全一致
        resp = requests.get(TOKEN_API, params=params, headers=headers, timeout=10)
        resp.raise_for_status()

        # 打印响应内容用于调试（可注释掉）
        logging.info("Token 响应内容: %s", resp.text)

        # 解析 JSON
        data = resp.json()

        # 提取 Data 字段作为 token（根据用户描述：token 是 Data 部分内容）
        if isinstance(data, dict):
            token = data.get("Data")
            if token:
                # 如果 Data 本身是字符串，直接返回
                if isinstance(token, str):
                    return token.strip()
                # 如果 Data 是字典，可能包含 Token 子字段
                elif isinstance(token, dict):
                    inner_token = token.get("Token") or token.get("token") or token.get("access_token")
                    if inner_token:
                        return inner_token
                    else:
                        # 无法识别子字段，返回整个 Data 的 JSON 字符串（后备）
                        return json.dumps(token)
                else:
                    # 其他类型，转为字符串返回
                    return str(token)
            else:
                # 没有 Data 字段，尝试其他常见字段
                token = data.get("token") or data.get("access_token")
                if token:
                    return token
                # 实在找不到，返回整个响应（可能出错）
                raise Exception(f"响应中未找到 token 字段: {data}")
        else:
            # 响应不是字典，直接返回文本（可能为纯文本 token）
            return resp.text.strip()

    except Exception as e:
        logging.error("获取 Token 失败: %s", e)
        raise


def upload_file(token, file_path):
    """
    上传文件，返回 fileId（兼容纯文本或 JSON 响应）
    完全模拟 curl 命令的格式：
    -F 'file=@...;type=application/vnd...'
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/plain"  # 与 curl 中的 accept 一致
    }
    filename = os.path.basename(file_path)
    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    with open(file_path, "rb") as f:
        files = {
            "file": (filename, f, mime_type)
        }
        try:
            resp = requests.post(UPLOAD_API, headers=headers, files=files, timeout=30)
            resp.raise_for_status()

            # 尝试解析 JSON
            try:
                result = resp.json()
                if isinstance(result, dict):
                    # 尝试常见字段名
                    if "Data" in result:
                        file_id = result["Data"]
                    elif "fileId" in result:
                        file_id = result["fileId"]
                    elif "id" in result:
                        file_id = result["id"]
                    else:
                        # 未知结构，记录日志并返回整个字典（需根据实际情况调整）
                        logging.warning("未知的 JSON 结构，返回完整响应: %s", result)
                        file_id = result
                else:
                    file_id = result
            except:
                # 非 JSON 响应，直接作为 fileId（纯文本）
                file_id = resp.text.strip()

            logging.info("文件上传成功，fileId: %s", file_id)
            return file_id
        except Exception as e:
            logging.error("文件上传失败: %s", e)
            raise


@app.route("/sendemail", methods=["POST"])
def send_email():
    """
    完整流程：
    1. 获取 Token
    2. 上传 Excel 文件，获得 fileId
    3. 使用 fileId 发送邮件
    4. 发送通知
    """
    # ======================
    # 1. 解析请求内容（仅用于日志）
    # ======================
    content = ""
    json_data = request.get_json(silent=True)
    if json_data:
        content = (
            json_data.get("content")
            or json_data.get("message")
            or json.dumps(json_data, ensure_ascii=False)
        )
    else:
        content = request.data.decode("utf-8", errors="ignore").strip()

    if not content:
        logging.error("请求体为空")
        return jsonify({"error": "A non-empty request body is required"}), 400

    logging.info("收到请求内容: %s", content)

    # ======================
    # 2. 获取 Token
    # ======================
    try:
        token = get_token()
        logging.info("Token 获取成功")
    except Exception as e:
        return jsonify({"error": "Failed to get token", "detail": str(e)}), 500

    # ======================
    # 3. 上传文件，获取 fileId
    # ======================
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, EXCEL_FILENAME)

    if not os.path.exists(file_path):
        logging.error("Excel 文件不存在: %s", file_path)
        return jsonify({"error": f"Excel file '{EXCEL_FILENAME}' not found"}), 500

    try:
        file_id = upload_file(token, file_path)
    except Exception as e:
        return jsonify({"error": "File upload failed", "detail": str(e)}), 500

    # ======================
    # 4. 构造邮件内容（使用上传得到的 fileId）
    # ======================
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    subject = f"{today_str}-巡检"
    body = "Hi， all:<br>以下是今天的巡检情况，请查收！"
    attachments_str = json.dumps([file_id])  # 转为字符串格式，如 "[12345]"

    mail_data = {
        "Subject": subject,
        "RecipientIds": MAIL_RECIPIENTS,
        "Body": body,
        "Attachments": attachments_str
    }
    mail_payload = {
        "TenantId": TENANT_ID,
        "Data": json.dumps(mail_data, ensure_ascii=False)
    }

    # ======================
    # 5. 发送邮件
    # ======================
    try:
        mail_resp = requests.post(MAIL_API, json=mail_payload, timeout=5)
        mail_resp.raise_for_status()
        logging.info("[MAIL] 状态码=%s 响应=%s", mail_resp.status_code, mail_resp.text)
    except requests.exceptions.RequestException as e:
        logging.error("[MAIL] 请求失败: %s", e)
        return jsonify({"error": "mail api request failed", "detail": str(e)}), 500

    # ======================
    # 6. 发送通知
    # ======================
    notify_payload = {
        "Type": 0,
        "EnterpriseId": TENANT_ID,
        "RecipientIds": NOTIFY_RECIPIENT_IDS
    }
    try:
        notify_resp = requests.post(NOTIFY_API, json=notify_payload, timeout=5)
        notify_resp.raise_for_status()
        notify_result = {
            "status_code": notify_resp.status_code,
            "response": notify_resp.text
        }
        logging.info("[PUSH] 通知发送成功，状态码=%s 响应=%s", notify_resp.status_code, notify_resp.text)
    except requests.exceptions.RequestException as e:
        notify_result = {"error": str(e)}
        logging.error("[PUSH] 通知发送失败: %s", e)

    # ======================
    # 7. 返回结果
    # ======================
    return jsonify({
        "status": "ok",
        "subject": subject,
        "file_id": file_id,
        "mail_status": mail_resp.status_code,
        "notify": notify_result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10086)

# curl -X POST http://localhost:10086/sendemail -H "Content-Type: application/json" -d '{"message":"test"}'
