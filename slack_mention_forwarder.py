import os
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from flask import Flask, request, jsonify
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    """アプリケーションファクトリー関数"""
    flask_app = Flask(__name__)
    
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

    @flask_app.route("/slack/events/<workspace_id>", methods=["POST"])
    def slack_events(workspace_id):
        logger.info(f"Received request for workspace: {workspace_id}")
        logger.info(f"Request data: {request.get_data()}")
        
        if workspace_id not in workspace_configs:
            return jsonify({"error": "Invalid workspace"}), 404
        
        handler = workspace_configs[workspace_id]["handler"]
        return handler.handle(request)

    for workspace_id, config in workspace_configs.items():
        @config["app"].event("message")
        def handle_message(body, logger):
            logger.info(f"Received message event: {body}")
            try:
                # メッセージ処理ロジック
                pass
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    return flask_app

# アプリケーションのインスタンス作成
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=10000)