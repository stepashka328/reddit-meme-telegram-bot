import os
import json
import feedparser
import requests
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
REDDIT_SUBREDDITS = ['memes', 'dankmemes', 'wholesomememes']  # Добавьте свои
POSTS_PER_RUN = 3  # Сколько постов публиковать за один запуск
MIN_UPVOTES = 100  # Минимальное количество лайков для публикации
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB (лимит Telegram для ботов)
FILE_PATH = 'posted.json'

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def load_posted():
    """Загружает список уже опубликованных постов"""
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_posted(posted):
    """Сохраняет список опубликованных постов"""
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

def download_image(url):
    """Скачивает изображение, возвращает bytes или None"""
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
    """Отправляет фото с подписью в Telegram"""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    files = {'photo': ('meme.jpg', image_bytes, 'image/jpeg')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
    return requests.post(url, files=files, data=data, timeout=30)

def send_message(text):
    """Отправляет текстовое сообщение (если нет картинки)"""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    return requests.post(url, json=data, timeout=30)

def parse_reddit_post(entry):
    """Извлекает данные из RSS-записи Reddit"""
    post_id = entry.link.split('/')[-3]  # Извлекаем ID из ссылки
    title = entry.title
    link = entry.link
    
    # Пытаемся найти прямое изображение
    image_url = None
    
    # Вариант 1: Прямая ссылка в enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                image_url = enc.get('href')
                break
    
    # Вариант 2: Поиск в content/summary
    if not image_url and hasattr(entry, 'content'):
        content = entry.content[0].get('value', '') if isinstance(entry.content, list) else str(entry.content)
        import re
        img_match = re.search(r'href="(https?://i\.redd\.it/[^"]+\.(jpg|png|gif))"', content)
        if img_match:
            image_url = img_match.group(1)
    
    # Вариант 3: Поиск в summary
    if not image_url and hasattr(entry, 'summary'):
        import re
        img_match = re.search(r'src="(https?://i\.redd\.it/[^"]+\.(jpg|png|gif))"', entry.summary)
        if img_match:
            image_url = img_match.group(1)
    
    # Извлекаем количество лайков (upvotes)
    upvotes = 0
    if hasattr(entry, 'score'):
        try:
            upvotes = int(entry.score)
        except:
            pass
    
    return {
        'id': post_id,
        'title': title,
        'link': link,
        'image_url': image_url,
        'upvotes': upvotes,
        'published': entry.get('published', datetime.now().isoformat())
    }

def main():
    posted = load_posted()
    new_posted = []
    
    for subreddit in REDDIT_SUBREDDITS:
        rss_url = f'https://www.reddit.com/r/{subreddit}/.rss?sort=top&t=day'
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            print(f"⚠️ Ошибка парсинга {subreddit}: {feed.bozo_exception}")
            continue
            
        for entry in feed.entries[:20]:  # Проверяем топ-20 записей
            post = parse_reddit_post(entry)
            
            # Фильтры
            if post['id'] in posted:
                continue
            if post['upvotes'] < MIN_UPVOTES:
                continue
            if len(post['title']) > 200:  # Слишком длинный заголовок
                continue
                
            # Формируем подпись
            caption = f"{post['title']}\n\n👍 {post['upvotes']} | 🔗 <a href='{post['link']}'>Reddit</a>\n\n#мем #reddit"
            
            # Публикуем
            if post['image_url']:
                image_bytes = download_image(post['image_url'])
                if image_bytes:
                    response = send_photo(caption, image_bytes)
                    if response and response.status_code == 200:
                        new_posted.append(post['id'])
                        print(f"✅ Опубликовано: {post['title'][:50]}...")
                        if len(new_posted) >= POSTS_PER_RUN:
                            break
                        continue
            
            # Если нет картинки — публикуем как текст со ссылкой
            response = send_message(f"{caption}\n\n🖼️ <i>Изображение не загружено, смотрите на Reddit</i>")
            if response and response.status_code == 200:
                new_posted.append(post['id'])
                print(f"✅ Опубликовано (текст): {post['title'][:50]}...")
                if len(new_posted) >= POSTS_PER_RUN:
                    break
        
        if len(new_posted) >= POSTS_PER_RUN:
            break
    
    # Сохраняем обновлённый список
    posted.extend(new_posted)
    save_posted(posted[-500:])  # Храним последние 500 ID, чтобы файл не рос бесконечно
    print(f"🔄 Готово. Опубликовано: {len(new_posted)}, всего в памяти: {len(posted)}")

if __name__ == '__main__':
    main()
