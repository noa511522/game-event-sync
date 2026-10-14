import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google import genai

# --- 全12タイトル・31URLのリスト ---
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
    {"app_name": "崩壊スターレイル", "url": "https://gamewith.jp/houkaistarrail/"},
    {"app_name": "崩壊スターレイル", "url": "https://game8.jp/houkaistarrail"},

    # --- 崩壊3rd ---
    {"app_name": "崩壊3rd", "url": "https://houkai3rd.hoyoverse.com/fab"},
    {"app_name": "崩壊3rd", "url": "https://spicycurryboy.hatenablog.com/archive/category/%E5%B4%A9%E5%A3%8A3rd"},

    # --- 鳴潮 ---
    {"app_name": "鳴潮", "url": "https://wutheringwaves.kurogames.com/jp/"},
    {"app_name": "鳴潮", "url": "https://gamewith.jp/wutheringwaves/"},
    {"app_name": "鳴潮", "url": "https://game8.jp/wutheringwaves"},
    {"app_name": "鳴潮", "url": "https://www.youtube.com/@toryu/featured"},

    # --- IDOLY PRIDE ---
    {"app_name": "IDOLY PRIDE", "url": "https://idolypride.jp/"},
    {"app_name": "IDOLY PRIDE", "url": "https://idolyp.cloudfree.jp/"},

    # --- プリンセスコネクト!Re:Dive ---
    {"app_name": "プリコネR", "url": "https://priconne-redive.jp/"},
    {"app_name": "プリコネR", "url": "https://gamewith.jp/pricone-re/"},
    {"app_name": "プリコネR", "url": "https://www.youtube.com/@vashpeer"},
    {"app_name": "プリコネR", "url": "https://www.youtube.com/@Eruru"},

    # --- ブルーアーカイブ ---
    {"app_name": "ブルーアーカイブ", "url": "https://bluearchive.jp/"},
    {"app_name": "ブルーアーカイブ", "url": "https://game8.jp/blue-archive"},
    {"app_name": "ブルーアーカイブ", "url": "https://www.youtube.com/@vashpeer"},

    # --- ヘブンバーンズレッド ---
    {"app_name": "ヘブンバーンズレッド", "url": "https://heaven-burns-red.com/"},
    {"app_name": "ヘブンバーンズレッド", "url": "https://game8.jp/heavenburnsred"},

    # --- アワーノーツ ---
    {"app_name": "アワーノーツ", "url": "https://bang-dream-on.bushimo.jp/"},
    {"app_name": "アワーノーツ", "url": "https://appmedia.jp/bang-dream-on"},
    {"app_name": "アワーノーツ", "url": "https://www.youtube.com/@marcie0404"},

    # --- マブラヴ ガールズガーデン ---
    {"app_name": "マブラヴ ガールズガーデン", "url": "https://muvluv-girls-garden.com/"},
    {"app_name": "マブラヴ ガールズガーデン", "url": "https://kamigame.jp/muvluv-gg/"},

    # --- 学園アイドルマスター ---
    {"app_name": "学園アイドルマスター", "url": "https://gakuen.idolmaster-official.jp/"}
    {"app_name": "学園アイドルマスター", "url": "https://game8.jp/gakuen-idolmaster"}
]

def fetch_web_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        print(f"URLの取得に失敗 ({url}): {e}")
        return ""

def fetch_youtube_text(channel_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(channel_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        link_tag = soup.find("link", {"rel": "alternate", "type": "application/rss+xml"})
        if not link_tag:
            return ""
        rss_response = requests.get(link_tag.get("href"), headers=headers, timeout=10)
        rss_soup = BeautifulSoup(rss_response.text, 'xml')
        
        text_data = []
        for entry in rss_soup.find_all('entry')[:5]:
            title = entry.find('title').text if entry.find('title') else ""
            group = entry.find('media:group')
            desc = group.find('media:description').text if group and group.find('media:description') else ""
            text_data.append(f"動画タイトル: {title}\n概要欄:\n{desc}\n---")
        return "\n".join(text_data)
    except Exception as e:
        print(f"YouTube取得失敗 ({channel_url}): {e}")
        return ""

def extract_events_with_ai(raw_text, app_name):
    try:
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
        prompt = f"""
以下のテキストはソシャゲ「{app_name}」の公式サイト、攻略情報、または関連YouTube動画の概要欄です。
ここから【ゲーム内イベント】および【リアルイベント】の情報をすべて抽出し、以下のJSON形式の配列だけで出力してください。
余計な解説文やバッククォート(```)は含めず、純粋なJSON文字列のみを返してください。見つからない場合は `[]` を返してください。
- title: イベント名
- start_date: 開始日 (YYYY-MM-DD)
- end_date: 終了日 (YYYY-MM-DD) （※終了日の記載がない場合は開始日と同日、または推測して必ずYYYY-MM-DD形式で入れてください。空欄にしないでください）
- description: 概要

対象テキスト：
{raw_text[:15000]}
"""
        response = client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
        time.sleep(12)
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        print(f"AI解析エラー ({app_name}): {e}")
        time.sleep(12)
        return []

def main():
    gas_url = os.environ.get('GAS_WEB_APP_URL')
    if not gas_url:
        print("GAS_WEB_APP_URL が設定されていません。")
        return

    all_events = []
    for target in TARGET_URLS:
        url = target['url']
        app_name = target['app_name']
        print(f"🔍 情報収集中: {app_name} ({url})")
        
        raw_text = fetch_youtube_text(url) if "youtube.com" in url else fetch_web_text(url)
        if not raw_text:
            continue
        
        events = extract_events_with_ai(raw_text, app_name)
        for ev in events:
            ev['app_name'] = app_name
            all_events.append(ev)

    if not all_events:
        print("⚠️ 抽出できたイベントが0件だったため、送信をスキップします。")
        return

    print(f"📤 スプレッドシート＆カレンダーへデータ送信中... (計 {len(all_events)} 件)")
    try:
        res = requests.post(gas_url, json=all_events, timeout=30)
        print(f"送信結果: {res.text}")
    except Exception as e:
        print(f"送信エラー: {e}")

if __name__ == '__main__':
    main()
