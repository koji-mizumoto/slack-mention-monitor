@echo off
echo Slack Mention Monitor Development Environment

REM ngrokを起動（別ウィンドウ）
start cmd /k "ngrok http 3000"

REM 5秒待機（ngrokの起動を待つ）
timeout /t 5

REM アプリケーションを起動
python slack_mention_forwarder_dev.py

pause