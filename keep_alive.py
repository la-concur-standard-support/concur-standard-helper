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
        options.add_argument('--window-size=1920,1080')  # 大きな画面サイズを設定
        
        # User-Agentの設定
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
        
        # ChromeDriverのセットアップ
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # タイムアウトを設定
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
        # URLにアクセス
        driver.get(url)
        logger.info(f"ページタイトル: {driver.title}")
        logger.info(f"現在のURL: {driver.current_url}")
        
        # スクリーンショット撮影 (初期状態)
        driver.save_screenshot('screenshot_initial.png')
        logger.info("初期状態のスクリーンショット撮影")
        
        # プライベートアプリでログインが必要な場合
        if email and password:
            try:
                # 「You do not have access to this app or it does not exist」のテキストを探す
                access_denied_text = "You do not have access to this app or it does not exist"
                if access_denied_text in driver.page_source:
                    logger.info("アクセス制限メッセージを検出: 'You do not have access to this app or it does not exist'")
                    
                    # 'sign in' リンクの詳細なセレクタ（スクリーンショットから）
                    sign_in_link = None
                    try:
                        # クラスを使用した正確なセレクタ
                        sign_in_link = driver.find_element(By.CLASS_NAME, "text-blue-700.hover\\:text-blue-600")
                        logger.info("sign in リンクを見つけました (クラス名で検索)")
                    except:
                        try:
                            # ページ内のすべてのリンクをチェック
                            links = driver.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                if "sign in" in link.text.lower():
                                    sign_in_link = link
                                    logger.info("sign in リンクを見つけました (テキストで検索)")
                                    break
                        except:
                            logger.warning("sign in リンクが見つかりませんでした")
                    
                    if sign_in_link:
                        sign_in_link.click()
                        logger.info("sign in リンクをクリックしました")
                    else:
                        # リンクが見つからない場合は直接ログインURLに移動
                        logger.info("sign in リンクが見つからないため、直接ログインページにアクセスします")
                        driver.get("https://share.streamlit.io/login")
                    
                    # 遷移後のスクリーンショット
                    time.sleep(3)
                    driver.save_screenshot('screenshot_login_page.png')
                    logger.info(f"ログインページの現在のURL: {driver.current_url}")
                    
                    # ログインフォームが表示されるまで待機
                    try:
                        email_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                        )
                        email_input.clear()
                        email_input.send_keys(email)
                        logger.info(f"メールアドレス '{email}' を入力しました")
                        
                        # 入力後のスクリーンショット
                        driver.save_screenshot('screenshot_email_entered.png')
                        
                        # Continueボタンを見つけてクリック
                        # 複数の可能性のあるセレクタを試す
                        continue_button = None
                        selectors = [
                            "//button[contains(text(), 'Continue')]",
                            "//button[@type='submit']",
                            "//button[contains(@class, 'bg-blue-700')]"
                        ]
                        
                        for selector in selectors:
                            try:
                                continue_button = driver.find_element(By.XPATH, selector)
                                break
                            except:
                                continue
                        
                        if continue_button:
                            continue_button.click()
                            logger.info("Continueボタンをクリックしました")
                        else:
                            logger.warning("Continueボタンが見つかりませんでした")
                            # ボタンのHTMLを表示（デバッグ用）
                            buttons = driver.find_elements(By.TAG_NAME, "button")
                            if buttons:
                                logger.info(f"ページ上のボタン数: {len(buttons)}")
                                for i, button in enumerate(buttons):
                                    logger.info(f"ボタン {i+1}: テキスト='{button.text}', クラス='{button.get_attribute('class')}', type='{button.get_attribute('type')}'")
                        
                        # パスワード入力フォームが表示されるまで待機
                        time.sleep(5)
                        driver.save_screenshot('screenshot_password_form.png')
                        
                        try:
                            password_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                            )
                            password_input.clear()
                            password_input.send_keys(password)
                            logger.info("パスワードを入力しました")
                            
                            # 入力後のスクリーンショット
                            driver.save_screenshot('screenshot_password_entered.png')
                            
                            # ログインボタンをクリック
                            login_button = None
                            login_selectors = [
                                "//button[contains(text(), 'Sign in')]",
                                "//button[contains(text(), 'Log in')]",
                                "//button[@type='submit']",
                                "//button[contains(@class, 'bg-blue-700')]"
                            ]
                            
                            for selector in login_selectors:
                                try:
                                    login_button = driver.find_element(By.XPATH, selector)
                                    break
                                except:
                                    continue
                            
                            if login_button:
                                login_button.click()
                                logger.info("ログインボタンをクリックしました")
                            else:
                                logger.warning("ログインボタンが見つかりませんでした")
                                # ボタンのHTMLを表示（デバッグ用）
                                buttons = driver.find_elements(By.TAG_NAME, "button")
                                if buttons:
                                    logger.info(f"ページ上のボタン数: {len(buttons)}")
                                    for i, button in enumerate(buttons):
                                        logger.info(f"ボタン {i+1}: テキスト='{button.text}', クラス='{button.get_attribute('class')}', type='{button.get_attribute('type')}'")
                            
                            # ログイン後の画面遷移を待機
                            time.sleep(10)
                            driver.save_screenshot('screenshot_after_login.png')
                            logger.info(f"ログイン後のURL: {driver.current_url}")
                            
                            # アクセス制限メッセージがまだあるかチェック
                            if access_denied_text in driver.page_source:
                                logger.warning("ログイン後もアクセス制限メッセージが表示されています。ログインに失敗した可能性があります。")
                            else:
                                logger.info("ログイン成功: アクセス制限メッセージが表示されなくなりました。")
                            
                        except Exception as e:
                            error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
                            logger.warning(f"パスワード入力中にエラー発生: {error_message}")
                    
                    except Exception as e:
                        error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
                        logger.warning(f"メールアドレス入力中にエラー発生: {error_message}")
                
                else:
                    logger.info("アクセス制限メッセージが検出されませんでした。ログイン不要かすでにログイン済みの可能性があります。")
                
            except Exception as e:
                error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
                logger.warning(f"ログイン処理中にエラー発生: {error_message}")
                driver.save_screenshot('screenshot_login_error.png')
        
        # アプリが読み込まれるまで待機
        time.sleep(15)
        
        # ページソースのサイズを取得してログ出力
        page_source_length = len(driver.page_source)
        logger.info(f"ページソース長: {page_source_length} bytes")
        
        # 最終確認のスクリーンショット
        driver.save_screenshot('screenshot_final.png')
        logger.info("最終確認のスクリーンショット撮影")
        logger.info(f"最終URL: {driver.current_url}")
        
        # 現在のページを再読み込み（Keep-Alive効果を最大化）
        driver.refresh()
        time.sleep(5)
        driver.save_screenshot('screenshot_after_refresh.png')
        logger.info("ページ再読み込み後のスクリーンショット撮影")
        
        logger.info(f"訪問成功: {url}")
        
    except Exception as e:
        error_message = str(e).split('\n')[0] if str(e) else "不明なエラー"
        logger.error(f"エラー発生: {error_message}")
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"詳細エラー情報:", exc_info=True)
        
        if 'driver' in locals() and driver:
            try:
                driver.save_screenshot('screenshot_error.png')
                logger.info("エラー時のスクリーンショット撮影")
            except:
                pass
    
    finally:
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
    
    # ログイン情報のチェック
    if email and password:
        logger.info(f"ログイン情報が設定されています (メールアドレス: {email})")
    else:
        logger.warning("ログイン情報が設定されていません。環境変数STREAMLIT_EMAILとSTREAMLIT_PASSWORDを確認してください。")
    
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