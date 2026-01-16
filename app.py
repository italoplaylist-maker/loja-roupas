from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)

app.config['SECRET_KEY'] = 'chave-secreta'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "banco.db")

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =====================
# MODELO DE USUÁRIO
# =====================
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    imagem = db.Column(db.String(200))

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, default=db.func.now())

    produto = db.relationship("Produto")

    

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# =====================
# ROTAS
# =====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        user = Usuario.query.filter_by(usuario=usuario).first()

        if user and check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", erro="Usuário ou senha inválidos")

    return render_template("login.html")

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        if Usuario.query.filter_by(usuario=usuario).first():
            return render_template("registrar.html", erro="Usuário já existe")

        novo = Usuario(
            usuario=usuario,
            senha=generate_password_hash(senha)
        )
        db.session.add(novo)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("registrar.html")


@app.route("/dashboard")
@login_required
def dashboard():
    total_produtos = Produto.query.count()

    total_estoque = db.session.query(
        db.func.sum(Produto.quantidade)
    ).scalar() or 0

    valor_total = db.session.query(
        db.func.sum(Produto.preco * Produto.quantidade)
    ).scalar() or 0

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        total_estoque=total_estoque,
        valor_total=valor_total
    )





@app.route("/relatorios")
@login_required
def relatorios():
    return "<h1>Relatórios (em construção)</h1>"

@app.route("/usuarios")
@login_required
def usuarios():
    return "<h1>Usuários (em construção)</h1>"


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def novo_produto():
    if request.method == "POST":
        nome = request.form["nome"]
        preco = float(request.form["preco"])
        quantidade = int(request.form["quantidade"])

        imagem = request.files["imagem"]
        nome_imagem = None

        if imagem:
            nome_imagem = secure_filename(imagem.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_imagem)
            imagem.save(caminho)

        produto = Produto(
            nome=nome,
            preco=preco,
            quantidade=quantidade,
            imagem=nome_imagem
        )

        db.session.add(produto)
        db.session.commit()
        return redirect(url_for("listar_produtos"))

    return render_template("novo_produto.html")



@app.route("/produtos")
@login_required
def listar_produtos():
    produtos = Produto.query.all()
    return render_template("produtos.html", produtos=produtos)

@app.route("/produtos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)

    if request.method == "POST":
        produto.nome = request.form["nome"]
        produto.preco = float(request.form["preco"])
        produto.quantidade = int(request.form["quantidade"])

        db.session.commit()
        return redirect(url_for("listar_produtos"))

    return render_template("editar_produto.html", produto=produto)


@app.route("/produtos/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)

    db.session.delete(produto)
    db.session.commit()

    return redirect(url_for("listar_produtos"))


@app.route("/venda", methods=["GET", "POST"])
@login_required
def venda():
    produtos = Produto.query.all()

    if request.method == "POST":
        produto_id = int(request.form["produto"])
        quantidade = int(request.form["quantidade"])

        produto = Produto.query.get(produto_id)

        if quantidade > produto.estoque:
            return render_template(
                "venda.html",
                produtos=produtos,
                erro="Estoque insuficiente"
            )

        produto.estoque -= quantidade

        venda = Venda(
            produto_id=produto_id,
            quantidade=quantidade
        )

        db.session.add(venda)
        db.session.commit()

        return redirect(url_for("listar_produtos"))

    return render_template("venda.html", produtos=produtos)



# =====================
# CRIAR USUÁRIO PADRÃO
# =====================


with app.app_context():
    if not os.path.exists("database"):
        os.makedirs("database")

    db.create_all()

    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(
            usuario="admin",
            senha=generate_password_hash("123")
        )
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)


