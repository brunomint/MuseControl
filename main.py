"""MuseControl: escrever no MuseScore pelo celular (Modo Pulsação).

A página principal é /pulso (pulsacao.py). Esta parte só cuida de subir o
servidor, mostrar o endereço/QR code e desligar o app.
"""
import os
import signal
import socket
import threading
import time
import webbrowser

import qrcode
from flask import Flask, redirect, render_template

from pulsacao import bp as pulso_bp
from projetos import bp as projetos_bp
from variaveis import bp as variaveis_bp

app = Flask(__name__)
app.register_blueprint(pulso_bp)
app.register_blueprint(variaveis_bp)
app.register_blueprint(projetos_bp)

porta = 8888


def obter_endereco_ip():
    """IP da máquina na rede local + porta (sem "http://")."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # não envia nada; só descobre a interface de rede
        ip_local = s.getsockname()[0]
    finally:
        s.close()
    return f"{ip_local}:{porta}"


def gerar_qrcode(url):
    caminho_qrcode = "static/qrcode.png"
    qrcode.make(url).save(caminho_qrcode)
    return caminho_qrcode


@app.route('/')
def boas_vindas():
    url_completa = f"http://{obter_endereco_ip()}/pulso"
    caminho_qrcode = gerar_qrcode(url_completa)
    return render_template('index.html', ip_address=url_completa, qrcode_url=caminho_qrcode)


@app.route('/control')
def control():
    # a página antiga de botões foi substituída pelo Modo Pulsação
    return redirect('/pulso')


@app.route('/shutdown', methods=['POST'])
def shutdown():
    # responde primeiro e encerra logo depois
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return 'Servidor encerrado.'


if __name__ == '__main__':
    def run_flask():
        app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)

    threading.Thread(target=run_flask).start()
    time.sleep(2)  # espera o servidor subir
    webbrowser.open(f"http://{obter_endereco_ip()}")
