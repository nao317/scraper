import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from scraper_template import fetch_bloomberg_article, parse_article

def get_bloomberg_articles_by_date(date_str):
    """
    指定した日付のBloomberg記事URLリストを取得
    date_str: 'YYYY-MM-DD' 形式の日付文字列
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) " +
                    "Chrome/115.0.0.0 Safari/537.36"
    }
    
    # Bloomberg日本語版のニュース一覧ページ
    base_url = "https://www.bloomberg.co.jp/"
    
    try:
        # 日付をYYYY-MM-DD形式に変換
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        search_date = date_obj.strftime("%Y-%m-%d")
        
        print(f"取得中: {search_date}の記事...")
        
        resp = requests.get(base_url, headers=headers)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Bloomberg記事のリンクを探す（URL形式: /news/articles/YYYY-MM-DD/記事ID）
        article_links = []
        
        # 記事リンクを含む要素を探す
        links = soup.find_all("a", href=True)
        
        for link in links:
            if isinstance(link, Tag) and link.get('href'):
                href = str(link.get('href'))
                # Bloomberg記事のURLパターンをチェック
                if "/news/articles/" in href and search_date in href:
                    # 相対URLを絶対URLに変換
                    if href.startswith('/'):
                        full_url = "https://www.bloomberg.co.jp" + href
                    else:
                        full_url = href
                    
                    # 重複を避けるため
                    if full_url not in article_links:
                        article_links.append(full_url)
        
        return article_links
        
    except Exception as e:
        print(f"記事リスト取得エラー: {e}")
        return []

def scrape_multiple_articles(article_urls):
    """
    複数の記事URLから記事情報を取得
    """
    articles = []
    total = len(article_urls)
    
    for i, url in enumerate(article_urls, 1):
        print(f"記事 {i}/{total} を取得中: {url}")
        
        try:
            html = fetch_bloomberg_article(url)
            article = parse_article(html)
            article["url"] = url
            articles.append(article)
            
        except Exception as e:
            print(f"記事取得エラー ({url}): {e}")
            continue
    
    return articles

def display_articles(articles):
    """
    取得した記事を整理して表示
    """
    if not articles:
        print("記事が見つかりませんでした。")
        return
    
    print(f"\n=== 取得した記事数: {len(articles)} ===\n")
    
    for i, article in enumerate(articles, 1):
        print(f"【記事 {i}】")
        print(f"タイトル: {article['title']}")
        print(f"URL: {article['url']}")
        print(f"日付: {article['date']}")
        print(f"著者: {article['author']}")
        print(f"本文: {article['content'][:200]}..." if len(article['content']) > 200 else f"本文: {article['content']}")
        print("-" * 80)