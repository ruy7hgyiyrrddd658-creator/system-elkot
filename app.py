from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
import pandas as pd
from difflib import get_close_matches
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_elkot_system'

# إعداد قاعدة البيانات وتجهيز الجداول
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # جدول الحسابات (أدمن وموظف)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        role TEXT)''')
    # جدول الداتا الأساسية للعملاء
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        civil_id TEXT,
                        phone TEXT)''')
    
    # إضافة حسابات افتراضية لو مش موجودة
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('user', 'user123', 'user')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

# صفحة تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            session['role'] = user[0]
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        return "اسم المستخدم أو كلمة المرور غير صحيحة!"
    return render_template('login.html')

# لوحة تحكم الأدمن (الرفع والتحكم)
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        file = request.files['excel_file']
        if file and file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
            # التأكد من وجود الأعمدة المطلوبة في الإكسيل
            required_cols = ['الاسم', 'الرقم المدني', 'رقم الهاتف']
            if all(col in df.columns for col in required_cols):
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("INSERT INTO clients (name, civil_id, phone) VALUES (?, ?, ?)",
                                   (str(row['الاسم']), str(row['الرقم المدني']), str(row['رقم الهاتف'])))
                conn.commit()
                conn.close()
                return "تم رفع وتحديث قاعدة البيانات بنجاح!"
            return "تنبيه: تأكد أن ملف الإكسيل يحتوي على أعمدة: الاسم، الرقم المدني، رقم الهاتف"
            
    return render_template('admin.html')

# لوحة تحكم الموظف العادي (البحث الذكي والتصدير)
@app.route('/user', methods=['GET'])
def user_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    search_query = request.args.get('search', '')
    results = []
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    if search_query:
        # سحب كل الأسماء لعمل مطابقة ذكية
        cursor.execute("SELECT name, civil_id, phone FROM clients")
        all_clients = cursor.fetchall()
        names_list = [row[0] for row in all_clients]
        
        # محرك البحث الذكي: يجلب الأسماء المشابهة بنسبة 60% فأعلى
        matched_names = get_close_matches(search_query, names_list, n=20, cutoff=0.6)
        
        for row in all_clients:
            if row[0] in matched_names or search_query in row[0] or search_query in str(row[1]):
                results.append({'name': row[0], 'civil_id': row[1], 'phone': row[2]})
    else:
        cursor.execute("SELECT name, civil_id, phone FROM clients LIMIT 50")
        for row in cursor.fetchall():
            results.append({'name': row[0], 'civil_id': row[1], 'phone': row[2]})
            
    conn.close()
    return render_template('user.html', results=results, search_query=search_query)

# تصدير النتائج المفلترة إلى إكسيل
@app.route('/export')
def export_excel():
    search_query = request.args.get('search', '')
    conn = sqlite3.connect('database.db')
    
    if search_query:
        cursor = conn.cursor()
        cursor.execute("SELECT name, civil_id, phone FROM clients")
        all_clients = cursor.fetchall()
        names_list = [row[0] for row in all_clients]
        matched_names = get_close_matches(search_query, names_list, n=5000, cutoff=0.6)
        
        filtered_data = [row for row in all_clients if row[0] in matched_names or search_query in row[0]]
        df = pd.DataFrame(filtered_data, columns=['الاسم', 'الرقم المدني', 'رقم الهاتف'])
    else:
        df = pd.read_sql_query("SELECT name, civil_id, phone FROM clients", conn)
        
    conn.close()
    
    output_path = 'filtered_output.xlsx'
    df.to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
