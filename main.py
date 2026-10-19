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
    seen_urls = {}  # 💡 重複リンクを排除して安定させるための辞書
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
            
        if url not in seen_urls:
            seen_urls[url] = True
            cleaned.append({"name": name, "url": url})
    return cleaned

def extract_events_with_ai(app_name):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    default_model = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    models_to_try = [default_model, 'gemini-2.5-flash']
    models_to_try = list(dict.fromkeys(models_to_try))

    # 💡 現在の年（2026年）を明示し、過去のイベントや古いライブの混入を徹底的に防ぐプロンプト
    current_year = datetime.datetime.now().strftime("%Y")
    prompt = f"""
あなたはソシャゲ「{app_name}」の正確な最新情報リサーチャーです。
現在（{current_year}年）にゲーム内で開催されているイベント、今後開催予定のイベント、ガチャ、リアルイベント（コラボカフェや生放送など）の情報を、Google検索を用いて正確に探してください。

【🚨 超重要・絶対厳守ルール（過去データの排除）】
- **必ず {current_year}年 の現在または未来のスケジュールのみを対象にしてください。** 過去（昨年や一昨年など、すでに終了した古いイベントや過去のライブツアー等）の情報は絶対に取得しないでください。
- 公式サイトや信頼できる最新ニュースに掲載されている情報のみをソースにしてください。
- 過去のイベントページ（すでに終了した日付のもの）がヒットした場合は、**「現在開催されていない過去のもの」として絶対に除外**してください。
- 関連リンクは主要な公式のものに絞り、無駄な増減がないよう整理してください。架空のURLは禁止です。

直近〜今後のスケジュールを調べ、以下のJSON形式の配列だけで出力してください。
余計な解説文やバッククォート(```)は含めず、純粋なJSON文字列のみを返してください。見つからない場合は `[]` を返してください。

各要素は以下のキーを持つオブジェクトにしてください：
- title: イベント名
- start_date: 開始日 (YYYY-MM-DD)
- end_date: 終了日 (YYYY-MM-DD) （※終了日の記載がない場合は開始日と同日、または推測して必ずYYYY-MM-DD形式で入れてください）
- description: 概要（開催場所や詳細な内容も含めてください）
- category: "game" （ゲーム内） または "gacha" （ガチャ） または "real" （リアルイベント・生放送等）
- links: 公式サイト等のリスト（配列）。各要素は name と url のキーを持つオブジェクト。
"""
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1  # 💡 揺らぎを最小限にするため温度を低めに設定
                )
            )
            
            # 🌐 どこを徘徊して情報を引っ張ってきたか（検索ソース）をGitHubのログに出力して確認
            try:
                if response.candidates and response.candidates[0].grounding_metadata:
                    metadata = response.candidates[0].grounding_metadata
                    if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                        print(f"   🌐 【参照されたWEBソース ({app_name})】")
                        for chunk in metadata.grounding_chunks:
                            if chunk.web:
                                print(f"      - {chunk.web.title}: {chunk.web.uri}")
            except Exception as log_err:
                pass
            
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
    
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(jst).date()
    
    all_events = []
    for app_name in APPS:
        print(f"🔍 Google検索で情報収集中: {app_name}")
        events = extract_events_with_ai(app_name)
        
        for ev in events:
            # 🛡️ 【最重要ガード】Python側で完全に日付を検証し、今日より過去のイベントを強制排除する
            end_str = ev.get('end_date')
            if end_str:
                try:
                    end_date = datetime.date.fromisoformat(end_str)
                    # 終了日が今日より前のものは、AIが何と言おうと絶対にリストに入れない
                    if end_date < today:
                        print(f"   ⏩ 過去のイベントのため除外: [{app_name}] {ev.get('title')} (終了日: {end_str})")
                        continue
                except:
                    continue
            else:
                continue

            ev['app_name'] = app_name
            if 'category' not in ev:
                ev['category'] = 'game'
            
            raw_links = ev.get('links', [])
            ev['links'] = clean_links(raw_links)
            
            all_events.append(ev)

    if not all_events:
        print("⚠️ 抽出できた有効なイベントが0件だったため、保存・送信をスキップします。")
        return

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
