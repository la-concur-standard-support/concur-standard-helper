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

###############################################################################
# Streamlitワンタイムコード判定
###############################################################################
def is_streamlit_verification_email(msg):
    """
    Streamlit のワンタイムコードメール:
    送信元 no-reply@streamlit.io ＆ 本文に "your one-time code is:" を含む
    """
    try:
        from_address = msg.get('from', '')
        from_header = msg.get('From', '')
        if 'no-reply@streamlit.io' not in from_address.lower() and 'no-reply@streamlit.io' not in from_header.lower():
            return False
        
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                body_raw = part.get_payload(decode=True).decode(errors='replace').lower()
                if "your one-time code is:" in body_raw:
                    return True
    except Exception as e:
        logger.warning(f"Streamlit判定中にエラー: {e}")
    return False

###############################################################################
# GitHubデバイス認証メール判定
###############################################################################
def is_github_device_verification_email(msg):
    """
    GitHub の Device verification メール:
    送信元 no-reply@github.com ＆ 本文に "Verification code: " を含む
    (大文字小文字不問)
    """
    try:
        from_address = msg.get('from', '')
        from_header = msg.get('From', '')
        if 'no-reply@github.com' not in from_address.lower() and 'no-reply@github.com' not in from_header.lower():
            return False
        
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                body_raw = part.get_payload(decode=True).decode(errors='replace').lower()
                if "verification code:" in body_raw:
                    return True
    except Exception as e:
        logger.warning(f"GitHubデバイス判定中にエラー: {e}")
    return False

###############################################################################
# メール接続共通
###############################################################################
def get_email_config():
    return {
        'email': os.environ.get('STREAMLIT_EMAIL', ''),
        'password': os.environ.get('STREAMLIT_EMAIL_PASSWORD', ''),
        'imap_server': os.environ.get('EMAIL_IMAP_SERVER', 'mas22.kagoya.net'),
        'imap_port': int(os.environ.get('EMAIL_IMAP_PORT', 993)),
        'username': os.environ.get('EMAIL_USERNAME', '')
    }

def login_imap(email_conf):
    mail = imaplib.IMAP4_SSL(email_conf['imap_server'], email_conf['imap_port'])
    # username or email でログイン試行
    for username in [email_conf['email'], email_conf['username']]:
        try:
            mail.login(username, email_conf['password'])
            logger.info(f"[DEBUG] IMAP login succeeded with '{username}'")
            return mail
        except Exception as e:
            logger.warning(f"{username} でのIMAPログイン失敗: {e}")
    raise ValueError("IMAPログインに失敗しました")

###############################################################################
# Streamlit ワンタイムコード抽出
###############################################################################
def extract_streamlit_code(mail, max_wait=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait:
        logger.info("[DEBUG] Searching UNSEEN for Streamlit code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        msg_ids = unseen_data[0].split()
        logger.info(f"[DEBUG] Found UNSEEN msg_ids: {msg_ids}")
        code = search_streamlit_msgs(mail, reversed(msg_ids))
        if code:
            return code
        time.sleep(5)
    return None

def search_streamlit_msgs(mail, msg_ids):
    for num in msg_ids:
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        if is_streamlit_verification_email(msg):
            logger.info("Streamlitワンタイムコードメールを検出")
            return parse_streamlit_code(msg)
    return None

def parse_streamlit_code(msg):
    # 6桁数字を先頭6桁返す
    for part in msg.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace')
            digits = re.findall(r'\d', body)
            logger.info(f"[DEBUG] digits_found={digits}")
            if len(digits) >= 6:
                code = "".join(digits[:6])
                logger.info(f"Streamlit code: {code}")
                return code
    return None

###############################################################################
# GitHub Device Verification code 抽出
###############################################################################
def extract_github_device_code(mail, max_wait=120):
    start_time = time.time()
    mail.select('inbox')
    while time.time() - start_time < max_wait:
        logger.info("[DEBUG] Searching UNSEEN for GitHub device code...")
        _, unseen_data = mail.search(None, 'UNSEEN')
        msg_ids = unseen_data[0].split()
        logger.info(f"[DEBUG] Found UNSEEN for GitHub code: {msg_ids}")
        code = search_github_msgs(mail, reversed(msg_ids))
        if code:
            return code
        time.sleep(5)
    return None

def search_github_msgs(mail, msg_ids):
    for num in msg_ids:
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        if is_github_device_verification_email(msg):
            logger.info("GitHubデバイス認証メールを検出")
            return parse_github_code(msg)
    return None

def parse_github_code(msg):
    """
    'Verification code: 123456' という形を正規表現で探す
    """
    for part in msg.walk():
        if part.get_content_type() in ('text/plain', 'text/html'):
            body = part.get_payload(decode=True).decode(errors='replace').lower()
            m = re.search(r'verification code:\s*([0-9]{6})', body)
            if m:
                code = m.group(1)
                logger.info(f"GitHubデバイスコード: {code}")
                return code
    return None

###############################################################################
# GitHubログイン
###############################################################################
def login_to_github_if_needed(driver):
    gh_user = os.environ.get("GIT_USERNAME", "la-concur-helper")
    gh_pass = os.environ.get("GIT_PASSWORD", "n@pr0001")

    try:
        WebDriverWait(driver, 5).until(EC.url_contains("github.com/login"))
        logger.info("GitHubログイン画面を検知 => ログイン開始")

        # Username
        user_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "login")))
        user_input.clear()
        user_input.send_keys(gh_user)
        logger.info(f"[DEBUG] GIT_USERNAME='{gh_user}' 入力")

        # Password
        pass_input = driver.find_element(By.NAME, "password")
        pass_input.clear()
        pass_input.send_keys(gh_pass)
        logger.info("[DEBUG] GIT_PASSWORD(マスク) 入力")

        # Sign in ボタン
        sign_in_btn = driver.find_element(By.NAME, "commit")
        sign_in_btn.click()
        logger.info("Sign in ボタンをクリック")

        # ログインページから抜けるまで最大15秒待機
        WebDriverWait(driver, 15).until_not(EC.url_contains("github.com/login"))
        logger.info("GitHubログイン完了 or 次の段階へ")
        handle_github_device_challenge(driver)

    except Exception as e:
        logger.info(f"GitHub login page was not found or not needed: {e}")

def handle_github_device_challenge(driver):
    """
    GitHub のデバイス認証画面があれば、メールを再度確認して code 入力
    """
    try:
        # Device verification: name="otp" フィールドを3秒待機
        otp_field = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, "otp")))
        logger.info("GitHub Device Verification画面を検知 => メールからcode取得")

        # IMAPログインし直して, GitHub Device codeを取得
        email_conf = get_email_config()
        mail = login_imap(email_conf)
        device_code = extract_github_device_code(mail)
        if not device_code:
            raise ValueError("GitHub Device code not found in mail")

        otp_field.clear()
        otp_field.send_keys(device_code)
        logger.info(f"Device code {device_code} 入力")

        # Verify ボタンを押す (type=submit)
        verify_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        verify_btn.click()
        logger.info("Device code Verifyボタンをクリック")

        # challenge ページを脱出するまで待つ
        WebDriverWait(driver, 30).until_not(EC.url_contains("challenge"))
        logger.info("GitHub Device Verification完了")

    except Exception as e:
        logger.info(f"Device verification page not found or skipping: {e}")

###############################################################################
# Streamlitログイン
###############################################################################
def login_to_streamlit(driver, email_address):
    """
    1) "Sign in" ボタンクリック
    2) メールアドレス入力 -> "Continue" -> Streamlitワンタイムコード
    3) GitHubログイン画面なら username/password
    4) デバイス認証画面なら mailから code 再取得 -> Verify
    """
    try:
        # Sign in ボタン (一度だけ)
        sign_in_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign in')]"))
        )
        sign_in_btn.click()
        logger.info("Sign in ボタンをクリック")

        # メールアドレス
        mail_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][name='email']"))
        )
        mail_field.clear()
        mail_field.send_keys(email_address)
        logger.info(f"メール '{email_address}' を入力")

        # Continueボタン
        cont_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        logger.info("ワンタイムコード送信用の Continueボタンをクリック(一度だけ)")
        cont_btn.click()
        time.sleep(2)

        # ワンタイムコード入力欄
        code_inputs = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']"))
        )

        # メールでワンタイムコード取得
        email_conf = get_email_config()
        mail = login_imap(email_conf)
        st_code = extract_streamlit_code(mail)
        if not st_code:
            raise ValueError("Streamlitワンタイムコードを取得できませんでした")

        # コード入力
        if len(code_inputs) == 6:
            for i, digit in enumerate(st_code):
                code_inputs[i].send_keys(digit)
            logger.info(f"ワンタイムコードを入力: {st_code}")
        else:
            raise ValueError(f"入力欄が {len(code_inputs)} 個。想定外")

        # GitHubログインがあれば自動処理
        login_to_github_if_needed(driver)

        # 最終的に streamlit.app へリダイレクトされるのを待つ
        WebDriverWait(driver, 60).until(EC.url_contains("streamlit.app"))
        logger.info("Streamlitログイン成功")

    except Exception as e:
        logger.error(f"ログイン中にエラー: {e}")
        driver.save_screenshot("screenshot_login_error.png")
        raise

def visit_streamlit_app(url, email_address):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        logger.info(f"URLにアクセス: {url}")

        login_to_streamlit(driver, email_address)
        time.sleep(5)
        driver.save_screenshot("screenshot_after_login.png")
        logger.info("ログイン後のスクリーンショットを保存")

    except Exception as e:
        logger.error(f"{url} の訪問中にエラー: {e}")
        driver.save_screenshot("screenshot_error.png")
        raise

    finally:
        driver.quit()
        logger.info("ブラウザを閉じました")

def main():
    email_conf = get_email_config()
    if not email_conf['email']:
        raise ValueError("STREAMLIT_EMAIL が未設定です")

    urls = ["https://concur-dev-support.streamlit.app/"]
    for u in urls:
        try:
            visit_streamlit_app(u, email_conf['email'])
        except Exception as e:
            logger.error(f"{u} の訪問中にエラー: {e}")
        time.sleep(5)

if __name__ == '__main__':
    start_time = time.time()
    logger.info("Keep-Alive ジョブ開始")
    main()
    end_time = time.time()
    logger.info(f"Keep-Alive ジョブ終了 (所要時間: {end_time - start_time:.2f}秒)")
