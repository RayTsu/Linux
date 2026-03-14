from flask import Flask, request, jsonify
import requests
import json
import logging

app = Flask(__name__)

# ======================
# 日志配置
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(funcName)s:%(lineno)s] %(message)s"
)

# ======================
# 内部接口配置
# ======================
MAIL_API = "http://prod.7renju.com/api/email/AppMails/LQ_Mail_SaveSystemMail"
NOTIFY_API = "http://prod.7renju.com/api/im-server/MessageExchange/NotifyEmail"

TENANT_ID = 16

# 邮件系统（带 E）
MAIL_RECIPIENTS = "E68348,E16291,E68217,E15477,E16182,E69561,E16307,E69854,E68263,E71415"

# 邮件通知系统（不带 E，数组）
NOTIFY_RECIPIENT_IDS = ["68348", "16291", "68217", "15477", "16182", "69561", "16307", "69854", "68263", "71415"]


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    prometheusalert webhook adapter
    - 支持 text/plain（默认）
    - 支持 application/json
    - 邮件成功后触发邮件通知
    """

    # ======================
    # 1️⃣ 解析告警内容
    # ======================
    content = ""
    json_data = request.get_json(silent=True)

    # 如果请求是JSON格式，尝试从JSON中提取content
    if json_data:
        content = (
            json_data.get("content")
            or json_data.get("message")
            or json.dumps(json_data, ensure_ascii=False)
        )
    else:
        # 如果是文本格式，则直接读取请求体
        content = request.data.decode("utf-8", errors="ignore").strip()

    if not content:
        logging.error("Received empty content in the request")
        return jsonify({
            "error": "A non-empty request body is required"
        }), 400

    logging.info("Parsed content: %s", content)

    # ======================
    # 2️⃣ 生成邮件标题
    # ======================
    subject = "【Prometheus 告警通知】"
    lower_content = content.lower()

    if "resolved" in lower_content or "恢复" in content:
        subject = "【已恢复】Prometheus 告警"
    elif "firing" in lower_content or "告警触发" in content:
        subject = "【告警触发】Prometheus 告警"

    logging.info("Generated subject: %s", subject)

    # ======================
    # 3️⃣ 调用邮件发送接口
    # ======================
    mail_payload = {
        "TenantId": TENANT_ID,
        "Data": json.dumps({
            "Subject": subject,
            "RecipientIds": MAIL_RECIPIENTS,
            "Body": content
        }, ensure_ascii=False)
    }

    try:
        logging.info("Sending mail to %s", MAIL_RECIPIENTS)
        mail_resp = requests.post(
            MAIL_API,
            json=mail_payload,
            timeout=5
        )
        mail_resp.raise_for_status()
        logging.info("[MAIL] status=%s response=%s", mail_resp.status_code, mail_resp.text)
    except requests.exceptions.RequestException as e:
        logging.error("[MAIL] Request failed: %s", e)
        return jsonify({
            "error": "mail api request failed",
            "detail": str(e)
        }), 500

    # ======================
    # 4️⃣ 邮件发送成功后 → 调用邮件通知接口
    # ======================
    notify_payload = {
        "Type": 0,
        "EnterpriseId": TENANT_ID,
        "RecipientIds": NOTIFY_RECIPIENT_IDS
    }

    try:
        logging.info("Sending notification to %s", NOTIFY_RECIPIENT_IDS)
        notify_resp = requests.post(
            NOTIFY_API,
            json=notify_payload,
            timeout=5
        )
        notify_resp.raise_for_status()
        notify_result = {
            "status_code": notify_resp.status_code,
            "response": notify_resp.text
        }
        logging.info("[PUSH] Notification sent, status=%s response=%s", notify_resp.status_code, notify_resp.text)
    except requests.exceptions.RequestException as e:
        notify_result = {
            "error": str(e)
        }
        logging.error("[PUSH] Failed to send notification: %s", e)

    # ======================
    # 5️⃣ 返回结果
    # ======================
    return jsonify({
        "status": "ok",
        "subject": subject,
        "mail_status": mail_resp.status_code,
        "notify": notify_result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
