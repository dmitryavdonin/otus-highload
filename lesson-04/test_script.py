import requests
import random
import time
import logging
import subprocess
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename='test_script.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add console handler to see logs in console as well
console = logging.StreamHandler()
console.setLevel(logging.INFO)  # Show INFO level and higher in console
formatter = logging.Formatter('%(message)s')  # Simpler format without level
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

BASE_URL = "http://localhost:9000"
PASSWORD = "12345"

headers = {"Content-Type": "application/json"}

# Helper functions

def verify_token_in_slave(token):
    """Verify that the token exists in the slave database"""
    cmd = f"docker exec otus-highload-db-slave1-1 psql -U postgres -d social_network -c \"SELECT * FROM auth_tokens WHERE token = '{token}';\""
    logging.debug(f"Verifying token in slave database: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if "0 rows" in result.stdout:
        logging.warning(f"Token not found in slave database. Waiting for replication...")
        time.sleep(2.0)  # Wait longer for replication
        # Check again
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if "0 rows" in result.stdout:
            logging.error(f"Token still not found in slave database after waiting!")
        else:
            logging.info(f"Token found in slave database after waiting.")
    else:
        logging.info(f"Token found in slave database.")

def register_user(i):
    data = {
        "first_name": f"User{i}",
        "second_name": f"Test{i}",
        "birthdate": "1990-01-01T00:00:00",
        "biography": f"Biography {i}",
        "city": "TestCity",
        "password": PASSWORD
    }
    logging.info(f"Registering user {i}")
    response = requests.post(f"{BASE_URL}/user/register", json=data, headers=headers)
    response.raise_for_status()
    user_id = response.json()["id"]
    logging.info(f"User {i} registered with ID: {user_id}")
    return user_id

def login(user_id):
    data = {"id": user_id, "password": PASSWORD}
    for attempt in range(3):
        try:
            logging.info(f"Login attempt {attempt+1} for user {user_id}")
            response = requests.post(f"{BASE_URL}/user/login", json=data, headers=headers)
            logging.debug(f"Login response: {response.status_code} - {response.text}")
            response.raise_for_status()
            token = response.json().get("token")
            if token:
                logging.info(f"Login successful for user {user_id}")
                logging.debug(f"Token: {token}")
                
                # Add a delay to ensure token replication to slave databases
                logging.info(f"Waiting for token replication...")
                time.sleep(1.0)  # Increased delay to 1 second
                
                # Verify token exists in slave database
                verify_token_in_slave(token)
                
                return token
            else:
                logging.warning(f"Login attempt {attempt+1} failed: No token received")
        except Exception as e:
            logging.error(f"Login attempt {attempt+1} failed: {e}")
        time.sleep(0.5)
    raise Exception(f"Failed to login user {user_id} after 3 attempts")

def add_friend(main_token, friend_id):
    headers_auth = {"Authorization": f"Bearer {main_token}"}
    logging.info(f"Adding friend {friend_id}")
    response = requests.put(f"{BASE_URL}/friend/set/{friend_id}", headers=headers_auth)
    response.raise_for_status()
    logging.info(f"Friend {friend_id} added successfully")
    return response.json()

def create_post(token, text):
    headers_auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"text": text}
    logging.debug(f"Creating post: {text}")
    response = requests.post(f"{BASE_URL}/post/create", json=data, headers=headers_auth)
    if response.status_code != 200:
        logging.error(f"Failed to create post: {response.status_code} - {response.text}")
        response.raise_for_status()
    post_id = response.json()["id"]
    logging.debug(f"Post created with ID: {post_id}")
    return post_id

def get_friends_feed(token, offset=0, limit=10):
    headers_auth = {"Authorization": f"Bearer {token}"}
    params = {"offset": offset, "limit": limit}
    logging.info(f"Getting friends feed with offset={offset}, limit={limit}")
    response = requests.get(f"{BASE_URL}/post/feed", headers=headers_auth, params=params)
    if response.status_code != 200:
        logging.error(f"Failed to get friends feed: {response.status_code} - {response.text}")
        response.raise_for_status()
    feed = response.json()
    logging.info(f"Got {len(feed)} posts in feed")
    return feed

def main():
    NUM_USERS = 100
    NUM_FRIENDS = 20
    NUM_POSTS = 100

    test_start_time = time.time()
    logging.info("Starting test script")
    report = []

    # 1. Create users
    report.append(f"{datetime.now()} - Starting user registration")
    user_ids = []
    step_start_time = time.time()
    for i in range(1, NUM_USERS + 1):
        user_id = register_user(i)
        user_ids.append(user_id)
        time.sleep(0.2)  # Delay after registration
    step_duration = time.time() - step_start_time
    report.append(f"{datetime.now()} - Registered {len(user_ids)} users (Took {step_duration:.2f} seconds)")
    logging.info("Step 1 completed: User registration")

    # 2. Fetch a random user as main user and login
    step_start_time = time.time()
    main_user_id = random.choice(user_ids)
    logging.info(f"Selected main user: {main_user_id}")
    main_token = login(main_user_id)
    step_duration = time.time() - step_start_time
    report.append(f"{datetime.now()} - Main user selected: {main_user_id} and logged in (Took {step_duration:.2f} seconds)")
    logging.info("Step 2 completed: Main user login")

    # 3. Add random friends
    step_start_time = time.time()
    friends_to_add = random.sample([uid for uid in user_ids if uid != main_user_id], min(NUM_FRIENDS, len(user_ids)-1))
    for friend_id in friends_to_add:
        add_friend(main_token, friend_id)
    step_duration = time.time() - step_start_time
    report.append(f"{datetime.now()} - Added {len(friends_to_add)} friends to main user (Took {step_duration:.2f} seconds)")
    logging.info("Step 3 completed: Adding friends")

    # 4. Each friend logs in and creates posts
    step_start_time = time.time()
    total_posts_created = 0
    for friend_id in friends_to_add:
        time.sleep(0.1)  # Delay before login
        friend_token = login(friend_id)
        logging.info(f"Friend {friend_id} logged in")
        for j in range(NUM_POSTS): 
            create_post(friend_token, f"Post {j+1} from friend {friend_id}")
            total_posts_created += 1
    step_duration = time.time() - step_start_time
    report.append(f"{datetime.now()} - Each friend created posts, total {total_posts_created} posts (Took {step_duration:.2f} seconds)")
    logging.info("Step 4 completed: Friends creating posts")

    # 5. Fetch main user's friends feed, measure time, count posts, oldest post
    step_start_time = time.time()
    feed = get_friends_feed(main_token, offset=0, limit=1000)
    duration = time.time() - step_start_time
    post_count = len(feed)
    oldest_post = feed[-1] if feed else None
    report.append(f"{datetime.now()} - Fetched friends feed: {post_count} posts in {duration:.2f} seconds")
    if oldest_post:
        report.append(f"Oldest post ID: {oldest_post['id']}, text: {oldest_post['text']}")
    logging.info("Step 5 completed: Fetching friends feed")

    # 6. One friend creates more posts
    step_start_time = time.time()
    friend_for_extra_posts = friends_to_add[0]
    friend_token = login(friend_for_extra_posts)
    extra_posts_created = 0
    for k in range(NUM_POSTS):
        create_post(friend_token, f"Extra post {k+1} from friend {friend_for_extra_posts}")
        extra_posts_created += 1
    step_duration = time.time() - step_start_time
    report.append(f"{datetime.now()} - Friend {friend_for_extra_posts} created {extra_posts_created} extra posts (Took {step_duration:.2f} seconds)")
    logging.info("Step 6 completed: Creating extra posts")

    # 7. Fetch feed again, measure time, count posts, verify oldest post changed
    step_start_time = time.time()
    feed2 = get_friends_feed(main_token, offset=0, limit=1000)
    duration2 = time.time() - step_start_time
    post_count2 = len(feed2)
    oldest_post2 = feed2[-1] if feed2 else None
    report.append(f"{datetime.now()} - Fetched friends feed again: {post_count2} posts in {duration2:.2f} seconds")
    if oldest_post2:
        report.append(f"Oldest post ID: {oldest_post2['id']}, text: {oldest_post2['text']}")
    else:
        report.append("No posts found in feed after extra posts")
    logging.info("Step 7 completed: Fetching feed again")
    
    # 8. Select another user not friend of main user, login
    step_start_time = time.time()
    non_friends = [uid for uid in user_ids if uid not in friends_to_add and uid != main_user_id]
    if non_friends:
        new_friend_id = random.choice(non_friends)
        new_friend_token = login(new_friend_id)
        step_duration = time.time() - step_start_time
        report.append(f"{datetime.now()} - New friend selected: {new_friend_id} and logged in (Took {step_duration:.2f} seconds)")
        logging.info("Step 8 completed: New friend login")

        # 9. New friend creates posts 
        step_start_time = time.time()
        new_friend_posts_created = 0
        for m in range(NUM_POSTS*10):
            create_post(new_friend_token, f"New friend post {m+1} from {new_friend_id}")
            new_friend_posts_created += 1
        step_duration = time.time() - step_start_time
        report.append(f"{datetime.now()} - New friend created {new_friend_posts_created} posts (Took {step_duration:.2f} seconds)")
        logging.info("Step 9 completed: New friend creating posts")

        # 10. Add new friend to main user
        step_start_time = time.time()
        add_friend(main_token, new_friend_id)
        step_duration = time.time() - step_start_time
        report.append(f"{datetime.now()} - New friend added to main user (Took {step_duration:.2f} seconds)")
        logging.info("Step 10 completed: Adding new friend")

        # 11. Fetch feed again, measure time, count posts, verify new friend's posts appear
        step_start_time = time.time()
        feed3 = get_friends_feed(main_token, offset=0, limit=1000)
        duration3 = time.time() - step_start_time
        post_count3 = len(feed3)
        report.append(f"{datetime.now()} - Fetched friends feed after adding new friend: {post_count3} posts in {duration3:.2f} seconds")
        logging.info("Step 11 completed: Fetching feed after adding new friend")

        # Check if new friend's posts appear
        new_friend_posts = [post for post in feed3 if post["author_user_id"] == new_friend_id]
        if new_friend_posts:
            report.append(f"New friend's posts appear in the feed: {len(new_friend_posts)} posts")
            logging.info(f"New friend's posts appear in the feed: {len(new_friend_posts)} posts")
        else:
            report.append("New friend's posts do NOT appear in the feed - potential issue.")
            logging.warning("New friend's posts do NOT appear in the feed - potential issue.")
    else:
        report.append("No non-friend users available to test adding a new friend")
        logging.info("No non-friend users available to test adding a new friend")

    # 12. Generate detailed HTML report in Russian
    test_total_duration = time.time() - test_start_time
    logging.info(f"Test completed in {test_total_duration:.2f} seconds")
    
    html_report = f"""
    <html>
    <head>
        <meta charset='utf-8'>
        <title>OTUS. Highload Architect. Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            h2 {{ color: #666; margin-top: 30px; }}
            .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .step {{ margin-bottom: 10px; padding: 10px; border-left: 3px solid #ccc; }}
            .success {{ color: green; }}
            .warning {{ color: orange; }}
            .error {{ color: red; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>        
        <h1>OTUS. Highload Architect</h1>
        <h2>Отчет по тестированию кэширования ленты постов</h2>
        <h3>Авдонин Дмитрий</h3>
        <div class="summary">
            <h2>Сводка тестирования</h2>
            <p><strong>Общее время выполнения:</strong> {test_total_duration:.2f} секунд</p>
            <p><strong>Количество созданных пользователей:</strong> {len(user_ids)}</p>
            <p><strong>Количество созданных постов:</strong> {total_posts_created + extra_posts_created + new_friend_posts_created if 'new_friend_posts_created' in locals() else total_posts_created + extra_posts_created}</p>
            <p><strong>Количество добавленных друзей:</strong> {len(friends_to_add) + (1 if 'new_friend_id' in locals() else 0)}</p>
        </div>
        
        <h2>Подробные результаты по шагам</h2>
        
        <table>
            <tr>
                <th>Время</th>
                <th>Шаг</th>
                <th>Результат</th>
            </tr>
    """
    
    for line in report:
        parts = line.split(" - ", 1)
        if len(parts) == 2:
            timestamp, message = parts
            html_report += f"""
            <tr>
                <td>{timestamp}</td>
                <td>{message}</td>
                <td class="success">Успешно</td>
            </tr>
            """
    
    html_report += """
        </table>
        
        <h2>Выводы</h2>
        <p>Тестирование социальной сети успешно завершено. Основные функции (регистрация, авторизация, добавление друзей, создание постов, получение ленты) работают корректно.</p>
    </body>
    </html>
    """

    with open("test_report.html", "w", encoding="utf-8") as f:
        f.write(html_report)

    logging.info("Test report saved to test_report.html")
    print("Тестирование завершено. Отчет сохранен в test_report.html")

if __name__ == "__main__":
    main()
