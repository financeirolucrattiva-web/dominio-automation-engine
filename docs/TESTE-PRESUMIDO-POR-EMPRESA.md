# Testar o Presumido por empresa e depois em lote

Atualização: 15/10/2026. A sequência integra Resumo por Acumulador, exportação
EFD Contribuições e Livros Fiscais (Entradas, Saídas e ICMS). Código revisado
com testes automatizados e navegador; emissão real no Windows ainda pendente.

Agosto/2026 foi confirmado fechado somente na empresa do primeiro teste.
Setembro/2026 estava aberto. Confirmar fechamento para cada empresa e mês.

## Repetir primeiro somente o Resumo

Encerrar o processo antigo antes de atualizar: pull não recarrega servidor
já aberto. A nova rodada deve imprimir RESUMO_EXECUCAO com protocolo
resumo-rastro-20261015-v1. No fim, abrir o indice.html em capturas/resumo_<id>
para conferir pontos e capturas. Melhor formulário/última tela são guardados
antes da recuperação; compartilhar apenas códigos e medidas, sem imagens
fiscais integrais. Sem o protocolo, o log veio de outro código/processo.

O teste individual agora mostra etapas e progresso a cada cinco segundos,
aceita 08/2026 ou 2026-08 e usa Ctrl+C cooperativo. A última falha ocorreu
na guarda inicial de avisos, antes de medir o botão; a leitura por motor
foi isolada e o diagnóstico agora informa o tipo da exceção.

O último log já confirmou ambas datas; o bloqueio era a duplicação das
bordas de Fechar. A correção mantém as datas e deduplica as bordas medidas
antes de procurar OK. Com servidor parado, usar **ferramentas/Testar Resumo
por Acumulador.bat** e agosto/2026 da empresa confirmada, ou executar
individualmente pelo painel após reiniciar o servidor.

A geração EFD foi confirmada pelo operador, com aviso “Arquivo gerado com
sucesso.”, sem interrupção manual. A correção reforça leitura e fechamento
desse aviso. Não repetir emissão já feita apenas para mudar seu status
antigo. Conferir o arquivo e validar o fechamento na próxima emissão normal.
O histórico anterior permanece como registrado.

## Executar as três rotinas pelo CMD

Fechar o servidor e os diagnósticos anteriores. Manter Domínio aberto no
painel azul, com referência calibrada. No CMD:

```bat
cd /d C:\Users\darto\dominio-automation-engine
git switch main
git pull --ff-only origin main
python -u scripts\explorar_presumido.py --competencia 2026-08
```

O script pede o código da empresa cadastrada no Presumido e a confirmação
do fechamento de agosto nessa empresa. Após responder, voltar ao Domínio
nos cinco segundos seguintes e deixar mouse/teclado livres. O mesmo fluxo
está em **atalhos → ferramentas → Executar Presumido por Empresa.bat**;
o atalho também pede a competência e prefere o Python da .venv existente.

Este comando executa o worker fiscal. Os comandos revisar_periodo_resumo
e revisar_formulario_livros somente leem uma captura ou formulário.

A sequência respeita a ordem cadastrada no regime e exige as três rotinas
nativas, sem alterar o cadastro automaticamente:

1. **Resumo por Acumulador:** confirmar período, clicar OK, aguardar prévia,
   exportar PDF e voltar ao painel azul.
2. **EFD Contribuições:** usar o exportador existente, reconhecer a mensagem
   completa de geração, confirmar o aviso e retornar ao painel azul.
3. **Livros Fiscais:** marcar somente Registro de Entradas, Registro de
   Saídas e Registro de ICMS, conferir as datas, gerar e escolher um PDF
   por relatório. Conferir os três arquivos antes de finalizar.

O código da tarefa determina a empresa. Se estiver diferente, o executor
usa F8 e confere novamente código e painel azul antes de emitir.

O terminal mostra etapas, tempos e progresso a cada cinco segundos.
O limite padrão da sequência é 30 minutos, configurável com
--limite-minutos; ao atingir o limite, solicita cancelamento cooperativo.
Ctrl+C solicita parada segura e impede começar a próxima rotina. Não
fechar à força nem lançar outra execução enquanto o worker encerra.

No fim, conferir o status de cada rotina, artefatos disponíveis e JSON
local em logs/piloto_presumido_<id>.json. O diagnóstico omite nome/código da
empresa, caminhos, conteúdo dos PDFs e texto livre do OCR. O histórico
continua no banco local e pode ser consultado após reabrir o servidor.

## Executar pelo painel

Com o servidor aberto, usar **Lucro Presumido por empresa** no início do
painel: escolher empresa e competência, conferir a sequência, confirmar a
apuração e clicar **Executar sequência nesta empresa** uma vez.

**Preparar teste dos três Livros Fiscais** preenche **Nova execução** com a
rotina conjunta; conferir código e mês, confirmar apuração e executar.
**Conferir formulário dos três livros** é somente uma leitura sem emissão
e requer a aba Geral aberta.

Na tabela de resultados, **Ver etapas** abre o histórico da rotina e seus
arquivos. **Baixar diagnóstico das etapas** registra estados, motivos,
tempos e retorno. Reenvio do mesmo pedido não repete emissão.

Rotinas custom pendentes continuam bloqueando a sequência completa. Teste
parcial exige opção explícita e mantém as pendências como não executadas.
Nenhum cadastro custom é apagado ou substituído para liberar o botão.

## Conferir o resultado antes de ampliar para lote

Abrir o PDF do Resumo e os três livros. Conferir empresa, competência e
valores com o supervisor. Para EFD, conferir também o arquivo no destino
configurado no Domínio: a integração atual reconhece a exportação, mas não
produz um demonstrativo PDF nem registra seu caminho como artefato.

“Geração sinalizada; encerramento não confirmado” significa que a mensagem
de geração foi lida, mas o ciclo não confirmou o retorno seguro. Conferir o
arquivo e o histórico antes de repetir; não tratar como aprovação fiscal.

Falhas permanecem no histórico. A próxima rotina só começa depois de
confirmar o retorno ao painel azul. Sem retorno confirmado, a sequência
para. Reiniciar não repete nem retoma uma emissão automaticamente.

Depois do aceite individual, testar poucas empresas do Presumido em lote,
uma empresa por vez. Lucro Real precisa de aceite próprio posteriormente.

## Onde ficam os arquivos

Resumo fica em saida/, com nome cadastrado e competência. Livros são
exportados para staging exclusivo em saida/ e os PDFs confirmados seguem
para o destino cadastrado da empresa. Padrão:
FISCAL/mês/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS. Sem raiz configurada, ficam
na saída local. **Ver destino** mostra o caminho; **Testar pasta** confere
a gravação sem emitir. Não substitui documentos de execuções anteriores.

Os downloads usam os arquivos registrados pela tarefa. Cada livro precisa
confirmar tipo, CNPJ, período e estabilidade do arquivo. Arquivo recusado
não é publicado como válido; PDFs confirmados permanecem disponíveis se
outro livro ou o retorno falhar.

## Revisão técnica desta atualização

- Resumo: procura Fechar e OK nos retângulos medidos da captura, inclusive
  quando Fechar desaparece no OCR global; exige rótulos inteiros e contexto
  inequívoco. Campos já corretos não são redigitados.
- Livros: novas capturas limitadas antes/depois de marcar cada caixa; não
  repete clique por demora de pintura. Datas e três seleções são conferidas
  juntas na captura anterior ao OK. Seletor aguarda unidade e árvore.
- EFD: relê resultados negativos mesmo em tela parada, limita a espera e
  confirma o fechamento do aviso com as mesmas escalas e motores. Envia
  um único Enter; foco perdido bloqueia novas ações.
- OCR: Tesseract com timeout de oito segundos por chamada; OCR Windows
  com espera de quatro segundos e no máximo uma leitura nativa pendente.
  Resultado tardio não passa para outra análise. Imagens ampliadas respeitam
  o limite informado pelo motor nativo e restauram as coordenadas.

Esses limites e testes não substituem a rodada real do escritório. Se
falhar, consultar a última etapa e o diagnóstico local; não reenviar uma
rotina que já sinalizou geração sem conferir o arquivo.
