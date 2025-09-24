from scraper_template import fetch_bloomberg_article
from scraper_template import parse_article
if __name__ == "__main__":
    url = input()
    html = fetch_bloomberg_article(url)
    article = parse_article(html)

    print("タイトル:", article["title"])
    print("日付:", article["date"])
    print("著者:", article["author"])
    print("本文:\n", article["content"])