import os
import imaplib
import email
import re
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# 環境変数 LANG の設定（GitHub Actions の環境でも適用されるように）
os.environ["LANG"] = "ja_JP.UTF-8"
os.environ["LC_ALL"] = "ja_JP.UTF-8"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# デバッグ用ユーティリティ関数

def log_mailbox_info(mail):
    """
    IMAPサーバー接続後の受信箱情報を出力します。
    """
    try:
        res_select, data_select = mail.select('inbox')
        logger.debug(f"SELECT INBOX response: {res_select}, data: {data_select}")
        res_status = mail.status('INBOX', '(MESSAGES UNSEEN)')
        logger.debug(f"INBOX status: {res_status}")
        mailboxes = mail.list()
        logger.debug(f"Available mailboxes: {mailboxes}")
    except Exception as e:
        logger.warning(f"Mailbox debug info error: {e}")


def is_streamlit_verification_email(email_message):
    try:
        from_address = email_message.get('from', '')
        from_header = email_message.get('From', '')
        if 'no-reply@streamlit.io' not in from_address.lower() and 'no-reply@streamlit.io' not in from_header.lower():
            return False
        for part in email_message.walk():
            if part.get_content_type() == 'text/plain':
                body_raw = part.get_payload(decode=True).decode(errors='replace')
                if "your one-time code is:" in body_raw.lower():
                    return True
    except Exception as e:
        logger.warning(f"Streamlit判定中にエラー: {e}")
    return False


def is_github_device_verification_email(email_message):
    try:
        from_address = email_message.get('from', '')
        from_header = email_message.get('From', '')
        if 'noreply@github.com' not in from_address.lower() and 'noreply@github.com' not in from_header.lower():
            return False
        for part in email_message.walk():
            if part.get_content_type() == 'text/plain':
                body_raw = part.get_payload(decode=True).decode(errors='replace')
                if "verification code:" in body_raw.lower():
                    return True
    except Exception as e:
        logger.warning(f"GitHubデバイス判定中にエラー: {e}")
    return False


def get_email_config():
    return {
        'email': os.environ.get('STREAMLIT_EMAIL', ''),
        'password': os.environ.get('STREAMLIT_EMAIL_PASSWORD', ''),
        'imap_server': os.environ.get('EMAIL_IMAP_SERVER', 'mas22.kagoya.net'),
        'imap_port': int(os.environ.get('EMAIL_IMAP_PORT', 993)),
        'username': os.environ.get('EMAIL_USERNAME', '')
    }


def login_imap(email_config):
    mail = imaplib.IMAP4_SSL(email_config['imap_server'], email_config['imap_port'])
    for username in [email_config['email'], email_config['username']]:
        try:
            mail.login(username, email_config['password'])
            logger.debug(f"[DEBUG] IMAP login succeeded with '{username}'")
            return mail
        except Exception as e:
            logger.debug(f"{username} でのIMAPログイン失敗: {e}")
    raise ValueError("メールサーバーへのIMAPログインに失敗しました")


def extract_streamlit_code(mail, max_wait_time=120):
    start_time = time.time()
    log_mailbox_info(mail)
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        logger.debug("[DEBUG] Searching UNSEEN mails for Streamlit code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        logger.debug(f"[DEBUG] Found UNSEEN message IDs: {message_ids}")
        code = search_for_streamlit_code_in_messages(mail, reversed(message_ids))
        if code:
            return code
        time.sleep(10)
    return None


def search_for_streamlit_code_in_messages(mail, message_ids):
    for num in message_ids:
        logger.debug(f"Fetching message ID: {num}")
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        logger.debug(f"Email Subject: {email_message.get('Subject')}, From: {email_message.get('From')}")
        if is_streamlit_verification_email(email_message):
            logger.info("Streamlitワンタイムコードメールを検出 (UNSEEN)")
            return parse_streamlit_code(email_message)
    return None


def parse_streamlit_code(email_message):
    for part in email_message.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace')
            preview = body[:200].replace('\n', ' ')
            logger.debug(f"Body preview (first 200 chars): {preview}")
            digits = re.findall(r'\d', body)
            logger.debug(f"[DEBUG] digits_found={digits}, length={len(digits)}")
            if len(digits) >= 6:
                code = "".join(digits[:6])
                logger.info(f"Streamlit検証コード(先頭6桁)を取得: {code}")
                return code
    return None


def extract_github_device_code(mail, max_wait_time=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        logger.debug("[DEBUG] Searching UNSEEN mails for GitHub device code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        logger.debug(f"[DEBUG] Found UNSEEN message IDs for GitHub: {message_ids}")
        code = search_for_github_device_code_in_messages(mail, reversed(message_ids))
        if code:
            return code
        time.sleep(10)
    return None


def search_for_github_device_code_in_messages(mail, message_ids):
    for num in message_ids:
        logger.debug(f"Fetching GitHub message ID: {num}")
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        if is_github_device_verification_email(email_message):
            logger.info("GitHubデバイス認証メールを検出 (UNSEEN)")
            return parse_github_device_code(email_message)
    return None
