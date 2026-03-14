from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

# ตั้งค่าการเชื่อมต่อ MySQL (เปลี่ยน root และรหัสผ่าน ให้ตรงกับเครื่องของคุณ)
# รูปแบบ: mysql+pymysql://username:password@localhost/database_name
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/atm_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models (โครงสร้างตารางฐานข้อมูล) ---
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    # เชื่อมความสัมพันธ์กับตาราง Transaction (ถ้าลบบัญชี ข้อมูลธุรกรรมจะหายไปด้วย)
    transactions = db.relationship('Transaction', backref='account', cascade="all, delete-orphan", lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    trans_type = db.Column(db.String(50), nullable=False) # ฝาก หรือ ถอน
    amount = db.Column(db.Float, nullable=False)
    # บันทึกเวลาประเทศไทย
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Bangkok')))

# สร้างตารางอัตโนมัติก่อนเริ่มแอปพลิเคชัน
with app.app_context():
    db.create_all()

# --- Routes (การทำงานของหน้าเว็บ) ---

@app.route('/')
def index():
    accounts = Account.query.all()
    # คำนวณยอดเงินรวมในระบบ
    total_system_balance = sum(acc.balance for acc in accounts)
    return render_template('index.html', accounts=accounts, total_balance=total_system_balance)

@app.route('/create_account', methods=['POST'])
def create_account():
    acc_num = request.form.get('account_number')
    username = request.form.get('username')
    initial_balance = float(request.form.get('balance', 0))

    # เช็คว่ามีเลขบัญชีนี้แล้วหรือยัง
    existing_acc = Account.query.filter_by(account_number=acc_num).first()
    if existing_acc:
        flash('เลขบัญชีนี้มีอยู่ในระบบแล้ว!', 'danger')
        return redirect(url_for('index'))

    new_acc = Account(account_number=acc_num, username=username, balance=initial_balance)
    db.session.add(new_acc)
    db.session.commit()
    
    # บันทึกประวัติถ้ามีการฝากเงินเริ่มต้น
    if initial_balance > 0:
        trans = Transaction(account_id=new_acc.id, trans_type='ฝากเงิน (เปิดบัญชี)', amount=initial_balance)
        db.session.add(trans)
        db.session.commit()

    flash('สร้างบัญชีผู้ใช้สำเร็จ!', 'success')
    return redirect(url_for('index'))

@app.route('/account/<string:acc_num>')
def view_account(acc_num):
    account = Account.query.filter_by(account_number=acc_num).first_or_404()
    # ดึงประวัติธุรกรรมเรียงจากล่าสุด
    transactions = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.timestamp.desc()).all()
    return render_template('account.html', account=account, transactions=transactions)

@app.route('/transaction/<string:acc_num>/<string:action>', methods=['POST'])
def perform_transaction(acc_num, action):
    account = Account.query.filter_by(account_number=acc_num).first_or_404()
    amount = float(request.form.get('amount', 0))

    if amount <= 0:
        flash('กรุณาระบุจำนวนเงินที่มากกว่า 0', 'warning')
        return redirect(url_for('view_account', acc_num=acc_num))

    if action == 'deposit':
        account.balance += amount
        trans = Transaction(account_id=account.id, trans_type='ฝากเงิน', amount=amount)
        flash(f'ฝากเงินจำนวน ฿{amount:,.2f} สำเร็จ', 'success')
    elif action == 'withdraw':
        if account.balance >= amount:
            account.balance -= amount
            trans = Transaction(account_id=account.id, trans_type='ถอนเงิน', amount=amount)
            flash(f'ถอนเงินจำนวน ฿{amount:,.2f} สำเร็จ', 'success')
        else:
            flash('ยอดเงินในบัญชีไม่เพียงพอ!', 'danger')
            return redirect(url_for('view_account', acc_num=acc_num))

    db.session.add(trans)
    db.session.commit()
    return redirect(url_for('view_account', acc_num=acc_num))

@app.route('/delete/<int:id>', methods=['POST'])
def delete_account(id):
    account = Account.query.get_or_404(id)
    db.session.delete(account)
    db.session.commit()
    flash('ลบบัญชีผู้ใช้เรียบร้อยแล้ว', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)