# This version is without comments
import sqlite3
import telebot
import openai
from data import ChatGPT_API, Bot_API, db_name
from telebot import types
import urllib.parse
from bs4 import BeautifulSoup
import requests
openai.api_key = ChatGPT_API  
bot = telebot.TeleBot(Bot_API) 

user_data = {}

years = ['1980-е', '1990-е', '2000-е', '2010-е', '2020-е']
vibes = ['Веселое', 'Грустное', 'Захватывающее', 'Трогательное', 'Романтичное', 'Ностальгическое', 'Интригующее', 'Мрачное', 'Оптимистичное', 'Стрессовое', 'Легкое']
genres = ['Комедия', 'Хоррор', 'Драма', 'Триллер', 'Боевик', 'Фантастика', 'Мелодрама', 'Документальный']

def create_db():
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, chat_id INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS watched_movies (user_id INTEGER, movie_name TEXT, rating INTEGER, FOREIGN KEY(user_id) REFERENCES users(id))''')

def add_user(chat_id):
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (chat_id) VALUES (?)', (chat_id,))

def add_watched_movie(chat_id, movie_name):
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
            cursor.execute('INSERT INTO watched_movies (user_id, movie_name, rating) VALUES (?, ?, ?)', (user_id, movie_name, 5))

def get_watched_movies_with_ratings(user_id):
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT movie_name, rating FROM watched_movies WHERE user_id = ?', (user_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}

def get_watched_movies_info(user_id):
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT movie_name, COALESCE(rating, 0) FROM watched_movies WHERE user_id = ?', (user_id,))
        movies = cursor.fetchall()
        total_movies = len(movies)
        avg_rating = round(sum(rating for _, rating in movies) / total_movies, 1) if total_movies > 0 else 0.0
        return movies, total_movies, avg_rating

create_db()

def notify_users():
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT chat_id FROM users')
        users = cursor.fetchall()
        
        for user in users:
            chat_id = user[0]
            try:
                bot.send_message(chat_id, "Бот был перезапущен. Для коректной работы нажмите /start")
            except:
                pass

notify_users()

@bot.message_handler(commands=['start']) 
def start(message): 
    user_data[message.chat.id] = {'genre': None, 'vibe': None, 'year': None, 'watched_movies': []} 
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor() 
    cursor.execute('SELECT * FROM users WHERE chat_id = ?', (message.chat.id,)) 
    if cursor.fetchone() is None: 
        add_user(message.chat.id) 
    conn.close() 
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True) 
    markup.add('Фильм')
    markup.add('Профиль') 
    bot.send_message(message.chat.id, "Привет! Меня зовут Кинофайндер. Я помогу вам подобрать фильм на вечер.",reply_markup=markup)

@bot.message_handler(regexp='Профиль') 
def profile_handler(message, page=0):
    try:
        chat_id = message.chat.id
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            bot.send_message(chat_id, "Ваш профиль не найден. Начните с команды /start.")
            return

        user_id = user[0]
        movies, total_movies, avg_rating = get_watched_movies_info(user_id)
        if total_movies <= 5:
            status = "Начинающий киноман"
        elif total_movies <= 20:
            status = "В поиске стиля"
        elif total_movies <= 50:
            status = "Знаток кино"
        elif total_movies <= 100:
            status = "Мастер кино"
        else:
            status = "Киноэксперт"

        text = f"🎬 Ваш профиль\n\nВаш статус: {status}\n📽Просмотрено фильмов: {total_movies}\n⭐ Средний рейтинг: {avg_rating}/10"

        keyboard = types.InlineKeyboardMarkup()

        movies_per_page = 9
        start_index = page * movies_per_page
        end_index = start_index + movies_per_page
        movies_page = movies[start_index:end_index]

        for movie_name, rating in movies_page:
            row = [
                types.InlineKeyboardButton(text=f"🎬 {movie_name}", callback_data=f"movie"),
                types.InlineKeyboardButton(text=f"⭐ {rating}/10", callback_data=f"rating")
            ]
            keyboard.add(*row)

        if end_index < total_movies:
            keyboard.add(types.InlineKeyboardButton("➡ Следующая страница", callback_data=f"profile_page_{page+1}"))



        bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")
    except:
        pass



def create_profile_keyboard(movies, page):
    try:
        keyboard = types.InlineKeyboardMarkup()
        movies_per_page = 9
        start_index = page * movies_per_page
        end_index = start_index + movies_per_page
        movies_page = movies[start_index:end_index]

        for movie_name, rating in movies_page:
            row = [
                types.InlineKeyboardButton(text=f"🎬 {movie_name}", callback_data=f"movie"),
                types.InlineKeyboardButton(text=f"⭐ {rating}/10", callback_data=f"rating")
            ]
            keyboard.add(*row)

        if end_index < len(movies):
            keyboard.add(types.InlineKeyboardButton (text="➡ Следующая страница", callback_data=f"profile_page_{page+1}"))

        return keyboard
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_page_"))
def next_profile_page(call):
    try:
        page = int(call.data.split("_")[-1])
        profile_handler(call.message, page)
    except:
        pass

@bot.message_handler(regexp='Фильм')
def ask_for_genre(message):
    try:
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        buttons = [telebot.types.KeyboardButton(genre) for genre in genres]
        markup.add(*buttons)
        bot.send_message(message.chat.id, "Какой жанр фильма вас интересует?", reply_markup=markup)
    except:
        pass

@bot.message_handler(func=lambda message: message.text in genres)
def handle_genre(message):
    try:
        user_data[message.chat.id]['genre'] = message.text
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        buttons = [telebot.types.KeyboardButton(vibe) for vibe in vibes] 
        markup.add(*buttons)
        bot.send_message(message.chat.id, f"Хороший выбор. Хотите добавить настроение?", reply_markup=markup)
    except:
        pass
@bot.message_handler(func=lambda message: message.text in vibes)
def handle_vibe(message):
    try:
        user_data[message.chat.id]['vibe'] = message.text
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        buttons = [telebot.types.KeyboardButton(year) for year in years] 
        markup.add(*buttons)
        markup.add('Пропустить')
        bot.send_message(message.chat.id, f"Перейдем к следующему шагу. Хотите указать год выпуска?", reply_markup=markup)
    except:
        pass
@bot.message_handler(func=lambda message: message.text in years)
def handle_year(message):
    try:
        user_data[message.chat.id]['year'] = message.text
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add('Нет пожеланий')   
        bot.send_message(message.chat.id, f"Отлично. Введите свои дополнительные пожелания по поводу фильма.", reply_markup=markup)
        bot.register_next_step_handler(message, handle_watched_movies)
    except:
        pass

def handle_watched_movies(message):
    try:
        comment = message.text
        user_data[message.chat.id]['comment'] = comment
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Жду')
        bot.send_message(message.chat.id, "Спасибо за информацию! Я подберу тебе фильм.", reply_markup=markup)
        recommend_movie(message)
    except:
        pass
@bot.message_handler(regexp='Пропустить')
def skip(message):
    try:
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add('Нет пожеланий')   
        bot.send_message(message.chat.id, f"Отлично. Введите свои дополнительные пожелания по поводу фильма.", reply_markup=markup)
        bot.register_next_step_handler(message, handle_watched_movies)
    except:
        pass
def recommend_movie(message, old_message_id=None):
    try:
        chat_id = message.chat.id
        preferences = user_data.get(chat_id, {})
        watched_movies = get_watched_movies_with_ratings(chat_id)

        watched_movies_text = (
            ", ".join([f"- {movie}: {rating}/10" for movie, rating in watched_movies.items()])
            if watched_movies else "Нет"
        )

        prompt = f"""
        Пользователь ищет фильм по следующим предпочтениям:
        - Жанр: {preferences.get('genre', 'Не указан')}
        - Настроение: {preferences.get('vibe', 'Не указано')}
        - Год выпуска: {preferences.get('year', 'Не указан')}
        - Комментарий по поводу фильма: {preferences.get('comment', 'Не указан')}
        - Фильмы, которые пользователь уже посмотрел и как он их оценил:
        {watched_movies_text}

        Пожалуйста, предложи 3 фильма, которые могут понравиться пользователю, учитывая эти параметры.
        Ответ должен быть в формате:
        1. Название фильма 1 (год) — Краткое описание./n
        2. Название фильма 2 (год) — Краткое описание./n
        3. Название фильма 3 (год) — Краткое описание./n
        Примечание: Названия фильмов должны быть на русском
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Ты помощник, который рекомендует фильмы."},
                                          {"role": "user", "content": prompt}],
            max_tokens=350
        )

        recommendation = response['choices'][0]['message']['content'].strip()
        movie_list = recommendation.split("\n")

        movie_titles = []
        for movie in movie_list:
            title = movie.split('(')[0].strip().replace('"', '')  
            movie_titles.append(title)

        recommended_movies = user_data[chat_id].get("recommended_movies", [])
        filtered_movie_list = [title for title in movie_titles if title not in recommended_movies]

        if len(filtered_movie_list) < 3:
            filtered_movie_list += [title for title in movie_titles if title not in recommended_movies][:3-len(filtered_movie_list)]

        user_data[chat_id]["recommended_movies"] = filtered_movie_list

        keyboard = types.InlineKeyboardMarkup()
        for idx, movie_name in enumerate(filtered_movie_list):
            movie_id = f"movie_{idx}" 
            if len(movie_id) > 20:
                movie_id = movie_id[:20] 
            keyboard.add(types.InlineKeyboardButton(text=movie_name, callback_data=movie_id))

        keyboard.add(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh"))

        if old_message_id:
            bot.delete_message(chat_id, old_message_id)
        bot.send_chat_action(chat_id, "typing")
        new_message = bot.send_message(chat_id, f"🎬 Вот несколько фильмов для вас:\n{recommendation}", reply_markup=keyboard)
        user_data[chat_id]["last_message_id"] = new_message.message_id
    except:
        pass

def get_movie_links(movie_name):
    movie_query = urllib.parse.quote(movie_name)

    sites = {
        "HDRezka": f"https://rezka.ag/search/?do=search&subaction=search&q={movie_query}",
        "Baskino": f"https://baskino.me/index.php?do=search&subaction=search&story={movie_query}",
        "Filmix": f"https://filmix.ac/search/{movie_query}"
    }

    valid_links = {}
    
    for site, url in sites.items():
        if check_link(url):
            valid_links[site] = url

    return valid_links

def check_link(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        return response.status_code == 200
    except:
        return False
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("movie_"))
def send_movie_details(call):
    try:
        chat_id = call.message.chat.id
        movie_index = int(call.data.split("_")[1])  
        movie_name = user_data[chat_id]["recommended_movies"][movie_index].split('—')[0].strip()
        movie_name = movie_name.split('.')[1].strip() if '.' in movie_name else movie_name.strip()

        prompt = f"Дай краткое описание фильма '{movie_name}', не более 3 предложений."
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - помощник по фильмам."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        movie_description = response['choices'][0]['message']['content'].strip()

        links = get_movie_links(movie_name)
        links_text = "\n".join([f"[{site}]({url})" for site, url in links.items()]) if links else "Ссылки не найдены."

        movie_details = f"🎥 *{movie_name}*\n\n📖 *Описание:* {movie_description}\n\n🔗 *Ссылки на просмотр:*\n{links_text}"
        bot.send_chat_action(chat_id, "typing")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="Буду смотреть", callback_data=f"watch_{movie_index}"))
        bot.send_message(chat_id, movie_details, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)

    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "refresh")
def refresh_movies(call):
    try:
        chat_id = call.message.chat.id
        last_message_id = user_data.get(chat_id, {}).get("last_message_id")

        loading_message = bot.send_message(chat_id, "🔄 Обновляю список фильмов...")
        bot.delete_message(chat_id, loading_message.message_id)

        recommend_movie(call.message, old_message_id=last_message_id)
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("watch_"))
def mark_as_watching(call):
    try:
        chat_id = call.message.chat.id
        movie_index = int(call.data[6:])  

        movie_name = user_data[chat_id]["recommended_movies"][movie_index]  

        movie_name_cleaned = movie_name.split('.')[1].strip() if '.' in movie_name else movie_name.strip()

        add_watched_movie(chat_id, movie_name_cleaned)

        keyboard = types.InlineKeyboardMarkup()
        buttons = [types.InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate_{movie_index}_{i}") for i in range(1, 11)]
        
        for i in range(0, 10, 5):
            keyboard.add(*buttons[i:i+5])

        bot.send_message(chat_id, f"Очень хороший выбор! Оцените, пожалуйста, фильм {movie_name_cleaned}, чтобы мы могли улучшить рекомендации. 🎬🍿", 
                        reply_markup=keyboard, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def rate_movie(call):
    try:
        chat_id = call.message.chat.id
        _, movie_index, rating = call.data.split("_")
        rating = int(rating)
        

        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
            user = cursor.fetchone()

            if user:
                user_id = user[0]
                movie_name = user_data[chat_id]["recommended_movies"][int(movie_index)]  
                movie_name_cleaned = movie_name.split('.')[1].strip() if '.' in movie_name else movie_name.strip()
                cursor.execute('''
                    SELECT rating FROM watched_movies 
                    WHERE user_id = ? AND movie_name = ?
                ''', (user_id, movie_name_cleaned))

                existing_rating = cursor.fetchone()

                if existing_rating is not None:
                    cursor.execute('''
                        UPDATE watched_movies 
                        SET rating = ? 
                        WHERE user_id = ? AND movie_name = ?
                    ''', (rating, user_id, movie_name_cleaned))
                else:
                    cursor.execute('''
                        INSERT INTO watched_movies (user_id, movie_name, rating) 
                        VALUES (?, ?, ?)
                    ''', (user_id, movie_name_cleaned, rating))
        
        conn.commit()
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Фильм', 'Профиль')

        bot.send_message(chat_id, f"Спасибо! Вы поставили фильму '{movie_name_cleaned}' оценку {rating}/10 ⭐", reply_markup=markup)
    except:
        pass

bot.polling()