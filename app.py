import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# Renderの永続ディスクのパスを取得、なければ現在のディレクトリを使う
DATA_DIR = os.environ.get('RENDER_DATA_DIR', os.path.abspath(os.path.dirname(__file__)))
DB_PATH = os.path.join(DATA_DIR, 'boards.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key') # Renderの環境変数を使うのが望ましい
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- モデル定義 ---
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
    histories = db.relationship('UpdateHistory', backref='board', lazy=True)

    def __repr__(self):
        return f'<Board {self.name}>'

# --- データベース初期化 ---
with app.app_context():
    db.create_all()

# --- ルート定義 ---
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
    return render_template('index.html', boards=all_boards)

@app.route('/add', methods=['GET', 'POST'])
@app.route('/add', methods=['GET', 'POST'])
def add_board():
    if request.method == 'POST':
        name = request.form.get('name')
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')

        # フォームから送られてきたキーでユーザーを決定
        user = request.form.get('owner') or request.form.get('updater')

        # 必須項目のチェック
        if not all([name, location_select, user]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('add_board'))

        # 重複チェック
        existing_board = Board.query.filter_by(name=name).first()
        if existing_board:
            flash(f'ボード名「{name}」は既に使用されています。', 'error')
            return redirect(url_for('add_board'))

        # 場所を決定
        location = request.form.get('location_other') if location_select == 'その他' else location_select

        updated_at = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
        new_board = Board(name=name, location=location, user=user, notes=notes, updated_at=updated_at)

        db.session.add(new_board)
        db.session.commit()

        flash(f'ボード「{name}」が正常に追加されました。', 'success')
        return redirect(url_for('index'))
    return render_template('add.html')
@app.route('/update/<int:board_id>', methods=['GET', 'POST'])
@app.route('/update/<int:board_id>', methods=['GET', 'POST'])
def update_board(board_id):
    board_to_update = Board.query.get_or_404(board_id)
    if request.method == 'POST':
        previous_location = board_to_update.location # 変更前の場所を保存

        new_name = request.form.get('name')
        notes = request.form.get('notes')
        location_select = request.form.get('location_select')
        new_user = request.form.get('owner') or request.form.get('updater')

        if not all([new_name, location_select, new_user]):
            flash('必須項目が入力されていません。', 'error')
            return redirect(url_for('update_board', board_id=board_id))

        # ... (以降の処理は、前回の完成版コードから流用して貼り付けます) ...
        # ボード名の重複チェック（自分自身以外のボードでチェック）
        existing_board = Board.query.filter(Board.name == new_name, Board.id != board_id).first()
        if existing_board:
            flash(f'ボード名「{new_name}」は既に使用されています。', 'error')
            return redirect(url_for('update_board', board_id=board_id))

        # 変更後の場所を決定
        new_location = request.form.get('location_other') if location_select == 'その他' else location_select

        # 履歴記録処理
        if previous_location != new_location or board_to_update.user != new_user:
            history_entry = UpdateHistory(board_id=board_id, previous_location=previous_location, new_location=new_location, updated_by=new_user, updated_at=datetime.datetime.now().strftime('%Y/%m/%d %H:%M'))
            db.session.add(history_entry)

        # ボード情報を更新
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
    # 履歴も一緒に削除する場合（任意）
    # UpdateHistory.query.filter_by(board_id=board_id).delete()
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
    updater = request.form['updater']
    location_select = request.form['location_select']
    if location_select == 'その他':
        new_location = request.form.get('location_other', 'その他')
    else:
        new_location = location_select
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
    # 対象のボード情報を取得
    board = Board.query.get_or_404(board_id)
    # そのボードに関連する履歴を、新しいものから順に全て取得
    histories = UpdateHistory.query.filter_by(board_id=board.id).order_by(UpdateHistory.id.desc()).all()

    # history.htmlをレンダリングし、ボード情報と履歴情報を渡す
    return render_template('history.html', board=board, histories=histories)

if __name__ == '__main__':
    app.run(debug=True)


