import os
import json
import time
import requests
from google import genai
from google.genai import types

# --- 対象のアプリ名リスト ---
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

def extract_events_with_ai(app_name):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    default_model = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    models_to_try = [default_model, 'gemini-2.5-flash']
    models_to_try = list(dict.fromkeys(models_to_try))

    prompt = f"""
あなたはソシャゲやゲームの最新情報リサーチャーです。
現在開催中、または今後開催予定のソシャゲ「{app_name}」に関する以下の情報を、Google検索を用いて網羅的に探してください：
1. ゲーム内イベント・キャンペーン情報
2. ガチャ・ピックアップ情報
3. リアルイベント（ポップアップストア、コラボカフェ、展覧会、ライブ、アニメイトフェアなど）

直近〜今後のスケジュールを調べ、以下のJSON形式の配列だけで出力してください。
余計な解説文やバッククォート(```)は含めず、純粋なJSON文字列のみを返してください。見つからない場合は `[]` を返してください。

各要素は以下のキーを持つオブジェクトにしてください：
- title: イベント名
- start_date: 開始日 (YYYY-MM-DD)
- end_date: 終了日 (YYYY-MM-DD) （※終了日の記載がない場合は開始日と同日、または推測して必ずYYYY-MM-DD形式で入れてください。空欄にしないでください）
- description: 概要（開催場所や詳細な内容も含めてください）
- category: "game" （ゲーム内イベント等の場合） または "gacha" （ガチャ等の場合） または "real" （コラボカフェ・ポップアップ等のリアルイベントの場合）
- links: 関連する公式サイトや主要な攻略サイト（Wiki等）のリスト（配列）。各要素は name（例: "公式サイト", "攻略Wiki" 等の名称）と url（URL）のキーを持つオブジェクト。見つからない場合は空配列 `[]` にしてください。
"""
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3
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

def main():
    gas_url = os.environ.get('GAS_WEB_APP_URL')
    if not gas_url:
        print("GAS_WEB_APP_URL が設定されていません。")
        return

    all_events = []
    for app_name in APPS:
        print(f"🔍 Google検索で情報収集中: {app_name}")
        events = extract_events_with_ai(app_name)
        for ev in events:
            ev['app_name'] = app_name
            if 'category' not in ev:
                ev['category'] = 'game'
            if 'links' not in ev:
                ev['links'] = []
            all_events.append(ev)

    if not all_events:
        print("⚠️ 抽出できたイベントが0件だったため、送信をスキップします。")
        return

    print(f"📤 スプレッドシートへデータ送信中... (計 {len(all_events)} 件)")
    try:
        res = requests.post(gas_url, json=all_events, timeout=120)
        print(f"送信結果: {res.text}")
    except Exception as e:
        print(f"送信エラー: {e}")

if __name__ == '__main__':
    main()
