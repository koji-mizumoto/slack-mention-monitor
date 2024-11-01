import os
from slack_bolt import App
from slack_sdk import WebClient
from flask import Flask, request
from slack_bolt.adapter.flask import SlackRequestHandler
from datetime import datetime

# Flaskアプリケーションの初期化
flask_app = Flask(__name__)

# 監視対象ワークスペースの設定
WORKSPACE_CONFIGS = {
    "workspace_b": {
        "app": App(
            token=os.environ["WORKSPACE_B_SOURCE_TOKEN"],
            signing_secret=os.environ["WORKSPACE_B_SIGNING_SECRET"]
        ),
        "client": WebClient(token=os.environ["WORKSPACE_B_SOURCE_TOKEN"]),
        "target_user_id": os.environ["WORKSPACE_B_TARGET_USER_ID"],
        "handler": None  # 後で初期化
    },
    "workspace_c": {
        "app": App(
            token=os.environ["WORKSPACE_C_SOURCE_TOKEN"],
            signing_secret=os.environ["WORKSPACE_C_SIGNING_SECRET"]
        ),
        "client": WebClient(token=os.environ["WORKSPACE_C_SOURCE_TOKEN"]),
        "target_user_id": os.environ["WORKSPACE_C_TARGET_USER_ID"],
        "handler": None  # 後で初期化
    }
}

# 各ワークスペースのハンドラーを初期化
for workspace_id, config in WORKSPACE_CONFIGS.items():
    config["handler"] = SlackRequestHandler(config["app"])

# 転送先（ワークスペースA）のクライアント初期化
dest_client = WebClient(token=os.environ["WORKSPACE_A_BOT_TOKEN"])
DEST_CHANNEL = os.environ["DEST_CHANNEL"]

def replace_mentions_with_names(text, client):
    """メンションを実際のユーザー名に置換する"""
    import re
    mention_pattern = r'<@(U[A-Z0-9]+)>'
    mentions = re.findall(mention_pattern, text)
    
    for user_id in mentions:
        try:
            user_info = client.users_info(user=user_id)
            if user_info["ok"]:
                user_name = user_info["user"]["profile"]["real_name"]
                text = text.replace(f'<@{user_id}>', f'@{user_name}')
        except Exception as e:
            print(f"ユーザー情報の取得に失敗: {e}")
    
    return text

@app.event("message")
def handle_message(event, context):
    """メッセージイベントの処理"""
    # ワークスペースの特定
    workspace_id = context.get("team_id")
    if workspace_id not in WORKSPACE_CONFIGS:
        print(f"未設定のワークスペース: {workspace_id}")
        return

    # 設定とクライアントの取得
    config = WORKSPACE_CONFIGS[workspace_id]
    client = workspace_clients[workspace_id]

    # タイムスタンプの確認
    timestamp = float(event.get('ts', 0))
    event_time = datetime.fromtimestamp(timestamp)
    
    print(f"==== 新しいメッセージ（{workspace_id}） ====")
    print(f"受信時刻: {datetime.now()}")
    print(f"メッセージ時刻: {event_time}")

    # メッセージの検証
    if "text" not in event:
        print("テキストなし")
        return

    text = event["text"]
    if f"<@{config['target_user_id']}>" not in text:
        print("監視対象ユーザーのメンションなし")
        return

    try:
        # メッセージ情報の取得
        user = event.get("user", "unknown_user")
        channel = event.get("channel", "unknown_channel")

        # ユーザー情報の取得
        try:
            user_info = client.users_info(user=user)
            user_name = user_info["user"]["profile"]["real_name"] if user_info["ok"] else f"Unknown ({user})"
        except Exception as e:
            print(f"ユーザー情報の取得エラー: {e}")
            user_name = f"Unknown ({user})"

        # チャンネル情報の取得
        try:
            channel_info = client.conversations_info(channel=channel)
            channel_name = channel_info["channel"]["name"] if channel_info["ok"] else f"Unknown ({channel})"
        except Exception as e:
            print(f"チャンネル情報の取得エラー: {e}")
            channel_name = f"Unknown ({channel})"

        # メッセージの整形
        processed_text = replace_mentions_with_names(text, client)
        message_lines = processed_text.split('\n')
        quoted_message = '\n>'.join(message_lines)

        # 転送メッセージの作成
        forward_message = (
            f"*{workspace_id}でメンションされました*\n"
            f">送信者: {user_name}\n"
            f">チャンネル: #{channel_name}\n"
            f">メッセージ: {quoted_message}"
        )

        # 別ワークスペースに転送
        dest_client.chat_postMessage(
            channel=DEST_CHANNEL,
            text=forward_message
        )
        print("メッセージを転送しました")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

# Flaskルート
@flask_app.route("/", methods=["GET"])
def health_check():
    return "Slack Mention Monitor is running!"

@flask_app.route("/slack/events/<workspace_id>", methods=["POST"])
def slack_events(workspace_id):
    if workspace_id not in WORKSPACE_CONFIGS:
        return "Workspace not found", 404
    return WORKSPACE_CONFIGS[workspace_id]["handler"].handle(request)

# Renderで実行する場合の設定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)

# Renderのアプリケーション
application = flask_app