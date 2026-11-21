# 🎹 MuseControl

<div align="center">

![MuseControl](https://img.shields.io/badge/MuseControl-v1.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.7+-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0+-red?style=for-the-badge&logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**Controle remoto moderno para MuseScore via interface web**

*Transforme seu smartphone em um controle remoto profissional para o MuseScore*

</div>

## ✨ Características

- 🥁 **Escreva marcando o pulso**: o ritmo sai da contagem de notas em cada pulso,
  sem clicar em botão de duração e sem metrônomo
- 🎹 **Piano na tela** com altura exata (MIDI) — funciona no celular e no iPad
- 👀 **Prévia da partitura** antes de enviar (tercinas, ligaduras, barras)
- 🛠 **Ferramentas do MuseScore** no celular: inserção, desfazer, apagar, tocar, setas
- 📡 **QR Code automático** e acesso pela rede local

## 🛠️ Instalação

### 1️⃣ Clone o repositório
```bash
git clone https://github.com/brunofragoso/MuseControl.git
cd MuseControl
```

### 2️⃣ Crie um ambiente virtual (recomendado)
```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3️⃣ Instale as dependências
```bash
pip install -r requirements.txt
```

## ▶️ Como usar

### 1️⃣ Execute o aplicativo
```bash
python main.py
```

### 2️⃣ Acesse via navegador
- **Local**: `http://127.0.0.1:8888`
- **Rede**: `http://[seu-ip]:8888`
- **Mobile**: Escaneie o QR Code exibido

### 3️⃣ Conecte-se
1. Certifique-se de que o MuseScore está aberto
2. Conecte seu dispositivo à mesma rede Wi-Fi
3. Leia o QR Code (ele abre direto o Modo Pulsação, em `/pulso`)
4. Comece a escrever!

## 🥁 Modo Pulsação (escrever contando pulsos)

É a página principal: `http://[seu-ip]:8888/pulso` (o endereço antigo
`/control` redireciona para cá). O botão 🛠 abre as ferramentas do MuseScore
(inserção, sair, tocar, desfazer/refazer, apagar, setas e desligar o app).
O pulso é uma referência de **contagem**, não de tempo: pode tocar devagar,
parar e pensar — só a ordem dos toques importa.

- O **PULSO** é um botão dividido em faixas: mínima, semínima, colcheia,
  semicolcheia. A faixa tocada é o valor daquele pulso (a última usada fica maior).
- Toque a 1ª nota **junto** com o pulso. Notas sozinhas depois dele dividem o
  pulso em partes iguais: 2 = metades, 3 = tercina, 4 = quartos, 5 = quintina…
- PULSO com a nota **segurada** prolonga a nota; PULSO **sem** nota segurada = pausa.
- Notas juntas = acorde. Nota segurada enquanto outra muda = duas vozes
  (aparece na prévia; o envio de duas vozes ainda não existe).

As notas são tocadas num **teclado de piano** na tela, com altura exata
(◀ ▶ mudam a oitava; o celular deitado mostra ~1,5 oitava, o iPad mais).

**Envio das notas (automático):**
- **MIDI** (oitava sempre exata): no MuseScore, Editar → Preferências → Áudio e
  MIDI → Entrada MIDI = **Midi Through**. No Linux o MuseControl detecta isso
  sozinho (indicador "MIDI ✓" no topo).
- **Teclado** (sem configurar nada): as notas vão por letras e o MuseControl
  calcula os Ctrl+↑/↓ de oitava e os ↑/↓ de acidente. A 1ª nota de cada envio
  pode sair uma oitava fora. Escolha a armadura da partitura nos ajustes.

Duração, ligadura, pausa e quiálteras sempre vão por teclas (o MuseScore
precisa estar em foco na hora de enviar).

Exemplos: colcheia + 2 semicolcheias = ♪+Dó, ♪+Ré, Mi ·
colcheia pontuada + semicolcheia = ♪+Dó (segura), ♬, solta, ♬+Ré ·
tercina = ♩+Dó, Ré, Mi.

Nada vai para o MuseScore enquanto você escreve. Confira a prévia e toque em
**Enviar**: o MuseControl envia tudo (duração, nota por MIDI, `T` para
ligadura, `0` para pausa, `Ctrl+3`… para quiálteras). Antes, deixe o MuseScore
em foco, no modo de inserção (N) e com o cursor no começo do compasso.

No computador: 6/5/4/3 = pulso de mínima/semínima/colcheia/semicolcheia,
Espaço = repete o último, C D E F G A B = teclas brancas da 1ª oitava visível
(segure para prolongar), ← → = muda a oitava,
Backspace = desfazer, Enter = enviar.

Testes: `pytest tests`

## 📱 Screenshots

### Desktop
Interface principal com todos os controles musicais organizados em seções.

### Mobile
Design responsivo otimizado para smartphones com controles touch-friendly.

## 🗂️ Estrutura do Projeto

```
MuseControl/
├── main.py                 # Sobe o servidor, QR code, desligar
├── pulsacao.py             # Modo Pulsação: regras do ritmo e envio ao MuseScore
├── requirements.txt        # Dependências Python
├── tests/                  # Testes (pytest)
├── static/
│   ├── pulso.js / pulso.css  # Tela do celular (pulso, piano, prévia)
│   ├── notas_musicais/     # Ícones das figuras
│   └── qrcode.png          # QR Code gerado automaticamente
└── templates/
    ├── index.html          # Página inicial (endereço + QR code)
    └── pulso.html          # Tela principal
```

## 🔧 Dependências

- **Flask** - Framework web
- **PyAutoGUI** - Automação de teclado/mouse
- **qrcode** - Geração de QR codes
- **Pillow** - Processamento de imagens
- **python-rtmidi** - Envio das notas por MIDI

## 🌟 Recursos Avançados

### QR Code Automático
O aplicativo gera automaticamente um QR Code com o endereço de acesso, facilitando a conexão de dispositivos móveis.

### Interface Moderna
- Design glass morphism com blur effects
- Animações suaves de entrada
- Gradientes modernos
- Efeitos hover interativos

### Controles Flutuantes
- Controle direcional minimizável
- Botão de desligar no canto inferior
- Ícone de informações com QR Code

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:

1. Fazer fork do projeto
2. Criar uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abrir um Pull Request

## 📝 Licença

Este projeto está licenciado sob a **MIT License** - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👤 Autor

**Bruno Fragoso**

- 📧 Email: brunofragosoa@gmail.com
- 🐙 GitHub: [@brunomint](https://github.com/brunomint)

---

<div align="center">

**⭐ Se este projeto te ajudou, considere dar uma estrela!**

*Desenvolvido por Bruno Fragoso*

</div>
