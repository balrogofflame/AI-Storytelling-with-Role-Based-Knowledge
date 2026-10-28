"""Offline checks by default; --live makes one billable API request."""

import argparse
import sys

from ai_client import AppError, configuration_status, generate, read_configuration


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="檢查 AI 設定，不顯示金鑰。")
    parser.add_argument("--live", action="store_true", help="送出一次真實 API 請求，可能產生費用")
    args = parser.parse_args()
    status = configuration_status()
    print("Python：" + sys.version.split()[0])
    print("API 金鑰：" + ("已設定（不顯示內容）" if status["key_configured"] else "尚未設定"))
    print("模型名稱：" + ("已設定" if status["model_configured"] else "尚未設定"))
    try:
        read_configuration()
        if not args.live:
            print("本機設定檢查通過；尚未驗證網路、金鑰權限、模型可用性或額度。")
            print("執行 python check_ai.py --live 可送出一次真實連線測試。")
            return 0
        print("正在送出一次真實連線測試（可能產生費用，不自動重試）…", flush=True)
        result = generate("請使用繁體中文簡短回答。", "請回覆：銀鈴旅店連線成功。")
        print("真實 API 問答成功。模型：" + result["model"])
        print("AI 回答：" + result["answer"])
        return 0
    except AppError as exc:
        print("檢查未通過：" + str(exc))
        print("準備步驟請見 README.md。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
