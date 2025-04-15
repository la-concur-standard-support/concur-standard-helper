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

# ログの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_email_config():
    """
    メール設定を環境変数から安全に取得
    
    Returns:
        dict: メール設定情報
    """
    # 環境変数から設定を取得（デフォルト値は空文字）
    config = {
        'email': os.environ.get('STREAMLIT_EMAIL', ''),
        'password': os.environ.get('STREAMLIT_EMAIL_PASSWORD', ''),
        'imap_server': os.environ.get('EMAIL_IMAP_SERVER', 'mas22.kagoya.net'),
        'imap_port': int(os.environ.get('EMAIL_IMAP_PORT', 993)),
        'username': os.environ.get('EMAIL_USERNAME', '')
    }
    
    # 必須パラメータの検証
    required_params = ['email', 'password', 'imap_server']
    for param in required_params:
        if not config[param]:
            logger.error(f"{param.upper()}が設定されていません")
            raise ValueError(f"{param.upper()}は環境変数で設定する必要があります")
    
    return config

def extract_verification_code(email_config, max_wait_time=300):
    """
    IMAPを使用してStreamlitのワンタイムコードを取得
    
    Args:
        email_config: メール設定情報の辞書
        max_wait_time: 最大待機時間（秒）
    
    Returns:
        検証コード（文字列）またはNone
    """
    start_time = time.time()
    
    try:
        # IMAPサーバーに接続
        mail = imaplib.IMAP4_SSL(
            email_config['imap_server'], 
            email_config['imap_port']
        )
        
        # ログイン（複数の認証方法を試行）
        login_attempts = [
            email_config['email'],  # フルメールアドレス
            email_config['username'],  # ユーザー名
        ]
        
        login_successful = False
        for username in login_attempts:
            try:
                mail.login(username, email_config['password'])
                login_successful = True
                break
            except Exception as login_error:
                logger.warning(f"{username}でのログインに失敗: {login_error}")
        
        if not login_successful:
            raise ValueError("メールサーバーへのログインに失敗しました")
        
        mail.select('inbox')
        
        logger.info("メールボックスを検索中...")
        
        while time.time() - start_time < max_wait_time:
            # 最新の未読メールを検索
            _, search_data = mail.search(None, 'UNSEEN')
            
            for num in search_data[0].split():
                _, data = mail.fetch(num, '(RFC822)')
                raw_email = data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Streamlitからのメールを確認
                if ('Streamlit Community Cloud' in str(email_message['subject']) or 
                    'streamlit.io' in str(email_message.get('from', ''))):
                    logger.info("Streamlitからのメールを発見")
                    
                    # メール本文から6桁のコードを抽出
                    for part in email_message.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode()
                            
                            # 6桁の数字コードを抽出
                            match = re.search(r'\b(\d{6})\b', body)
                            if match:
                                verification_code = match.group(1)
                                logger.info("検証コードを取得しました")
                                mail.close()
                                mail.logout()
                                return verification_code
            
            # 少し待機してから再試行
            time.sleep(10)
        
        logger.warning("指定時間内にコードを見つけられませんでした")
    except Exception as e:
        logger.error(f"メール検索中にエラーが発生: {e}")
    
    finally:
        try:
            mail.close()
            mail.logout()
        except:
            pass
    
    return None

def login_to_streamlit(driver, email):
    """
    Streamlitログインプロセス全体を処理
    
    Args:
        driver: WebDriverインスタンス
        email: Streamlitログインメールアドレス
    """
    try:
        # メールアドレス入力
        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".rt-TextFieldRoot.rt-r-size-3.rt-variant-surface input[type='email']"))
        )
        email_input.clear()
        email_input.send_keys(email)
        logger.info(f"メールアドレス '{email}' を入力")
        
        # Continueボタンクリック
        continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        continue_button.click()
        logger.info("Continueボタンをクリック")
        
        # コード入力フィールドが読み込まれるまで待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']"))
        )
        logger.info("コード入力ページに遷移")
        
        # メールからコードを取得
        email_config = get_email_config()
        verification_code = extract_verification_code(email_config)
        
        if not verification_code:
            raise ValueError("ワンタイムコードの取得に失敗しました")
        
        # ワンタイムコード入力フィールドを取得
        code_inputs = driver.find_elements(By.XPATH, "//input[@maxlength='1' and @inputmode='numeric']")
        
        # 6桁のコードを入力
        if len(code_inputs) == 6:
            for i, digit in enumerate(verification_code):
                code_inputs[i].send_keys(digit)
            logger.info("検証コードを入力")
        else:
            logger.warning(f"予期しない数の入力フィールド: {len(code_inputs)}")
            raise ValueError(f"入力フィールドの数が不正です: {len(code_inputs)}")
        
        # 最終的なログインボタン
        login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
        login_button.click()
        logger.info("ログインボタンをクリック")
        
        # ログイン後の状態を待機
        WebDriverWait(driver, 30).until(
            EC.url_contains('share.streamlit.io')
        )
        logger.info("ログイン成功")
    
    except Exception as e:
        logger.error(f"ログイン中にエラーが発生: {e}")
        # エラー時のスクリーンショットを保存
        driver.save_screenshot('screenshot_login_error.png')
        raise

def visit_streamlit_app(url, email):
    """
    Streamlitアプリにアクセスしてログインを試みる
    
    Args:
        url: アクセスするURL
        email: ログインに使用するメールアドレス
    """
    # WebDriverのセットアップ
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # ChromeDriverの自動インストール
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # Streamlitログインページにアクセス
        driver.get(url)
        logger.info(f"URLにアクセス: {url}")
        
        # ログイン処理
        login_to_streamlit(driver, email)
        
        # アプリが読み込まれるまで待機
        time.sleep(15)
        
        # スクリーンショットを保存
        driver.save_screenshot('screenshot_after_login.png')
        logger.info("ログイン後のスクリーンショットを保存")
    
    except Exception as e:
        logger.error(f"アプリ訪問中にエラーが発生: {e}")
        # エラー時のスクリーンショットを保存
        driver.save_screenshot('screenshot_error.png')
        raise
    
    finally:
        driver.quit()
        logger.info("ブラウザを閉じました")

def main():
    """
    メイン関数 - Streamlitアプリにログインを試みる
    """
    # 環境変数から認証情報を取得
    email_config = get_email_config()
    
    # 訪問するStreamlitアプリのリスト
    streamlit_apps = [
        "https://concur-dev-support.streamlit.app/"
    ]
    
    for app_url in streamlit_apps:
        try:
            visit_streamlit_app(app_url, email_config['email'])
        except Exception as e:
            logger.error(f"{app_url}の訪問中にエラーが発生: {e}")
        
        time.sleep(5)  # アプリ間の訪問に少し間隔を空ける

if __name__ == '__main__':
    start_time = time.time()
    logger.info("Keep-Alive ジョブ開始")
    
    main()
    
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Keep-Alive ジョブ終了 (所要時間: {duration:.2f}秒)")