import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from google import genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- ご指定いただいた全12タイトル、公式サイト・攻略Wiki・YouTubeチャンネルのリスト ---
TARGET_URLS = [
    # --- FGO ---
    {"app_name": "FGO", "url": "https://news.fate-go.jp/"},
    {"app_name": "FGO", "url": "https://gamewith.jp/fgo/"},
    {"app_name": "FGO", "url": "https://game8.jp/fgo"},
    {"app_name": "FGO", "url": "https://www.youtube.com/@FGOAppMedia"},
    {"app_name": "FGO", "url": "https://www.youtube.com/@koyahan"},
    {"app_name": "FGO", "url": "https://www.youtube.com/@hakuginhato"},

    # --- 勝利の女神NIKKE ---
    {"app_name": "勝利の女神NIKKE", "url": "https://nikke-jp.com/"},
    {"app_name": "勝利の女神NIKKE", "url": "https://gamewith.jp/nikke/"},
    {"app_name": "勝利の女神NIKKE", "url": "https://game8.jp/nikke"},

    # --- 崩壊スターレイル ---
    {"app_name": "崩壊スターレイル", "url": "https://hsr.hoyoverse.com/news"},
    {"app_name": "崩壊スターレイル", "url": "https://gamewith.jp/star-rail/"},
    {"app_name": "崩壊スターレイル", "url": "https://game8.jp/hsr"},

    # --- 崩壊3rd ---
    {"app_name": "崩壊3rd", "url": "https://honkaiimpact3.hoyoverse.com/news"},

    # --- 鳴潮 ---
    {"app_name": "鳴潮", "url": "https://wutheringwaves.kurogames.com/jp/"},
    {"app_name": "鳴潮", "url": "https://gamewith.jp/wutheringwaves/"},
    {"app_name": "鳴潮", "url": "https://game8.jp/wutheringwaves"},
    {"app_name": "鳴潮", "url": "https://www.youtube.com/@toryu/featured"},

    # --- IDOLY PRIDE ---
    {"app_name": "IDOLY PRIDE", "url": "https://idolypride.jp/"},

    # --- プリンセスコネクト!Re:Dive ---
    {"app_name": "プリコネR", "url": "https://priconne-redive.jp/"},
    {"app_name": "プリコネR", "url": "https://www.youtube.com/@vashpeer"},
    {"app_name": "プリコネR", "url": "https://www.youtube.com/@Eruru"},

    # --- ブルーアーカイブ ---
    {"app_name": "ブルーアーカイブ", "url": "https://bluearchive.jp/"},
    {"app_name": "ブルーアーカイブ", "url": "https://www.youtube.com/@vashpeer"},

    # --- ヘブンバーンズレッド ---
    {"app_name": "ヘブンバーンズレッド", "url": "https://heaven-burns-red.com/"},
    {"app_name": "ヘブンバーンズレッド", "url": "https://game8.jp/heavenburnsred"},

    # --- アワーノーツ ---
    {"app_name": "アワーノーツ", "url": "https://ournotes.jp/"},
    {"app_name": "アワーノーツ", "url": "https://www.youtube.com/@marcie0404"},

    # --- マブラヴ ガールズガーデン ---
    {"app_name": "マブラヴ ガールズガーデン", "url": "https://muvluv-gg.com/"},
    {"app_name": "マブラヴ ガールズガーデン", "url": "https://kamigame.jp/muvluv-gg/"},

    # --- 学園アイドルマスター ---
    {"app_name": "学園アイドルマスター", "url": "https://game8.jp/gakuen-imas"}
]

def fetch_web_text(url):
    """通常のWebサイトや攻略Wikiからテキストを抽出する"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        print(f"URLの取得に失敗しました ({url}): {e}")
        return ""

def fetch_youtube_text(channel_url):
    """YouTubeチャンネルのRSSから最新動画のタイトルと概要欄を取得する"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(channel_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rss_link = None
        link_tag = soup.find("link", {"rel": "alternate", "type": "application/rss+xml"})
        if link_tag:
            rss_link = link_tag.get("href")
            
        if not rss_link:
            return ""
            
        rss_response = requests.get(rss_link, headers=headers, timeout=10)
        rss_soup = BeautifulSoup(rss_response.text, 'xml')
        
        text_data = []
        entries = rss_soup.find_all('entry')
        for entry in entries[:5]:
            title = entry.find('title').text if entry.find('title') else ""
            group = entry.find('media:group')
            desc = group.find('media:description').text if group and group.find('media:description') else ""
            text_data.append(f"動画タイトル: {title}\n概要欄:\n{desc}\n---")
            
        return "\n".join(text_data)
    except Exception as e:
        print(f"YouTubeの取得に失敗しました ({channel_url}): {e}")
        return ""

def extract_events_with_ai(raw_text, app_name):
    """新しい google-genai SDK を使ってイベント情報を抽出する"""
    try:
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
        
        prompt = f"""
以下のテキストはソシャゲ「{app_name}」の公式サイト、攻略情報、または関連YouTube動画の概要欄です。
ここから**【ゲーム内イベント】**および**【リアルイベント（ポップアップストア、展覧会、コラボカフェ、コンビニ・飲食店とのコラボ、リアルライブ等）】**の情報をすべて抽出し、以下のJSON形式の配列（リスト）だけで出力してください。
余計な解説文やマークダウンのバッククォート(```)は含めず、純粋なJSON文字列のみを返してください。イベントが見つからない場合は空の配列 `[]` を返してください。

抽出項目：
- title: イベント名（リアルイベントの場合は「【リアル】イベント名」のように分かりやすくしてください）
- start_date: 開始日 (YYYY-MM-DD形式)
- end_date: 終了日 (YYYY-MM-DD形式)
- description: 開催場所（秋葉原、渋谷など）やコラボ先、特典、獲得できる報酬などの概要

対象テキスト：
{raw_text[:15000]}
"""
        
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        time.sleep(12)
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        print(f"AIによる解析エラー ({app_name}): {e}")
        time.sleep(12)
        return []

def main():
    calendar_id = os.environ.get('GOOGLE_CALENDAR_ID')

    if not calendar_id:
        print("環境変数（GOOGLE_CALENDAR_ID）が設定されていません。")
        return

    # ★ワークフロー側で作成したファイルから安全に読み込む
    try:
        creds = Credentials.from_service_account_file(
            'service_account.json',
            scopes=['[https://www.googleapis.com/auth/calendar](https://www.googleapis.com/auth/calendar)']
        )
    except Exception as e:
        print(f"Googleカレンダーの認証情報の読み込みに失敗しました: {e}")
        return

    calendar_service = build('calendar', 'v3', credentials=creds)
    today = datetime.now().date()

    all_events = []
    for target in TARGET_URLS:
        url = target['url']
        app_name = target['app_name']
        print(f"🔍 情報収集中: {app_name} ({url})")
        
        if "youtube.com" in url or "youtu.be" in url:
            raw_text = fetch_youtube_text(url)
        else:
            raw_text = fetch_web_text(url)
            
        if not raw_text:
            continue
        
        events = extract_events_with_ai(raw_text, app_name)
        for ev in events:
            ev['app_name'] = app_name
            all_events.append(ev)

    try:
        existing_events_res = calendar_service.events().list(
            calendarId=calendar_id, singleEvents=True
        ).execute()
        existing_items = existing_events_res.get('items', [])
    except Exception as e:
        print(f"カレンダーのイベント取得に失敗しました: {e}")
        return

    # 期限切れイベントの削除
    for item in existing_items:
        summary = item.get('summary', '')
        end_date_str = item.get('end', {}).get('date')
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < today:
                    calendar_service.events().delete(
                        calendarId=calendar_id, eventId=item['id']
                    ).execute()
                    print(f"🗑️ 期限切れイベントを削除: {summary}")
            except Exception:
                continue

    # 新規登録・更新
    for ev in all_events:
        title = ev.get('title')
        app_name = ev.get('app_name')
        start_date = ev.get('start_date')
        end_date = ev.get('end_date')
        desc = f"詳細: {ev.get('description')}"

        if not title or not start_date or not end_date:
            continue

        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            next_day = (end_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            continue

        display_title = f"【{app_name}】{title}"
        
        found_event_id = None
        for item in existing_items:
            if item.get('summary') == display_title:
                found_event_id = item['id']
                break

        event_body = {
            'summary': display_title,
            'description': desc,
            'start': {'date': start_date},
            'end': {'date': next_day},
        }

        try:
            if found_event_id:
                calendar_service.events().update(
                    calendarId=calendar_id, eventId=found_event_id, body=event_body
                ).execute()
                print(f"🔄 更新: {display_title}")
            else:
                calendar_service.events().insert(
                    calendarId=calendar_id, body=event_body
                ).execute()
                print(f"✨ 新規登録: {display_title}")
        except Exception as e:
            print(f"カレンダーへの登録/更新に失敗しました ({display_title}): {e}")

if __name__ == '__main__':
    main()
