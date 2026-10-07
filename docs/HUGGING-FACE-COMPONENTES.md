# Componentes do Hugging Face para o Automation Engine

Consulta documental em **07/10/2026**. Foram lidos metadados, model cards e documentação oficial. **Nenhum modelo foi instalado, nenhum peso foi baixado e nenhum benchmark nas telas do Domínio foi realizado nesta consulta.** Não foram enviados dados ou imagens de cliente. Esta lista orienta melhorias dentro do projeto existente.

## Primeiro candidato: OCR com localização de texto

O candidato inicial é o pipeline PaddleOCR com **detecção `PP-OCRv5_mobile_det` e reconhecimento `latin_PP-OCRv5_mobile_rec`**, para comparar com os mecanismos locais já utilizados. Os dois modelos estão publicados pela organização oficial PaddlePaddle no Hugging Face e declaram licença Apache-2.0:

- [PaddlePaddle/PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det)
- [PaddlePaddle/latin_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec)

A [documentação oficial multilíngue PP-OCRv5](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html) lista **português com `lang="pt"`**. Seus exemplos de saída incluem texto, `rec_scores`, `rec_polys` e `rec_boxes`. Esses campos permitem adaptar resultados a texto, confiança e coordenadas, necessários para a percepção atual. Reconhecer uma linha não equivale a identificar sozinho o botão ou confirmar o estado da interface.

O card do reconhecedor latino contém uma inconsistência: a introdução menciona reconhecimento de coreano, embora o identificador seja latino. As tags de idioma também não demonstram português. Por isso, a confirmação de português acima vem da documentação multilíngue, e deve ser conferida novamente na versão instalada.

A [instalação oficial](https://www.paddleocr.ai/latest/en/version3.x/installation.html) separa o pacote OCR básico dos grupos opcionais. OCR geral não requer instalar todas as capacidades de documentos, tradução e extração. O framework escolhido também precisa de instalação compatível com Windows, Python e CPU/GPU do usuário; instalar apenas `paddleocr` não resolve necessariamente esse requisito.

Os exemplos oficiais apresentam CPU e GPU. Isso **não comprova** que o candidato será mais rápido ou mais preciso em menus pequenos, campos de data ou avisos do Domínio. Tesseract continua disponível; a seleção do padrão depende de regressão e medição local.

## Instalação opcional: versões e download conferidos

Para preparar uma avaliação local CPU, foram consultados também os metadados atuais do PyPI e o código publicado nas tags dos pacotes. Uma combinação com versões fixadas é **`paddleocr==3.7.0`, `paddlex==3.7.0`, `paddlepaddle==3.3.1` e `huggingface-hub==2.1.1`**, em ambiente virtual opcional dentro deste mesmo projeto. Ela não foi instalada ou executada nesta consulta.

- [`paddleocr` 3.7.0](https://pypi.org/project/paddleocr/3.7.0/) declara Python ≥ 3.8 e depende de `paddlex[ocr-core]>=3.7.0,<3.8.0`.
- [`paddlex` 3.7.0](https://pypi.org/project/paddlex/3.7.0/) declara Python ≥ 3.8 e dependência `huggingface-hub` sem limite de versão. Não declara instalação de `paddlepaddle`; o framework CPU precisa ser incluído explicitamente.
- [`paddlepaddle` 3.3.1](https://pypi.org/project/paddlepaddle/3.3.1/#files) publica wheels Windows **AMD64/64 bits para CPython 3.9 a 3.13**. Não foram encontrados wheels Windows ARM64, 32 bits ou CPython 3.14 nessa versão.
- [`huggingface-hub` 2.1.1](https://pypi.org/project/huggingface-hub/2.1.1/) exige **Python ≥ 3.10**. A interseção proposta para o instalador Windows é, portanto, **CPython 3.10 a 3.13, AMD64/64 bits**. A documentação [Windows do PaddlePaddle](https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/windows-pip_en.html) também exige Python e pip de 64 bits e processador x86_64.

Compatibilidade declarada e presença de wheels não demonstram instalação estável na máquina do usuário. As fontes das tags do Hub 2.1.1 e PaddleX 3.7.0 expõem as funções e exceções necessárias para os caminhos inspecionados; ainda é necessário executar o teste local de instalação e inferência. Pins dos pacotes principais também não equivalem a um lock completo de todas as dependências transitivas.

A [API PaddleOCR na tag v3.7.0](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/paddleocr/_pipelines/ocr.py) aceita os nomes dos dois modelos acima, `device="cpu"` e `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_textline_orientation=False`. Nessa API, `lang` e `ocr_version` são ignorados quando nomes ou diretórios explícitos de modelos são passados. O reconhecedor latino selecionado, e sua validação local, são a escolha efetiva de reconhecimento.

Para download exclusivamente pelo Hugging Face, as revisões consultadas são:

| Repositório | Revisão |
| --- | --- |
| `PaddlePaddle/PP-OCRv5_mobile_det` | `0d63e78e2b680928f6b1747d76a08db6e645efb7` |
| `PaddlePaddle/latin_PP-OCRv5_mobile_rec` | `ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57` |

Ambos listam `inference.json`, `inference.pdiparams` e `inference.yml`. `snapshot_download` pode fixar a revisão e limitar `allow_patterns` a esses três arquivos; o OCR recebe os diretórios locais via `text_detection_model_dir` e `text_recognition_model_dir`.

A variável `PADDLE_PDX_MODEL_SOURCE="huggingface"` existe na [tag PaddleX v3.7.0](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.0/paddlex/utils/flags.py). Seus aliases de fonte são `huggingface`, `aistudio`, `modelscope` e `bos`, mas a variável define **preferência**, não exclusividade: o [gerenciador de modelos](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.0/paddlex/inference/utils/official_models.py) mantém fallback entre fontes. Download explícito pelo Hub e diretórios locais evitam depender desse fallback para os dois modelos avaliados.

## PaddleOCR-VL-1.6 existe oficialmente

O modelo oficial é [**PaddlePaddle/PaddleOCR-VL-1.6**](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6), um componente VLM de **0,9 bilhão de parâmetros**, com licença declarada **Apache-2.0**. O card informa lançamento em 28/05/2026. A revisão consultada no Hugging Face foi `c5630abae1d940eafe0697512a0325494b02ab42`.

O card documenta a API `PaddleOCRVL(pipeline_version="v1.6")` e `paddleocr[doc-parser]>=3.6.0`. Também oferece uso via Transformers 5 ou posterior. A versão, o backend e os pesos devem ser fixados depois da validação; os comandos com atualização irrestrita do card não são uma política de atualização automática para este projeto.

Há uma distinção prática entre o **VLM sozinho** e o **pipeline completo** de análise de layout e reconhecimento. O [guia oficial PaddleOCR-VL](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html) explica que chamar apenas o VLM não equivale ao pipeline completo. O exemplo Transformers do card fornece reconhecimento de elementos e text spotting; não oferece por si só a mesma análise de página do pipeline.

Requisitos documentados no guia consultado:

- CPU x64: suportada pelos caminhos locais PaddlePaddle e Transformers; seguir instalação manual.
- Python: o guia informa faixa verificada de 3.9 a 3.13.
- PaddlePaddle para VL: 3.2.1 ou posterior; não instalar simultaneamente distribuições CPU e GPU do framework.
- NVIDIA GPU nos caminhos PaddlePaddle/Transformers: o guia indica Compute Capability ≥ 7.0 e CUDA ≥ 11.8. Blackwell tem guia próprio.
- vLLM, SGLang e FastDeploy: o guia informa que **não executam nativamente no Windows**; os caminhos de serviço e Docker exigem outra avaliação de implantação.

Esses dados são suporte documentado por backend, não um teste de instalação no Windows do usuário. O guia ressalva que exemplos locais de início rápido podem não atender velocidade, memória e estabilidade de produção. As fontes consultadas **não estabelecem um mínimo universal de RAM ou VRAM** aplicável ao nosso uso. Tamanho de imagem Docker, quantidade de parâmetros e tamanho dos pesos não equivalem ao pico de memória durante inferência.

A pontuação anunciada em OmniDocBench mede documentos de outro conjunto. Ela não comprova localização confiável de controles de GUI nem redução de falhas neste RPA. Testar VL somente diante de uma falha concreta de percepção que permaneça após OCR, recorte e OpenCV. Resultados generativos precisam de confirmação por estado e validação; não devem produzir cliques diretamente.

## Layout e outros componentes

[PP-DocLayoutV3](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3), também Apache-2.0, é um componente de layout documental com regiões e ordem de leitura. Pode ser avaliado se surgir dificuldade concreta para separar cabeçalho, tabela ou outra região de documento. Isso não demonstra capacidade de detectar menus, caixas de seleção ou botões do Domínio. Não há motivo comprovado nesta consulta para instalá-lo separadamente.

A organização oficial também publica PP-OCRv6. Sua existência foi verificada, mas ele não foi selecionado nem testado aqui. Não ampliar a instalação para várias famílias simultaneamente: primeiro medir um candidato útil contra o mecanismo atual.

## Como decidir a integração

Usar um pequeno conjunto local de telas representativas, com referências conferidas pelo operador, mantido fora do Git. Comparar o mecanismo atual e o candidato no mesmo recorte, resolução, escala e hardware. Incluir os elementos usados por SPED Fiscal: menus, formulário, competência, confirmação de geração, avisos de erro e retorno à tela principal.

Registrar identificação e revisão do modelo, versões, licença, CPU/GPU, instalação no Windows, acerto dos textos críticos, caixas de localização, ambiguidade, latência inicial e com modelo já carregado, pico de RAM e, quando houver GPU, pico de VRAM. Separar resultados sintéticos, resultados em capturas reais e execução real do fluxo. Testes com mocks não demonstram ganho de OCR.

Uma adoção exige ganho útil e **ausência de regressão nas evidências que sustentam SPED**, além de instalação estável e fallback quando a dependência opcional estiver ausente ou falhar. Falta de confiança ou conflito entre mecanismos deve resultar em estado inconclusivo. Manter o contrato de percepção e a separação entre reconhecimento, decisão, ação, validação e recuperação.

Os pesos podem vir do Hugging Face para executar **localmente**. Usar o Hub como fonte não exige enviar telas a Inference API, Spaces ou serviços externos. Não fazer upload de dados reais de cliente.

## Verificação de execução posterior à pesquisa

A combinação opcional foi instalada em ambiente Linux/CPU separado do
ambiente da automação. Foram baixados somente os dois modelos fixados.
Uma imagem **sintética** de 900×260 com rótulos de menu foi reconhecida:
três segmentos, alvo presente e caixas dentro dos limites, em três
leituras. Uma factory foi reutilizada. A inferência funcionou com
`socket.connect` bloqueado no Python; não é um teste exaustivo de todo
tráfego nativo ou uma avaliação nas telas do Domínio.

O primeiro teste reproduziu `NotImplementedError` no executor OneDNN:
`ConvertPirAttribute2RuntimeAttribute` não suportava o atributo PIR
encontrado. A configuração CPU desativa `enable_mkldnn` para esses
pesos/versões. Com a alteração, o teste passou. Os tempos ilustrativos
foram 3,624 s inicialmente e 0,804/0,811 s aquecido nessa máquina e
imagem; não demonstram precisão/velocidade no Windows ou vantagem sobre
o pipeline atual de recorte/escala do Domínio. RAM não foi medida.

Esse smoke comprova que os pesos, a API e a normalização funcionaram nesse
cenário Linux. Posteriormente, em 07/10/2026, o operador concluiu três
leituras por motor de uma captura atual no Windows: Paddle inicial
24,751s, aquecidas 14,309/15,802s; Tesseract inicial 0,935s, aquecidas
0,623/0,576s. Médias aquecidas de 15,06s e 0,60s, respectivamente.
Paddle levou aproximadamente 25 vezes mais tempo nesse teste; não há
evidência para promovê-lo a padrão. Manter Tesseract e revalidar estados
SPED. A precisão não foi medida: 32 segmentos Paddle versus 35 Tesseract
não representam acerto. RAM, coordenadas críticas e estabilidade em
múltiplas telas/rotinas ainda precisam de comparação.

## Fontes e limites desta consulta

- [Repositório oficial e licença PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), revisão documental consultada `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`.
- [Model card PaddleOCR-VL-1.6 na revisão consultada](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/c5630abae1d940eafe0697512a0325494b02ab42/README.md).
- [OCR: parâmetros e formato dos resultados](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html).
- [Instalação do framework PaddlePaddle](https://www.paddleocr.ai/latest/en/version3.x/paddlepaddle_installation.html).
- [Guia VL: hardware, instalação e distinção entre pipeline e VLM](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html).

Links `latest` e branches `main` podem mudar. Conferir versões e compatibilidade antes da implementação. Esta pesquisa não altera o backend atual e não resolve, por si só, falhas de foco, datas, validação de arquivo ou recuperação da interface.
