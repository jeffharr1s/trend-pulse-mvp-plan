import requests
from bs4 import BeautifulSoup

print("Testing trends24.in scraper...")
url = "https://trends24.in/united-states/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

resp = requests.get(url, headers=headers, timeout=15)
print(f"Status: {resp.status_code}")

soup = BeautifulSoup(resp.text, "html.parser")
trends = soup.select(".trend-card__list li a")
print(f"Found {len(trends)} trends")
print()
print("Top 10 X/Twitter trends:")
for i, t in enumerate(trends[:10], 1):
    print(f"  {i}. {t.get_text(strip=True)}")
