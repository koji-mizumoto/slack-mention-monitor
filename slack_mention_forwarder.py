import os
from slack_bolt import App
from slack_sdk import WebClient
from flask import Flask, request
from slack_bolt.adapter.flask import SlackRequestHandler
from datetime import datetime
import logging

# ロギングの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 環境変数の確認（WORKSPACE_CONFIGSの定義の前に）
logger.debug("=== Environment Variables Check ===")
for key in os.environ:
    if 'TOKEN' in key or 'SECRET' in key:
        logger.debug(f"{key}: {'*' * 10}")

# 環境変数の確認
logger.debug("=== Environment Variables Check ===")
for key in os.environ:
    if 'TOKEN' in key or 'SECRET' in key:
        logger.debug(f"{key}: {'*' * 10}")  # トークンの値は隠して表示

# 監視対象ワークスペースの設定
WORKSPACE_CONFIGS = {
    "workspace_b": {
        "app": App(
            token=os.environ.get("WORKSPACE_B_SOURCE_TOKEN"),
            signing_secret=os.environ.get("WORKSPACE_B_SIGNING_SECRET")
        ),
        "client": WebClient(token=os.environ.get("WORKSPACE_B_SOURCE_TOKEN")),
        "target_user_id": os.environ.get("WORKSPACE_B_TARGET_USER_ID"),
        "handler": None  # 後で初期化
    },
    "workspace_c": {
        "app": App(
            token=os.environ.get("WORKSPACE_C_SOURCE_TOKEN"),
            signing_secret=os.environ.get("WORKSPACE_C_SIGNING_SECRET")
        ),
        "client": WebClient(token=os.environ.get("WORKSPACE_C_SOURCE_TOKEN")),
        "target_user_id": os.environ.get("WORKSPACE_C_TARGET_USER_ID"),
        "handler": None  # 後で初期化
    }
}

# 設定の詳細なデバッグ出力
logger.debug("=== Workspace Configs ===")
for workspace_id, config in WORKSPACE_CONFIGS.items():
    logger.debug(f"\n{workspace_id}:")
    logger.debug(f"app: {bool(config.get('app'))}")
    logger.debug(f"client: {bool(config.get('client'))}")
    logger.debug(f"target_user_id: {config.get('target_user_id')}")
    logger.debug(f"handler: {bool(config.get('handler'))}")

# クライアントの初期化を確認
try:
    dest_client = WebClient(token=os.environ["WORKSPACE_A_BOT_TOKEN"])
    logger.debug("Destination client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing destination client: {e}")

# 各ワークスペースのクライアント初期化を確認
for workspace_id in ["workspace_b", "workspace_c"]:
    try:
        token_key = f"WORKSPACE_{workspace_id[-1].upper()}_SOURCE_TOKEN"
        secret_key = f"WORKSPACE_{workspace_id[-1].upper()}_SIGNING_SECRET"
        logger.debug(f"Checking {workspace_id}")
        logger.debug(f"Token key exists: {token_key in os.environ}")
        logger.debug(f"Secret key exists: {secret_key in os.environ}")
    except Exception as e:
        logger.error(f"Error checking {workspace_id}: {e}")

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

def setup_message_handlers():
    """各ワークスペースのメッセージハンドラーを設定"""
    for workspace_id, config in WORKSPACE_CONFIGS.items():
        @config["app"].event("message")
        def handle_message(event, context):
            """メッセージイベントの処理"""
            # ワークスペースの特定
            current_workspace_id = context.get("team_id")
            current_config = WORKSPACE_CONFIGS.get(workspace_id)
            if not current_config:
                print(f"未設定のワークスペース: {current_workspace_id}")
                return

            # 設定とクライアントの取得
            client = current_config["client"]  # workspace_clientsの代わりにconfigから直接取得

            # タイムスタンプの確認
            timestamp = float(event.get('ts', 0))
            event_time = datetime.fromtimestamp(timestamp)
            
            print(f"==== 新しいメッセージ（{current_workspace_id}） ====")
            print(f"受信時刻: {datetime.now()}")
            print(f"メッセージ時刻: {event_time}")

            # メッセージの検証
            if "text" not in event:
                print("テキストなし")
                return

            text = event["text"]
            if f"<@{current_config['target_user_id']}>" not in text:
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
                    f"*{current_workspace_id}でメンションされました*\n"
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

# メッセージハンドラーの設定を実行
setup_message_handlers()

# Flaskルート
@flask_app.route("/", methods=["GET"])
def health_check():
    return "Slack Mention Monitor is running!"

@flask_app.route("/slack/events/<workspace_id>", methods=["POST"])
def slack_events(workspace_id):
    logger.info(f"\n=== Received Slack Event ===")
    logger.info(f"Workspace ID: {workspace_id}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    logger.info(f"Request Data: {request.get_data().decode('utf-8')}")
    
    if workspace_id not in WORKSPACE_CONFIGS:
        logger.error(f"Error: Workspace not found: {workspace_id}")
        return "Workspace not found", 404
    
    try:
        result = WORKSPACE_CONFIGS[workspace_id]["handler"].handle(request)
        logger.info("Event handled successfully")
        return result
    except Exception as e:
        logger.error(f"Error handling event: {e}")
        return str(e), 500

# Renderで実行する場合の設定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)

# Renderのアプリケーション
application = flask_app

# 起動時に環境変数をチェック
print("=== Environment Variables Check ===")
for workspace_id, config in WORKSPACE_CONFIGS.items():
    print(f"\nChecking {workspace_id}:")
    print(f"Token exists: {'source_token' in config}")
    print(f"Target user ID: {config['target_user_id']}")

# 起動時のデバッグ情報
logger.info("=== Starting Slack Mention Monitor ===")
for workspace_id, config in WORKSPACE_CONFIGS.items():
    logger.info(f"\nChecking {workspace_id}:")
    logger.info(f"Token exists: {bool(config.get('client'))}")
    logger.info(f"Target User ID: {config.get('target_user_id')}")