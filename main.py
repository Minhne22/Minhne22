from flask import Flask, request, render_template, jsonify, redirect, send_from_directory
import os
import zipfile
from werkzeug.utils import secure_filename
import time
from hashlib import md5
import shutil
import re
from bs4 import BeautifulSoup




UPLOAD_FOLDER = 'uploaded_files'
EXTRACT_FOLDER = 'extracted_files'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACT_FOLDER'] = EXTRACT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)

def simplify_path_auto(full_path, root_folder=EXTRACT_FOLDER):
    full_path = os.path.normpath(full_path)  # Chuyển về định dạng phù hợp cho hệ điều hành
    index = full_path.find(root_folder)
    if index != -1:
        return full_path[index:]  # Cắt từ vị trí root_folder
    return full_path

def extract_number(filename):
    match = re.search(r'message_(\d+)\.html', filename)
    return int(match.group(1)) if match else float('inf')


@app.route('/')
@app.route('/home')
def home():
    return 'Web OK', 200


@app.route('/view_file', methods=['GET', 'POST'])
def view_file():
    request_method = request.method
    if request_method == 'GET':
        return render_template('uploadzip.html')

    else:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected for uploading'}), 400

        if file and file.filename.endswith('.zip'):
            filename = secure_filename(file.filename)
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(zip_path)

            # Giải nén file ZIP
            file_path = md5(f'{filename[:-4]}-{time.time()}'.encode('utf8')).hexdigest()
            extract_to = os.path.join(app.config['EXTRACT_FOLDER'], file_path).replace('\\', '/')
            os.makedirs(extract_to, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)

            html_main = os.path.join(extract_to, 'start_here.html').replace('\\', '/')

            # print(html_main)

            os.remove(zip_path)

            if not os.path.exists(html_main):
                shutil.rmtree(extract_to)
                return 'File không hợp lệ', 400

            html_content = open(html_main, encoding='utf8').read()
            with open(html_main, 'w+', encoding='utf8') as f:
                pattern = r'<div class="[^"]*">Giới thiệu về phần tải xuống</div>'
                replacement = f'''
                <div class="button-container">
                    <a href="/{extract_to}/thong_ke.html">Thống kê</a>
                </div>
                '''
                updated_content = re.sub(pattern, replacement, html_content)
                f.write(updated_content)

            return jsonify({'redirect_url': html_main})
        else:
            return '''
                <!doctype html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Error</title>
                </head>
                <body>
                    <h1>Error: Invalid file format</h1>
                    <p>Please upload a valid .zip file.</p>
                    <a href="/">Try Again</a>
                </body>
                </html>
                ''', 400


@app.route(f'/{EXTRACT_FOLDER}/<folder_name>/<path:filename>')
def serve_files(folder_name, filename):
    # Xác định đường dẫn đến thư mục con dựa trên tên folder (123, 234, 456...)
    folder_path = os.path.join(os.getcwd(), EXTRACT_FOLDER, folder_name)

    # Kiểm tra xem thư mục con có tồn tại không
    if os.path.exists(folder_path):
        return send_from_directory(folder_path, filename)
    else:
        return "Folder not found!", 404


@app.route(f'/{EXTRACT_FOLDER}/<folder_name>/thong_ke.html')
def thong_ke(folder_name):
    # Xác định đường dẫn đến thư mục con dựa trên tên folder (123, 234, 456...)
    folder_path = os.path.join(os.getcwd(), EXTRACT_FOLDER, folder_name)

    # Kiểm tra xem thư mục con có tồn tại không
    if os.path.exists(folder_path):

        data_list = []

        # Tin nhan
        message_path = 'your_facebook_activity/messages/inbox'
        folder_message_list = os.path.join(folder_path, message_path)
        user_message_list = os.listdir(folder_message_list)
        print(folder_message_list)
        data_list.append([
            'Số thứ tự', 'Url đoạn chat', 'ID/Tên đoạn chat', 'Tổng số',
            'Time updated tin nhắn cuối'
        ])
        for index, thread_name in enumerate(user_message_list):
            # Đi vào từng nhóm
            object_message_path = os.path.join(folder_message_list, thread_name)
            message_list = sorted(os.listdir(object_message_path), key=extract_number)  # -> Doạn chat: message_1.html
            message_file_list = [
                os.path.join(object_message_path, message) for message in message_list if message.endswith('.html')
            ] # -> Gắn đường dẫn cho từng file, lọc html

            for s_message in message_file_list:
                with open(s_message, encoding='utf8') as f:
                    content = f.read()
                    # Sử dụng bs4 để đọc dữ liệu
                    soup = BeautifulSoup(content, 'html.parser')

                    messages = []
                    # Lọc tin nhắn
                    for message_block in soup.find_all('div', recursive=True):
                        # Xác định người gửi (nằm trong thẻ div đầu tiên chứa tên người gửi)
                        sender_tag = message_block.find(
                            lambda tag: tag.name == 'div' and tag.text.strip() and len(tag.text.strip()) < 50)
                        sender_name = sender_tag.get_text(strip=True) if sender_tag else 'Unknown'

                        # Tìm nội dung tin nhắn (có text, không rỗng)
                        content_tag = message_block.find(
                            lambda tag: tag.name == 'div' and tag.text.strip() and len(tag.text.strip()) > 1)
                        message_content = content_tag.get_text(strip=True) if content_tag else 'No content'

                        # Tìm thời gian (thường là định dạng thời gian nằm trong div riêng biệt)
                        time_tag = message_block.find(
                            lambda tag: tag.name == 'div' and 'Tháng' in tag.text and len(tag.text.strip()) < 50)
                        message_time = time_tag.get_text(strip=True) if time_tag else 'No timestamp'

                        # Kiểm tra xem khối tin nhắn có đủ thông tin không (người gửi, nội dung, thời gian)
                        if sender_name != 'Unknown' and message_content != 'No content':
                            messages.append({
                                'sender': sender_name,
                                'content': message_content,
                                'time': message_time
                            })

                    # Ghi list
                    path = simplify_path_auto(s_message).replace("\\", "/")
                    data_list.append([
                        str(index + 1), # Số thứ tự
                        f'/{path}', # URL
                        soup.title.text, # Title
                        str(len(messages)), # Số lượng,
                        messages[0]['time'], # Thời gian cuối
                    ])






        return render_template('table.html', data_list=data_list)
    else:
        return "Folder not found!", 404


app.run('0.0.0.0', 8080)
