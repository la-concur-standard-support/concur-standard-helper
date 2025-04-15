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
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    config = {
        'email': os.environ.get('STREAMLIT_EMAIL', ''),
        'password': os.environ.get('STREAMLIT_EMAIL_PASSWORD', ''),
        'imap_server': os.environ.get('EMAIL_IMAP_SERVER', 'mas22.kagoya.net'),
        'imap_port': int(os.environ.get('EMAIL_IMAP_PORT', 993)),
        'username': os.environ.get('EMAIL_USERNAME', '')
    }
    return config

def login_imap(email_config):
    mail = imaplib.IMAP4_SSL(email_config['imap_server'], email_config['imap_port'])
    for username in [email_config['email'], email_config['username']]:
        try:
            mail.login(username, email_config['password'])
            logger.info(f"[DEBUG] IMAP login succeeded with '{username}'")
            return mail
        except Exception as e:
            logger.warning(f"{username} でのIMAPログイン失敗: {e}")
    raise ValueError("メールサーバーへのIMAPログインに失敗しました")

def extract_streamlit_code(mail, max_wait_time=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        logger.info("[DEBUG] Searching UNSEEN mails for Streamlit code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        logger.info(f"[DEBUG] Found UNSEEN message IDs: {message_ids}")
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
            logger.info("Streamlitワンタイムコードメールを検出 (UNSEEN)")
            return parse_streamlit_code(email_message)
    return None

def parse_streamlit_code(email_message):
    for part in email_message.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace')
            digits = re.findall(r'\d', body)
            logger.info(f"[DEBUG] digits_found={digits}, length={len(digits)}")
            if len(digits) >= 6:
                code = "".join(digits[:6])
                logger.info(f"Streamlit検証コード(先頭6桁)を取得: {code}")
                return code
    return None

def extract_github_device_code(mail, max_wait_time=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait_time:
        logger.info("[DEBUG] Searching UNSEEN mails for GitHub device code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        message_ids = unseen_data[0].split()
        logger.info(f"[DEBUG] Found UNSEEN message IDs for GitHub: {message_ids}")
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
            logger.info("GitHubデバイス認証メールを検出 (UNSEEN)")
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
    gh_user = os.environ.get("GIT_USERNAME", "la-concur-helper")
    gh_pass = os.environ.get("GIT_PASSWORD", "n@pr0001")

    try:
        WebDriverWait(driver, 5).until(EC.url_contains("github.com/login"))
        logger.info("Detected GitHub login page. Attempting to sign in...")
        username_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "login")))
        username_input.clear()
        username_input.send_keys(gh_user)
        logger.info(f"[DEBUG] GitHub username '{gh_user}' を入力")
        password_input = driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(gh_pass)
        logger.info("[DEBUG] GitHub パスワードを入力 (マスク)")
        sign_in_button = driver.find_element(By.NAME, "commit")
        sign_in_button.click()
        logger.info("GitHub 'Sign in' ボタンをクリック")
        WebDriverWait(driver, 15).until_not(EC.url_contains("github.com/login"))
        logger.info("GitHubログイン処理完了(または次ステップに遷移)")
        handle_github_device_verification(driver)
    except Exception as e:
        logger.info(f"GitHub login page was not found or not needed: {e}")

def handle_github_device_verification(driver):
    try:
        otp_field = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.NAME, "otp"))
        )
        logger.info("Detected GitHub Device Verification page. Retrieving code from email...")
        email_config = get_email_config()
        mail = login_imap(email_config)
        device_code = extract_github_device_code(mail)
        if not device_code:
            raise ValueError("GitHubデバイス認証コードの取得に失敗しました")
        otp_field.clear()
        otp_field.send_keys(device_code)
        logger.info(f"GitHub デバイス認証コードを入力: {device_code}")
        # 修正：Verify ボタンは "Verify" というテキストから探す
        verify_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Verify')]")
        verify_btn.click()
        logger.info("GitHub Device Verification: Verifyボタンをクリック")
        WebDriverWait(driver, 30).until_not(EC.url_contains("challenge"))
        logger.info("GitHubデバイス認証が完了しました。")
    except Exception as e:
        logger.info(f"Device verification page not found or not needed: {e}")

def login_to_streamlit(driver, email):
    try:
        sign_in_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign in')]"))
        )
        sign_in_btn.click()
        logger.info("Sign in ボタンをクリック")
        mail_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][name='email']"))
        )
        mail_field.clear()
        mail_field.send_keys(email)
        logger.info(f"メール '{email}' を入力")
        cont_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        logger.info("ワンタイムコード送信用の Continueボタンをクリック(一度だけ)")
        cont_btn.click()
        time.sleep(2)
        code_inputs = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']"))
        )
        email_config = get_email_config()
        mail = login_imap(email_config)
        st_code = extract_streamlit_code(mail)
        if not st_code:
            raise ValueError("Streamlitワンタイムコードを取得できませんでした")
        if len(code_inputs) == 6:
            for i, digit in enumerate(st_code):
                code_inputs[i].send_keys(digit)
            logger.info(f"ワンタイムコードを入力: {st_code}")
        else:
            raise ValueError(f"入力フィールド数が不正: {len(code_inputs)}")
        login_to_github_if_needed(driver)
        # ★ここで、ログイン後に管理画面に遷移してしまう場合は、明示的にアプリURLに再アクセスする
        driver.get("https://concur-dev-support.streamlit.app/")
        logger.info("アプリURLに再アクセスして、実際のアプリ画面を表示")
        WebDriverWait(driver, 60).until(EC.url_contains("streamlit.app"))
        logger.info("Streamlitログイン成功")
    except Exception as e:
        logger.error(f"ログイン中にエラー: {e}")
        driver.save_screenshot('screenshot_login_error.png')
        raise

def visit_streamlit_app(url, email):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        logger.info(f"URLにアクセス: {url}")
        driver.save_screenshot("debug_screenshot_0_initial.png")
        login_to_streamlit(driver, email)
        time.sleep(5)
        driver.save_screenshot('screenshot_after_login.png')
        logger.info("ログイン後のスクリーンショットを保存")
    except Exception as e:
        logger.error(f"{url} の訪問中にエラー: {e}")
        driver.save_screenshot('screenshot_error.png')
        raise
    finally:
        driver.quit()
        logger.info("ブラウザを閉じました")

def main():
    email_config = get_email_config()
    target_email = email_config['email']
    if not target_email:
        raise ValueError("STREAMLIT_EMAIL が設定されていないため、メールアドレス不明")
    streamlit_apps = ["https://concur-dev-support.streamlit.app/"]
    for app_url in streamlit_apps:
        try:
            visit_streamlit_app(app_url, target_email)
        except Exception as e:
            logger.error(f"{app_url} の訪問中にエラー: {e}")
        time.sleep(5)

if __name__ == '__main__':
    start_time = time.time()
    logger.info("Keep-Alive ジョブ開始")
    main()
    end_time = time.time()
    logger.info(f"Keep-Alive ジョブ終了 (所要時間: {end_time - start_time:.2f}秒)")
