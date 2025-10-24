from flask import Flask, render_template, request
import pyautogui
import webbrowser
import socket
import time 
import qrcode 
import os
import signal

app = Flask(__name__)

KEY_MAPPING = {
    'period': '.',
    'comma': ',',
    'semicolon': ';',
    'colon': ':',
    'space': 'space',
    'minus': '-',        # bemol
    'equal': '=',        # bequadro
    'plus': ('shift', '+')  # Sustenido no MuseScore
}



# Definindo a porta
porta = 8888

# Função para obter o endereço IP local
def obter_endereco_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_local = s.getsockname()[0]
    s.close()
    return f"{ip_local}:{porta}"  # Retorna apenas o IP e a porta, sem "http://"

# Função para gerar QR Code
def gerar_qrcode(url):
    # Gerar QR Code a partir da URL
    qr = qrcode.make(url)
    # Salva a imagem gerada em um arquivo temporário
    caminho_qrcode = "static/qrcode.png"
    qr.save(caminho_qrcode)
    return caminho_qrcode

# Rota para testar o comando shift+equal
@app.route('/test_shift_equal')
def test_shift_equal():
    try:
        pyautogui.hotkey('shift', 'equal')  # Isso deve gerar o caractere '+'
        return 'Comando shift+equal enviado com sucesso!'
    except Exception as e:
        return f'Ocorreu um erro: {str(e)}'

# Rota para enviar + diretamente via /plus
@app.route('/combo/plus')
def combo_plus():
    try:
        print("Enviando Shift+Plus para sustenido...")
        pyautogui.hotkey('shift', '+')
        return 'Sustenido (Shift++) enviado com sucesso!'
    except Exception as e:
        print(f"Erro no sustenido: {str(e)}")
        return f'Erro: {str(e)}'

@app.route('/')
def boas_vindas():
    endereco_ip = obter_endereco_ip()
    if endereco_ip:
        # Corrigido: concatenar http:// de forma correta
        url_completa = f"http://{endereco_ip}/control"
        
        # Gera o QR Code para o endereço completo
        caminho_qrcode = gerar_qrcode(url_completa)
        
        # Renderiza o HTML da pasta 'templates' passando a URL completa e o QR Code
        return render_template('index.html', ip_address=url_completa, qrcode_url=caminho_qrcode)
    else:
        return "Não foi possível obter o endereço IP."

# Serve o HTML da pasta 'templates'
@app.route('/control')
def control():
    endereco_ip = obter_endereco_ip()
    
    if endereco_ip:
        # Corrigido: concatenar http:// de forma correta
        url_completa = f"http://{endereco_ip}/control"
        
        # Gera o QR Code para o endereço completo
        caminho_qrcode = gerar_qrcode(url_completa)

        return render_template('control.html', ip_address=url_completa, qrcode_url=caminho_qrcode)
    else:
        return "Não foi possível obter o endereço IP."

@app.route('/app_encerrado')
def app_encerrado():
    return render_template('app_encerrado.html')


# Rota para enviar teclas simples (ex: /cmd/5)
@app.route('/cmd/<key>')
def cmd(key):
    pyautogui_key = KEY_MAPPING.get(key, key)
    if isinstance(pyautogui_key, tuple):
        pyautogui.hotkey(*pyautogui_key)
    else:
        pyautogui.press(pyautogui_key)
    print(f'Sent: {pyautogui_key}')
    return f'Sent: {pyautogui_key}'


# Rota para enviar combinações (ex: /combo/shift+s)
@app.route('/combo/<combo>')
def combo_route(combo):
    # Divide a combinação por '+' (ex: 'shift+s' vira ['shift', 's'])
    keys = combo.split('+')
    pyautogui.hotkey(*keys)
    return f'Sent combo: {combo}'

# Rota para testar o sustenido no MuseScore
@app.route('/test_musescore_sustenido')
def test_musescore_sustenido():
    try:
        print("Tentando enviar Shift++ para MuseScore...")  # Log no terminal
        pyautogui.hotkey('shift', '+')
        print("Comando enviado!")
        return 'Sustenido (Shift++) enviado com sucesso para MuseScore!'
    except Exception as e:
        print(f"ERRO: {str(e)}")
        return f'Erro ao enviar sustenido: {str(e)}'

# 🔥 Rota para encerrar o servidor
@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Servidor encerrado.'

def shutdown_server():
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)

if __name__ == '__main__':
    # Inicia o servidor Flask em uma thread separada
    from threading import Thread
    
    def run_flask():
        app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)  # Desabilitando o debug e o reloader

    # Cria e inicia uma thread para rodar o servidor Flask
    thread = Thread(target=run_flask)
    thread.start()

    # Aguarda um pequeno tempo para o servidor iniciar completamente
    time.sleep(2)  # Aguarda o servidor estar no ar

    # Abre o navegador automaticamente
    endereco_ip = obter_endereco_ip()
    if endereco_ip:
        webbrowser.open(f"http://{endereco_ip}")