import datetime
import os
import re
import time
import json
import pytz
import html
from dateutil import parser
from dotenv import load_dotenv
from bs4 import BeautifulSoup

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

# Hàm khởi tạo và lấy kết nối Google Sheets (tránh bị lỗi NoneType toàn cục)
def get_spreadsheet():
    sa_json_str = os.environ.get('GCP_SA_KEY') or os.environ.get('GCP_CREDENTIALS_JSON')
    if not sa_json_str:
        print("⚠️ Không tìm thấy Service Account JSON trong Environment Variables!")
        return None

    try:
        # Xử lý chuỗi JSON phòng trường hợp xuống dòng bị lỗi hóa ký tự escape
        service_account_info = json.loads(sa_json_str, strict=False)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
        client = gspread.authorize(creds)
        ss = client.open_by_key(SPREADSHEET_ID)
        print("✅ Kết nối Google Sheets thành công via Service Account.")
        return ss
    except Exception as e:
        print(f"❌ Lỗi kết nối Google Sheets chi tiết: {e}")
        return None

# Khởi tạo biến spreadsheet
spreadsheet = get_spreadsheet()

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


def scroll_and_scrape_chat(driver, chat_name, max_scrolls=12):
    print(f"🔍 Bắt đầu cào dữ liệu HTML từ chat: {chat_name}")
    if not open_chat(driver, chat_name):
        return []

    try:
        message_pane = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="document"] | //div[@contenteditable="true"]'))
        )
        message_pane.click()
        time.sleep(1)

        for _ in range(max_scrolls):
            message_pane.send_keys(Keys.PAGE_UP)
            time.sleep(1.2)

        message_pane.send_keys(Keys.HOME)
        time.sleep(2)
    except Exception as e:
        print(f"⚠️ Cuộn trang không thành công, thử cào dữ liệu hiện tại. Lỗi: {e}")

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

        # CẮT BỎ CÁC DÒNG CHECKLIST MỤC 6, 7, 8, 9, 10
        if re.match(r"^\+?\s*(6|7|8|9|10)\s*/", line):
            continue

        if re.match(r"^(\+|\d+\.|=>|-)", line):
            line = "\u200b" + line
        processed_lines.append(line)

    content = "\n".join(processed_lines)
    return content.strip()


def is_valid_message(content):
    if not bool(MESSAGE_PATTERN.match(content)):
        return False

    lower_content = content.lower()
    if "checkin" in lower_content or "check in" in lower_content or "reset 15min" in lower_content:
        if "check out" in lower_content or "checkout" in lower_content:
            return True
        return False

    return True


def filter_scraped_messages(all_scraped_data, current_hour):
    """
    Logic phân tách Ca chuẩn xác:
    - Chạy Buổi Sáng (< 12h): Lấy dữ liệu Ca Chiều & Ca Tối (ngày HÔM QUA hoặc gửi rạng sáng HÔM NAY).
    - Chạy Buổi Chiều (>= 12h): Lấy dữ liệu Ca Sáng (ngày HÔM NAY).
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
    is_run_morning = current_hour < 12

    if is_run_morning:
        target_date = now_vn - datetime.timedelta(days=1)
    else:
        target_date = now_vn

    target_day = target_date.day
    target_month = target_date.month

    for chat_name, msg_list in all_scraped_data.items():
        if chat_name in EXCLUDED_SHEETS:
            continue

        filtered_results[chat_name] = []
        for item in msg_list:
            raw_content = item.get("content", "").strip()

            if not is_valid_message(raw_content):
                continue

            # 1. KIỂM TRA NGÀY TRONG NỘI DUNG (Khớp cả 29/7 và 29/07)
            dates_in_content = re.findall(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", raw_content)
            if dates_in_content:
                has_target_date = False
                for d_str, m_str, y_str in dates_in_content:
                    d_int, m_str_int = int(d_str), int(m_str)
                    if (d_int == target_day and m_str_int == target_month) or \
                       (is_run_morning and d_int == now_vn.day and m_str_int == now_vn.month):
                        has_target_date = True
                        break
                if not has_target_date:
                    continue

            lower_raw = raw_content.lower()
            is_matched_shift = False

            # Regex nâng cấp: Bắt mọi dạng khoảng giờ như 14:00 - 17:00, 14h-17h, 22:00-24:00, 22h-0h
            time_ranges = re.findall(r"(\d{1,2})\s*(?::\d{2}|h\d{0,2})?\s*-\s*(\d{1,2})\s*(?::\d{2}|h\d{0,2})?", lower_raw)

            if is_run_morning:
                # 🌞 CHẠY 8H/10H SÁNG -> LẤY CA CHIỀU & CA TỐI
                if time_ranges:
                    for start_h, end_h in time_ranges:
                        sh, eh = int(start_h), int(end_h)
                        # Bắt đầu từ 12h trở đi HOẶC kết thúc sau 13h HOẶC kết thúc lúc 0h/24h
                        if sh >= 12 or eh > 13 or eh == 0 or eh == 24:
                            is_matched_shift = True
                            break

                # Fallback từ khóa mốc giờ đơn lẻ
                if not is_matched_shift:
                    evening_keywords = ["13h", "14h", "15h", "16h", "17h", "18h", "20h", "21h", "22h", "24h", "0h", "14:00", "15:00", "16:00", "17:00", "22:00", "ca chiều", "ca chieu", "ca tối", "ca toi", "ca đêm"]
                    if any(kw in lower_raw for kw in evening_keywords):
                        is_matched_shift = True

            else:
                # 🌆 CHẠY 14H CHIỀU -> LẤY CA SÁNG HÔM NAY
                if time_ranges:
                    for start_h, end_h in time_ranges:
                        sh, eh = int(start_h), int(end_h)
                        # Ca sáng: bắt đầu 6h-11h và kết thúc <= 13h
                        if 6 <= sh <= 11 and (0 < eh <= 13):
                            is_matched_shift = True
                            break

                if not is_matched_shift:
                    morning_keywords = ["8h-11h", "8h30-11h30", "7h30-11h30", "8h-12h", "9h-11h", "8:00-11:30", "7:30-11:30"]
                    if any(kw in lower_raw for kw in morning_keywords):
                        is_matched_shift = True

            if not is_matched_shift:
                continue

            content = preprocess_message(raw_content)
            if content and content not in filtered_results[chat_name]:
                filtered_results[chat_name].append(content)

    return filtered_results


def write_to_sheet(sheet_target_name, messages):
    global spreadsheet
    if spreadsheet is None:
        print(f"⚠️ Thử kết nối lại Google Sheets cho [{sheet_target_name}]...")
        spreadsheet = get_spreadsheet()
        if spreadsheet is None:
            print(f"❌ Không thể ghi vào [{sheet_target_name}] do chưa kết nối được Google Sheets.")
            return
            
    try:
        EXCLUDED_SHEETS = [
            "Report",
            "GetReport",
            "iX000s iSSale TTS Base.XoắnNỆN50k*CấuTrúcVolunt",
            "iX000s iSSale gbBOSS AH*AU*cOL*YeuCauTop-iUp*KTra",
            "BoomWTF..AiLàmViệcRiêngThựcNÃOProofFileNGAY",
        ]

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
            print(f"✅ Đã ghi thêm {len(rows_to_append)} dòng mới vào [{sheet_target_name}]")
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

    chrome_version = None
    try:
        result = subprocess.check_output(["google-chrome", "--version"]).decode("utf-8")
        chrome_version = int(re.search(r"\d+", result).group(0))
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
                extra_signin[0].click()
                time.sleep(10)

                actions = webdriver.ActionChains(driver)
                actions.move_by_offset(500, 500).click().perform()
                actions.send_keys(Keys.TAB).perform()
                time.sleep(1)
                actions.send_keys(Keys.ENTER).perform()
                time.sleep(20)
        except Exception as e:
            print(f"⚠️ Bỏ qua lỗi check màn hình phụ: {e}")

        display_screenshot(driver, "after_login_success.png")
        return driver

    except Exception as e:
        display_screenshot(driver, "error_login.png")
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

    display_screenshot(driver, "after_login.png")

    # 1. CÀO TIN NHẮN TỪ TEAMS HTML
    all_scraped_data = {}
    for chat_name in chat_names_to_process:
        chat_messages = scroll_and_scrape_chat(driver, chat_name, max_scrolls=12)
        all_scraped_data[chat_name] = chat_messages

    # 2. XỬ LÝ LỌC TIN NHẮN
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
