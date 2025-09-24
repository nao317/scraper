import requests
from bs4 import BeautifulSoup, Tag
import time
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any
from scraper_template import fetch_bloomberg_article, parse_article

def get_nikkei_articles_by_date(date_str: str) -> List[Dict[str, Any]]:
    """
    指定日付の日経新聞記事を取得
    """
    articles: List[Dict[str, Any]] = []
    
    try:
        # 日経新聞の検索URL（日付フィルター付き）
        search_url = f"https://www.nikkei.com/search/?s={date_str}&t=0"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 記事リンクを取得
        article_links = soup.find_all('a', href=True)
        
        for link in article_links:
            if isinstance(link, Tag):
                href = link.get('href')
                if href and isinstance(href, str) and ('/article/' in href or '/news/' in href):
                    full_url = urljoin("https://www.nikkei.com", href)
                    title = link.get_text(strip=True)
                
                if title and len(title) > 10:  # タイトルが適切な長さ
                    articles.append({
                        'title': title,
                        'url': full_url,
                        'source': '日経新聞'
                    })
        
        # 重複除去
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        print(f"日経記事 {len(unique_articles)}件を発見")
        return unique_articles[:10]  # 最大10件
        
    except Exception as e:
        print(f"日経記事取得エラー: {e}")
        return []

def get_reuters_articles_by_date(date_str: str) -> List[Dict[str, Any]]:
    """
    指定日付のロイター記事を取得
    """
    articles: List[Dict[str, Any]] = []
    
    try:
        # ロイターの日付別記事URL
        date_formatted = date_str.replace('-', '/')
        reuters_url = f"https://jp.reuters.com/news/archive/{date_formatted}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(reuters_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ロイター記事のリンクを取得
        article_links = soup.find_all('a', href=True)
        
        for link in article_links:
            if isinstance(link, Tag):
                href = link.get('href')
                if href and isinstance(href, str) and '/news/' in href and '/archive/' not in href:
                    full_url = urljoin("https://jp.reuters.com", href)
                    title = link.get_text(strip=True)
                
                if title and len(title) > 10:  # タイトルが適切な長さ
                    articles.append({
                        'title': title,
                        'url': full_url,
                        'source': 'ロイター'
                    })
        
        # 重複除去
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        print(f"ロイター記事 {len(unique_articles)}件を発見")
        return unique_articles[:10]  # 最大10件
        
    except Exception as e:
        print(f"ロイター記事取得エラー: {e}")
        return []

def get_article_content(url: str, source: str) -> str:
    """
    記事URLから本文を取得
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        content = ""
        
        if source == '日経新聞':
            # 日経新聞の本文取得
            content_divs = soup.find_all(['div', 'p'], class_=re.compile(r'.*article.*|.*content.*|.*body.*'))
            for div in content_divs:
                if isinstance(div, Tag):
                    text = div.get_text(strip=True)
                    if text and len(text) > 20:
                        content += text + "\n"
        
        elif source == 'ロイター':
            # ロイターの本文取得
            content_divs = soup.find_all(['div', 'p'], class_=re.compile(r'.*ArticleBody.*|.*content.*|.*text.*'))
            for div in content_divs:
                if isinstance(div, Tag):
                    text = div.get_text(strip=True)
                    if text and len(text) > 20:
                        content += text + "\n"
        
        # 本文が取得できない場合の代替
        if not content:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                if isinstance(p, Tag):
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        content += text + "\n"
        
        return content.strip() if content else "本文を取得できませんでした"
        
    except Exception as e:
        print(f"本文取得エラー ({url}): {e}")
        return "本文取得に失敗しました"

def scrape_news_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事リストから各記事の本文を取得
    """
    full_articles: List[Dict[str, Any]] = []
    
    for i, article in enumerate(articles, 1):
        print(f"記事 {i}/{len(articles)} を処理中: {article['title'][:50]}...")
        
        try:
            # 記事本文を取得
            content = get_article_content(article['url'], article['source'])
            
            # 記事情報を更新
            article['content'] = content
            full_articles.append(article)
            
        except Exception as e:
            print(f"記事本文取得エラー ({article['title']}): {e}")
            article['content'] = "本文取得に失敗しました"
            full_articles.append(article)
    
    return full_articles

def main():
    """
    メイン関数
    """
    print("ニュース記事取得システム")
    print("="*30)
    print("1: Bloomberg記事取得（全文）")
    print("2: 日経・ロイター記事取得（本文含む）")
    print("0: 終了")
    print("="*30)
    
    while True:
        try:
            option = int(input("選択してください（0-2）: "))
            
            if option == 0:
                print("プログラムを終了します。")
                break
            elif option == 1:
                # Bloomberg記事取得
                url = input("Bloomberg記事のURLを入力してください: ").strip()
                if url:
                    try:
                        html = fetch_bloomberg_article(url)
                        if html:
                            article = parse_article(html)
                            print("\n=== 記事情報 ===")
                            print(f"タイトル: {article.get('title', 'タイトル不明')}")
                            print(f"URL: {url}")
                            print(f"投稿日: {article.get('date', '日付不明')}")
                            print(f"著者: {article.get('author', '著者不明')}")
                            content = article.get('content', '内容なし')
                            print(f"内容（最初の500文字）: {content[:500]}...")
                        else:
                            print("記事の取得に失敗しました。")
                    except Exception as e:
                        print(f"記事取得エラー: {e}")
            elif option == 2:
                # 日経・ロイター記事取得
                date_str = input("取得したい日付を入力してください（YYYY-MM-DD形式）: ").strip()
                if date_str:
                    try:
                        # 日付形式の検証
                        datetime.strptime(date_str, "%Y-%m-%d")
                        
                        print(f"\n{date_str}の記事を取得しています...")
                        
                        # ロイター記事を取得
                        print("ロイター記事を取得中...")
                        reuters_articles = get_reuters_articles_by_date(date_str)
                        
                        if reuters_articles:
                            print(f"ロイター記事 {len(reuters_articles)}件を発見")
                            
                            # 各記事の本文を取得
                            full_articles = scrape_news_articles(reuters_articles)
                            
                            # 結果を表示
                            print(f"\n=== {date_str}の記事（本文付き）===")
                            for i, article in enumerate(full_articles, 1):
                                print(f"\n{i}. {article['title']}")
                                print(f"   ソース: {article['source']}")
                                print(f"   URL: {article['url']}")
                                print(f"   内容（最初の200文字）: {article['content'][:200]}...")
                        else:
                            print("該当する記事が見つかりませんでした。")
                    except ValueError:
                        print("無効な日付形式です。YYYY-MM-DD形式で入力してください。")
            else:
                print("無効な選択です。0-2の範囲で選択してください。")
        
        except ValueError:
            print("無効な入力です。数字を入力してください。")
        except KeyboardInterrupt:
            print("\nプログラムを終了します。")
            break
        except Exception as e:
            print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
