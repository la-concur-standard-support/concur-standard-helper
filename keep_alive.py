#!/usr/bin/env python3
"""
Streamlit アプリ Keep-Alive スクリプト
GitHub Actions で定期実行し、Streamlit アプリを活性化し続けるためのスクリプト
"""

import os
import time
import logging
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ログの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def visit_streamlit_app(url, email=None, password=None):
    """
    Streamlit アプリにアクセスする関数
    
    Parameters:
    - url: アクセス先の Streamlit アプリの URL
    - email: Streamlit ログイン用メールアドレス (プライベートアプリの場合)
    - password: Streamlit ログイン用パスワード (プライベートアプリの場合)
    """
    try:
        logger.info(f"訪問開始: {url}")
        
        # リクエストでアプリの存在確認 (初期チェック)
        try:
            response = requests.get(url, timeout=30)
            logger.info(f"初期アクセスステータス: {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"初期アクセス失敗: {e}")
        
        # ヘッドレスChromeの設定
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # User-Agentの設定
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
        
        # ChromeDriverのセットアップ
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # タイムアウトを設定
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(30)
        
        # URLにアクセス
        driver.get(url)
        logger.info(f"ページタイトル: {driver.title}")
        
        # プライベートアプリでログインが必要な場合
        if email and password:
            try:
                # スクリーンショット撮影（ログイン前の状態確認用）
                driver.save_screenshot('screenshot_before_login.png')
                logger.info("ログイン前のスクリーンショット撮影")
                
                # ログインボタンが存在するか確認（短いタイムアウトで）
                login_button = None
                try:
                    login_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Log in')]"))
                    )
                    logger.info("ログインボタンが見つかりました。ログイン処理を開始します。")
                except Exception as e:
                    # エラーメッセージをシンプルにする
                    error_message = str(e).split('\n')[0] if str(e) else "タイムアウト"
                    logger.info(f"ログインボタンが見つかりません: {error_message}")
                    logger.info("ログインは不要かすでにログイン済みの可能性があります。処理を続行します。")
                
                # ログインボタンが見つかった場合のみログイン処理を実行
                if login_button:
                    login_button.click()
                    
                    # メールアドレスの入力
                    email_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                    )
                    email_input.send_keys(email)
                    
                    # 次へボタンのクリック
                    continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                    continue_button.click()
                    
                    # パスワードの入力
                    password_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                    )
                    password_input.send_keys(password)
                    
                    # ログインボタンのクリック
                    login_submit = driver.find_element(By.XPATH, "//button[@type='submit']")
                    login_submit.click()
                    
                    # ログイン後、アプリが読み込まれるまで待機
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                    )
                    
                    logger.info("ログイン成功")
                
                # スクリーンショット撮影（ログイン後の状態確認用）
                driver.save_screenshot('screenshot_after_login.png')
                logger.info("ログイン後のスクリーンショット撮影")
            except Exception as e:
                # エラーメッセージをシンプルにする
                error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
                logger.warning(f"ログイン処理中にエラー発生: {error_message}")
                logger.info("ログインに失敗しましたが、処理を続行します。")
                # エラー時のスクリーンショット
                driver.save_screenshot('screenshot_login_error.png')
                logger.info("エラー時のスクリーンショット撮影")
        
        # アプリが読み込まれるまで待機
        time.sleep(15)
        
        # ページソースのサイズを取得してログ出力
        page_source_length = len(driver.page_source)
        logger.info(f"ページソース長: {page_source_length} bytes")
        
        # 最終確認のスクリーンショット
        driver.save_screenshot('screenshot_final.png')
        logger.info("最終確認のスクリーンショット撮影")
        
        # 追加の待機時間 (アプリの完全ロード用)
        time.sleep(10)
        
        logger.info(f"訪問成功: {url}")
        
    except Exception as e:
        # エラーメッセージをシンプルにする
        error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
        logger.error(f"エラー発生: {error_message}")
        
        # エラー詳細は必要な場合のみ出力
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"詳細エラー情報:", exc_info=True)
        
        # エラー時のスクリーンショット
        if 'driver' in locals() and driver:
            try:
                driver.save_screenshot('screenshot_error.png')
                logger.info("エラー時のスクリーンショット撮影")
            except:
                pass
    
    finally:
        # ブラウザを閉じる
        if 'driver' in locals() and driver:
            try:
                driver.quit()
                logger.info("ブラウザを閉じました")
            except Exception as e:
                logger.warning(f"ブラウザを閉じる際にエラーが発生: {e}")

def main():
    """
    メイン関数 - 訪問するStreamlitアプリのリストを定義し、順に訪問
    """
    # 環境変数からログイン情報を取得
    email = os.environ.get('STREAMLIT_EMAIL')
    password = os.environ.get('STREAMLIT_PASSWORD')
    
    # 訪問するStreamlitアプリのリスト
    streamlit_apps = [
        "https://concur-dev-support.streamlit.app/"
    ]
    
    for app_url in streamlit_apps:
        visit_streamlit_app(app_url, email, password)
        time.sleep(5)  # アプリ間の訪問に少し間隔を空ける

if __name__ == "__main__":
    start_time = datetime.now()
    logger.info(f"Keep-Alive ジョブ開始: {start_time}")
    
    main()
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Keep-Alive ジョブ終了: {end_time} (所要時間: {duration})")