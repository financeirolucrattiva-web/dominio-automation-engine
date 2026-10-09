# Resumo por Acumulador — implementação para teste individual

Fluxo mapeado nos prints/instruções de 09/10/2026. Integrado no motor e
painel; **ainda não executado nem homologado no Domínio real nesta sessão**.
Integração técnica não significa aprovação fiscal.

## Fluxo observado

1. **Relatórios → Acompanhamentos → Resumo por Acumulador**.
2. Formulário com **Data inicial**, **Data final**, **Destacar linhas**,
   **OK** e **Fechar**. Preencher as duas datas completas e clicar OK.
   A opção Destacar linhas permanece como o operador deixou.
3. Aguardar a prévia **RESUMO POR ACUMULADOR**, com CNPJ e Período.
4. Ícone PDF → **Salvar em PDF**, com **File name**, **Save** e extensão PDF.
   É diálogo de arquivo; difere de Procurar Pasta dos livros conjuntos.
5. Salvar via Client C na pasta saida/ do projeto, como nos prints,
   conferir o PDF e fechar até reconhecer o painel azul.

O formulário mostra setembro e a prévia agosto; podem ser capturas de
emissões diferentes, não um log único. O gerador compara datas dos campos,
da prévia e do PDF antes de declarar sucesso.

## Implementação e limites

app.dominio.gerar_resumo_acumulador() usa as primitivas existentes e
registra oito etapas. As posições das datas são medidas nas caixas OCR
da captura atual, ao lado dos rótulos, sem offsets copiados dos livros.
Tenta Tesseract em duas escalas e OCR do Windows quando disponível.
Ambiguidade ou campo não confirmado interrompe antes do OK.

Ícone PDF pelo template existente, sem fallback de coordenada fixa.
Salvar em PDF e File name precisam ser reconhecidos antes de Alt+n,
atalho do diálogo Windows em inglês para focar o nome. O nome temporário
exclusivo precisa ser lido após digitar, antes de salvar. Esse foco/OCR
ainda precisa ser confirmado no ambiente real. As imagens inline não
foram medidas nesta sessão; nenhum offset novo foi calibrado a partir delas.

Confere código novamente na prévia, título/período/CNPJ e PDF novo estável,
legível e da mesma empresa. Isso não verifica os valores tributários:
o supervisor precisa comparar o relatório de referência. Arquivo antigo
não comprova geração; colisões usam sufixo. Documento inválido permanece
temporário local; conclusão exige retorno calibrado ao painel azul.

Nome: acumulador_empresa_exemplo_AAAA-MM.pdf, usando o cadastro.
Destino desta etapa: saida/, com download no painel. O destino dos
livros por empresa continua exclusivo de Entradas/Saídas; o Resumo não
é colocado automaticamente dentro de LIVROS_FISCAIS.

Migração substitui a cópia pendente por resumo_acumulador nos regimes,
preserva ordem, arquiva passos anteriores e evita duplicação. Não restaura
rotinas removidas. ICMS continua pendente e bloqueia o lote completo;
primeiro testar o Resumo individualmente.

## Correção da abertura após a primeira tentativa

O operador informou falha na etapa Abrir Resumo por Acumulador. A revisão
encontrou a busca de submenu limitada aos 300 pixels superiores, recorte
legado das outras rotinas. O item do Resumo fica mais abaixo no menu longo
de Acompanhamentos. A busca desse submenu agora usa a captura completa,
mantendo OCR e espera por estado. Não introduz coordenada fixa ou clique
em item vizinho quando o texto não aparece.

O console distingue Relatórios ausente, Acompanhamentos ausente, item
Resumo ausente e formulário não confirmado. As capturas de diagnóstico
continuam locais em capturas/. Um teste com OCR real em menu sintético
confirma que o alvo abaixo de 300 pixels é encontrado. Ainda é necessário
repetir no Windows para confirmar a causa da falha relatada.

Os campos da interface permitem digitar ou usar o calendário. O limite
de período só é reaplicado quando muda; atualizações do servidor não
reiniciam a edição de um ano incompleto no navegador.

## Como testar

1. Atualizar, reiniciar servidor e atualizar a página do painel.
2. Conferir empresa cadastrada de Lucro Presumido, código, competência
   passada apurada e calibração do painel azul.
3. **Nova execução → Resumo por Acumulador**: informar código e duas datas,
   confirmar apuração fechada e executar. Manter Domínio em foco no executor;
   usar o painel por outro dispositivo quando necessário.
4. Alternativa: parar o servidor e abrir
   **atalhos/ferramentas/Testar Resumo por Acumulador.bat**. Informar código
   cadastrado, competência AAAA-MM e apuração fechada. Há cinco segundos
   para colocar Domínio em foco; as travas ainda conferem tela/empresa.
   Usa o mesmo worker, lock e banco real, sem concorrência.
5. Não tocar no mouse/teclado durante a emissão. Conferir nome/pasta,
   empresa, período, valores e retorno. Guardar o log local e o resultado;
   uma falha precisa do log e, se necessário, captura local da etapa.

CLI opcional: python scripts\explorar_resumo_acumulador.py --empresa CODIGO --competencia AAAA-MM --apuracao-confirmada.
Nenhum código ou caminho pessoal foi deduzido/fixado a partir do print.
