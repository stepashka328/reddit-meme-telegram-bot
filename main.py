import os
import json
import feedparser
import requests
import re
import random
import time
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
# Используем 'memes' или 'dankmemes'
REDDIT_SUBREDDITS = ['memes'] 
POSTS_PER_RUN = 1  # ⬅️ ВАЖНО: Публикуем по 1 штуке за раз, чтобы не было "пачек"
FILE_PATH = 'posted.json'

# Маскировка под браузер (чтобы Reddit не блокировал)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

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
        response = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        response.raise_for_status()
        return response.content
    except:
        return None

def send_photo(caption, image_bytes):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    files = {'photo': ('meme.jpg', image_bytes, 'image/jpeg')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
    return requests.post(url, files=files, data=data, timeout=30)

def send_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    return requests.post(url, json=data, timeout=30)

def main():
    posted = load_posted()
    count_published = 0
    
    for subreddit in REDDIT_SUBREDDITS:
        # 🔥 ИСПОЛЬЗУЕМ OLD.REDDIT.COM - ОН СТАБИЛЬНЕЕ ДЛЯ ПАРСИНГА
        rss_url = f'https://old.reddit.com/r/{subreddit}/hot/.rss'
        
        # Добавляем случайную задержку перед запросом (анти-спам)
        time.sleep(random.uniform(1, 3)) 
        
        feed = feedparser.parse(rss_url)
        
        if feed.bozo and feed.status != 200:
            print(f"⚠️ Ошибка доступа к {subreddit}: {feed.bozo_exception}")
            continue
            
        # Перемешиваем посты, чтобы не брать всегда одни и те же топы
        entries = list(feed.entries)
        random.shuffle(entries)

        for entry in entries:
            if count_published >= POSTS_PER_RUN:
                break

            try:
                post_id = entry.link.split('/')[-3]
            except:
                continue
            
            if post_id in posted:
                continue
            
            title = entry.title
            link = entry.link
            
            # Ищем картинку
            image_url = None
            text_to_search = ''
            if hasattr(entry, 'summary'): text_to_search += entry.summary
            if hasattr(entry, 'content') and isinstance(entry.content, list):
                text_to_search += entry.content[0].get('value', '')
            
            match = re.search(r'(https?://i\.redd\.it/[^"\s\']+\.(jpg|png|gif|jpeg))', text_to_search)
            if match:
                image_url = match.group(1)
            
            # Формируем текст
            # Убираем ссылки из заголовка для красоты
            clean_title = re.sub(r'http\S+', '', title).strip()
            caption = f"{clean_title}\n\n🔗 <a href='{link}'>Источник</a>\n#мем"
            
            success = False
            
            # Публикация
            if image_url:
                img_bytes = download_image(image_url)
                if img_bytes:
                    resp = send_photo(caption, img_bytes)
                    if resp and resp.status_code == 200:
                        success = True
            else:
                # Если нет картинки - шлем текст
                resp = send_message(caption)
                if resp and resp.status_code == 200:
                    success = True
            
            if success:
                print(f"✅ Опубликовано: {clean_title[:30]}...")
                posted.append(post_id)
                count_published += 1
                # Задержка между постами, если их несколько
                time.sleep(2) 
    
    # Сохраняем историю (храним последние 1000, чтобы не раздувать файл)
    save_posted(posted[-1000:])
    print(f"🏁 Цикл завершен. Отправлено: {count_published}")

if __name__ == '__main__':
    main()
