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

- 🎮 **Interface moderna** com design glass morphism
- 📱 **Totalmente responsiva** - funciona perfeitamente no celular
- 🎵 **Controles musicais completos** - notas, ritmos, acordes
- 🎯 **Controle direcional** flutuante e compacto
- 📡 **QR Code automático** para acesso rápido
- 🌐 **Acesso via rede local** - conecte qualquer dispositivo
- ⚡ **Tempo real** - comandos instantâneos via PyAutoGUI

## 🚀 Funcionalidades

### 🎼 Controles Musicais
- **Notas**: Dó, Ré, Mi, Fá, Sol, Lá, Si
- **Alterações**: Sustenido, Bemol, Bequadro
- **Ritmos**: Semibreve até Semifusa, Pontuação, Ligaduras
- **Navegação**: Setas direcionais, Oitavas
- **Edição**: Desfazer, Refazer, Apagar

### 📱 Interface Mobile
- Design moderno com gradientes e animações
- Controles otimizados para touch
- QR Code para acesso instantâneo
- Layout responsivo para todos os tamanhos de tela

### 🔧 Recursos Técnicos
- Servidor Flask integrado
- Descoberta automática de IP
- Geração automática de QR Code
- Controles flutuantes minimizáveis

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
3. Acesse o endereço mostrado na tela
4. Comece a controlar!

## 📱 Screenshots

### Desktop
Interface principal com todos os controles musicais organizados em seções.

### Mobile
Design responsivo otimizado para smartphones com controles touch-friendly.

## 🗂️ Estrutura do Projeto

```
MuseControl/
├── main.py                 # Servidor Flask principal
├── requirements.txt        # Dependências Python
├── README.md              # Documentação
├── .gitignore             # Arquivos ignorados pelo Git
├── static/                # Recursos estáticos
│   ├── notas_musicais/    # Ícones de notas musicais
│   ├── webfonts/          # Font Awesome
│   └── qrcode.png         # QR Code gerado automaticamente
└── templates/             # Templates HTML
    ├── index.html         # Página inicial
    └── control.html       # Interface de controle
```

## 🔧 Dependências

- **Flask** - Framework web
- **PyAutoGUI** - Automação de teclado/mouse
- **qrcode** - Geração de QR codes
- **Pillow** - Processamento de imagens
- **netifaces** - Detecção de interfaces de rede

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
- 🐙 GitHub: [@brunofragoso](https://github.com/brunomint)

---

<div align="center">

**⭐ Se este projeto te ajudou, considere dar uma estrela!**

*Desenvolvido por Bruno Fragoso*

</div>
