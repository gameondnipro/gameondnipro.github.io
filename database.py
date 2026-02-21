import sqlite3
import os

DB_NAME = 'guarantee_repairs.db'
UPLOAD_FOLDER = 'uploads' 
DATE_FORMAT = '%Y-%m-%d'

def init_db():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        request_date TEXT NOT NULL,         -- Дата обращения
        issue_date TEXT,                    -- Дата выдачи ПК
        ttn_number TEXT,                    -- Номер ТТН
        client_name TEXT NOT NULL,          -- Имя клиента
        warranty_ticket_number TEXT,        -- Номер гарантийного талона
        
        claimed_problem TEXT,               -- Заявленная проблема
        diagnosed_problem TEXT,             -- Что продиагностировано
        replaced_parts TEXT,                -- Что заменено
        
        status TEXT NOT NULL DEFAULT 'Принят', 
        
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,         -- Краткий заголовок (для быстрого поиска)
        content TEXT NOT NULL,       -- Полное содержание ответа
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        -- ... (существующие колонки) ...
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER NOT NULL,
        comment_text TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
    )
    ''')

    try:
        cursor.execute("ALTER TABLE records ADD COLUMN client_phone TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
             raise

    try:
        cursor.execute("ALTER TABLE records ADD COLUMN client_telegram TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
             raise
         
    conn.execute('''CREATE TABLE IF NOT EXISTS ttn (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        number TEXT,
        client_name TEXT,
        amount REAL,
        note TEXT
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS pc_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        color TEXT,
        form_factor TEXT,
        price REAL,
        stock_count INTEGER,
        photos TEXT  -- Будем хранить пути к фото через запятую
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        priority TEXT, -- Low, Medium, High, Critical
        status TEXT,   -- To Do, In Progress, Done
        created_at TEXT
    )''')     
    cursor.execute("DROP TABLE IF EXISTS bank_rates") 

    cursor.execute('''CREATE TABLE IF NOT EXISTS bank_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_name TEXT,
        month_count INTEGER,
        rate REAL,
        UNIQUE(bank_name, month_count)
    )''')

    banks = ['monobank', 'ПриватБанк', 'ПУМБ']
    rates_data = []
    
    for bank in banks:
        base_rate = 1.9 if bank == 'monobank' else 2.1 if bank == 'ПриватБанк' else 2.5
        for m in range(3, 13):
            current_rate = base_rate + (m - 3) * 0.1 
            rates_data.append((bank, m, round(current_rate, 2)))

    for bank, m, r in rates_data:
        cursor.execute("INSERT OR IGNORE INTO bank_rates (bank_name, month_count, rate) VALUES (?, ?, ?)", (bank, m, r))
        
    cursor.execute('''CREATE TABLE IF NOT EXISTS pc_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,        -- 'cpu', 'motherboard', 'ram' и т.д.
        name TEXT,            -- 'Ryzen 5 5600'
        price INTEGER,        -- Цена захода
        socket TEXT,          -- 'AM4', 'AM5' (для CPU и плат)
        ram_type TEXT,        -- 'DDR4', 'DDR5' (для CPU, плат и ОЗУ)
        is_active INTEGER DEFAULT 1
    )''')   
        
    #conn.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
    #    id INTEGER PRIMARY KEY AUTOINCREMENT,
    #    user_name TEXT,             -- Кто (например, Женя, Ростик)
    #    action_type TEXT,           -- Тип (Создание, Удаление, Изменение)
    #    target_table TEXT,          -- Где (records, ttn, pc_cases)
    #    target_id INTEGER,          -- ID записи
    #    details TEXT,               -- Что именно изменилось
    #    created_at TEXT DEFAULT CURRENT_TIMESTAMP
    #)''')
    #def log_action(user, action, table, target_id, details=""):
    #conn.execute(
    #    "INSERT INTO audit_logs (user_name, action_type, target_table, target_id, details) VALUES (?, ?, ?, ?, ?)",
    #    (user, action, table, target_id, details)
    #)    
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS speeches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    title TEXT,
    content TEXT,
    position INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS urgent_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    pc_config TEXT NOT NULL,
    deadline DATETIME NOT NULL,
    status TEXT DEFAULT 'В черзі', -- 'В черзі', 'Збирається', 'Тестується', 'Готово'
    priority TEXT DEFAULT 'Нормальний', -- 'Терміново', 'Критично', 'Вчора'
    manager_note TEXT
    )''')
    conn.commit()
    conn.close()

print("DB initialized. UPLOAD_FOLDER:", UPLOAD_FOLDER)

def db_query(query, params=(), fetch_one=False):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    if fetch_one:
        result = cursor.fetchone()
        return dict(result) if result else None
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def db_execute(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

init_db()

print("DB initialized. UPLOAD_FOLDER:", UPLOAD_FOLDER)