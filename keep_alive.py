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
        subject = email_message.get('Subject', '')

        logger.info(f"[DEBUG] Checking from='{from_address}', header='{from_header}', subject='{subject}'")

        # 差出人が no-reply@streamlit.io でなければスキップ
        if 'no-reply@streamlit.io' not in from_address and 'no-reply@streamlit.io' not in from_header:
            return False
        
        # 本文に "Sign in to Streamlit Community Cloud" と "Your one-time code is:" が含まれるか判定
        for part in email_message.walk():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload(decode=True).decode(errors='replace')
                logger.info(f"[DEBUG] Plain text body:\n{body}")

                if ('Sign in to Streamlit Community Cloud' in body
                        and 'Your one-time code is:' in body):
                    return True
    except Exception as e:
        logger.warning(f"メール検証中にエラー: {e}")
    return False

def get_email_config():
    config = {
        'email': os.environ.get('STREAMLIT_EMAIL', ''),
        'password': os.environ.get('STREAMLIT_EMAIL_PASSWORD', ''),
        'imap_server': os.environ.get('EMAIL_IMAP_SERVER', 'mas22.kagoya.net'),
        'imap_port': int(os.environ.get('EMAIL_IMAP_PORT', 993)),
        'username': os.environ.get('EMAIL_USERNAME', '')
    }
    
    required_params = ['email', 'password', 'imap_server']
    for param in required_params:
        if not config[param]:
            logger.error(f"{param.upper()}が設定されていません")
            raise ValueError(f"{param.upper()}は環境変数で設定する必要があります")

    logger.info(
        "[DEBUG] get_email_config: "
        f"email='{config['email']}', "
        f"username='{config['username']}', "
        f"password length={len(config['password'])}, "
        f"imap_server='{config['imap_server']}', "
        f"imap_port={config['imap_port']}"
    )
    return config

def extract_verification_code(email_config, max_wait_time=300):
    """
    UNSEEN (未読) メールだけを対象に、Streamlit のワンタイムコードを探す。
    デバッグ用の ALL 検索を削除し、無関係なメールログを出さない。
    """
    start_time = time.time()
    mail = None
    
    try:
        # IMAPに接続
        mail = imaplib.IMAP4_SSL(email_config['imap_server'], email_config['imap_port'])
        
        # ユーザー名として 'email' または 'username' を試行
        login_attempts = [email_config['email'], email_config['username']]
        login_successful = False
        
        for username in login_attempts:
            logger.info(
                f"[DEBUG] Trying IMAP login with username='{username}' (pwd len={len(email_config['password'])})"
            )
            try:
                mail.login(username, email_config['password'])
                logger.info(f"[DEBUG] IMAP login succeeded with '{username}'")
                login_successful = True
                break
            except Exception as login_error:
                logger.warning(f"{username} でのログインに失敗: {login_error}")
        
        if not login_successful:
            raise ValueError("メールサーバーへのログインに失敗しました")
        
        mail.select('inbox')
        
        # max_wait_time の間、未読メールを探し続ける
        while time.time() - start_time < max_wait_time:
            logger.info("[DEBUG] Searching UNSEEN mails only...")
            _, unseen_data = mail.search(None, 'UNSEEN')
            message_ids = unseen_data[0].split()
            logger.info(f"[DEBUG] Found UNSEEN message IDs: {message_ids}")

            found_code = search_for_code_in_messages(mail, message_ids)
            if found_code:
                return found_code
            
            time.sleep(10)

        logger.warning("指定時間内にコードを見つけられませんでした")
    except Exception as e:
        logger.error(f"メール検索中にエラー: {e}")
    finally:
        if mail is not None:
            try:
                mail.close()
                mail.logout()
            except:
                pass
    
    return None

def search_for_code_in_messages(mail, message_ids, debug_only=False):
    """
    UNSEEN のメッセージID一覧を順にチェックし、
    Streamlit ワンタイムコードが含まれるメールを見つけたらコードを返す。
    """
    for num in message_ids:
        _, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        
        if is_streamlit_verification_email(email_message):
            logger.info("Streamlitからのメールを発見 (UNSEEN)")
            # 本文からスペース入り6桁コードを抽出
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode(errors='replace')
                    # すべての数字を取り出し、先頭6桁を連結
                    match_digits = re.findall(r'\d', body)
                    if len(match_digits) >= 6:
                        code = "".join(match_digits[:6])
                        logger.info(f"検証コードを取得(スペース考慮): {code}")
                        return code
    return None

def login_to_streamlit(driver, email):
    try:
        sign_in_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign in')]"))
        )
        sign_in_button.click()
        logger.info("Sign in ボタンをクリック")

        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'][name='email']"))
        )
        email_input.clear()
        email_input.send_keys(email)
        logger.info(f"メールアドレス '{email}' を入力")
        
        continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        continue_button.click()
        logger.info("Continueボタンをクリックしてワンタイムコード送信")

        time.sleep(5)

        code_inputs = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']"))
        )
        logger.info("ワンタイムコード入力欄が表示されました")

        email_config = get_email_config()
        verification_code = extract_verification_code(email_config)
        if not verification_code:
            raise ValueError("ワンタイムコードの取得に失敗")

        if len(code_inputs) == 6:
            for i, digit in enumerate(verification_code):
                code_inputs[i].send_keys(digit)
            logger.info(f"ワンタイムコードを入力: {verification_code}")
        else:
            raise ValueError(f"入力フィールドが {len(code_inputs)} 個あるため想定外")

        confirm_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        confirm_button.click()
        logger.info("ワンタイムコード入力後のContinueボタンをクリック")

        WebDriverWait(driver, 40).until(
            EC.url_contains("streamlit.app")
        )
        logger.info("ログイン成功！")
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
        
        login_to_streamlit(driver, email)
        time.sleep(10)
        driver.save_screenshot('screenshot_after_login.png')
        logger.info("ログイン後のスクリーンショットを保存")
    except Exception as e:
        logger.error(f"アプリ訪問中にエラー: {e}")
        driver.save_screenshot('screenshot_error.png')
        raise
    finally:
        driver.quit()
        logger.info("ブラウザを閉じました")

def main():
    email_config = get_email_config()
    streamlit_apps = [
        "https://concur-dev-support.streamlit.app/"
    ]
    for app_url in streamlit_apps:
        try:
            visit_streamlit_app(app_url, email_config['email'])
        except Exception as e:
            logger.error(f"{app_url} の訪問中にエラー発生: {e}")
        time.sleep(5)

if __name__ == '__main__':
    start_time = time.time()
    logger.info("Keep-Alive ジョブ開始")
    
    main()
    
    end_time = time.time()
    logger.info(f"Keep-Alive ジョブ終了 (所要時間: {end_time - start_time:.2f}秒)")
