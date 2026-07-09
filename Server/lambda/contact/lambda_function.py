import json
import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError

ses_client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "ap-northeast-1"))

# 環境変数で設定しておくと便利
NOTIFY_TO_EMAIL = "info.polis.japan@gmail.com"  # 転送先（自分のアドレス）
FROM_EMAIL = '"PolisJAPAN" <noreply@mail.pol-is.jp>'  # SES で検証済みの送信元アドレス


def lambda_handler(event, context):
    """
    フォームから POST された内容をメールで転送する Lambda ハンドラ
    """
    try:
        # API Gateway (Lambda プロキシ統合) 経由の場合の例
        if "body" in event:
            # body は JSON 文字列として来ることが多いのでパース
            body_dict = json.loads(event["body"])
        else:
            # 直接テストなどで JSON を渡す場合用
            body_dict = event

        mail_address = body_dict.get("mail", "")
        user_name = body_dict.get("name", "")
        inquiry_content = body_dict.get("content", "")

        print(body_dict)
        print(f"mail_address: {mail_address}")
        print(f"user_name: {user_name}")
        print(f"inquiry_content: {inquiry_content}")

        # 管理者宛のメール本文を整形
        subject = "【お問い合わせ】Webフォームからの新規問い合わせ"
        body_text = (
            "Webフォームからお問い合わせがありました。\n\n"
            f"お名前: {user_name}\n"
            f"メールアドレス: {mail_address}\n\n"
            "お問い合わせ内容:\n"
            "------------------------------\n"
            f"{inquiry_content}\n"
            "------------------------------\n"
        )

        # SES でメール送信
        response = ses_client.send_email(
            Source=FROM_EMAIL,
            Destination={
                "ToAddresses": [NOTIFY_TO_EMAIL],
            },
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                },
            },
            ReplyToAddresses=[],
        )

        # ユーザー宛メール本文を整形
        user_mail_subject = "【PolisJAPAN】お問い合わせありがとうございます。(自動返信)"
        user_mail_body_text = (
            "------------------------------\n"
            "※このメールは自動配信メールです。\n"
            "------------------------------\n"
            "\n"
            f"{user_name} 様\n"
            "\n"
            "この度は、お問い合わせいただき誠にありがとうございます。\n"
            "以下の内容にて、お問い合わせを受け付けいたしました。\n"
            "\n"
            "------------------------------\n"
            "\n"
            f"お名前: {user_name}\n"
            "\n"
            f"メールアドレス: {mail_address}\n\n"
            "\n"
            "お問い合わせ内容:\n"
            f"{inquiry_content}\n"
            "\n"
            "------------------------------\n"
            "\n"
            "お問い合わせの内容は、順次確認させていただきます。\n"
            "ご返信させていただく場合、返信までにお時間を頂戴することがございます。\n"
            "あらかじめご了承ください。\n"
            "\n"
            "※このメールは送信専用アドレスで送信しているため、ご返信いただいてもご回答できかねます。何卒ご了承ください。\n"
            "\n"
            "\n"
            "------------------------------\n"
            "PolisJAPAN運営チーム\n"
            "https://pol-is.jp/\n"
        )

        # SES でメール送信
        response = ses_client.send_email(
            Source=FROM_EMAIL,
            Destination={
                "ToAddresses": [mail_address],
            },
            Message={
                "Subject": {"Data": user_mail_subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": user_mail_body_text, "Charset": "UTF-8"},
                },
            },
            ReplyToAddresses=[],
        )

        # API Gateway 用の戻り値
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"message": "ok", "ses_message_id": response["MessageId"]}),
        }

    except (BotoCoreError, ClientError) as e:
        # SES 通信エラーなど
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"message": "send error", "error": str(e)}),
        }

    except Exception as e:
        # その他エラー
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"message": "internal error", "error": str(e)}),
        }
