import os
import json
import feedparser
import requests
import re
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
REDDIT_SUBREDDITS = ['memes', 'dankmemes']
POSTS_PER_RUN = 3
MIN_UPVOTES = -1  # ⬇️ -1 = отключить фильтр лайков
MAX_IMAGE_SIZE = 10 * 1024 * 1024
FILE_PATH = 'posted.json'

def load_posted():
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_posted(posted):
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

def download_image(url):
    try:
        response = requests.get(url, timeout=15, stream=True)
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_IMAGE_SIZE:
            return None
        return content
    except:
        return None

def send_photo(caption, image_bytes):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    files = {'photo': ('meme.jpg', image_bytes, 'image/jpeg')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
    return requests.post(url, files=files, data=data, timeout=30)

def send_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    return requests.post(url, json=data, timeout=30)

def extract_image_url(entry):
    """Извлекает прямую ссылку на картинку из RSS-записи Reddit"""
    # Вариант 1: enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href')
    
    # Вариант 2: поиск в summary/content
    text = ''
    if hasattr(entry, 'summary'):
        text += entry.summary
    if hasattr(entry, 'content') and isinstance(entry.content, list):
        text += entry.content[0].get('value', '')
    
    # Ищем i.redd.it ссылки
    match = re.search(r'(https?://i\.redd\.it/[^"\s\']+\.(jpg|png|gif|jpeg))', text)
    if match:
        return match.group(1)
    
    # Ищем v.redd.it (видео) — пропускаем
    if 'v.redd.it' in text:
        return None
        
    return None

def main():
    posted = load_posted()
    print(f"📦 Загружено {len(posted)} уже опубликованных ID")
    
    for subreddit in REDDIT_SUBREDDITS:
        # 🔥 Используем /hot/ вместо /?sort=top — более надёжно для RSS
        rss_url = f'https://www.reddit.com/r/{subreddit}/hot/.rss?limit=25'
        print(f"🔍 Парсим: {rss_url}")
        
        feed = feedparser.parse(rss_url)
        print(f"📊 Найдено записей: {len(feed.entries)}")
        
        if feed.bozo:
            print(f"⚠️ Ошибка парсинга: {feed.bozo_exception}")
            continue
            
        for entry in feed.entries[:20]:
            try:
                post_id = entry.link.split('/')[-3]
            except:
                post_id = entry.get('id', 'unknown')
            
            if post_id in posted:
                continue
                
            title = entry.title
            link = entry.link
            image_url = extract_image_url(entry)
            
            # 👍 Пытаемся получить лайки (не всегда доступно в RSS)
            upvotes = 0
            if hasattr(entry, 'score'):
                try:
                    upvotes = int(entry.score)
                except:
                    pass
            
            # 🔥 Фильтр лайков (если MIN_UPVOTES >= 0)
            if MIN_UPVOTES >= 0 and upvotes < MIN_UPVOTES:
                continue
            
            # Формируем подпись
            caption = f"{title}\n\n👍 {upvotes} | 🔗 <a href='{link}'>Reddit</a>\n\n#мем #reddit"
            
            # Публикуем
            if image_url:
                print(f"🖼️ Картинка: {image_url[:50]}...")
                image_bytes = download_image(image_url)
                if image_bytes:
                    response = send_photo(caption, image_bytes)
                    if response and response.status_code == 200:
                        print(f"✅ Опубликовано: {title[:50]}...")
                        posted.append(post_id)
                        save_posted(posted[-500:])
                        if len([p for p in posted if p in [entry.link.split('/')[-3] for entry in feed.entries]]) >= POSTS_PER_RUN:
                            break
                        continue
            
            # Фолбэк: текстовый пост
            response = send_message(f"{caption}\n\n🖼️ <i>Картинка не загружена</i>")
            if response and response.status_code == 200:
                print(f"✅ Опубликовано (текст): {title[:50]}...")
                posted.append(post_id)
                save_posted(posted[-500:])
            
            # Ограничитель постов за запуск
            if sum(1 for p in posted if p in [e.link.split('/')[-3] for e in feed.entries]) >= POSTS_PER_RUN:
                break
    
    print(f"🔄 Готово. Всего в памяти: {len(posted)}")

if __name__ == '__main__':
    main()
