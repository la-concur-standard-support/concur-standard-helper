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

# INFO以上のログを出力し、DEBUGログは抑止
logging.basicConfig(
    level=logging.INFO,
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
            logger.debug(f"IMAP login succeeded with '{username}'")
            return mail
        except Exception as e:
            logger.debug(f"{username} でのIMAPログイン失敗: {e}")
    raise ValueError("メールサーバーへのIMAPログインに失敗しました")


def extract_streamlit_code(mail, max_wait_time=180):  # タイムアウトを180秒に延長
    start_time = time.time()
    log_mailbox_info(mail)
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        logger.debug("Searching UNSEEN mails for Streamlit code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        logger.debug(f"Found UNSEEN message IDs: {message_ids}")
        code = search_for_streamlit_code_in_messages(mail, reversed(message_ids))
        if code:
            return code
        time.sleep(10)
    return None


def search_for_streamlit_code_in_messages(mail, message_ids):
    for num in message_ids:
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        if is_streamlit_verification_email(email_message):
            logger.info("Streamlitワンタイムコードメールを検出")
            return parse_streamlit_code(email_message)
    return None


def parse_streamlit_code(email_message):
    for part in email_message.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace')
            digits = re.findall(r'\d', body)
            if len(digits) >= 6:
                code = "".join(digits[:6])
                logger.info(f"Streamlit検証コードを取得: {code}")
                return code
    return None


def extract_github_device_code(mail, max_wait_time=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        code = search_for_github_device_code_in_messages(mail, reversed(message_ids))
        if code:
            return code
        time.sleep(10)
    return None


def search_for_github_device_code_in_messages(mail, message_ids):
    for num in message_ids:
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        if is_github_device_verification_email(email_message):
            logger.info("GitHubデバイス認証メールを検出")
            return parse_github_device_code(email_message)
    return None


def parse_github_device_code(email_message):
    for part in email_message.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace').lower()
            m = re.search(r'(?:device\s+)?verification code:\s*([0-9]{6})', body)
            if m:
                code = m.group(1)
                logger.info(f"GitHubデバイス認証コードを取得: {code}")
                return code
    return None


def login_to_github_if_needed(driver):
    gh_user = os.environ.get("GIT_USERNAME", '')
    gh_pass = os.environ.get("GIT_PASSWORD", '')

    try:
        WebDriverWait(driver, 5).until(EC.url_contains("github.com/login"))
        logger.info("Detected GitHub login page. Signing in...")
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "login"))
        )
        username_input.clear()
        username_input.send_keys(gh_user)
        password_input = driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(gh_pass)
        logger.info("GitHub credentials entered")
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()
        WebDriverWait(driver, 15).until_not(EC.url_contains("github.com/login"))
        handle_github_device_verification(driver)
    except Exception as e:
        logger.info(f"GitHub login not required: {e}")


def handle_github_device_verification(driver):
    try:
        otp_field = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.NAME, "otp"))
        )
        email_config = get_email_config()
        mail = login_imap(email_config)
        device_code = extract_github_device_code(mail)
        if not device_code:
            raise ValueError("GitHubボコード取得失敗")
        otp_field.clear()
        otp_field.send_keys(device_code)
        try:
            driver.find_element(By.XPATH, "//button[contains(text(), 'Verify')]").click()
        except NoSuchElementException:
            return
        WebDriverWait(driver, 30).until_not(EC.url_contains("challenge"))
    except Exception:
        pass


def login_to_streamlit(driver, email):
    try:
        sign_in_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign in')]"))
        )
        sign_in_btn.click()
        logger.info("Clicked Sign in")
        mail_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][name='email']"))
        )
        mail_field.clear()
        mail_field.send_keys(email)
        logger.info("Email entered")
        cont_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        cont_btn.click()
        # ワンタイムコード取得
        st_code = extract_streamlit_code(mail)
        if not st_code:
            # 再試行
            logger.info("ワンタイムコード取得失敗、再試行します")
            cont_btn.click()
            st_code = extract_streamlit_code(mail)
            if not st_code:
                raise ValueError("Streamlitコード取得失敗(再試行)")
        inputs = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']"))
        )
        for i, digit in enumerate(st_code):
            inputs[i].send_keys(digit)
        logger.info(f"Entered code: {st_code}")
        login_to_github_if_needed(driver)
        driver.get("https://concur-dev-support.streamlit.app/")
        logger.info("Reloaded app URL")
        WebDriverWait(driver, 60).until(EC.url_contains("streamlit.app"))
    except Exception as e:
        logger.error(f"Error during login: {e}")
        driver.save_screenshot('screenshot_login_error.png')
        raise

    # 保存


def visit_streamlit_app(url, email):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        logger.info(f"Accessing URL: {url}")
        login_to_streamlit(driver, email)
    except Exception as e:
        logger.error(f"Error visiting {url}: {e}")
        driver.save_screenshot('screenshot_error.png')
        raise
    finally:
        driver.quit()
        logger.info("Browser closed")


def main():
    email_config = get_email_config()
    target_email = email_config['email']
    if not target_email:
        raise ValueError("STREAMLIT_EMAIL not set")
    for app_url in ["https://concur-dev-support.streamlit.app/"]:
        try:
            visit_streamlit_app(app_url, target_email)
        except Exception as e:
            logger.error(f"Error on {app_url}: {e}")
        time.sleep(5)

if __name__ == '__main__':
    logger.info("Keep-Alive job start")
    main()
    logger.info("Keep-Alive job end")
