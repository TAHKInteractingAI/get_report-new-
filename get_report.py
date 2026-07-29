import datetime
from dotenv import load_dotenv
import pytz
import gspread
from dateutil import parser
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os

# Import Colab authentication libraries
from google.colab import auth
from google.auth import default

# Import for HTML parsing
from bs4 import BeautifulSoup

load_dotenv()

email = os.environ.get('TEAMS_EMAIL') or "tech.qtdata@gmail.com"
password = os.environ.get('TEAMS_PASSWORD') or "passnotE@1234"
chat_names_to_process = [
    "GetReport",
    "iX000s iSSale Boom&Task_1h TTS TAHK Foundation POSITIVE iShowOff/Top-iUp",
    "SAM Foundation TTSVol",
    "iX000s iSSale AH GlobalGroup.NỆN*iHugeNewRev*TiUp",
    "iX000s iSSale Boom QT*iHugeNewRev*Top-iUp",
    "iX000s iSSale AU GlobalGroup.NỆN*iHugeNewRev*TiUp",
    "iX000s iSSale Boom CMT*iHugeNewRev*Top-iUp",
    "iX000s iSSale Boom&Task_1h TTS AA POSITIVE iShowOff/Top-iUp"
]
message_content = "Thông báo: Reset 15min (Giải lao)"
local_tz = pytz.timezone("Asia/Ho_Chi_Minh")
SPREADSHEET_ID = "1_m7s-1-I-SOFfzlWe7CBf5fstFir7qXYAKW4j-8hKYM"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Define MESSAGE_PATTERN for message validation
MESSAGE_PATTERN = re.compile(r".*\w.*")

client = None
sheet_names = []
spreadsheet = None

try:
    auth.authenticate_user()
    creds, project = default()
    client = gspread.authorize(creds)
    print(f"Spreadsheet ID: {SPREADSHEET_ID}")
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet_names = [s.title for s in spreadsheet.worksheets()]
    print("✅ Google Sheets connected successfully using Colab authentication.")
except Exception as e:
    print(f"⚠️ Error connecting to Google Sheets: {e}. Google Sheets functionality will be disabled.")
def display_screenshot(driver: webdriver.Chrome, file_name: str = "screenshot.png"):
    driver.save_screenshot(file_name)
    time.sleep(3)


def open_chat(driver, chat_name):
    try:
        chat_element = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//span[normalize-space(text())='{chat_name}']")
            )
        )
        chat_element.click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]'))
        )
        display_screenshot(driver, "after_opening_chat.png")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi mở chat '{chat_name}': {e}")
        return False


def extract_messages_from_teams_html(driver):
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, "html.parser")
    scraped_messages = []

    message_containers = soup.find_all(
        lambda tag: tag.has_attr("data-mid") or
                    tag.get("role") in ["listitem", "article"] or
                    "message" in tag.get("class", []) or
                    "fui-ChatMessage" in str(tag.get("class", []))
    )

    for container in message_containers:
        try:
            body_elem = container.select_one(
                '[data-tid="message-body"], [class*="message-body"], [class*="body"], [role="document"]'
            )
            if not body_elem:
                continue

            for br in body_elem.find_all(["br", "p"]):
                br.replace_with("\n" + br.text if br.name == "p" else "\n")

            text_content = body_elem.get_text().strip()

            if text_content and text_content not in [m["content"] for m in scraped_messages]:
                sender_elem = container.select_one('[data-tid="message-author"], [class*="author"]')
                sender = sender_elem.get_text(strip=True) if sender_elem else "Unknown"

                time_elem = container.select_one('time, [data-tid="message-timestamp"], [class*="timestamp"]')
                timestamp = time_elem.get_text(strip=True) if time_elem else ""

                scraped_messages.append({
                    "sender": sender,
                    "timestamp": timestamp,
                    "content": text_content
                })
        except Exception:
            continue

    return scraped_messages


def scroll_and_scrape_chat(driver, chat_name, max_scrolls=5):
    print(f"🔍 Bắt đầu cào dữ liệu HTML từ chat: {chat_name}")
    if not open_chat(driver, chat_name):
        return []

    try:
        message_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]'))
        )
        message_box.click()
        time.sleep(1)

        for _ in range(max_scrolls):
            message_box.send_keys(Keys.PAGE_UP)
            time.sleep(1.5)
    except Exception as e:
        print(f"⚠️ Cuộn trang không thành công, thử cào dữ liệu màn hình hiện tại. Lỗi: {e}")

    time.sleep(2)
    extracted_data = extract_messages_from_teams_html(driver)
    print(f"✅ Thu thập được {len(extracted_data)} tin nhắn từ [{chat_name}]")
    return extracted_data


def send_message(driver, message):
    try:
        message_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]'))
        )

        for line in message.split("\n"):
            message_box.send_keys(line)
            message_box.send_keys(Keys.SHIFT, Keys.ENTER)

        display_screenshot(driver, "after_typing_message.png")
        time.sleep(3)
        message_box.send_keys(Keys.ENTER)
        time.sleep(3)
        display_screenshot(driver, "after_sending_message.png")

    except Exception as e:
        print(f"❌ Lỗi khi gửi tin nhắn: {e}")


def combine_messages(messages_dict):
    combined = {}
    for sheet_name, msg_list in messages_dict.items():
        if msg_list:
            combined[sheet_name] = "\n\n".join(msg_list)
    return combined


def preprocess_message(content):
    content = re.sub(r"-\s+-", "-", content)
    content = re.sub(r"\s*[+]+\s*(\d+/)\s*", r"\n+ \1 ", content)

    lines = content.splitlines()
    processed_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if re.match(r"^\+\s*(6|7|8|9|10)\s*/", line):
            continue

        if re.match(r"^(\+|\d+\.|=>|-)", line):
            line = "\u200b" + line
        processed_lines.append(line)

    changed = True
    while changed:
        changed = False
        n = len(processed_lines)
        for L in range(n // 2, 0, -1):
            for i in range(n - 2 * L + 1):
                if processed_lines[i : i + L] == processed_lines[i + L : i + 2 * L]:
                    processed_lines = (
                        processed_lines[: i + L] + processed_lines[i + 2 * L :]
                    )
                    changed = True
                    break
            if changed:
                break

    content = "\n".join(processed_lines)
    return content.strip()


def is_valid_message(content):
    if not bool(MESSAGE_PATTERN.match(content)):
        return False

    lower_content = content.lower()
    if "checkin" in lower_content or "check in" in lower_content or "reset" in lower_content:
        return False

    return True


def filter_scraped_messages(all_scraped_data, current_hour):
    """
    Lọc dữ liệu dựa theo khung giờ chạy script:
    - Nếu chạy buổi sáng (< 12h, ví dụ 8h): Lọc báo cáo Ca Chiều/Tối của NGÀY HÔM QUA.
    - Nếu chạy buổi chiều (>= 12h, ví dụ 14h): Lọc báo cáo Ca Sáng của NGÀY HÔM NAY.
    """
    filtered_results = {}
    EXCLUDED_SHEETS = [
        "Report",
        "GetReport",
        "iX000s iSSale TTS Base.XoắnNỆN50k*CấuTrúcVolunt",
        "iX000s iSSale gbBOSS AH*AU*cOL*YeuCauTop-iUp*KTra",
        "BoomWTF..AiLàmViệcRiêngThựcNÃOProofFileNGAY",
    ]

    now_vn = datetime.datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    
    # Xác định mục tiêu lọc theo giờ chạy
    is_run_morning = current_hour < 12  # Ví dụ: 8h sáng chạy -> Lấy ca chiều/tối hôm qua

    if is_run_morning:
        # Chạy lúc 8h sáng -> Tìm dữ liệu ngày HÔM QUA
        target_date = now_vn - datetime.timedelta(days=1)
    else:
        # Chạy lúc 14h chiều -> Tìm dữ liệu ngày HÔM NAY
        target_date = now_vn

    target_ddmm = target_date.strftime("%d/%m")        # "23/07" hoặc "24/07"
    target_full = target_date.strftime("%d/%m/%Y")    # "23/07/2026" hoặc "24/07/2026"

    for chat_name, msg_list in all_scraped_data.items():
        if chat_name in EXCLUDED_SHEETS:
            continue

        filtered_results[chat_name] = []
        for item in msg_list:
            raw_content = item.get("content", "").strip()
            ts_raw = item.get("timestamp", "").strip()
            ts_lower = ts_raw.lower()

            # 1. Kiểm tra cấu trúc tin nhắn
            if not is_valid_message(raw_content):
                continue

            # 2. KIỂM TRA NGÀY TRONG NỘI DUNG (CONTENT)
            dates_in_content = re.findall(r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b", raw_content)
            if dates_in_content:
                has_target_date = any(d == target_full or d == target_ddmm or d.startswith(target_ddmm) for d in dates_in_content)
                if not has_target_date:
                    continue 

            lower_raw = raw_content.lower()
            is_matched_shift = False

            if is_run_morning:
                # --- PHÂN NHÁNH 1: LỌC CA CHIỀU & TỐI (Gửi lúc 8h sáng) ---
                evening_keywords = ["ca chiều", "ca chieu", "ca tối", "ca toi", "ca đêm", "13h", "17h", "18h", "21h", "22h"]
                if any(kw in lower_raw for kw in evening_keywords):
                    is_matched_shift = True
                else:
                    # Hoặc check timestamp gửi trong khoảng 13:00 - 23:59 hôm qua
                    time_match = re.search(r"\b(\d{1,2}):(\d{2})(?:\s*(am|pm))?\b", ts_lower)
                    if time_match:
                        hr = int(time_match.group(1))
                        ampm = time_match.group(3)
                        if ampm == "pm" and hr < 12: hr += 12
                        elif ampm == "am" and hr == 12: hr = 0
                        
                        if 13 <= hr <= 23:
                            is_matched_shift = True
            else:
                # --- PHÂN NHÁNH 2: LỌC CA SÁNG (Gửi lúc 14h chiều) ---
                morning_keywords = ["ca sáng", "ca sang", "- 11h", "-11h", "- 12h", "-12h", "8h-12h", "8h30-11h30"]
                if any(kw in lower_raw for kw in morning_keywords):
                    is_matched_shift = True
                else:
                    # Check timestamp hệ thống gửi trong khoảng 06:00 - 13:00 hôm nay
                    time_match = re.search(r"\b(\d{1,2}):(\d{2})(?:\s*(am|pm))?\b", ts_lower)
                    if time_match:
                        hr = int(time_match.group(1))
                        ampm = time_match.group(3)
                        if ampm == "pm" and hr < 12: hr += 12
                        elif ampm == "am" and hr == 12: hr = 0

                        if 6 <= hr <= 13:
                            is_matched_shift = True

            if not is_matched_shift:
                continue

            # Tiền xử lý & gộp kết quả
            content = preprocess_message(raw_content)
            if content and content not in filtered_results[chat_name]:
                filtered_results[chat_name].append(content)

    return filtered_results


def write_to_sheet(sheet_target_name, messages):
    try:
        EXCLUDED_SHEETS = [
            "Report",
            "GetReport",
            "iX000s iSSale TTS Base.XoắnNỆN50k*CấuTrúcVolunt",
            "iX000s iSSale gbBOSS AH*AU*cOL*YeuCauTop-iUp*KTra",
            "BoomWTF..AiLàmViệcRiêngThựcNÃOProofFileNGAY",
        ]

        # Lấy danh sách key đang có dữ liệu
        sheet_names_with_data = [name for name in messages.keys() if name not in EXCLUDED_SHEETS and messages.get(name)]

        if not sheet_names_with_data:
            print(f"--- Không có dữ liệu để ghi vào {sheet_target_name} ---")
            return

        try:
            ws = spreadsheet.worksheet(sheet_target_name)
            existing_data = ws.get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(
                title=sheet_target_name, rows="1000", cols=str(max(20, len(sheet_names_with_data)))
            )
            ws.append_row(sheet_names_with_data, value_input_option="USER_ENTERED")
            existing_data = [sheet_names_with_data]
            print(f"🔹 Đã khởi tạo dòng tiêu đề cho [{sheet_target_name}]")

        headers_on_sheet = existing_data[0] if existing_data else sheet_names_with_data
        column_map = {str(col).strip().lower(): idx for idx, col in enumerate(headers_on_sheet)}

        updated_headers = list(headers_on_sheet)
        has_new_column = False
        for s_name in sheet_names_with_data:
            if s_name.strip().lower() not in column_map:
                updated_headers.append(s_name)
                column_map[s_name.strip().lower()] = len(updated_headers) - 1
                has_new_column = True

        if has_new_column:
            ws.update(range_name='A1', values=[updated_headers], value_input_option="USER_ENTERED")
            headers_on_sheet = updated_headers
            print(f"🔹 Đã tự động cập nhật thêm cột mới cho [{sheet_target_name}]")

        max_len = max(len(messages[s]) for s in sheet_names_with_data)

        rows_to_append = []
        for i in range(max_len):
            row = [""] * len(headers_on_sheet)
            for sheet_name, msg_list in messages.items():
                if msg_list and i < len(msg_list):
                    s_key = sheet_name.strip().lower()
                    if s_key in column_map:
                        col_idx = column_map[s_key]
                        row[col_idx] = msg_list[i]

            if row not in existing_data:
                rows_to_append.append(row)

        if rows_to_append:
            ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            print(f"✅ Đã ghi thêm {len(rows_to_append)} dòng mới vào [{sheet_target_name}] (Đã tự khớp cột)")
        else:
            print(f"ℹ️ Không có dữ liệu mới (trùng lặp) cho [{sheet_target_name}]")

    except Exception as e:
        print(f"❌ Lỗi khi ghi vào sheet {sheet_target_name}: {e}")


def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.page_load_strategy = "eager"
    options.add_argument("--lang=en-GB")

    prefs = {
        "profile.cookie_controls_mode": 0,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }

    options.add_experimental_option("prefs", prefs)

    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        options.add_argument(f"--proxy-server={proxy_url}")

    import subprocess
    import re

    chrome_version = None
    try:
        result = subprocess.check_output(["google-chrome", "--version"]).decode("utf-8")
        chrome_version = int(re.search(r"\d+", result).group(0))
        print(f"✅ Đã tự động nhận diện Chrome trên máy chủ là version: {chrome_version}")
    except Exception:
        pass

    if chrome_version:
        driver = uc.Chrome(options=options, version_main=chrome_version)
    else:
        driver = uc.Chrome(options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'credentials', {
                get: () => undefined
            });

            window.PublicKeyCredential = undefined;
        """},
    )

    return driver


def login():
    driver = get_driver()
    driver.get("https://teams.live.com/v2/")
    wait = WebDriverWait(driver, 30)

    try:
        print("⏳ Đang tiến hành đăng nhập...")
        sign_in_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(., "Sign in")]'))
        )
        sign_in_btn.click()

        email_input = wait.until(
            EC.presence_of_element_located((By.ID, "usernameEntry"))
        )
        email_input.send_keys(email)
        email_input.send_keys(Keys.RETURN)
        time.sleep(3)

        try:
            use_pass_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//span[contains(text(), "Use your password")]')
                )
            )
            use_pass_btn.click()
        except:
            pass

        pass_input = wait.until(
            EC.presence_of_element_located((By.ID, "passwordEntry"))
        )
        pass_input.send_keys(password)
        pass_input.send_keys(Keys.RETURN)

        try:
            no_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]')
                )
            )
            no_btn.click()
        except:
            pass

        print("✅ Đăng nhập thành công!")
        time.sleep(15)

        try:
            extra_signin = driver.find_elements(
                By.XPATH,
                '//button[contains(., "Sign in") or contains(@aria-describedby, "signIn-title singIn-subtitle")]',
            )
            if len(extra_signin) > 0:
                print("Phát hiện trang bắt Sign in tiếp theo...")
                extra_signin[0].click()
                print("Đã ấn nút Sign in")
                time.sleep(10)

                print("Bắt đầu ấn nút Retry")
                actions = webdriver.ActionChains(driver)
                actions.move_by_offset(500, 500).click().perform()
                actions.send_keys(Keys.TAB).perform()
                time.sleep(1)
                actions.send_keys(Keys.ENTER).perform()
                print("Đã ấn nút Retry")
                time.sleep(20)
            else:
                print("👉 Giao diện Teams đã load thẳng, không có popup chặn, tiếp tục công việc!")

        except Exception as e:
            print(f"⚠️ Bỏ qua lỗi check màn hình phụ: {e}")

        driver.save_screenshot("after_login_success.png")
        return driver

    except Exception as e:
        driver.save_screenshot("error_login.png")
        print(f"❌ Lỗi đăng nhập chính: {e}")
        driver.quit()
        return None


if __name__ == "__main__":
    driver = None
    for attempt_login in range(5):
        driver = login()
        if driver:
            print("login thành công")
            break
        else:
            print(f"⚠️ Thử đăng nhập lại lần {attempt_login + 1}/5...")
            time.sleep(2)

    time.sleep(5)
    if not driver:
        print("❌ Đăng nhập không thành công!")
        exit()

    driver.save_screenshot("after_login.png")

    # 1. CÀO TIN NHẮN TỪ TEAMS HTML
    all_scraped_data = {}
    for chat_name in chat_names_to_process:
        chat_messages = scroll_and_scrape_chat(driver, chat_name, max_scrolls=3)
        all_scraped_data[chat_name] = chat_messages

    # 2. XỬ LÝ LỌC TIN NHẮN TỪ DỮ LIỆU VỪA CÀO THAY VÌ ĐỌC TAB SHEET CŨ
    current_hour = datetime.datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).hour
    messages = filter_scraped_messages(all_scraped_data, current_hour)
    combined_msgs = combine_messages(messages)

    print(f"\n✅ Báo cáo lọc được lúc {current_hour}h:")

    # 3. GỬI TIN NHẮN ĐÃ GỘP VÀO TEAMS CHAT
    target_chat = "GetReport"
    print(f"\n➡️ Đang gửi báo cáo tổng hợp vào chat: {target_chat}")
    if open_chat(driver, target_chat):
        for sheet_name, msg_content in combined_msgs.items():
            if msg_content:
                print(f"Testing\nSheet: [ {sheet_name} ]\nMessage: [ {msg_content} ]\n")
                message = f"[ {sheet_name} ]\n" + msg_content
                send_message(driver, message)

    # 4. GHI DỮ LIỆU BÁO CÁO LÊN GOOGLE SHEETS
    write_to_sheet("Report", messages)
    write_to_sheet("GetReport", messages)

    driver.quit()
    print("✅ Hoàn tất toàn bộ công việc!")
