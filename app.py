import os
import datetime  # 日時を扱うためにインポート
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for, flash

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# ↓ この行を追記。セッション情報を暗号化するための秘密鍵です。
app.config['SECRET_KEY'] = 'my_secret_key_12345' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'boards.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class UpdateHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False) # どのボードの履歴かを示すID
    previous_location = db.Column(db.String(100)) # 変更前の場所
    new_location = db.Column(db.String(100), nullable=False) # 変更後の場所
    updated_by = db.Column(db.String(50), nullable=False) # 更新者
    updated_at = db.Column(db.String(50), nullable=False) # 更新日時

    def __repr__(self):
        return f'<History for board id {self.board_id}>'

# --- Boardクラスに「親子関係」の定義を追加 ---
class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    location = db.Column(db.String(100), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # このボードに関連付けられた全ての履歴を histories という名前で参照できるようにする
    histories = db.relationship('UpdateHistory', backref='board', lazy=True)

    def __repr__(self):
        return f'<Board {self.name}>'
with app.app_context():
    db.create_all()
@app.route('/')
def index():
    # URLクエリからソートの指定を取得
    sort_by = request.args.get('sort_by', 'id') # デフォルトはID順
    order = request.args.get('order', 'asc')   # デフォルトは昇順

    # クエリビルダを初期化
    query = Board.query

    # ソートの指定に応じて、クエリに並べ替え条件を追加
    if sort_by == 'name':
        if order == 'desc':
            query = query.order_by(Board.name.desc())
        else:
            query = query.order_by(Board.name.asc())
    else:
        # デフォルト（または不正な指定）の場合はID順
        query = query.order_by(Board.id.asc())

    # 最終的にクエリを実行して、すべてのデータを取得
    all_boards = query.all()
    
    return render_template('index.html', boards=all_boards)
# --- ここから下を追記 ---

@app.route('/add', methods=['GET', 'POST'])
def add_board():
    if request.method == 'POST':
        name = request.form['name']
        notes = request.form['notes']
        location_select = request.form['location_select']

        # 重複チェックはそのまま
        existing_board = Board.query.filter_by(name=name).first()
        if existing_board:
            flash(f'ボード名「{name}」は既に使用されています。', 'error')
            return redirect(url_for('add_board'))

        # 場所に応じてlocationとuserを決定
        if location_select == 'その他':
            location = request.form.get('location_other', 'その他') # 空なら'その他'
            user = request.form['owner']
        else:
            location = location_select
            user = request.form['updater']

        updated_at = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')

        new_board = Board(
            name=name,
            location=location,
            user=user,
            notes=notes, # notesを追加
            updated_at=updated_at
        )

        db.session.add(new_board)
        db.session.commit()

        flash(f'ボード「{name}」が正常に追加されました。', 'success')
        return redirect(url_for('index'))
    else:
        return render_template('add.html')
# --- 追記はここまで ---
# --- ここから下を追記 ---

@app.route('/update/<int:board_id>', methods=['GET', 'POST'])
def update_board(board_id):
    board_to_update = Board.query.get_or_404(board_id)
    previous_location = board_to_update.location # 変更前の場所を保存

    if request.method == 'POST':
        # --- ↓↓この部分が抜けていました！↓↓ ---
        new_name = request.form['name']
        notes = request.form['notes']
        location_select = request.form['location_select']
        # --- ↑↑ここまでが抜けていた部分です↑↑ ---

        # ボード名の重複チェック（自分自身以外のボードでチェック）
        existing_board = Board.query.filter(Board.name == new_name, Board.id != board_id).first()
        if existing_board:
            flash(f'ボード名「{new_name}」は既に使用されています。', 'error')
            return redirect(url_for('update_board', board_id=board_id))

        # 変更後の場所を決定
        if location_select == 'その他':
            new_location = request.form.get('location_other', 'その他')
            new_user = request.form['owner']
        else:
            new_location = location_select
            new_user = request.form['updater']

        # 履歴記録処理
        if previous_location != new_location or board_to_update.user != new_user:
            history_entry = UpdateHistory(
                board_id=board_id,
                previous_location=previous_location,
                new_location=new_location,
                updated_by=new_user,
                updated_at=datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            )
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
    else:
        return render_template('update.html', board=board_to_update)

@app.route('/delete/<int:board_id>', methods=['POST'])
def delete_board(board_id):
    # 削除対象のボード情報をデータベースから取得
    board_to_delete = Board.query.get_or_404(board_id)

    # データベースから対象のデータを削除
    db.session.delete(board_to_delete)
    # データベースの変更を保存
    db.session.commit()

    # トップページにリダイレクト
    return redirect(url_for('index'))
# --- 追記はここまで ---


@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    # --- ↓↓この部分が抜けていました！↓↓ ---
    board_ids = request.form.getlist('board_ids')
    updater = request.form['updater']
    location_select = request.form['location_select']
    # --- ↑↑ここまでが抜けていた部分です↑↑ ---

    if not board_ids:
        flash('更新するボードが選択されていません。', 'error')
        return redirect(url_for('index'))

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
                history_entry = UpdateHistory(
                    board_id=board.id,
                    previous_location=previous_location,
                    new_location=new_location,
                    updated_by=updater,
                    updated_at=datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
                )
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
    # histories = board.histories  <-- これでも取得できますが、順序を保証するために下の方法がおすすめです
    histories = UpdateHistory.query.filter_by(board_id=board.id).order_by(UpdateHistory.id.desc()).all()

    # history.htmlをレンダリングし、ボード情報と履歴情報を渡す
    return render_template('history.html', board=board, histories=histories)

# --- 追記はここまで ---
# --- 追記はここまで ---
# if __name__ == '__main__': ... の部分は変更なし
if __name__ == '__main__':

    app.run(debug=True)
