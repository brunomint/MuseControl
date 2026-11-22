"""MuseControl: escrever no MuseScore pelo celular (Modo Pulsação).

A página principal é /pulso (pulsacao.py). Esta parte só cuida de subir o
servidor, mostrar o endereço/QR code e desligar o app.

Variáveis de ambiente (opcionais):
  MUSECONTROL_PORTA=8888       porta do servidor
  MUSECONTROL_NAO_ABRIR=1      não abre o navegador ao ligar (ex.: ligar com o PC)
  MUSECONTROL_DADOS=/pasta     onde fica o banco (ver caminhos.py)
"""
import io
import os
import signal
import socket
import threading
import time
import webbrowser

import qrcode
from flask import Flask, redirect, render_template, send_file

import caminhos
from pulsacao import bp as pulso_bp
from projetos import bp as projetos_bp
from variaveis import bp as variaveis_bp

app = Flask(__name__,
            template_folder=os.path.join(caminhos.pasta_recursos(), "templates"),
            static_folder=os.path.join(caminhos.pasta_recursos(), "static"))
app.register_blueprint(pulso_bp)
app.register_blueprint(variaveis_bp)
app.register_blueprint(projetos_bp)

porta = int(os.environ.get("MUSECONTROL_PORTA", "8888"))


def obter_endereco_ip():
    """IP da máquina na rede local + porta (sem "http://")."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # não envia nada; só descobre a interface de rede
        ip_local = s.getsockname()[0]
    except OSError:
        ip_local = "127.0.0.1"  # sem rede
    finally:
        s.close()
    return f"{ip_local}:{porta}"


def endereco_pulso():
    return f"http://{obter_endereco_ip()}/pulso"


@app.route('/')
def boas_vindas():
    return render_template('index.html', ip_address=endereco_pulso(), qrcode_url='/qrcode.png')


@app.route('/qrcode.png')
def qrcode_png():
    # gerado na hora, em memória (a pasta do programa pode ser só de leitura)
    imagem = io.BytesIO()
    qrcode.make(endereco_pulso()).save(imagem, format="PNG")
    imagem.seek(0)
    return send_file(imagem, mimetype="image/png", max_age=0)


@app.route('/control')
def control():
    # a página antiga de botões foi substituída pelo Modo Pulsação
    return redirect('/pulso')


@app.route('/shutdown', methods=['POST'])
def shutdown():
    # responde primeiro e encerra logo depois
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return 'Servidor encerrado.'


def ja_esta_rodando():
    """Já existe um MuseControl nesta porta? (aí só abrimos a página)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


if __name__ == '__main__':
    abrir = not os.environ.get("MUSECONTROL_NAO_ABRIR")
    if ja_esta_rodando():
        print(f"O MuseControl já está ligado em http://{obter_endereco_ip()}")
        if abrir:
            webbrowser.open(f"http://127.0.0.1:{porta}")
        raise SystemExit(0)

    def run_flask():
        app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)

    threading.Thread(target=run_flask).start()
    time.sleep(2)  # espera o servidor subir
    print()
    print("  MuseControl ligado!")
    print(f"  No celular (mesmo Wi-Fi), abra: {endereco_pulso()}")
    print(f"  Dados salvos em: {caminhos.pasta_dados()}")
    print("  Para desligar: feche esta janela ou use o botão Desligar na página.")
    print()
    if abrir:
        webbrowser.open(f"http://{obter_endereco_ip()}")
