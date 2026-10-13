# Conferir caixas e datas de Livros Fiscais sem emitir

Na captura nova de 13/10/2026, Registro de Entradas, Registro de Saídas e
Registro de ICMS estão desmarcados. Datas mostradas: 01/09/2026 a 30/09/2026.
O operador informou que setembro ainda não está fechado. Não emitir essa
competência; escolher um mês cuja apuração esteja confirmada para essa
empresa. Em 13/10, "mês passado" significa setembro, não agosto.

## Diagnóstico local

No painel atualizado, também pode usar **Testar Livros Fiscais → Conferir
formulário dos três livros**, com a aba Geral aberta no Domínio do servidor.
O worker identifica/foca a janela do Domínio, captura e lê os controles.
Recusa enquanto há emissão/login ativo. Não modifica caixas/datas, não
clica OK e não emite. Mostra resumo de estados/datas/medidas; a captura
fica local. Detalhes em [TESTE-PRESUMIDO-POR-EMPRESA.md](TESTE-PRESUMIDO-POR-EMPRESA.md).

1. Atualizar para a main publicada. A recuperação da instalação em
   949a760 foi confirmada pelo log do operador, com backup local.
2. Abrir Relatórios → Livros → Livros Fiscais, aba Geral. Deixar a janela
   inteira visível. Não precisa confirmar apuração para apenas ler os
   controles do formulário: esse diagnóstico não emite nem altera nada.
3. Abrir o atalho Revisar Formulario Livros.bat em atalhos/ferramentas,
   ou executar no CMD da pasta do projeto:

   ```bat
   python scripts\revisar_formulario_livros.py
   ```

4. Nos cinco segundos de preparação, colocar o formulário em foco.
5. O script salva a captura somente em capturas/ do PC, mede por OCR e
   pixels e mostra as três caixas, Inicial/Final e a contagem de outras
   opções de emissão marcadas. Não imprime texto livre do OCR, nomes de
   empresas, CNPJ ou valores fiscais. Não envia imagem para serviços.
6. Se a leitura não for confirmada, guardar o log e a captura local para
   revisar o ponto indicado. Não transforma leitura parcial em sucesso.

Para analisar um PNG já salvo, sem capturar o desktop:

```bat
python scripts\revisar_formulario_livros.py --imagem "CAMINHO_DO_PNG_LOCAL"
```

## Implementação e limites

formulario_livros mede os quadrados ao lado dos rótulos OCR na captura
atual; separa borda/miolo e recusa estados indeterminados. Exige as 16
caixas do grupo Emitir presentes nas capturas observadas, incluindo
Relação de Emitentes. Opções do painel à direita não são caixas de emissão.
Se a versão/tamanho do formulário não puder ser reconhecido, interrompe.

Inicial/Final são associados às datas da mesma linha, e não ao texto
Conforme período inicial do rodapé. Não usa os offsets antigos de 60/57
pixels. Tenta OCR local em duas escalas, depois OCR do Windows.

A primitiva marcar_tres_livros recebe leitores/cliques do futuro chamador:
marca somente as caixas conhecidas ainda desmarcadas, relê após alterar e
recusa outras opções selecionadas ou estados desconhecidos. Não clica OK.
**Essa primitiva ainda não está ligada ao executor ou aos geradores.**
O script de diagnóstico não a chama. Foco, empresa, trava e apuração devem
ser impostos pelo executor quando a emissão conjunta for implementada.

Não foram medidos os pixels do print inline como um arquivo nesta nuvem.
Não há offsets calibrados a partir dele. Testes usam imagens sintéticas,
incluindo janela movida/ampliada, marcações mistas, opções extras, caixas
ambíguas e Tesseract real. O log do diagnóstico no Windows é o próximo
passo antes de integrar cliques ou declarar a leitura calibrada.
