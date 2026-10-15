import os
import json
import time
import datetime
import requests
from google import genai
from google.genai import types

APPS = [
    "FGO",
    "勝利の女神NIKKE",
    "崩壊スターレイル",
    "崩壊3rd",
    "鳴潮",
    "IDOLY PRIDE",
    "プリコネR",
    "ブルーアーカイブ",
    "ヘブンバーンズレッド",
    "アワーノーツ",
    "マブラヴ ガールズガーデン",
    "学園アイドルマスター"
]

def clean_links(links):
    cleaned = []
    for l in links:
        if not isinstance(l, dict):
            continue
        url = l.get('url', '')
        name = l.get('name', '')
        
        if not url or not url.startswith('http'):
            continue
            
        if 'youtube.com' in url or 'youtu.be' in url:
            if not ('watch?v=' in url or '@' in url or '/channel/' in url or '/c/' in url or '/playlist?list=' in url or '/live/' in url):
                continue
                
        if 'javascript:' in url or 'example.com' in url or 'placeholder' in url:
            continue
            
        cleaned.append({"name": name, "url": url})
    return cleaned

def extract_events_with_ai(app_name):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    default_model = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    models_to_try = [default_model, 'gemini-2.5-flash']
    models_to_try = list(dict.fromkeys(models_to_try))

    # 💡 表記揺れの防止とリンクの安定化ルールをプロンプトに追加・強化
    prompt = f"""
あなたはソシャゲやゲームの最新情報リサーチャーです。
現在開催中、または今後開催予定のソシャゲ「{app_name}」に関する以下の情報を、Google検索を用いて網羅的に探してください：
1. ゲーム内イベント・キャンペーン情報
2. ガチャ・ピックアップ情報
3. リアルイベント（ポップアップストア、コラボカフェ、展覧会、ライブ、アニメイトフェアなど）
4. 公式生放送やYouTubeでの記念配信、PVなどの情報

【重要なお願い（データの安定化・正規化ルール）】
- イベント名は、公式サイトで使われている公式名称を正確に取得し、更新のたびに微妙な表現や略称が変わらない（揺れない）ように統一してください。
- 過去に開催されている定番イベントや継続中のものについても、正式なタイトルで一貫性を持たせてください。
- 関連リンク（公式サイト、公式YouTube、配信ページなど）は、主要なものを厳選して出力してください。無駄な増減や重複が発生しないよう整理してください。実際に存在する確実なURLのみを記載し、架空のURLは絶対に作らないでください。

直近〜今後のスケジュールを調べ、以下のJSON形式の配列だけで出力してください。
余計な解説文やバッククォート(```)は含めず、純粋なJSON文字列のみを返してください。見つからない場合は `[]` を返してください。

各要素は以下のキーを持つオブジェクトにしてください：
- title: イベント名（公式生放送などの場合はそのタイトル）
- start_date: 開始日 (YYYY-MM-DD)
- end_date: 終了日 (YYYY-MM-DD) （※終了日の記載がない場合は開始日と同日、または推測して必ずYYYY-MM-DD形式で入れてください）
- description: 概要（開催場所や詳細な内容も含めてください）
- category: "game" （ゲーム内イベント等の場合） または "gacha" （ガチャ等の場合） または "real" （コラボカフェ・リアルイベント・公式生放送等の場合）
- links: 公式サイト、公式YouTubeチャンネル、配信ページ等のリスト（配列）。各要素は name（例: "公式サイト", "公式YouTube", "配信ページ" 等の名称）と url（URL）のキーを持つオブジェクト。見つからない場合は空配列 `[]` にしてください。
"""
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2  # 💡 より安定した出力を得るため温度を少し下げました
                )
            )
            
            time.sleep(12)
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.endswith("```"): text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            print(f"⚠️ モデル '{model_name}' でエラー ({app_name}): {e}")
            time.sleep(5)
            continue
            
    print(f"AI検索エラー ({app_name}): すべてのモデルでの処理に失敗しました。")
    time.sleep(12)
    return []

def send_line_notification(messages):
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
    if not line_token or not messages:
        return

    text_body = "📢 【ゲームイベント リマインダー】\n\n" + "\n".join(messages)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }

    try:
        res = requests.post("[https://api.line.me/v2/bot/message/broadcast](https://api.line.me/v2/bot/message/broadcast)", headers=headers, json={"messages": [{"type": "text", "text": text_body}]}, timeout=30)
        print(f"LINE通知送信結果: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"LINE通知エラー: {e}")

def main():
    gas_url = os.environ.get('GAS_WEB_APP_URL')
    
    all_events = []
    for app_name in APPS:
        print(f"🔍 Google検索で情報収集中: {app_name}")
        events = extract_events_with_ai(app_name)
        for ev in events:
            ev['app_name'] = app_name
            if 'category' not in ev:
                ev['category'] = 'game'
            
            raw_links = ev.get('links', [])
            ev['links'] = clean_links(raw_links)
            
            all_events.append(ev)

    if not all_events:
        print("⚠️ 抽出できたイベントが0件だったため、保存・送信をスキップします。")
        return

    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(jst).date()
    notifications = []

    for ev in all_events:
        start_str = ev.get('start_date')
        end_str = ev.get('end_date')
        app = ev.get('app_name')
        title = ev.get('title')

        if start_str:
            try:
                start_date = datetime.date.fromisoformat(start_str)
                if start_date == today:
                    notifications.append(f"🟢 【本日から開始】\n[{app}] {title}")
            except:
                pass

        if end_str:
            try:
                end_date = datetime.date.fromisoformat(end_str)
                diff_days = (end_date - today).days
                if diff_days == 7:
                    notifications.append(f"⚠️ 【終了1週間前】\n[{app}] {title}\n(〜{end_str})")
            except:
                pass

    if notifications:
        print(f"📤 LINEへ通知を送信します（計 {len(notifications)} 件）")
        send_line_notification(notifications)
    else:
        print("📭 本日通知すべきイベントはありません。")

    if gas_url:
        print(f"📤 スプレッドシートへデータ送信中... (計 {len(all_events)} 件)")
        try:
            res = requests.post(gas_url, json=all_events, timeout=120)
            print(f"送信結果: {res.text}")
        except Exception as e:
            print(f"送信エラー (スプレッドシート): {e}")

    try:
        now_str = datetime.datetime.now(jst).strftime("%Y-%m-%d %H:%M")
        output_data = {
            "last_updated": now_str,
            "events": all_events
        }
        
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print("📁 data.json を正常に保存しました。")
    except Exception as e:
        print(f"ファイル保存エラー (data.json): {e}")

if __name__ == '__main__':
    main()
