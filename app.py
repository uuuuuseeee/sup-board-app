import os
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# JSTタイムゾーンの定義 (UTC+9)
JST = timezone(timedelta(hours=+9), 'JST')

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_development')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'boards.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "このページにアクセスするにはログインが必要です。"
login_manager.login_message_category = "error"

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class UpdateHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    previous_location = db.Column(db.String(100))
    new_location = db.Column(db.String(100), nullable=False)
    updated_by = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)

class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    location = db.Column(db.String(100), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    histories = db.relationship('UpdateHistory', backref='board', lazy=True, cascade="all, delete-orphan")

# --- Flask-Login Helper (変更なし) ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Initialization (変更なし) ---
with app.app_context():
    db.create_all()

# --- Routes ---
# login, register, logout (変更なし)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('ユーザー名またはパスワードが正しくありません。', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('ユーザー名とパスワードの両方を入力してください。', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('そのユーザー名は既に使用されています。', 'error')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('ユーザー登録が完了しました。ログインしてください。', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# index (変更なし)
@app.route('/')
@login_required
def index():
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')
    query = Board.query
    if sort_by == 'name':
        query = query.order_by(Board.name.desc()) if order == 'desc' else query.order_by(Board.name.asc())
    else:
        query = query.order_by(Board.id.asc())
    all_boards = query.all()
    location_counts = {}
    for board in all_boards:
        location_counts[board.location] = location_counts.get(board.location, 0) + 1
    return render_template('index.html', boards=all_boards, location_counts=location_counts)

# --- ↓↓ ここからシリアル番号関連の修正 ↓↓ ---
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_board():
    if request.method == 'POST':
        name = request.form.get('name')
        # 空文字列の場合はNoneに変換する
        serial_number = request.form.get('serial_number') or None
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')
        user = current_user.username
        if not all([name, location_select]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('add_board'))
        
        if Board.query.filter_by(name=name).first():
            flash(f'ボード名「{name}」は既に使用されています。', 'error')
            return redirect(url_for('add_board'))
        # serial_numberがNoneでない場合のみ重複チェック
        if serial_number and Board.query.filter_by(serial_number=serial_number).first():
            flash(f'シリアル番号「{serial_number}」は既に使用されています。', 'error')
            return redirect(url_for('add_board'))

        location = request.form.get('location_other') if location_select == 'その他' else location_select
        updated_at = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
        new_board = Board(name=name, serial_number=serial_number, location=location, user=user, notes=notes, updated_at=updated_at)
        db.session.add(new_board)
        db.session.commit()
        flash(f'ボード「{name}」が正常に追加されました。', 'success')
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/update/<int:board_id>', methods=['GET', 'POST'])
@login_required
def update_board(board_id):
    board_to_update = Board.query.get_or_404(board_id)
    if request.method == 'POST':
        previous_location = board_to_update.location
        previous_user = board_to_update.user
        new_name = request.form.get('name')
        # 空文字列の場合はNoneに変換する
        new_serial_number = request.form.get('serial_number') or None
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')
        new_user = current_user.username
        if not all([new_name, location_select]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('update_board', board_id=board_id))
        
        if Board.query.filter(Board.name == new_name, Board.id != board_id).first():
            flash(f'ボード名「{new_name}」は既に使用されています。', 'error')
            return redirect(url_for('update_board', board_id=board_id))
        # new_serial_numberがNoneでない場合のみ重複チェック
        if new_serial_number and Board.query.filter(Board.serial_number == new_serial_number, Board.id != board_id).first():
            flash(f'シリアル番号「{new_serial_number}」は既に使用されています。', 'error')
            return redirect(url_for('update_board', board_id=board_id))

        new_location = request.form.get('location_other') if location_select == 'その他' else location_select
        current_time_jst = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
        if previous_location != new_location or previous_user != new_user:
            history_entry = UpdateHistory(board_id=board_id, previous_location=previous_location, new_location=new_location, updated_by=new_user, updated_at=current_time_jst)
            db.session.add(history_entry)

        board_to_update.name = new_name
        board_to_update.serial_number = new_serial_number
        board_to_update.notes = notes
        board_to_update.location = new_location
        board_to_update.user = new_user
        board_to_update.updated_at = current_time_jst
        db.session.commit()
        flash(f'ボード「{board_to_update.name}」が正常に更新されました。', 'success')
        return redirect(url_for('index'))
    return render_template('update.html', board=board_to_update)

# bulk_update, delete, history (変更なし)
@app.route('/delete/<int:board_id>', methods=['POST'])
@login_required
def delete_board(board_id):
    board_to_delete = Board.query.get_or_404(board_id)
    db.session.delete(board_to_delete)
    db.session.commit()
    flash(f'ボード「{board_to_delete.name}」を削除しました。', 'success')
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
@login_required
def bulk_update():
    board_ids = request.form.getlist('board_ids')
    if not board_ids:
        flash('更新するボードが選択されていません。', 'error')
        return redirect(url_for('index'))
    updater = current_user.username
    location_select = request.form.get('location_select')
    new_location = request.form.get('location_other') if location_select == 'その他' else location_select
    current_time_jst = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
    updated_count = 0
    for board_id in board_ids:
        board = Board.query.get(board_id)
        if board:
            previous_location = board.location
            previous_user = board.user
            if previous_location != new_location or previous_user != updater:
                history_entry = UpdateHistory(board_id=board.id, previous_location=previous_location, new_location=new_location, updated_by=updater, updated_at=current_time_jst)
                db.session.add(history_entry)
            board.location = new_location
            board.user = updater
            board.updated_at = current_time_jst
            updated_count += 1
    if updated_count > 0:
        db.session.commit()
        flash(f'{updated_count}件のボード情報を一括更新しました。', 'success')
    return redirect(url_for('index'))

@app.route('/history/<int:board_id>')
@login_required
def history(board_id):
    board = Board.query.get_or_404(board_id)
    histories = UpdateHistory.query.filter_by(board_id=board.id).order_by(UpdateHistory.id.desc()).all()
    return render_template('history.html', board=board, histories=histories)


if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)


