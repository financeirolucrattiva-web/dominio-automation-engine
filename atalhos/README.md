# Atalhos do projeto

Os instaladores principais e `Atualizar.bat` ficam na raiz do projeto.
Aqui estão os atalhos de uso e manutenção. Abra por duplo clique;
eles usam os mesmos scripts, opções, dependências e dados locais.
Mantenha estas pastas dentro do projeto, pois os atalhos precisam de
`app/`, `scripts/` e dos arquivos da raiz.

## Servidor

| Atalho | Função |
| --- | --- |
| [Abrir Servidor.bat](servidor/Abrir%20Servidor.bat) | Consulta local, sem aceitar execuções |
| [Testar Interface Servidor.bat](servidor/Testar%20Interface%20Servidor.bat) | Simulação no próprio PC |
| [Executar Dominio no Servidor.bat](servidor/Executar%20Dominio%20no%20Servidor.bat) | Execução real no próprio PC |
| [Configurar Acesso Rede.bat](servidor/Configurar%20Acesso%20Rede.bat) | Preparar HTTPS/endereço e pacote público do cliente |
| [Configurar Destino Livros.bat](servidor/Configurar%20Destino%20Livros.bat) | Definir a raiz local das pastas de empresas para conferir/testar os destinos no painel |
| [Liberar Acesso Rede.bat](servidor/Liberar%20Acesso%20Rede.bat) | Criar regra de firewall; executar como administrador |
| [Testar Interface na Rede.bat](servidor/Testar%20Interface%20na%20Rede.bat) | Simulação para dois PCs |
| [Executar Dominio na Rede.bat](servidor/Executar%20Dominio%20na%20Rede.bat) | Execução real para dois PCs |

O [guia de servidor e interface](../docs/SERVIDOR-E-INTERFACE.md)
explica a configuração e a conexão. Os modos de execução real mantêm
os requisitos de sessão Windows visível, calibração e apuração fechada.

## Interface local

| Atalho | Função |
| --- | --- |
| [Abrir Interface Gráfica.bat](interface/Abrir%20Interface%20Gr%C3%A1fica.bat) | GUI completa, incluindo gravação/revisão de rotinas |
| [Abrir Interface Gráfica (Operador).bat](interface/Abrir%20Interface%20Gr%C3%A1fica%20%28Operador%29.bat) | GUI no modo operador existente |

Estes atalhos abrem a GUI do motor neste PC. No PC cliente conectado,
use o instalador `Instalar Interface.bat` do pacote fornecido pelo servidor.

## OCR opcional

| Atalho | Função |
| --- | --- |
| [Instalar Python OCR.bat](ocr/Instalar%20Python%20OCR.bat) | Preparar Python compatível e OCR Paddle |
| [Instalar OCR Paddle.bat](ocr/Instalar%20OCR%20Paddle.bat) | Preparar OCR Paddle com Python compatível já instalado |
| [Avaliar OCR Paddle.bat](ocr/Avaliar%20OCR%20Paddle.bat) | Comparar motores em uma imagem local |
| [Avaliar OCR Tela.bat](ocr/Avaliar%20OCR%20Tela.bat) | Comparar motores na captura atual selecionada |

Paddle continua opcional; o motor mantém o Tesseract atual.

## Ferramentas

| Atalho | Função |
| --- | --- |
| [Calibrar Tela Principal.bat](ferramentas/Calibrar%20Tela%20Principal.bat) | Medir referência da tela azul do Domínio |
| [Diagnosticar PDF.bat](ferramentas/Diagnosticar%20PDF.bat) | Diagnosticar PDF exportado |
| [Listar Funcoes.bat](ferramentas/Listar%20Funcoes.bat) | Consultar o catálogo descritivo |
| [Abrir Motor SPED.bat](ferramentas/Abrir%20Motor%20SPED.bat) | Abrir o menu de texto existente |
