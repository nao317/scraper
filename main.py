import requests
from bs4 import BeautifulSoup, Tag
import time
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from scraper_template import fetch_bloomberg_article, parse_article

# BERT感情分析のインポート（オプション）
try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        BertJapaneseTokenizer,
    )
    SENTIMENT_ANALYSIS_AVAILABLE = True
    
    # BERTを用いた日本語の感情分析モデルをロード
    print("BERT感情分析モデルをロード中...")
    tokenizer = BertJapaneseTokenizer.from_pretrained(
        "cl-tohoku/bert-base-japanese-whole-word-masking"
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        "koheiduck/bert-japanese-finetuned-sentiment"
    )
    print("BERT感情分析モデルのロードが完了しました。")
    
except ImportError as e:
    print(f"感情分析ライブラリが見つかりません: {e}")
    print("感情分析機能は無効になります。")
    SENTIMENT_ANALYSIS_AVAILABLE = False

def extract_text_from_html(html_content: str) -> str:
    """
    HTMLコンテンツからテキストを抽出し、不要な要素を除去する
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # スクリプトやスタイルタグを除去
    for script in soup(["script", "style"]):
        script.decompose()
    
    # テキストを取得
    text = soup.get_text()
    
    # 改行や空白を整理
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    # 不要な文字を除去（日本語文字と基本的な句読点を保持）
    text = re.sub(r'\s+', ' ', text)  # 複数の空白を1つに
    text = re.sub(r'[^\w\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\u3000-\u303F。、！？]', '', text)
    
    return text

def get_sentiment_score(text: str) -> float:
    """
    テキストの感情スコアを計算する（BERT使用）
    """
    if not SENTIMENT_ANALYSIS_AVAILABLE:
        return 0.0
    
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs).logits
        prob = torch.softmax(logits, dim=1)[0]
        return float(prob[2] - prob[1])  # Positive - Negative
    except Exception as e:
        print(f"感情分析エラー: {e}")
        return 0.0

def analyze_article_sentiment(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    記事のコンテンツに対して感情分析を実行する
    """
    if not SENTIMENT_ANALYSIS_AVAILABLE:
        print("感情分析機能が利用できません。")
        return article
    
    content = article.get('content', '')
    if not content or content == "本文取得に失敗しました" or content == "本文を取得できませんでした":
        print(f"記事「{article.get('title', 'タイトル不明')[:30]}...」の本文が取得できていません。")
        article['sentiment'] = {
            'available': False,
            'message': '本文が取得できていないため分析できません'
        }
        return article
    
    print(f"感情分析中: {article.get('title', 'タイトル不明')[:30]}...")
    
    # HTMLの場合はテキストを抽出
    if '<' in content and '>' in content:
        text_content = extract_text_from_html(content)
    else:
        text_content = content
    
    if not text_content.strip():
        article['sentiment'] = {
            'available': False,
            'message': '分析可能なテキストが見つかりません'
        }
        return article
    
    # テキストを文（句点「。」）で分割
    sentences = [s.strip() for s in text_content.split('。') if s.strip()]
    
    if not sentences:
        article['sentiment'] = {
            'available': False,
            'message': '文に分割できませんでした'
        }
        return article
    
    print(f"  {len(sentences)}個の文を分析中...")
    
    # 各文のスコアを計算
    scores = []
    for sentence in sentences:
        if len(sentence) > 5:  # 短すぎる文は除外
            score = get_sentiment_score(sentence)
            scores.append(score)
    
    if scores:
        average_score = sum(scores) / len(scores)
        positive_count = sum(1 for s in scores if s > 0.1)
        negative_count = sum(1 for s in scores if s < -0.1)
        neutral_count = len(scores) - positive_count - negative_count
        
        # 感情の判定
        if average_score > 0.1:
            overall_sentiment = "ポジティブ"
        elif average_score < -0.1:
            overall_sentiment = "ネガティブ"
        else:
            overall_sentiment = "中立"
        
        article['sentiment'] = {
            'available': True,
            'average_score': round(average_score, 4),
            'overall_sentiment': overall_sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'total_sentences': len(scores)
        }
        
        print(f"  結果: {overall_sentiment} (スコア: {average_score:.4f})")
    else:
        article['sentiment'] = {
            'available': False,
            'message': '分析できる文が見つかりませんでした'
        }
    
    return article

def scrape_single_article(url: str) -> Dict[str, Any] | None:
    """
    単一の記事URLから記事情報を取得する汎用関数
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print(f"記事を取得中: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # URLに基づいてソースを判定
        if 'bloomberg.com' in url:
            # Bloomberg記事の場合
            article = parse_article(response.text)
            article['url'] = url
            article['source'] = 'Bloomberg'
            return article
        else:
            # 汎用的なスクレイピング
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_selectors = ['h1', 'title', '.headline', '.title', '[data-testid="headline"]']
            title = "タイトル不明"
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if len(title) > 5:
                        break
            
            # 本文取得
            content_selectors = [
                'article', '.article-body', '.content', '.post-content', 
                '.entry-content', '[data-testid="article-body"]', 'main',
                '.story-body', '.article-content'
            ]
            
            content = "本文を取得できませんでした"
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # スクリプトやスタイルタグを除去
                    for script in content_elem(["script", "style", "nav", "header", "footer", "aside"]):
                        script.decompose()
                    
                    content = content_elem.get_text(strip=True)
                    if len(content) > 100:
                        break
            
            # 日付取得（ベストエフォート）
            date_selectors = ['.date', '.published', '.timestamp', 'time', '[datetime]']
            date = "日付不明"
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date = date_elem.get_text(strip=True) or date_elem.get('datetime', '日付不明')
                    if date != "日付不明":
                        break
            
            # ソース判定
            source = "不明"
            if 'reuters.com' in url:
                source = 'ロイター'
            elif 'nikkei.com' in url:
                source = '日経新聞'
            elif 'asahi.com' in url:
                source = '朝日新聞'
            elif 'mainichi.jp' in url:
                source = '毎日新聞'
            elif 'yomiuri.co.jp' in url:
                source = '読売新聞'
            elif 'cnn.co.jp' in url:
                source = 'CNN'
            elif 'nhk.or.jp' in url:
                source = 'NHK'
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': source,
                'date': date,
                'author': '著者不明'
            }
            
    except Exception as e:
        print(f"記事取得エラー: {e}")
        return None

def display_article(article: Dict[str, Any]) -> None:
    """
    記事情報を見やすく表示する
    """
    print(f"タイトル: {article.get('title', 'タイトル不明')}")
    print(f"ソース: {article.get('source', '不明')}")
    print(f"URL: {article.get('url', '不明')}")
    print(f"投稿日: {article.get('date', '日付不明')}")
    print(f"著者: {article.get('author', '著者不明')}")
    
    content = article.get('content', '内容なし')
    if len(content) > 500:
        print(f"内容（最初の500文字）: {content[:500]}...")
    else:
        print(f"内容: {content}")

# 日付指定関連の関数群は削除（URL直接指定方式に変更したため）

def process_csv_articles(csv_file_path: str) -> pd.DataFrame:
    """
    CSVファイルからURLを読み込み、記事をスクレイピングして感情分析を実行
    """
    print(f"CSVファイルを読み込み中: {csv_file_path}")
    
    try:
        # CSVファイルを読み込み
        df = pd.read_csv(csv_file_path)
        print(f"総記事数: {len(df)}件")
        
        # 結果を格納するリスト
        results = []
        
        # 進行状況の表示
        total_articles = len(df)
        processed = 0
        
        for index, row in df.iterrows():
            processed += 1
            date_str = row['date']
            url = row['bloomberg_url']
            
            print(f"\n進行状況: {processed}/{total_articles} ({processed/total_articles*100:.1f}%)")
            print(f"処理中: {date_str} - {url}")
            
            try:
                # 記事をスクレイピング
                article = scrape_single_article(url)
                
                if article and article.get('content') != "本文を取得できませんでした":
                    # 感情分析を実行
                    if SENTIMENT_ANALYSIS_AVAILABLE:
                        analyzed_article = analyze_article_sentiment(article)
                        sentiment = analyzed_article.get('sentiment', {})
                        
                        if sentiment.get('available', False):
                            results.append({
                                'date': pd.to_datetime(date_str),
                                'url': url,
                                'title': article.get('title', 'タイトル不明'),
                                'sentiment_score': sentiment['average_score'],
                                'overall_sentiment': sentiment['overall_sentiment'],
                                'positive_count': sentiment['positive_count'],
                                'negative_count': sentiment['negative_count'],
                                'neutral_count': sentiment['neutral_count'],
                                'total_sentences': sentiment['total_sentences']
                            })
                            print(f"✅ 分析完了: {sentiment['overall_sentiment']} (スコア: {sentiment['average_score']:.4f})")
                        else:
                            print(f"⚠️ 感情分析失敗: {sentiment.get('message', '不明なエラー')}")
                    else:
                        results.append({
                            'date': pd.to_datetime(date_str),
                            'url': url,
                            'title': article.get('title', 'タイトル不明'),
                            'sentiment_score': 0.0,
                            'overall_sentiment': '分析不可',
                            'positive_count': 0,
                            'negative_count': 0,
                            'neutral_count': 0,
                            'total_sentences': 0
                        })
                        print("⚠️ BERT感情分析が利用できません")
                else:
                    print("❌ 記事の取得に失敗")
                    
            except Exception as e:
                print(f"❌ エラー: {e}")
                
            # リクエスト間隔を調整（サーバー負荷軽減）
            time.sleep(2)
        
        # 結果をDataFrameに変換
        results_df = pd.DataFrame(results)
        print(f"\n処理完了: {len(results_df)}件の記事を分析しました")
        return results_df
        
    except Exception as e:
        print(f"CSV処理エラー: {e}")
        return pd.DataFrame()

def create_sentiment_timeline_chart(df: pd.DataFrame, save_path: str = "sentiment_timeline.png"):
    """
    感情分析結果の時系列グラフを作成
    """
    if df.empty:
        print("データが空のため、グラフを作成できません")
        return
    
    # 日本語フォント設定
    plt.rcParams['font.family'] = ['DejaVu Sans', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']
    
    # 図のサイズを設定
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
    fig.suptitle('Bloomberg記事の感情分析 - 時系列チャート', fontsize=16, fontweight='bold')
    
    # データを日付でソート
    df_sorted = df.sort_values('date')
    
    # 1. 感情スコアの時系列プロット
    ax1.plot(df_sorted['date'], df_sorted['sentiment_score'], 'b-', linewidth=1.5, alpha=0.7)
    ax1.scatter(df_sorted['date'], df_sorted['sentiment_score'], c=df_sorted['sentiment_score'], 
                cmap='RdYlGn', s=30, alpha=0.8)
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_ylabel('感情スコア', fontweight='bold')
    ax1.set_title('感情スコアの推移', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # 2. 感情カテゴリの分布（積み上げ棒グラフ）
    # 日付ごとにグループ化
    daily_sentiment = df_sorted.groupby('date').agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'neutral_count': 'sum'
    }).reset_index()
    
    ax2.bar(daily_sentiment['date'], daily_sentiment['positive_count'], 
            label='ポジティブ', color='green', alpha=0.7)
    ax2.bar(daily_sentiment['date'], daily_sentiment['negative_count'], 
            bottom=daily_sentiment['positive_count'],
            label='ネガティブ', color='red', alpha=0.7)
    ax2.bar(daily_sentiment['date'], daily_sentiment['neutral_count'], 
            bottom=daily_sentiment['positive_count'] + daily_sentiment['negative_count'],
            label='中立', color='gray', alpha=0.7)
    
    ax2.set_ylabel('文章数', fontweight='bold')
    ax2.set_title('感情カテゴリ別文章数の推移', fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. 移動平均線
    window_size = min(5, len(df_sorted))  # 最大5日の移動平均
    if window_size >= 2:
        df_sorted['sentiment_ma'] = df_sorted['sentiment_score'].rolling(window=window_size, center=True).mean()
        ax3.plot(df_sorted['date'], df_sorted['sentiment_score'], 'lightblue', alpha=0.5, label='感情スコア')
        ax3.plot(df_sorted['date'], df_sorted['sentiment_ma'], 'darkblue', linewidth=2, label=f'{window_size}件移動平均')
        ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax3.set_ylabel('感情スコア', fontweight='bold')
        ax3.set_title('感情スコア移動平均', fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # X軸の日付フォーマット
    for ax in [ax1, ax2, ax3]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # レイアウト調整
    plt.tight_layout()
    
    # グラフを保存
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"グラフを保存しました: {save_path}")
    
    # グラフを表示
    plt.show()
    
    # 統計情報を表示
    print("\n=== 感情分析統計 ===")
    print(f"平均感情スコア: {df['sentiment_score'].mean():.4f}")
    print(f"感情スコア標準偏差: {df['sentiment_score'].std():.4f}")
    print(f"最高スコア: {df['sentiment_score'].max():.4f}")
    print(f"最低スコア: {df['sentiment_score'].min():.4f}")
    
    sentiment_counts = df['overall_sentiment'].value_counts()
    print(f"\n感情分布:")
    for sentiment, count in sentiment_counts.items():
        percentage = (count / len(df)) * 100
        print(f"  {sentiment}: {count}件 ({percentage:.1f}%)")

def main():
    """
    メイン関数：ユーザーに選択肢を提供してニュース記事を取得
    """
    print("=== ニュース記事取得・感情分析システム ===")
    print("利用可能な機能:")
    print("1. 記事取得（URL指定）")
    if SENTIMENT_ANALYSIS_AVAILABLE:
        print("2. 記事取得＋感情分析（URL指定）")
        print("3. CSV一括処理＋感情分析＋時系列グラフ")
    print("0. 終了")
    print("")
    
    while True:
        try:
            print("\n=== メニュー ===")
            print("1. 記事取得（URL指定）")
            if SENTIMENT_ANALYSIS_AVAILABLE:
                print("2. 記事取得＋感情分析（URL指定）")
                print("3. CSV一括処理＋感情分析＋時系列グラフ")
            print("0. 終了")
            
            max_option = 3 if SENTIMENT_ANALYSIS_AVAILABLE else 1
            option = int(input(f"選択してください（0-{max_option}）: "))
            
            if option == 0:
                print("プログラムを終了します。")
                break
            elif option == 1:
                # 記事取得（URL指定）
                url = input("記事のURLを入力してください: ").strip()
                if url:
                    try:
                        article = scrape_single_article(url)
                        if article:
                            display_article(article)
                        else:
                            print("記事の取得に失敗しました。")
                    except Exception as e:
                        print(f"記事取得エラー: {e}")
            elif option == 2 and SENTIMENT_ANALYSIS_AVAILABLE:
                # 記事取得＋感情分析（URL指定）
                url = input("分析したい記事のURLを入力してください: ").strip()
                if url:
                    try:
                        article = scrape_single_article(url)
                        if article:
                            print("\n=== 記事情報 ===")
                            display_article(article)
                            
                            print("\n=== 感情分析実行中 ===")
                            analyzed_article = analyze_article_sentiment(article)
                            
                            sentiment = analyzed_article.get('sentiment', {})
                            if sentiment.get('available', False):
                                print(f"\n=== 感情分析結果 ===")
                                print(f"全体的な感情: {sentiment['overall_sentiment']}")
                                print(f"感情スコア: {sentiment['average_score']:.4f}")
                                print(f"分析対象文数: {sentiment['total_sentences']}文")
                                print(f"ポジティブ: {sentiment['positive_count']}文")
                                print(f"ネガティブ: {sentiment['negative_count']}文")
                                print(f"中立: {sentiment['neutral_count']}文")
                            else:
                                print(f"感情分析が実行できませんでした: {sentiment.get('message', '不明なエラー')}")
                        else:
                            print("記事の取得に失敗しました。")
                    except Exception as e:
                        print(f"記事取得・分析エラー: {e}")
            elif option == 3 and SENTIMENT_ANALYSIS_AVAILABLE:
                # CSV一括処理＋感情分析＋時系列グラフ
                csv_file = "bloomberg_urls.csv"
                print(f"CSVファイル「{csv_file}」から記事を一括処理します")
                
                # ユーザーに確認
                confirm = input(f"この処理には時間がかかります。続行しますか？ (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    try:
                        # CSV処理を実行
                        results_df = process_csv_articles(csv_file)
                        
                        if not results_df.empty:
                            # 結果をCSVファイルに保存
                            output_file = "sentiment_analysis_results.csv"
                            results_df.to_csv(output_file, index=False, encoding='utf-8')
                            print(f"結果を保存しました: {output_file}")
                            
                            # 時系列グラフを作成
                            create_sentiment_timeline_chart(results_df)
                        else:
                            print("処理できる記事がありませんでした。")
                    except Exception as e:
                        print(f"CSV処理エラー: {e}")
                else:
                    print("処理をキャンセルしました。")
            else:
                print(f"無効な選択です。0-{max_option}の範囲で選択してください。")
        
        except ValueError:
            print("無効な入力です。数字を入力してください。")
        except KeyboardInterrupt:
            print("\nプログラムを終了します。")
            break
        except Exception as e:
            print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
