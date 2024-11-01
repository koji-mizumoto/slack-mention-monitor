import os
from slack_bolt import App
from slack_sdk import WebClient
from dotenv import load_dotenv
from datetime import datetime
import requests
import threading
import time

# 環境変数の読み込み
load_dotenv()

# ポート番号の設定
port = int(os.environ.get("PORT", 3000))

# 送信元のSlackワークスペースの設定
SOURCE_SLACK_BOT_TOKEN = os.environ["SOURCE_SLACK_BOT_TOKEN"]
SOURCE_SIGNING_SECRET = os.environ["SOURCE_SIGNING_SECRET"]

# 転送先のSlackワークスペースの設定
DEST_SLACK_BOT_TOKEN = os.environ["DEST_SLACK_BOT_TOKEN"]
DEST_CHANNEL = os.environ["DEST_CHANNEL"]

# 監視対象のユーザーIDを環境変数から取得
TARGET_USER_ID = os.environ["TARGET_USER_ID"]

# メンション対象のユーザーID
MENTION_USERS = [
    "<@U014UEXF9NG>",  # 高丸さん
    "<@U05T1273RN1>",  # 浮ケ谷さん
    "<@U01STUG6QQN>",  # 小林(未)さん
]

# アプリの初期化
app = App(
    token=SOURCE_SLACK_BOT_TOKEN,
    signing_secret=SOURCE_SIGNING_SECRET
)

# 転送先のクライアント初期化
dest_client = WebClient(token=DEST_SLACK_BOT_TOKEN)

@app.event("message")
def handle_message(event, say):
    # タイムスタンプの確認を追加
    from datetime import datetime
    timestamp = float(event.get('ts', 0))
    event_time = datetime.fromtimestamp(timestamp)
    
    print("==== 新しいメッセージイベント ====")
    print(f"受信時刻: {datetime.now()}")
    print(f"メッセージ時刻: {event_time}")
    print(f"イベントタイプ: {event.get('subtype', 'message')}")
    print(f"メッセージ: {event.get('text', 'No text')}")
    print("================================")

    # メッセージにテキストが含まれていない場合はスキップ
    if "text" not in event:
        print("テキストが含まれていません")
        return

    # メッセージ本文からメンションされているユーザーを確認
    text = event["text"]
    print(f"検索するユーザーID: <@{TARGET_USER_ID}>")
    print(f"メッセージ本文: {text}")
    
    if f"<@{TARGET_USER_ID}>" not in text:
        print("監視対象のユーザーがメンションされていません")
        return
   
    # イベントの内容を確認
    print("==== イベント内容の確認 ====")
    print("イベント全体:", event)
    print("利用可能なキー:", list(event.keys()))

    try:
        user = event.get("user", "unknown_user")
        channel = event.get("channel", "unknown_channel")
        text = event.get("text", "")
        
        # メンションを含むテキストを処理する関数
        def replace_mentions_with_names(text, client):
            import re
            # メンションのパターン: <@USERID>
            mention_pattern = r'<@(U[A-Z0-9]+)>'
            mentions = re.findall(mention_pattern, text)
            
            # 置換用の辞書を作成
            replacements = {}
            for user_id in mentions:
                try:
                    user_info = client.users_info(user=user_id)
                    if user_info["ok"]:
                        user_name = user_info["user"]["profile"]["real_name"]
                        replacements[f'<@{user_id}>'] = f'@{user_name}'
                except Exception as e:
                    print(f"ユーザー {user_id} の情報取得に失敗: {e}")
                    continue
            
            # テキスト内のメンションを置換
            processed_text = text
            for mention_id, name in replacements.items():
                processed_text = processed_text.replace(mention_id, name)
            
            return processed_text

        # ユーザー情報の取得
        try:
            user_info_response = WebClient(token=SOURCE_SLACK_BOT_TOKEN).users_info(user=user)
            if user_info_response["ok"]:
                user_name = user_info_response["user"]["profile"]["real_name"]
            else:
                user_name = f"Unknown User ({user})"
        except Exception as e:
            print(f"ユーザー情報の取得でエラー: {e}")
            user_name = f"Unknown User ({user})"

        # チャンネル情報の取得
        try:
            channel_info_response = WebClient(token=SOURCE_SLACK_BOT_TOKEN).conversations_info(channel=channel)
            if channel_info_response["ok"]:
                channel_name = channel_info_response["channel"]["name"]
            else:
                channel_name = f"Unknown Channel ({channel})"
        except Exception as e:
            print(f"チャンネル情報の取得でエラー: {e}")
            channel_name = f"Unknown Channel ({channel})"
            
        # メッセージ本文のメンションを実際の名前に変換
        processed_text = replace_mentions_with_names(text, WebClient(token=SOURCE_SLACK_BOT_TOKEN))
        
        # メッセージの各行に引用記号（>）をつける
        message_lines = processed_text.split('\n')
        quoted_message = '\n>'.join(message_lines)
            
        # メンション文字列の作成
        mentions = " ".join(MENTION_USERS)
            
        # 転送するメッセージの作成
        forward_message = (
            f"{mentions}\n"  # メンションを先頭に追加
            f"*特定のユーザーがメンションされました*\n"
            f">送信者: {user_name}\n"
            f">チャンネル: #{channel_name}\n"
            f">メッセージ: {quoted_message}"
        )
        
        print(f"転送メッセージを作成しました: {forward_message}")
        
        # 転送先のチャンネルにメッセージを送信
        dest_client.chat_postMessage(
            channel=DEST_CHANNEL,
            text=forward_message
        )
        print("メッセージの転送に成功しました")
        
    except Exception as e:
        print(f"全体的なエラーが発生しました: {e}")
        print("イベントの内容:", event)


def keep_alive():
    app_url = "https://slack-mention-monitor.onrender.com/"  # RenderのURLに変更
    while True:
        try:
            response = requests.get(app_url)
            print(f"[{datetime.now()}] キープアライブ ping 送信: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now()}] キープアライブ エラー: {e}")
        time.sleep(600)  # 10分ごとにリクエスト

if __name__ == "__main__":
    while True:
        try:
            print("アプリケーションを起動します...")
            
            # キープアライブスレッドの起動
            keep_alive_thread = threading.Thread(target=keep_alive)
            keep_alive_thread.daemon = True
            keep_alive_thread.start()
            
            # 定期チェックスレッドの起動
            check_thread = threading.Thread(target=periodic_check)
            check_thread.daemon = True
            check_thread.start()
            
            # アプリケーションの起動
            app.start(port=port, host="0.0.0.0")
        
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            print("30秒後に再起動します...")
            time.sleep(30)