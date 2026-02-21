from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.serving import run_simple
from flask import send_file
import os
import random
import shutil 
import sqlite3 
import socket 
import requests
from io import BytesIO
from datetime import datetime, timedelta
from database import init_db, db_query, db_execute, UPLOAD_FOLDER, DATE_FORMAT, DB_NAME
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_default') 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
SECRET_PASSWORD = "838995" 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_ticket_number():
    random_part = str(random.randint(100, 999))
    return f"TBR-{random_part}"

def save_photos(record_id, files):
   
    saved_paths = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = int(datetime.now().timestamp())
           
            new_filename = f"{record_id}_{timestamp}_{filename}" 
            
            
            fs_file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            
           
            db_file_path = fs_file_path.replace(os.sep, '/')
            
            try:
                file.save(fs_file_path) 
                
                
                db_execute("INSERT INTO photos (record_id, file_path) VALUES (?, ?)", 
                           (record_id, db_file_path))
                saved_paths.append(db_file_path)
            except Exception as e:
                print(f"Ошибка сохранения файла {new_filename}: {e}")
                
    return saved_paths

def db_vacuum():
    conn = sqlite3.connect(DB_NAME)
    
    try:
        conn.execute("VACUUM")
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Ошибка VACUUM: {e}")
        return False
    finally:
        conn.close()
def get_exchange_rates():
    try:
        response = requests.get('https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5', timeout=2000)
        data = response.json()
        
        rates = {}
        for item in data:
            if item['ccy'] == 'USD':
                rates['usd'] = round(float(item['buy']), 2)
        
        rates['usdt'] = rates['usd'] + 0.50 
        return rates
    except:
        return {'usd': '??', 'usdt': '??'}

@app.context_processor
def inject_rates():
    return dict(rates=get_exchange_rates())


@app.route('/settings')
def settings_page():
    return render_template('settings.html')


# 1. Страница со списком заказов
@app.route('/urgent')
def urgent_orders():

    orders = db_query("SELECT * FROM urgent_orders ORDER BY deadline ASC")
    return render_template('urgent.html', orders=orders)

# 2. Добавление нового заказа
@app.route('/urgent/add', methods=['POST'])
def add_urgent_order():
    data = request.form

    db_execute("""
        INSERT INTO urgent_orders (client_name, pc_config, deadline, priority, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data['client_name'], 
        data['pc_config'], 
        data['deadline'], 
        data['priority'], 
        'В очереди'
    ))
    return redirect(url_for('urgent_orders'))

# 3. Кнопка "Ракета" (быстрая смена статуса)
@app.route('/urgent/next_status/<int:order_id>', methods=['POST'])
def next_status(order_id):
    stages = ['В очереди', 'Сборка', 'Тестирование', 'Готов к выдаче']
    
    order = db_query("SELECT status FROM urgent_orders WHERE id = ?", (order_id,), one=True)
    if not order:
        return {"status": "error"}, 404
        
    current_status = order['status']
    
    try:
        current_index = stages.index(current_status)
        if current_index < len(stages) - 1:
            new_status = stages[current_index + 1]
            db_execute("UPDATE urgent_orders SET status = ? WHERE id = ?", (new_status, order_id))
            return {"status": "ok", "new_status": new_status}
        else:
            return {"status": "finished"}
    except ValueError:
        return {"status": "error"}, 400

# 4. Удаление заказа (когда забрали)
@app.route('/urgent/delete/<int:order_id>')
def delete_urgent_order(order_id):
    db_execute("DELETE FROM urgent_orders WHERE id = ?", (order_id,))
    return redirect(url_for('urgent_orders'))



# --- РАЗДЕЛ: ТТН ---
@app.route('/ttn')
def ttn_list():
    items = db_query("SELECT * FROM ttn ORDER BY date DESC")
    return render_template('ttn.html', items=items)

@app.route('/add_ttn', methods=['POST'])
def add_ttn():
    number = request.form.get('number')
    client_name = request.form.get('client_name')
    amount = request.form.get('amount')
    note = request.form.get('note', '') 
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    db_execute("INSERT INTO ttn (date, number, client_name, amount, note) VALUES (?, ?, ?, ?, ?)",
               (current_date, number, client_name, amount, note))
    
    flash("Запись добавлено!", "success")
    return redirect(url_for('ttn_list'))

@app.route('/delete_ttn/<int:ttn_id>')
def delete_ttn(ttn_id):
    db_execute("DELETE FROM ttn WHERE id = ?", (ttn_id,))
    flash("Запись удалена!", "warning")
    return redirect(url_for('ttn_list'))

@app.route('/ttn/edit/<int:ttn_id>', methods=['POST'])
def edit_ttn(ttn_id):
    number = request.form.get('number')
    client_name = request.form.get('client_name')
    amount = request.form.get('amount')
    note = request.form.get('note')

    db_execute(
        "UPDATE ttn SET number = ?, client_name = ?, amount = ?, note = ? WHERE id = ?",
        (number, client_name, amount, note, ttn_id)
    )
    flash("Запись отредактирована!", "success")
    return redirect(url_for('ttn_list'))

# --- РАЗДЕЛ: КОРПУСА ---
@app.route('/cases')
def cases_gallery():
    data_from_db = db_query("SELECT * FROM pc_cases ORDER BY id DESC")
    
    print(f"DEBUG: : {len(data_from_db)}")
    
    return render_template('cases.html', cases=data_from_db)

@app.route('/add_case', methods=['POST'])
def add_case():
    name = request.form.get('name')
    color = request.form.get('color')
    form_factor = request.form.get('form_factor')
    price = request.form.get('price')
    stock = request.form.get('stock_count')
    
    files = request.files.getlist('photos')
    saved_filenames = []
    
    for file in files:
        if file and file.filename:
            filename = secure_filename(f"{name}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            saved_filenames.append(filename)
    photos_str = ",".join(saved_filenames)
    
    db_execute("""INSERT INTO pc_cases (name, color, form_factor, price, stock_count, photos) 
                  VALUES (?, ?, ?, ?, ?, ?)""",
               (name, color, form_factor, price, stock, photos_str))
    
    flash("Корпус доабвлено!", "success")
    return redirect(url_for('cases_gallery'))

@app.route('/delete_case/<int:case_id>')
def delete_case(case_id):
    case = db_query("SELECT photos FROM pc_cases WHERE id = ?", (case_id,), one=True)
    
    if case:
        if case['photos']:
            photo_list = case['photos'].split(',')
            for photo in photo_list:
                file_path = os.path.join('uploads', photo) 
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        db_execute("DELETE FROM pc_cases WHERE id = ?", (case_id,))
        flash("Корпус та його фото успішно видалено!", "danger")
    
    return redirect(url_for('cases_gallery'))



@app.route('/tasks')
def tasks_board():
    tasks = db_query("SELECT * FROM tasks ORDER BY created_at DESC")
    return render_template('tasks.html', tasks=tasks)

@app.route('/notes')
def notes_page():
    return render_template('notes.html')

@app.route('/search')
def global_search():
    q = request.args.get('q', '').strip()
    
    if len(q) < 2:
        return redirect(request.referrer or '/')
    
    service_sql = """
        SELECT id, client_name as title, 'Сервис' as category, 
               status || ' | ' || claimed_problem as info, 
               '/service/record/' || id as link 
        FROM records 
        WHERE client_name LIKE ? 
           OR client_phone LIKE ? 
           OR client_telegram LIKE ? 
           OR warranty_ticket_number LIKE ? 
           OR ttn_number LIKE ? 
           OR id = ?
    """
    search_param = f'%{q}%'
    service_res = db_query(service_sql, (search_param, search_param, search_param, search_param, search_param, q))


    cases_sql = """
        SELECT id, name as title, 'Корпуса' as category, 
               price || ' грн | ' || color as info, '/cases' as link 
        FROM pc_cases 
        WHERE name LIKE ? OR color LIKE ?
    """
    cases_res = db_query(cases_sql, (search_param, search_param))


    ttn_sql = """
        SELECT id, number as title, 'НП ТТН' as category, 
               client_name || ' | ' || amount || ' грн' as info, '/ttn' as link 
        FROM ttn 
        WHERE number LIKE ? OR client_name LIKE ? OR note LIKE ?
    """
    ttn_res = db_query(ttn_sql, (search_param, search_param, search_param))


    tasks_sql = """
        SELECT id, title, 'Завдання' as category, 
               status || ' | Пріоритет: ' || priority as info, '/tasks' as link 
        FROM tasks 
        WHERE title LIKE ? OR description LIKE ?
    """
    tasks_res = db_query(tasks_sql, (search_param, search_param))

    results = service_res + cases_res + ttn_res + tasks_res
    
    return render_template('search_results.html', results=results, query=q)

@app.route('/installment')
def installment_calc():
    raw_rates = db_query("SELECT * FROM bank_rates")
    rates_map = {}
    for r in raw_rates:
        bank = r['bank_name']
        if bank not in rates_map:
            rates_map[bank] = {}
        rates_map[bank][str(r['month_count'])] = r['rate']
    
    return render_template('installment.html', rates_json=rates_map)

@app.route('/update_rates', methods=['POST'])
def update_rates():
    data = request.form
    for key, value in data.items():
        if '_' in key:
            bank_name, month = key.split('_')
            try:
                new_rate = float(value)
                db_execute(
                    "UPDATE bank_rates SET rate = ? WHERE bank_name = ? AND month_count = ?", 
                    (new_rate, bank_name, int(month))
                )
            except ValueError:
                continue
                
    flash("Всі відсоткові ставки успішно оновлено!", "success")
    return redirect(url_for('installment_calc'))


# Просчёт ПК

@app.route('/configurator')
def configurator():
    components = db_query("SELECT * FROM pc_components WHERE is_active = 1")
    return render_template('configurator.html', components=components)

@app.route('/configurator/settings', methods=['POST'])
def save_component():
    data = request.form
    db_execute("INSERT INTO pc_components (category, name, price, socket, ram_type) VALUES (?, ?, ?, ?, ?)",
               (data['category'], data['name'], data['price'], data['socket'], data['ram_type']))
    return redirect(url_for('configurator'))

@app.route('/configurator/delete/<int:comp_id>')
def delete_component(comp_id):
    db_execute("DELETE FROM pc_components WHERE id = ?", (comp_id,))
    return redirect(url_for('configurator'))

@app.route('/configurator/update_price/<int:comp_id>/<int:new_price>', methods=['POST'])
def update_price(comp_id, new_price):
    db_execute("UPDATE pc_components SET price = ? WHERE id = ?", (new_price, comp_id))
    return {"status": "ok"}


@app.route('/configurator/print_page')
def print_page():
    return render_template('print_layout.html')
# Спичи

@app.route('/speeches')
def speeches_list():
    all_speeches = db_query("SELECT * FROM speeches ORDER BY category, position")
    categorized = {}
    for s in all_speeches:
        categorized.setdefault(s['category'], []).append(s)
    return render_template('speeches.html', speeches=categorized)

@app.route('/speeches/save', methods=['POST'])
def save_speech():
    data = request.form
    db_execute("INSERT INTO speeches (category, title, content, position) VALUES (?, ?, ?, ?)",
               (data['category'], data['title'], data['content'], data['position'] or 0))
    return redirect(url_for('speeches_list'))

@app.route('/speeches/update/<int:speech_id>', methods=['POST'])
def update_speech(speech_id):
    data = request.form
    db_execute("""
        UPDATE speeches 
        SET category = ?, title = ?, content = ?, position = ? 
        WHERE id = ?
    """, (data['category'], data['title'], data['content'], data['position'], speech_id))
    return redirect(url_for('speeches_list'))

@app.route('/speeches/delete/<int:speech_id>')
def delete_speech(speech_id):
    db_execute("DELETE FROM speeches WHERE id = ?", (speech_id,))
    return redirect(url_for('speeches_list'))

@app.route('/speeches/click/<int:speech_id>', methods=['POST'])
def register_click(speech_id):
    db_execute("UPDATE speeches SET usage_count = usage_count + 1 WHERE id = ?", (speech_id,))
    return {"status": "ok"}



# Настройки

@app.route('/settings/export')
def export_database():
    password = request.args.get('password')
    
    if not password or password != SECRET_PASSWORD:
        flash("Ошибка: Пароль не предоставлен или неверный.", 'danger')
        return redirect(url_for('settings_page'))

    try:
        return send_file(DB_NAME, 
                         as_attachment=True,
                         download_name=f'warranty_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    except Exception as e:
        flash(f"Ошибка экспорта БД: {e}", 'danger')
        return redirect(url_for('settings_page'))

@app.route('/settings/import', methods=['POST'])
def import_database():
    password = request.form.get('password')
    
    if not password or password != SECRET_PASSWORD:
        flash("Ошибка: Пароль не предоставлен или неверный.", 'danger')
        return redirect(url_for('settings_page'))


    if 'file' not in request.files:
        flash("Файл не выбран.", 'danger')
        return redirect(url_for('settings_page'))

    file = request.files['file']

    if file.filename == '' or not file.filename.endswith('.db'):
        flash("Выберите корректный файл базы данных (.db).", 'danger')
        return redirect(url_for('settings_page'))

    try:
        backup_path = os.path.join(os.getcwd(), DB_NAME)
        file.save(backup_path) 
        
        flash("База данных успешно восстановлена! Пожалуйста, перезапустите приложение (run.py).", 'success')
        
    except Exception as e:
        flash(f"Ошибка импорта БД: {e}", 'danger')
    
    return redirect(url_for('settings_page'))

@app.route('/settings/reset_id_sequence', methods=['POST'])
def reset_id_sequence():
    password = request.form.get('password')

    if not password or password != SECRET_PASSWORD:
        flash("Ошибка: Неверный пароль для сброса ID.", 'danger')
        return redirect(url_for('settings_page'))
    
    try:
        db_execute("DELETE FROM records") 
        db_execute("DELETE FROM sqlite_sequence WHERE name='records'") 
        flash("✅ Нумерация ID успешно сброшена (все данные удалены!). Новая запись начнется с ID 1.", 'success')
    except Exception as e:
        flash(f"Ошибка сброса ID: {e}", 'danger')
    return redirect(url_for('settings_page'))


@app.route('/settings/optimize_db', methods=['POST'])
def optimize_database():
    if not db_vacuum():
        flash("Ошибка оптимизации: Не удалось выполнить VACUUM.", 'danger')
        return redirect(url_for('settings_page'))
    flash("✅ База данных успешно оптимизирована и сжата!", 'success')
    return redirect(url_for('settings_page'))

@app.route('/quick_add', methods=['POST'])
def quick_add_record():
    client_name = request.form.get('client_name')
    claimed_problem = request.form.get('claimed_problem')
    
    if not client_name or not claimed_problem:
        flash("Ошибка: Заполните Имя и Проблему для быстрого приёма.", 'danger')
        return redirect(url_for('dashboard'))
    new_ticket = generate_ticket_number()
    
    data = {
        'request_date': datetime.now().strftime('%Y-%m-%d'),
        'client_name': client_name,
        'claimed_problem': claimed_problem,
        'warranty_ticket_number': new_ticket, 
        'status': 'Принят'
    }
    cols = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    insert_query = f"INSERT INTO records ({cols}) VALUES ({placeholders})"
    record_id = db_execute(insert_query, tuple(data.values()))
    
    flash(f"Заявка №{record_id} принята! Талон: {new_ticket}", 'success')
    return redirect(url_for('view_record', record_id=record_id))

@app.route('/')
@app.route('/hub')
def hub():
    return render_template('hub.html')



@app.route('/service')
def service_list():
    query_parts = []
    query_params = []
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'desc')
    search_query = request.args.get('q', '').strip()

    valid_sorts = ['id', 'request_date', 'client_name', 'ttn_number', 'status', 'created_at']
    if sort_by not in valid_sorts:
        sort_by = 'id'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'
    
    if search_query:
        search_term_lower = f"%{search_query.lower()}%"
        search_term_original = f"%{search_query}%"
        
        where_clause = """
            WHERE 
                LOWER(IFNULL(client_name, '')) LIKE ? OR             
                IFNULL(ttn_number, '') LIKE ? OR                     
                LOWER(IFNULL(claimed_problem, '')) LIKE ? OR         
                IFNULL(warranty_ticket_number, '') LIKE ?            
        """
        query_parts.append(where_clause)
        
        query_params.extend([
            search_term_lower,      # client_name (LOWER)
            search_term_original,   # ttn_number (ORIGINAL)
            search_term_lower,      # claimed_problem (LOWER)
            search_term_original    # warranty_ticket_number (ORIGINAL)
        ]) 
        
    main_query = f"""
    SELECT 
        id, request_date, client_name, ttn_number, status, claimed_problem, warranty_ticket_number,
        client_phone, client_telegram
    FROM records 
    {' '.join(query_parts)} 
    ORDER BY {sort_by} {order}
"""
    records = db_query(main_query, query_params)


    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=7)
    
    for record in records:
   
        photo_result = db_query("SELECT file_path FROM photos WHERE record_id = ? ORDER BY id LIMIT 1", (record['id'],), fetch_one=True)
        record['first_photo_path'] = photo_result['file_path'] if photo_result else None
        

        record['is_stale'] = False
        if record['status'] == 'В работе':
            try:
                request_date = datetime.strptime(record['request_date'], '%Y-%m-%d').date()
                if request_date < seven_days_ago:
                    record['is_stale'] = True
            except (ValueError, TypeError):
                pass
            
    new_order = 'asc' if order == 'desc' else 'desc'
    
    return render_template('list.html', 
                           records=records, 
                           current_sort=sort_by, 
                           current_order=order,
                           new_order=new_order,
                           search_query=search_query, 
                           statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ'])
    
@app.route('/dashboard')
def dashboard():
    status_counts = db_query("SELECT status, COUNT(id) as count FROM records GROUP BY status")
    
    metrics = {item['status']: item['count'] for item in status_counts}
    total_records = sum(metrics.values())
    recent_records = db_query("SELECT id, request_date, client_name, status, claimed_problem FROM records ORDER BY id DESC LIMIT 5")
    
    three_months_ago = datetime.now() - timedelta(days=90)
    start_date_str = three_months_ago.strftime('%Y-%m-%d')

    chart_data_raw = db_query("""
        SELECT 
            strftime('%Y-%m', request_date) AS month, 
            COUNT(id) AS count 
        FROM records 
        WHERE request_date >= ?
        GROUP BY month 
        ORDER BY month ASC
    """, (start_date_str,))
    
    chart_labels = [item['month'] for item in chart_data_raw]
    chart_values = [item['count'] for item in chart_data_raw]

    seven_days_ago_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    stale_records = db_query("""
        SELECT id, client_name, request_date, claimed_problem 
        FROM records 
        WHERE status = 'В работе' AND request_date < ? 
        ORDER BY request_date ASC
    """, (seven_days_ago_str,))
    status_chart_labels = []
    status_chart_data = []
    status_chart_colors = {
        'Принят': 'rgba(0, 123, 255, 0.8)',      
        'В работе': 'rgba(255, 193, 7, 0.8)',    
        'Исполнено': 'rgba(40, 167, 69, 0.8)',   
        'Обработан': 'rgba(111, 66, 193, 0.8)',  
        'Отказ': 'rgba(220, 53, 69, 0.8)',       
        'Архив': 'rgba(108, 117, 125, 0.8)',     
    }


    for status, count in metrics.items():
        if count > 0 and status != 'Архив': 
            status_chart_labels.append(status)
            status_chart_data.append(count)



    return render_template('dashboard.html', 
                            metrics=metrics, 
                            total_records=total_records,
                            recent_records=recent_records,
                            statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ'], 
                            chart_labels=chart_labels,
                            chart_values=chart_values,
                            stale_records=stale_records,
                            status_chart_labels=status_chart_labels,
                            status_chart_data=status_chart_data,
                            status_chart_colors=status_chart_colors)
        
@app.route('/add', methods=['GET', 'POST'])
def add_record():
    if request.method == 'POST':
        try:
            data = {
                'request_date': request.form['request_date'],
                'issue_date': request.form.get('issue_date'),
                'ttn_number': request.form.get('ttn_number'),
                'client_name': request.form['client_name'],
                'client_phone': request.form.get('client_phone'),   
                'client_telegram': request.form.get('client_telegram'),
                'warranty_ticket_number': request.form.get('warranty_ticket_number'),
                'claimed_problem': request.form.get('claimed_problem'),
                'diagnosed_problem': request.form.get('diagnosed_problem'),
                'replaced_parts': request.form.get('replaced_parts'),
                'status': request.form.get('status', 'Принят')
            }
            
            if not data['request_date'] or not data['client_name']:
                flash("Дата обращения и Имя клиента обязательны.", 'danger')
                return render_template('add_record.html', data=data)

            cols = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            insert_query = f"INSERT INTO records ({cols}) VALUES ({placeholders})"
            
            record_id = db_execute(insert_query, tuple(data.values()))
            
            files = request.files.getlist('photos')
            if files:
                save_photos(record_id, files)
            
            flash(f"Запись №{record_id} успешно добавлена!", 'success')
            return redirect(url_for('service_list'))
            
        except Exception as e:
            flash(f"Ошибка при добавлении записи: {e}", 'danger')
            return redirect(url_for('add_record'))

    today_date = datetime.now().strftime(DATE_FORMAT)
    return render_template('add_record.html', 
                           default_request_date=today_date,
                           statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ']) 


@app.route('/add_comment/<int:record_id>', methods=['POST'])
def add_comment(record_id):
    comment_text = request.form.get('comment_text')
    
    if not comment_text:
        flash("Ошибка: Комментарий не может быть пустым.", 'danger')
        return redirect(url_for('view_record', record_id=record_id))

    try:
        db_execute("""
            INSERT INTO comments (record_id, comment_text, created_at)
            VALUES (?, ?, ?)
        """, (record_id, comment_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        flash("Комментарий успешно добавлен.", 'success')
    except Exception as e:
        flash(f"Ошибка БД при добавлении комментария: {e}", 'danger')
        
    return redirect(url_for('view_record', record_id=record_id))

@app.route('/view/<int:record_id>')
def old_view_redirect(record_id):
    return redirect(url_for('view_record', record_id=record_id))

@app.route('/service/record/<int:record_id>')
def view_record(record_id):
    record = db_query("SELECT * FROM records WHERE id = ?", (record_id,), fetch_one=True)
    if not record:
        flash("Запись не найдена.", 'warning')
        return redirect(url_for('service_list'))

    photos = db_query("SELECT * FROM photos WHERE record_id = ?", (record_id,))
    comments = db_query("SELECT * FROM comments WHERE record_id = ? ORDER BY created_at DESC", (record_id,))
    return render_template('detail_record.html', 
                           record=record, 
                           photos=photos,
                           comments=comments,
                           statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ']) 

@app.route('/report/<int:record_id>')
def print_report(record_id):

    record = db_query("SELECT * FROM records WHERE id = ?", (record_id,), fetch_one=True)
    
    if not record:
        flash("Запись для акта не найдена.", 'warning')
        return redirect(url_for('service_list'))

    report_data = {
        'id': record['id'],
        'client_name': record['client_name'],
        'warranty_ticket_number': record['warranty_ticket_number'] or '—',
        'request_date': record['request_date'],
        'issue_date': record['issue_date'] or '—',
        'claimed_problem': record['claimed_problem'],
        'diagnosed_problem': record['diagnosed_problem'],
        'replaced_parts': record['replaced_parts'],     
        'report_date': datetime.now().strftime('%Y-%m-%d'), 
    }
    
    return render_template('service_report.html', record=report_data)
@app.route('/intake_report/<int:record_id>')
def print_intake_report(record_id):
    record = db_query("SELECT * FROM records WHERE id = ?", (record_id,), fetch_one=True)
    if not record:
        flash("Запис для акту не знайдено.", 'warning')
        return redirect(url_for('service_list'))

    intake_data = {
        'id': record['id'],
        'client_name': record['client_name'],
        'warranty_ticket_number': record['warranty_ticket_number'] or '—',
        'request_date': record['request_date'],
        'planned_work': record['diagnosed_problem'] or 'Повна діагностика.',
        'claimed_problem': record['claimed_problem'], 
        'report_date': datetime.now().strftime('%Y-%m-%d'), 
    }
    
    return render_template('intake_report.html', record=intake_data)
@app.route('/edit/<int:record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    record = db_query("SELECT * FROM records WHERE id = ?", (record_id,), fetch_one=True)
    
    if not record:
        flash("Запись для редактирования не найдена.", 'danger')
        return redirect(url_for('service_list'))

    if request.method == 'POST':
        try:
            data = {
                'request_date': request.form['request_date'],
                'issue_date': request.form.get('issue_date'),
                'ttn_number': request.form.get('ttn_number'),
                'client_name': request.form['client_name'],
                'client_phone': request.form.get('client_phone'),
                'client_telegram': request.form.get('client_telegram'),
                'warranty_ticket_number': request.form.get('warranty_ticket_number'),
                'claimed_problem': request.form.get('claimed_problem'),
                'diagnosed_problem': request.form.get('diagnosed_problem'),
                'replaced_parts': request.form.get('replaced_parts'),
                'status': request.form.get('status', 'Принят')
            }
            
            set_clause = ', '.join([f'"{col}" = ?' for col in data.keys()])
            
            update_query = f"UPDATE records SET {set_clause} WHERE id = ?"
            
            params = tuple(data.values()) + (record_id,)
            
            db_execute(update_query, params)

            files = request.files.getlist('photos')
            if files:
                save_photos(record_id, files) 
            
            flash(f"Запись №{record_id} успешно обновлена!", 'success')
            return redirect(url_for('view_record', record_id=record_id))
            
        except Exception as e:
            flash(f"Ошибка при обновлении записи: {e}", 'danger')
            photos = db_query("SELECT * FROM photos WHERE record_id = ?", (record_id,))
            return render_template('edit_record.html', 
                                   record=record, 
                                   photos=photos,
                                   statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ']) 

    photos = db_query("SELECT * FROM photos WHERE record_id = ?", (record_id,))
    
    return render_template('edit_record.html', 
                           record=record, 
                           photos=photos,
                           statuses=['Принят', 'В работе', 'Исполнено', 'Обработан', 'Отказ']) 

@app.route('/delete/<int:record_id>', methods=['POST', 'GET'])
def delete_record(record_id):
    try:
        photos = db_query("SELECT file_path FROM photos WHERE record_id = ?", (record_id,))
        

        for photo in photos:
            file_path_in_db = photo['file_path'] 
            
            filename = os.path.basename(file_path_in_db)
            file_path_on_disk = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            if os.path.exists(file_path_on_disk):
                os.remove(file_path_on_disk)
        db_execute("DELETE FROM photos WHERE record_id = ?", (record_id,))
        db_execute("DELETE FROM records WHERE id = ?", (record_id,))
        flash(f"Запись №{record_id} и все связанные файлы успешно удалены.", 'success')
    except Exception as e:
        flash(f"Ошибка при удалении записи №{record_id}: {e}", 'danger')
    return redirect(url_for('service_list'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


#Faq

@app.route('/faq')
def faq_list():
    search_term = request.args.get('faq_q', '').strip()
    query = "SELECT * FROM faq ORDER BY id DESC"
    params = ()

    if search_term:
        search_term = f"%{search_term}%"
        query = "SELECT * FROM faq WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ? ORDER BY id DESC"
        params = (search_term.lower(), search_term.lower())

    faqs = db_query(query, params)
    return render_template('faq_list.html', faqs=faqs)

@app.route('/faq/add', methods=['POST'])
def faq_add():
    title = request.form.get('title')
    content = request.form.get('content')

    if not title or not content:
        flash("Поля пустые.", 'warning')
        return redirect(url_for('faq_list'))

    db_execute("INSERT INTO faq (title, content) VALUES (?, ?)", (title, content))
    flash("Новая FAQ-запись успешно добавлена.", 'success')
    return redirect(url_for('faq_list'))

@app.route('/faq/delete/<int:faq_id>', methods=['POST'])
def faq_delete(faq_id):
    db_execute("DELETE FROM faq WHERE id = ?", (faq_id,))
    flash(f"FAQ-запись №{faq_id} успешно удалена.", 'success')
    return redirect(url_for('faq_list'))


@app.route('/reports')
def advanced_reports():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    query_params = []
    where_clauses = []
    
    try:
        if start_date_str:
            datetime.strptime(start_date_str, '%Y-%m-%d')
            where_clauses.append("request_date >= ?")
            query_params.append(start_date_str)
            
        if end_date_str:
            datetime.strptime(end_date_str, '%Y-%m-%d')
            where_clauses.append("request_date <= ?")
            query_params.append(end_date_str)
    except ValueError:
        flash("Неверный формат даты. Правильный: ГГГГ-ММ-ДД.", 'danger')
        start_date_str = end_date_str = None
        where_clauses = []
        query_params = []

    where_sql = " AND ".join(where_clauses)
    if where_sql:
        where_sql = " WHERE " + where_sql
        
    stats_query = f"SELECT status, COUNT(id) as count FROM records {where_sql} GROUP BY status"
    status_stats = db_query(stats_query, query_params)
    
    detailed_records_query = f"SELECT id, request_date, client_name, status FROM records {where_sql} ORDER BY request_date DESC"
    detailed_records = db_query(detailed_records_query, query_params)

    return render_template('reports.html', 
                           status_stats=status_stats, 
                           detailed_records=detailed_records,
                           start_date=start_date_str,
                           end_date=end_date_str)

@app.route('/analytics')
def problem_analytics():
    top_problems = db_query("""
        SELECT claimed_problem, COUNT(id) as count 
        FROM records 
        WHERE claimed_problem IS NOT NULL AND claimed_problem != ''
        GROUP BY claimed_problem
        ORDER BY count DESC
        LIMIT 10
    """)
    
    top_solutions = db_query("""
        SELECT replaced_parts, COUNT(id) as count 
        FROM records 
        WHERE replaced_parts IS NOT NULL AND replaced_parts != ''
        GROUP BY replaced_parts
        ORDER BY count DESC
        LIMIT 10
    """)
    
    return render_template('analytics.html', 
                           top_problems=top_problems, 
                           top_solutions=top_solutions)


@app.route('/audit')
def view_audit():
    logs = db_query("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100")
    return render_template('audit.html', logs=logs)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

"""if __name__ == '__main__':
    
    local_ip = '127.0.0.1'#Значение по умолчанию
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1)) 
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            local_ip = '127.0.0.1'
            
    print(f"\nWeb server loaded on:")
    print(f"   (LOCAL HOST): http://127.0.0.1:5000")
    print(f"   (FOR ALL CLIENTS ON LAN NETWORK): http://{local_ip}:5000\n")
"""
    # host='0.0.0.0' 
    #app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False, threaded=True, use_debugger=True , ssl_context='adhoc')
    
app.config.update(
SECRET_KEY='super_secret_gmonx_key',
PERMANENT_SESSION_LIFETIME=timedelta(days=31),
JSON_AS_ASCII=False,
SEND_FILE_MAX_AGE_DEFAULT=0  
)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0', 
        port=8080, 
        debug=False, 
        threaded=True,  
        ssl_context='adhoc'
    )
    # use_reloader=False