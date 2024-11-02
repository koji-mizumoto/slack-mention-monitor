import os
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from flask import Flask, request, jsonify
import logging

# ロギングの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    """アプリケーションファクトリー関数"""
    flask_app = Flask(__name__)
    
    # デバッグモードを有効化
    flask_app.debug = True
    
    port = int(os.getenv("PORT", 10000))
    flask_app.config['PORT'] = port
    
    # 環境変数の確認
    workspace_configs = {
        "workspace_b": {
            "app": App(
                token=os.environ.get("WORKSPACE_B_SOURCE_TOKEN"),
                signing_secret=os.environ.get("WORKSPACE_B_SIGNING_SECRET")
            ),
            "client": WebClient(token=os.environ.get("WORKSPACE_B_SOURCE_TOKEN")),
            "target_user_id": os.environ.get("WORKSPACE_B_TARGET_USER_ID"),
            "handler": None
        },
        "workspace_c": {
            "app": App(
                token=os.environ.get("WORKSPACE_C_SOURCE_TOKEN"),
                signing_secret=os.environ.get("WORKSPACE_C_SIGNING_SECRET")
            ),
            "client": WebClient(token=os.environ.get("WORKSPACE_C_SOURCE_TOKEN")),
            "target_user_id": os.environ.get("WORKSPACE_C_TARGET_USER_ID"),
            "handler": None
        }
    }

    # ハンドラーの初期化
    for config in workspace_configs.values():
        config["handler"] = SlackRequestHandler(config["app"])

    @flask_app.route("/slack/events", methods=["POST"])
    def slack_events():
        logger.info("Received Slack event")
        logger.info(f"Headers: {request.headers}")
        logger.info(f"Body: {request.get_data().decode('utf-8')}")
        
        try:
            event_data = request.json
            
            # URLの検証チャレンジに応答
            if event_data.get("type") == "url_verification":
                return jsonify({"challenge": event_data["challenge"]})
                
            # チーム情報の取得
            team_id = event_data.get("team_id")
            if not team_id:
                logger.error("team_id not found in request")
                return jsonify({"error": "team_id not found"}), 400
                
            # イベントの処理
            event = event_data.get("event", {})
            event_type = event.get("type")
            
            logger.info(f"Processing {event_type} event for team {team_id}")
            
            if event_type == "message":
                # メッセージイベントの処理
                return handle_message_event(team_id, event)
                
            return jsonify({"ok": True})
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return jsonify({"error": str(e)}), 500

    def handle_message_event(team_id, event):
        try:
            if team_id not in workspace_configs:
                logger.error(f"Team {team_id} not configured")
                return jsonify({"error": "Team not configured"}), 404
                
            config = workspace_configs[team_id]
            text = event.get("text", "")
            channel = event.get("channel")
            
            logger.info(f"Message in channel {channel}: {text}")
            
            # メンションの検知と処理
            if "@mention" in text:
                config["client"].chat_postMessage(
                    channel=channel,
                    text="メンションを検知しました"
                )
                
            return jsonify({"ok": True})
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return jsonify({"error": str(e)}), 500

    for workspace_id, config in workspace_configs.items():
        @config["app"].event("message")
        def handle_message(body, logger):
            logger.info(f"Received message event: {body}")
            try:
                event = body["event"]
                channel = event["channel"]
                text = event["text"]
                
                # メッセージ処理ロジックを実装
                if "@mention" in text:
                    config["client"].chat_postMessage(
                        channel=channel,
                        text="メンションを検知しました"
                    )
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    # ヘルスチェックエンドポイントを追加
    @flask_app.route("/", methods=["GET", "HEAD"])
    def health_check():
        return jsonify({"status": "ok"}), 200

    # 環境変数のログ出力（トークンは除く）
    logger.info("Checking environment variables...")
    logger.info(f"PORT: {os.environ.get('PORT')}")
    logger.info(f"Configured workspaces: {list(workspace_configs.keys())}")

    return flask_app

# アプリケーションのインスタンス作成
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=10000)