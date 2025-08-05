import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- Configuration ---
# Renderの環境変数からSECRET_KEYを取得。なければデフォルト値を使用。
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_should_be_changed')

# Renderの環境変数からDATABASE_URLを取得し、SQLAlchemy用にURLを修正
# 'postgres://' で始まるURLを 'postgresql://' に置換します
database_url = os.environ.get('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    # ローカルでの開発用にSQLiteをフォールバックとして設定
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'boards.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- Models ---
class UpdateHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    previous_location = db.Column(db.String(100))
    new_location = db.Column(db.String(100), nullable=False)
    updated_by = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<History for board id {self.board_id}>'

class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    location = db.Column(db.String(100), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    histories = db.relationship('UpdateHistory', backref='board', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Board {self.name}>'


# --- Database Initialization ---
# アプリ起動時にテーブルが存在しなければ自動で作成する
with app.app_context():
    db.create_all()


# --- Routes ---
@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')
    query = Board.query
    if sort_by == 'name':
        query = query.order_by(Board.name.desc()) if order == 'desc' else query.order_by(Board.name.asc())
    else:
        query = query.order_by(Board.id.asc())
    all_boards = query.all()

    # 場所ごとの本数を集計
    location_counts = {}
    for board in all_boards:
        location_counts[board.location] = location_counts.get(board.location, 0) + 1
    
    return render_template('index.html', boards=all_boards, location_counts=location_counts)

@app.route('/add', methods=['GET', 'POST'])
def add_board():
    if request.method == 'POST':
        name = request.form.get('name')
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')
        user = request.form.get('owner') or request.form.get('updater')

        if not all([name, location_select, user]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('add_board'))

        existing_board = Board.query.filter_by(name=name).first()
        if existing_board:
            flash(f'ボード名「{name}」は既に使用されています。', 'error')
            return redirect(url_for('add_board'))

        location = request.form.get('location_other') if location_select == 'その他' else location_select
        updated_at = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
        new_board = Board(name=name, location=location, user=user, notes=notes, updated_at=updated_at)
        
        db.session.add(new_board)
        db.session.commit()
        flash(f'ボード「{name}」が正常に追加されました。', 'success')
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/update/<int:board_id>', methods=['GET', 'POST'])
def update_board(board_id):
    board_to_update = Board.query.get_or_404(board_id)
    if request.method == 'POST':
        previous_location = board_to_update.location
        previous_user = board_to_update.user
        
        new_name = request.form.get('name')
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')
        new_user = request.form.get('owner') or request.form.get('updater')

        if not all([new_name, location_select, new_user]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('update_board', board_id=board_id))

        existing_board = Board.query.filter(Board.name == new_name, Board.id != board_id).first()
        if existing_board:
            flash(f'ボード名「{new_name}」は既に使用されています。', 'error')
            return redirect(url_for('update_board', board_id=board_id))
        
        new_location = request.form.get('location_other') if location_select == 'その他' else location_select
        
        if previous_location != new_location or previous_user != new_user:
            history_entry = UpdateHistory(board_id=board_id, previous_location=previous_location, new_location=new_location, updated_by=new_user, updated_at=datetime.datetime.now().strftime('%Y/%m/%d %H:%M'))
            db.session.add(history_entry)

        board_to_update.name = new_name
        board_to_update.notes = notes
        board_to_update.location = new_location
        board_to_update.user = new_user
        board_to_update.updated_at = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
        
        db.session.commit()
        flash(f'ボード「{board_to_update.name}」が正常に更新されました。', 'success')
        return redirect(url_for('index'))
    
    return render_template('update.html', board=board_to_update)

@app.route('/delete/<int:board_id>', methods=['POST'])
def delete_board(board_id):
    board_to_delete = Board.query.get_or_404(board_id)
    db.session.delete(board_to_delete)
    db.session.commit()
    flash(f'ボード「{board_to_delete.name}」を削除しました。', 'success')
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    board_ids = request.form.getlist('board_ids')
    if not board_ids:
        flash('更新するボードが選択されていません。', 'error')
        return redirect(url_for('index'))
    
    updater = request.form.get('updater')
    location_select = request.form.get('location_select')

    if not updater:
        flash('更新者名を入力してください。', 'error')
        return redirect(url_for('index'))

    new_location = request.form.get('location_other') if location_select == 'その他' else location_select
    
    updated_count = 0
    for board_id in board_ids:
        board = Board.query.get(board_id)
        if board:
            previous_location = board.location
            if previous_location != new_location:
                history_entry = UpdateHistory(board_id=board.id, previous_location=previous_location, new_location=new_location, updated_by=updater, updated_at=datetime.datetime.now().strftime('%Y/%m/%d %H:%M'))
                db.session.add(history_entry)
            
            board.location = new_location
            board.user = updater
            board.updated_at = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            updated_count += 1
    
    if updated_count > 0:
        db.session.commit()
        flash(f'{updated_count}件のボード情報を一括更新しました。', 'success')
    
    return redirect(url_for('index'))

@app.route('/history/<int:board_id>')
def history(board_id):
    board = Board.query.get_or_404(board_id)
    histories = UpdateHistory.query.filter_by(board_id=board.id).order_by(UpdateHistory.id.desc()).all()
    return render_template('history.html', board=board, histories=histories)


if __name__ == '__main__':
    app.run(debug=True)



