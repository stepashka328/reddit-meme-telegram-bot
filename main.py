import os
import json
import feedparser
import requests
import re
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
REDDIT_SUBREDDITS = ['memes']  # Для теста — только один
POSTS_PER_RUN = 1  # Для теста — 1 пост
MIN_UPVOTES = 1    # ⬇️ СНИЗИЛИ для отладки
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

def send_message(text):
    """Отправляет ТЕКСТОВОЕ сообщение — для надёжного теста"""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID, 
        'text': text, 
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    response = requests.post(url, json=data, timeout=30)
    print(f"📤 Telegram API ответ: {response.status_code} — {response.text[:200]}")
    return response

def main():
    posted = load_posted()
    print(f"📦 Загружено {len(posted)} уже опубликованных ID")
    
    for subreddit in REDDIT_SUBREDDITS:
        rss_url = f'https://www.reddit.com/r/{subreddit}/.rss?sort=top&t=day'
        print(f"🔍 Парсим: {rss_url}")
        
        feed = feedparser.parse(rss_url)
        print(f"📊 Найдено записей в RSS: {len(feed.entries)}")
        
        if feed.bozo:
            print(f"⚠️ Ошибка парсинга: {feed.bozo_exception}")
            continue
            
        for i, entry in enumerate(feed.entries[:5]):  # Проверяем топ-5 для отладки
            print(f"\n--- Пост #{i+1} ---")
            
            # Извлекаем базовые данные
            try:
                post_id = entry.link.split('/')[-3]
            except:
                post_id = entry.get('id', 'unknown')
                
            title = entry.title
            link = entry.link
            
            print(f"🆔 ID: {post_id}")
            print(f"📝 Заголовок: {title[:100]}...")
            print(f"🔗 Ссылка: {link}")
            
            # Пробуем найти картинку (упрощённо)
            image_url = None
            if hasattr(entry, 'summary'):
                # Ищем прямую ссылку на i.redd.it
                match = re.search(r'(https?://i\.redd\.it/[^"\s\']+\.(jpg|png|gif))', entry.summary)
                if match:
                    image_url = match.group(1)
                    print(f"🖼️ Найдена картинка: {image_url}")
            
            # Извлекаем лайки (если есть в расширенных данных)
            upvotes = 0
            if hasattr(entry, 'score'):
                try:
                    upvotes = int(entry.score)
                except:
                    pass
            print(f"👍 Лайки: {upvotes}")
            
            # Фильтры
            if post_id in posted:
                print("⏭️ Уже опубликован, пропускаем")
                continue
            if upvotes < MIN_UPVOTES:
                print(f"⏭️ Мало лайков ({upvotes} < {MIN_UPVOTES})")
                continue
            
            # ✅ Публикуем ТЕКСТОВОЕ сообщение для теста
            caption = f"{title}\n\n👍 {upvotes} | 🔗 <a href='{link}'>Reddit</a>\n\n#мем #reddit #тест"
            
            print(f"🚀 Отправляем в Telegram...")
            response = send_message(caption)
            
            if response and response.status_code == 200:
                print("✅ УСПЕШНО ОПУБЛИКОВАНО!")
                posted.append(post_id)
                save_posted(posted[-100:])
                break  # Один пост для теста
            else:
                print("❌ Ошибка публикации")
    
    print(f"\n🔄 Готово. Всего в памяти: {len(posted)}")

if __name__ == '__main__':
    main()
