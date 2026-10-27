# Atalhos do projeto

Os instaladores principais e `Atualizar.bat` ficam na raiz do projeto.
Aqui estão os atalhos de uso e manutenção. Abra por duplo clique;
eles usam os mesmos scripts, opções, dependências e dados locais.

O atalho `ferramentas/Revisar Formulario Livros.bat` lê caixas/datas da
aba Geral, com captura/OCR locais. Não clica nem emite. Veja o
[diagnóstico do formulário](../docs/DIAGNOSTICO-FORMULARIO-LIVROS.md).
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
| [Instalar Servidor Permanente.bat](servidor/Instalar%20Servidor%20Permanente.bat) | Servidor sobe sozinho no logon, sem janela, e reinicia se cair (1 vez, sem administrador) |
| [Ver Servidor Permanente.bat](servidor/Ver%20Servidor%20Permanente.bat) | Mostra se a tarefa do servidor permanente está instalada |
| [Remover Servidor Permanente.bat](servidor/Remover%20Servidor%20Permanente.bat) | Remove a tarefa e encerra o servidor aberto |

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
| [Testar Resumo por Acumulador.bat](ferramentas/Testar%20Resumo%20por%20Acumulador.bat) | Teste individual com código cadastrado, competência passada e as mesmas travas do painel; parar o servidor antes |
| [Executar Presumido por Empresa.bat](ferramentas/Executar%20Presumido%20por%20Empresa.bat) | Resumo, EFD e três livros na mesma empresa, etapas/progresso no terminal e cancelamento seguro; parar o servidor antes |
| [Executar Presumido em Lote.bat](ferramentas/Executar%20Presumido%20em%20Lote.bat) | Informe os códigos separados por vírgula; executa as três rotinas por empresa na mesma fila, após confirmar competência fechada em todas; parar o servidor antes |
| [Listar Funcoes.bat](ferramentas/Listar%20Funcoes.bat) | Consultar o catálogo descritivo |
| [Abrir Motor SPED.bat](ferramentas/Abrir%20Motor%20SPED.bat) | Abrir o menu de texto existente |
| [Verificar Ambiente.bat](ferramentas/Verificar%20Ambiente.bat) | Pre-voo antes do lote: Tesseract, OCR do Windows, calibracao, pasta de saida, espaco, servidor, atalho; nao opera o Dominio. O lote por atalho roda isso sozinho |
| [Limpar Pastas.bat](ferramentas/Limpar%20Pastas.bat) | Mostra e remove capturas, caches e backups antigos gerados pela automação (nunca configuração) |
| [Gerar Pacote Instalador.bat](ferramentas/Gerar%20Pacote%20Instalador.bat) | Refaz o projeto.zip do instalador a partir do origin/main |
| [Configurar Atalho de Saida.bat](ferramentas/Configurar%20Atalho%20de%20Saida.bat) | Cria a juncao `C:\saida` para a pasta de saida: o Procurar Pasta anda 1 nivel em vez de 4 (~35 s a menos por empresa nos Livros). Opcional; ensaie com `Testar Seletor de Pasta.bat` |
| [Remover Atalho de Saida.bat](ferramentas/Remover%20Atalho%20de%20Saida.bat) | Volta ao caminho completo (nao apaga nada) |
| [Ver Otimizacoes.bat](ferramentas/Ver%20Otimizacoes.bat) | Mostra quais otimizacoes de velocidade estao ligadas (LIGADA) ou no caminho classico (desligada) |
| [Modo Seguro (sem otimizacoes).bat](ferramentas/Modo%20Seguro%20%28sem%20otimizacoes%29.bat) | Volta todas as rotinas ao caminho classico (mais lento, ja testado); vale na proxima leitura, sem reiniciar o servidor |
| [Modo Rapido (otimizacoes ligadas).bat](ferramentas/Modo%20Rapido%20%28otimizacoes%20ligadas%29.bat) | Liga de novo todas as otimizacoes (padrao) |
| [Voltar Versao Estavel.bat](ferramentas/Voltar%20Versao%20Estavel.bat) | Troca para uma versao marcada `estavel-*` sem apagar nada; `Atualizar.bat` traz a mais nova de volta; parar o servidor antes |

- `ferramentas/Testar Livros Fiscais.bat`: teste individual dos três livros,
  com código/competência/apuração informados e servidor parado. Usa o mesmo
  worker e troca de empresa do painel; conferir os três PDFs antes do lote.
