from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from datetime import datetime, date, timedelta
import os

# =====================
# CONFIGURAÇÃO
# =====================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "banco.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# =====================
# MODELOS
# =====================
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)

    preco_custo = db.Column(db.Float, nullable=False)
    preco_venda = db.Column(db.Float, nullable=False)

    quantidade = db.Column(db.Integer, nullable=False)
    imagem = db.Column(db.String(200))


class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship("Produto")


class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_loja = db.Column(db.String(100), default="A Menina da Loja")
    cor_primaria = db.Column(db.String(7), default="#2563eb")  # hexadecimal
    cor_sucesso = db.Column(db.String(7), default="#16a34a")
    cor_perigo = db.Column(db.String(7), default="#dc2626")


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# =====================
# FUNÇÕES AUXILIARES
# =====================
def arquivo_permitido(nome):
    return "." in nome and nome.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# =====================
# LOGIN
# =====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Usuario.query.filter_by(
            usuario=request.form["usuario"]
        ).first()

        if user and check_password_hash(user.senha, request.form["senha"]):
            login_user(user)
            return redirect(url_for("dashboard"))

        return render_template("login.html", erro="Usuário ou senha inválidos")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# =====================
# DASHBOARD
# =====================
@app.route("/dashboard")
@login_required
def dashboard():
    filtro = request.args.get("filtro")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    hoje = date.today()

    # 🔹 DATA MANUAL TEM PRIORIDADE
    if data_inicio and data_fim:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        fim = datetime.strptime(data_fim, "%Y-%m-%d")
        fim = datetime.combine(fim.date(), datetime.max.time())
        filtro = None  # 🔥 IMPORTANTE: desmarca botões

    elif filtro == "hoje":
        inicio = datetime.combine(hoje, datetime.min.time())
        fim = datetime.combine(hoje, datetime.max.time())

    elif filtro == "7":
        inicio = datetime.combine(hoje - timedelta(days=6), datetime.min.time())
        fim = datetime.combine(hoje, datetime.max.time())

    else:
        filtro = "30"
        inicio = datetime.combine(hoje - timedelta(days=29), datetime.min.time())
        fim = datetime.combine(hoje, datetime.max.time())


    # =====================
    # ESTOQUE
    # =====================
    total_produtos = Produto.query.count()

    total_estoque = db.session.query(
        func.coalesce(func.sum(Produto.quantidade), 0)
    ).scalar()

    valor_estoque = db.session.query(
        func.coalesce(func.sum(Produto.preco_custo * Produto.quantidade), 0)
    ).scalar()

    # =====================
    # VENDAS / LUCRO
    # =====================
    total_vendas = db.session.query(
        func.coalesce(func.sum(Venda.quantidade * Venda.preco_unitario), 0)
    ).filter(
        Venda.data.between(inicio, fim)
    ).scalar()

    vendas_dia = db.session.query(
        func.coalesce(func.sum(Venda.quantidade * Venda.preco_unitario), 0)
    ).filter(
        func.date(Venda.data) == hoje
    ).scalar()

    lucro_total = db.session.query(
        func.coalesce(
            func.sum((Venda.preco_unitario - Produto.preco_custo) * Venda.quantidade),
            0
        )
    ).join(Produto).filter(
        Venda.data.between(inicio, fim)
    ).scalar()

    # =====================
    # GRÁFICO
    # =====================
    vendas_db = db.session.query(
        func.strftime("%Y-%m-%d", Venda.data),
        func.sum(Venda.quantidade * Venda.preco_unitario)
    ).filter(
        Venda.data.between(inicio, fim)
    ).group_by(
        func.strftime("%Y-%m-%d", Venda.data)
    ).all()

    mapa = dict(vendas_db)

    dias, valores = [], []
    d = inicio.date()

    while d <= fim.date():
        chave = d.strftime("%Y-%m-%d")
        dias.append(chave)
        valores.append(float(mapa.get(chave, 0)))
        d += timedelta(days=1)

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        total_estoque=total_estoque,
        valor_estoque=valor_estoque,
        vendas_dia=vendas_dia,
        total_vendas=total_vendas,
        lucro_total=lucro_total,
        dias=dias,
        valores=valores,
        filtro=filtro
    )


# =====================
# PRODUTOS
# =====================
@app.route("/produtos")
@login_required
def listar_produtos():
    return render_template(
        "produtos.html",
        produtos=Produto.query.all()
    )


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def novo_produto():
    if request.method == "POST":
        try:
            preco_custo = float(request.form["preco_custo"])
            preco_venda = float(request.form["preco_venda"])
            quantidade = int(request.form["quantidade"])
        except ValueError:
            return render_template("novo_produto.html", erro="Valores inválidos")

        if preco_venda <= preco_custo:
            return render_template(
                "novo_produto.html",
                erro="Preço de venda deve ser maior que o custo"
            )

        produto = Produto(
            codigo=request.form["codigo"],
            nome=request.form["nome"],
            preco_custo=preco_custo,
            preco_venda=preco_venda,
            quantidade=quantidade
        )

        imagem = request.files.get("imagem")
        if imagem and imagem.filename and arquivo_permitido(imagem.filename):
            nome_arquivo = secure_filename(imagem.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_arquivo)
            imagem.save(caminho)
            produto.imagem = nome_arquivo

        db.session.add(produto)
        db.session.commit()
        return redirect(url_for("listar_produtos"))

    return render_template("novo_produto.html")

# =====================
# VENDAS
# =====================
@app.route("/vendas")
@login_required
def listar_vendas():
    vendas = Venda.query.order_by(Venda.data.desc()).all()
    total = sum(v.quantidade * v.preco_unitario for v in vendas)

    return render_template(
        "vendas.html",
        vendas=vendas,
        total_vendido=total
    )


@app.route("/vendas/nova", methods=["GET", "POST"])
@login_required
def nova_venda():
    produtos = Produto.query.order_by(Produto.nome).all()
    hoje = date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        produto = Produto.query.get_or_404(int(request.form["produto_id"]))
        quantidade = int(request.form["quantidade"])
        preco = float(request.form["preco_venda"])
        data_venda = datetime.strptime(
            request.form["data_venda"], "%Y-%m-%d"
        )

        if quantidade <= 0 or quantidade > produto.quantidade:
            erro = "Quantidade inválida"
        elif preco <= produto.preco_custo:
            erro = "Preço abaixo do custo"
        else:
            produto.quantidade -= quantidade

            venda = Venda(
                produto_id=produto.id,
                quantidade=quantidade,
                preco_unitario=preco,
                data=data_venda
            )

            db.session.add(venda)
            db.session.commit()
            return redirect(url_for("listar_vendas"))

        return render_template(
            "vendas_nova.html",
            produtos=produtos,
            erro=erro,
            hoje=hoje
        )

    return render_template(
        "vendas_nova.html",
        produtos=produtos,
        hoje=hoje
    )


@app.route("/vendas/excluir/<int:venda_id>")
@login_required
def excluir_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    produto = Produto.query.get(venda.produto_id)

    produto.quantidade += venda.quantidade

    db.session.delete(venda)
    db.session.commit()

    return redirect(url_for("listar_vendas"))


@app.route("/vendas/editar/<int:venda_id>", methods=["GET", "POST"])
@login_required
def editar_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    produto = Produto.query.get(venda.produto_id)

    if request.method == "POST":
        nova_qtd = int(request.form["quantidade"])
        novo_preco = float(request.form["preco_venda"])
        nova_data = datetime.strptime(
            request.form["data_venda"], "%Y-%m-%d"
        ).date()

        diferenca = nova_qtd - venda.quantidade

        if diferenca > produto.quantidade:
            return render_template(
                "venda_editar.html",
                venda=venda,
                erro="Estoque insuficiente"
            )

        produto.quantidade -= diferenca
        venda.quantidade = nova_qtd
        venda.preco_unitario = novo_preco
        venda.data = datetime.combine(nova_data, datetime.min.time())

        db.session.commit()
        return redirect(url_for("listar_vendas"))

    return render_template("venda_editar.html", venda=venda)



@app.route("/configuracoes", methods=["GET", "POST"])
@login_required
def configuracoes():
    config = Configuracao.query.first()  # pega a única configuração

    if request.method == "POST":
        config.nome_loja = request.form.get("nome_loja", config.nome_loja)
        config.cor_primaria = request.form.get("cor_primaria", config.cor_primaria)
        config.cor_sucesso = request.form.get("cor_sucesso", config.cor_sucesso)
        config.cor_perigo = request.form.get("cor_perigo", config.cor_perigo)

        db.session.commit()
        sucesso = "Configurações salvas com sucesso!"
        return render_template("configuracoes.html", config=config, sucesso=sucesso)

    return render_template("configuracoes.html", config=config)


# =====================
# USUÁRIOS
# =====================
@app.route("/configuracoes/usuarios")
@login_required
def configuracoes_usuarios():
    usuarios = Usuario.query.all()
    return render_template("configuracoes_usuarios.html", usuarios=usuarios)


@app.route("/configuracoes/usuarios/novo", methods=["POST"])
@login_required
def novo_usuario():
    usuario = request.form.get("usuario")
    senha = request.form.get("senha")
    senha_confirm = request.form.get("senha_confirm")

    # Validações
    if not usuario or not senha:
        return "Preencha todos os campos", 400

    if senha != senha_confirm:
        return "As senhas não conferem", 400

    if Usuario.query.filter_by(usuario=usuario).first():
        return "Usuário já existe", 400

    db.session.add(
        Usuario(
            usuario=usuario,
            senha=generate_password_hash(senha)
        )
    )
    db.session.commit()
    return redirect(url_for("configuracoes_usuarios"))


@app.route("/configuracoes/usuarios/editar/<int:user_id>", methods=["GET", "POST"])
@login_required
def editar_usuario(user_id):
    usuario = Usuario.query.get_or_404(user_id)

    if request.method == "POST":
        novo_nome = request.form.get("usuario")
        nova_senha = request.form.get("senha")
        nova_senha_confirm = request.form.get("senha_confirm")

        if not novo_nome:
            return "Nome de usuário é obrigatório", 400

        if nova_senha and nova_senha != nova_senha_confirm:
            return "Senhas não conferem", 400

        # Atualiza
        usuario.usuario = novo_nome
        if nova_senha:
            usuario.senha = generate_password_hash(nova_senha)

        db.session.commit()
        return redirect(url_for("configuracoes_usuarios"))

    return render_template("editar_usuario.html", usuario=usuario)


@app.route("/configuracoes/usuarios/excluir/<int:user_id>")
@login_required
def excluir_usuario(user_id):
    usuario = Usuario.query.get_or_404(user_id)

    # Não permite excluir o usuário logado
    if usuario.id == current_user.id:
        return "Não é possível excluir o usuário logado", 400

    db.session.delete(usuario)
    db.session.commit()
    return redirect(url_for("configuracoes_usuarios"))



@app.context_processor
def inject_config():
    config = Configuracao.query.first()
    return dict(config=config)



# =====================
# INIT
# =====================
with app.app_context():
    os.makedirs("database", exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    db.create_all()

    if not Usuario.query.filter_by(usuario="admin").first():
        db.session.add(
            Usuario(
                usuario="admin",
                senha=generate_password_hash("123")
            )
        )
        db.session.commit()

    if not Configuracao.query.first():
        db.session.add(Configuracao())
        db.session.commit()    

if __name__ == "__main__":
    app.run(debug=True)
