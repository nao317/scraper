import requests
from bs4 import BeautifulSoup, Tag

def fetch_bloomberg_article(url):
    headers = {
        # User-Agent を設定しないとブロックされることがあるので一応入れておく
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) " +
                    "Chrome/115.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text

def parse_article(html):
    soup = BeautifulSoup(html, "html.parser")

    # タイトルを取得
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "タイトルなし"

    # 日付を取得
    # たとえば class や要素構造を見て適宜修正
    date_tag = soup.find("time")
    if not date_tag:
        # Bloomberg JP サイトだと span 等に “2025年9月23日 1:40 JST 更新日時 ..." という文字列が入ってることがある
        # その場合、他の selector を探す
        date_tag = soup.find("span", {"class": "some‐date‐class"})  # ←要調整
    date = date_tag.get_text(strip=True) if date_tag else "日付なし"

    # 本文を取得
    # 本文が <div> タグの中に <p> の形で入ってたりする
    content_div = soup.find("div", {"class": "body-copy"})  # class 名は実際にサイトの HTML を調べて置き換え
    if not content_div:
        # あるいは article タグの中
        content_div = soup.find("article")
    paragraphs = []
    if content_div and isinstance(content_div, Tag):
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
    content = "\n".join(paragraphs)

    # 著者情報
    author_tag = soup.find("span", {"class": "byline__name"})
    if not author_tag:
        author_tag = soup.find("a", {"class": "author-link"})
    author = author_tag.get_text(strip=True) if author_tag else "著者情報なし"

    return {
        "title": title,
        "date": date,
        "author": author,
        "content": content
    }
