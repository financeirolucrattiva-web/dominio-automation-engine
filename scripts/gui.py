"""Interface gráfica do motor — mesmas ações do menu de texto
(`scripts/app.py`), em janela, sem digitar comando.

Reescrita em 01/10/2026 (pedido do usuário: a versão anterior "tava
feia e sem tanta utilidade") — três mudanças:

1. **Visual**: usa `ttkbootstrap` (tema "flatly") em vez de Tkinter
   puro — mesma biblioteca de sempre por baixo, só com skin moderno
   plano, sem precisar de nenhuma infraestrutura nova (continua um
   único processo Python nesta máquina).
2. **Abas**: "Rotinas" (tudo que já existia + a rotina nova de
   Registro de Saídas) e "Histórico" (novo — lista as últimas
   execuções, com botão pra abrir o arquivo gerado ou a pasta de
   saída). Resolve o pedido original de painel: "consultar falhas e
   evidências" e "abrir os arquivos gerados".
3. **Registro de Saídas**: primeira rotina nova fora do SPED Fiscal/
   EFD Contribuições a ganhar botão próprio na interface — com campos
   de competência (início/fim) e pasta de destino, em vez de só
   "empresa já selecionada" (os outros botões continuam desse jeito,
   sem mudança).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela):

    python scripts\\gui.py

Não muda nada do motor em si (`app/dominio.py`) além do que já estava
documentado (`regime`, `confirmar` em `executar_lote()`) — sem
informar os dois, o comportamento por terminal (`scripts/app.py`,
`scripts/executar_lote.py`) continua idêntico a antes.
"""

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X, Y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, empresas, historico, ia, interacao, verificacao
from gravar import Gravador

PASTA_SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "saida"


class EscritorFila:
    """Arquivo falso: em vez de escrever num arquivo/terminal, poem
    cada linha numa fila — é o que deixa o print() de dentro de
    app/dominio.py (rodando numa thread separada) aparecer na caixa de
    texto da janela, sem mexer em cada print um por um.

    Também grava em `data/ultimo_log.txt`, linha por linha, em tempo
    real (achado real, 06/10/2026: a própria janela se minimiza antes
    de mexer no Domínio — `_rodar_em_thread()` — pra não roubar foco
    de clique; isso esconde a caixa de texto bem na hora em que mais
    precisa ser lida. Um arquivo em disco permite acompanhar o log ao
    vivo de fora da interface — inclusive outra pessoa, ou um
    assistente de IA rodando na mesma máquina, sem precisar restaurar
    a janela no meio da automação, o que arriscaria atrapalhar um
    clique)."""

    def __init__(self, fila, arquivo_log=None):
        self.fila = fila
        self.arquivo_log = arquivo_log

    def write(self, texto):
        if texto:
            self.fila.put(texto)
            if self.arquivo_log is not None:
                try:
                    self.arquivo_log.write(texto)
                    self.arquivo_log.flush()
                except OSError:
                    pass

    def flush(self):
        pass


class EscolherRegime(simpledialog.Dialog):
    """Janelinha modal com uma lista suspensa de regimes — substitui o
    `input("Qual regime...")` do terminal por uma escolha clicável."""

    def __init__(self, pai, regimes):
        self.regimes = regimes
        self.resultado = None
        super().__init__(pai, title="Escolher regime")

    def body(self, master):
        tb.Label(master, text="Qual regime você quer processar hoje?").pack(padx=10, pady=(10, 4))
        self.combo = tb.Combobox(master, values=self.regimes, state="readonly")
        self.combo.pack(padx=10, pady=(0, 10))
        if self.regimes:
            self.combo.current(0)
        return self.combo

    def apply(self):
        self.resultado = self.combo.get()


def _abrir_no_explorador(caminho):
    """Abre um arquivo (no programa padrão) ou pasta (no Explorer) —
    só Windows (`os.startfile`), mesma restrição do resto do projeto."""
    caminho = Path(caminho)
    if not caminho.exists():
        messagebox.showwarning("Não encontrado", f"Não existe mais em disco:\n{caminho}")
        return
    os.startfile(caminho)  # nosec — caminho sempre vem do histórico local, nunca de input externo


class JanelaPrincipal:
    def __init__(self, root):
        self.root = root
        # "operador" esconde gravador e ações de empresa única — pra
        # instalação enxuta em outro computador, que só roda lote
        # (pedido do usuário, seção 0.41): setado por
        # "Abrir Interface Gráfica (Operador).bat", não pelos outros.
        self.modo = os.environ.get("DOMINIO_MODO", "completo").strip().lower()
        titulo = "Automação Fiscal Domínio"
        if self.modo == "operador":
            titulo += " (Operador)"
        self.root.title(titulo)
        self.root.geometry("1000x720")
        self.root.minsize(820, 580)

        self.fila = queue.Queue()
        self.em_execucao = False
        self.botoes = []
        # "set" = rodando, "clear" = pausado — checado por
        # dominio.executar_lote() entre uma empresa e outra (seção
        # 0.34). Só faz sentido pra ações em lote; pra ação de empresa
        # só (rápida), o botão de pausa fica desabilitado.
        self.evento_pausa = threading.Event()
        self.evento_pausa.set()

        self._montar_layout()
        self._carregar_historico()
        self.root.after(100, self._drenar_fila)

    def _montar_layout(self):
        cabecalho = tb.Frame(self.root, bootstyle="primary")
        cabecalho.pack(fill=X)
        tb.Label(
            cabecalho, text="Automação Fiscal Domínio", bootstyle="inverse-primary",
            font=("Segoe UI", 16, "bold"), padding=(16, 12),
        ).pack(side=LEFT)

        corpo = tb.Frame(self.root, padding=14)
        corpo.pack(fill=BOTH, expand=True)

        self.abas = tb.Notebook(corpo)
        self.abas.pack(fill=BOTH, expand=True, pady=(0, 10))

        aba_rotinas = tb.Frame(self.abas, padding=10)
        aba_historico = tb.Frame(self.abas, padding=10)
        aba_log = tb.Frame(self.abas, padding=10)
        self.abas.add(aba_rotinas, text="Rotinas")
        self.abas.add(aba_historico, text="Histórico")
        self.abas.add(aba_log, text="Log")
        self._aba_log = aba_log

        self._montar_aba_rotinas(aba_rotinas)
        self._montar_aba_historico(aba_historico)
        self._montar_aba_log(aba_log)

    def _montar_aba_log(self, pai):
        """Log numa aba própria (pedido do usuário, 06/10/2026: na
        barra embaixo ficava pequeno demais, espremido pelos botões da
        aba "Rotinas" — aqui ocupa a janela inteira). Muda sozinho pra
        esta aba quando uma ação começa (`_rodar_em_thread()`), mas a
        janela ainda se minimiza durante a automação (não mexi nisso —
        continua existindo o risco de roubar clique do Domínio se
        aparecer por cima); ver também `data/ultimo_log.txt`, que tem
        o mesmo conteúdo gravado em disco, pra ler sem precisar abrir a
        janela."""
        barra_status = tb.Frame(pai)
        barra_status.pack(fill=X, pady=(0, 6))
        self.status = tb.Label(barra_status, text="Pronto.", bootstyle="success", font=("Segoe UI", 10, "bold"))
        self.status.pack(side=LEFT)
        self.botao_pausa = tb.Button(
            barra_status, text="Pausar", command=self._alternar_pausa, state="disabled", bootstyle="warning-outline",
        )
        self.botao_pausa.pack(side=RIGHT)

        self.log = scrolledtext.ScrolledText(
            pai, width=100, height=30, state="disabled",
            font=("Consolas", 9), background="#1e1e1e", foreground="#d4d4d4",
            insertbackground="white", relief="flat", borderwidth=0,
        )
        self.log.pack(fill=BOTH, expand=True)

    # --- Aba "Rotinas" ---

    def _montar_aba_rotinas(self, pai):
        secao_lote = tb.Labelframe(pai, text="Rodar em lote (várias empresas)", padding=10, bootstyle="primary")
        secao_lote.pack(fill=X, pady=(0, 10))
        if self.modo != "operador":
            self._botao(secao_lote, "Empresas de EXEMPLO (sem risco)", self.acao_lote_exemplo, estilo="secondary")
        rotulo_lote_real = "Rodar SPED" if self.modo == "operador" else "Empresas REAIS"
        self._botao(secao_lote, rotulo_lote_real, self.acao_lote_real, estilo="primary")

        secao_empresa = tb.Labelframe(pai, text="Empresa já selecionada no Domínio", padding=10, bootstyle="info")
        secao_empresa.pack(fill=X, pady=(0, 10))
        self._botao(secao_empresa, "Trocar só a empresa", self.acao_trocar_empresa, estilo="secondary")
        self._botao(secao_empresa, "Gerar SPED Fiscal", self.acao_sped_fiscal, estilo="info")
        self._botao(secao_empresa, "Gerar EFD Contribuições", self.acao_efd_contribuicoes, estilo="info")
        # Automações extras, promovidas do gravador (seção 0.48) — um
        # botão a mais por item de dominio.AUTOMACOES_EXTRAS, sem
        # editar esta função de novo a cada automação nova.
        for nome, funcao in dominio.AUTOMACOES_EXTRAS:
            self._botao(
                secao_empresa, nome, lambda f=funcao, n=nome: self._rodar_gerador(f, n), estilo="info",
            )

        self._montar_secao_registro_saidas(pai)

        if self.modo != "operador":
            secao_gravar = tb.Labelframe(pai, text="Criar automação nova", padding=10, bootstyle="secondary")
            secao_gravar.pack(fill=X, pady=(0, 10))
            self._botao(secao_gravar, "Gravar clique (rascunho de automação nova)", self.acao_gravar, estilo="secondary")

        secao_config = tb.Labelframe(pai, text="Configuração", padding=10, bootstyle="secondary")
        secao_config.pack(fill=X, pady=(0, 10))
        self._botao(secao_config, "Configurar chave da IA de erro", self.acao_configurar_ia, estilo="secondary")

    def _montar_secao_registro_saidas(self, pai):
        """Seção nova (seção 0.57 do documento) — primeira rotina fora
        do SPED Fiscal/EFD Contribuições a ganhar campos próprios na
        interface (competência + pasta de destino), porque, ao
        contrário das outras, não dá pra confiar só em
        "mês anterior" (a apuração de ICMS daquele mês pode não ter
        sido fechada ainda no Domínio — achado real, mesma seção)."""
        secao = tb.Labelframe(
            pai, text="Livro Fiscal — Entradas/Saídas (empresa já selecionada)", padding=10, bootstyle="warning",
        )
        secao.pack(fill=X, pady=(0, 10))

        linha_tipo = tb.Frame(secao)
        linha_tipo.pack(fill=X, pady=(0, 6))
        tb.Label(linha_tipo, text="Livro:").pack(side=LEFT, padx=(0, 4))
        self.combo_tipo_livro = tb.Combobox(
            linha_tipo, values=["Registro de Saídas", "Registro de Entradas"], state="readonly", width=20,
        )
        self.combo_tipo_livro.current(0)
        self.combo_tipo_livro.pack(side=LEFT)

        linha_periodo = tb.Frame(secao)
        linha_periodo.pack(fill=X, pady=(0, 6))
        data_inicial_padrao, data_final_padrao = dominio.competencia_anterior()
        tb.Label(linha_periodo, text="Competência de:").pack(side=LEFT, padx=(0, 4))
        self.entrada_data_inicial = tb.Entry(linha_periodo, width=12)
        self.entrada_data_inicial.insert(0, data_inicial_padrao)
        self.entrada_data_inicial.pack(side=LEFT, padx=(0, 10))
        tb.Label(linha_periodo, text="até:").pack(side=LEFT, padx=(0, 4))
        self.entrada_data_final = tb.Entry(linha_periodo, width=12)
        self.entrada_data_final.insert(0, data_final_padrao)
        self.entrada_data_final.pack(side=LEFT)

        tb.Label(
            secao,
            text="Confirme que esta competência JÁ TEVE a apuração de ICMS fechada no Domínio "
                 "para esta empresa — \"mês anterior\" nem sempre significa \"já apurado\". "
                 "O mecanismo do Registro de Entradas foi observado anteriormente; "
                 "a versão atual requer revalidação.",
            bootstyle="warning", wraplength=700, justify="left",
        ).pack(fill=X, pady=(0, 6))

        self._botao(secao, "Gerar livro selecionado (PDF)", self.acao_registro_saidas, estilo="warning")

    # --- Aba "Histórico" ---

    def _montar_aba_historico(self, pai):
        barra = tb.Frame(pai)
        barra.pack(fill=X, pady=(0, 8))
        tb.Button(barra, text="Atualizar", command=self._carregar_historico, bootstyle="secondary-outline").pack(side=LEFT)
        tb.Button(
            barra, text="Abrir pasta de saída",
            command=lambda: _abrir_no_explorador(PASTA_SAIDA_PADRAO if PASTA_SAIDA_PADRAO.exists() else Path(".")),
            bootstyle="secondary-outline",
        ).pack(side=LEFT, padx=(6, 0))
        tb.Button(
            barra, text="Abrir arquivo gerado (selecionado)",
            command=self._abrir_arquivo_selecionado, bootstyle="primary-outline",
        ).pack(side=LEFT, padx=(6, 0))

        colunas = ("quando", "rotina", "resultado", "arquivo")
        self.tabela_historico = tb.Treeview(pai, columns=colunas, show="headings", height=16, bootstyle="primary")
        for coluna, titulo, largura in (
            ("quando", "Quando", 140), ("rotina", "Rotina", 220),
            ("resultado", "Resultado", 90), ("arquivo", "Arquivo gerado", 380),
        ):
            self.tabela_historico.heading(coluna, text=titulo)
            self.tabela_historico.column(coluna, width=largura, anchor="w")
        self.tabela_historico.pack(fill=BOTH, expand=True)
        self.tabela_historico.tag_configure("falhou", foreground="#c0392b")
        self.tabela_historico.tag_configure("sucesso", foreground="#2e9e4f")

    def _carregar_historico(self):
        for linha in self.tabela_historico.get_children():
            self.tabela_historico.delete(linha)
        for item in reversed(historico.carregar()):
            tag = "sucesso" if item.get("sucesso") else "falhou"
            self.tabela_historico.insert("", "end", values=(
                item.get("quando", ""),
                item.get("rotina", ""),
                "OK" if item.get("sucesso") else "Falhou",
                item.get("arquivo_gerado") or "—",
            ), tags=(tag,))

    def _abrir_arquivo_selecionado(self):
        selecao = self.tabela_historico.selection()
        if not selecao:
            messagebox.showinfo("Nada selecionado", "Selecione uma linha do histórico primeiro.")
            return
        valores = self.tabela_historico.item(selecao[0], "values")
        caminho_arquivo = valores[3] if len(valores) > 3 else None
        if not caminho_arquivo or caminho_arquivo == "—":
            messagebox.showinfo("Sem arquivo", "Essa execução não tem arquivo gerado associado.")
            return
        _abrir_no_explorador(caminho_arquivo)

    def _botao(self, pai, texto, comando, estilo="secondary"):
        botao = tb.Button(pai, text=texto, command=comando, bootstyle=estilo)
        botao.pack(fill=X, pady=3)
        self.botoes.append(botao)
        return botao

    def _marcar_status(self, texto, estilo):
        self.status.configure(text=texto, bootstyle=estilo)

    def _log(self, texto):
        self.log.configure(state="normal")
        self.log.insert("end", texto)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drenar_fila(self):
        try:
            while True:
                self._log(self.fila.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._drenar_fila)

    def _rodar_em_thread(self, alvo, *args, pausavel=False, nome_rotina=None):
        """Roda `alvo(*args)` numa thread separada, com o print() dela
        redirecionado pra a caixa de texto (`EscritorFila`), sem travar
        a janela enquanto a automação demora (até ~3 minutos por
        documento, seção 0.27).

        `pausavel=True` (só as ações em lote) habilita o botão
        "Pausar". `nome_rotina`, se informado, registra o resultado no
        histórico (`app/historico.py`) — aceita `alvo` devolvendo
        `True`/`False` ou `(True/False, caminho_ou_None)` (formato de
        `gerar_registro_saidas()`); funções em lote (sem retorno,
        só print) entram no histórico como "ver log" em vez de
        sucesso/falha, porque uma rodada de lote tem vários resultados
        misturados, não um só.
        """
        if self.em_execucao:
            messagebox.showwarning("Aguarde", "Já tem uma ação rodando — espera terminar.")
            return

        def trabalho():
            saida_original = sys.stdout
            caminho_log = Path(__file__).resolve().parent.parent / "data" / "ultimo_log.txt"
            try:
                caminho_log.parent.mkdir(parents=True, exist_ok=True)
                arquivo_log = caminho_log.open("a", encoding="utf-8")
                arquivo_log.write(f"\n{'=' * 60}\n[{nome_rotina or alvo.__name__}]\n")
            except OSError:
                arquivo_log = None
            sys.stdout = EscritorFila(self.fila, arquivo_log)
            deu_erro = False
            resultado = None
            try:
                resultado = alvo(*args)
            except Exception as e:  # nunca deixa a janela travada por um erro não previsto
                deu_erro = True
                self.fila.put(f"\nErro inesperado: {e}\n")
            finally:
                sys.stdout = saida_original
                if arquivo_log is not None:
                    arquivo_log.close()
                if nome_rotina is not None:
                    sucesso, arquivo = _normalizar_resultado(resultado, deu_erro)
                    historico.registrar(nome_rotina, sucesso, arquivo_gerado=arquivo)
                self.root.after(0, self._fim_execucao, deu_erro)

        self.evento_pausa.set()
        self.em_execucao = True
        for botao in self.botoes:
            botao.configure(state="disabled")
        if pausavel:
            self.botao_pausa.configure(state="normal", text="Pausar")
        self._marcar_status("Rodando...", "warning")
        self.fila.put(f"\n{'=' * 60}\n")
        # Troca pra aba "Log" sozinha — assim, se/quando a pessoa
        # restaurar a janela (minimizada a seguir), já está na aba
        # certa, sem precisar clicar em nada a mais (pedido do usuário,
        # 06/10/2026).
        self.abas.select(self._aba_log)
        # Minimiza a própria janela antes de mexer no Domínio — senão
        # ela pode ficar por cima e roubar o clique de foco (mesmo
        # risco da seção 0.28/0.37). Volta sozinha em _fim_execucao().
        self.root.iconify()
        threading.Thread(target=trabalho, daemon=True).start()

    def _alternar_pausa(self):
        """Pausa/continua o lote atual — só tem efeito entre uma
        empresa e outra (`dominio._esperar_se_pausado()`, seção 0.34),
        nunca no meio de uma ação."""
        if self.evento_pausa.is_set():
            self.evento_pausa.clear()
            self.botao_pausa.configure(text="Continuar")
            self._marcar_status("Pausando (termina a empresa atual antes de parar)...", "warning")
        else:
            self.evento_pausa.set()
            self.botao_pausa.configure(text="Pausar")
            self._marcar_status("Rodando...", "warning")

    def _fim_execucao(self, deu_erro=False):
        self.em_execucao = False
        self.root.deiconify()
        for botao in self.botoes:
            botao.configure(state="normal")
        self.botao_pausa.configure(state="disabled", text="Pausar")
        self.evento_pausa.set()
        if deu_erro:
            self._marcar_status("Erro — veja o log acima.", "danger")
        else:
            self._marcar_status("Pronto.", "success")
        self._carregar_historico()

    # --- Ações (espelham scripts/app.py, seção 0.18) ---

    def _confirmar_lote(self, selecionadas):
        """Chamado de dentro de `dominio.executar_lote()`, que roda na
        thread de trabalho (seção 0.33) — mas uma caixa de diálogo do
        Tkinter só pode ser criada na thread principal. `root.after()`
        agenda a pergunta de verdade lá, e essa função (na thread de
        trabalho) só espera a resposta chegar pela fila — não mostra
        nada diretamente."""
        resposta = queue.Queue()

        def perguntar():
            lista = "\n".join(f"  {e['codigo']} - {e['apelido']}" for e in selecionadas)
            aceitou = messagebox.askyesno(
                "Confirmar lote",
                f"Rodar pra essas {len(selecionadas)} empresa(s)?\n\n{lista}",
            )
            if aceitou:
                self.root.iconify()
            resposta.put(aceitou)

        self.root.after(0, perguntar)
        return resposta.get()

    def _rodar_lote(self, usar_real):
        lista = empresas.carregar_empresas(None if usar_real else empresas.ARQUIVO_EXEMPLO)
        if not lista:
            messagebox.showerror("Lista vazia", "Não achei nenhuma empresa na planilha.")
            return
        regimes = empresas.regimes_disponiveis(lista)
        escolha = EscolherRegime(self.root, regimes)
        if not escolha.resultado:
            return
        self._rodar_em_thread(
            dominio.executar_lote, usar_real, escolha.resultado, self._confirmar_lote, self.evento_pausa,
            pausavel=True, nome_rotina=f"Lote ({escolha.resultado}) — ver log pra detalhe por empresa",
        )

    def acao_lote_exemplo(self):
        self._rodar_lote(usar_real=False)

    def acao_lote_real(self):
        self._rodar_lote(usar_real=True)

    def acao_trocar_empresa(self):
        codigo = simpledialog.askstring("Trocar empresa", "Código da empresa (ex.: 9996):")
        if not codigo:
            return

        def rodar():
            interacao.focar_dominio()
            if dominio.trocar_empresa(codigo.strip()):
                print("Confira na tela se a empresa certa ficou selecionada.")

        self._rodar_em_thread(rodar, nome_rotina=f"Trocar empresa ({codigo.strip()})")

    def _confirmar_empresa_selecionada(self, nome, extra=""):
        return messagebox.askyesno(
            "Confirmar antes de continuar",
            f"A empresa certa já está selecionada no Domínio?\n\n{extra}"
            f"Vai gerar: {nome}",
        )

    def _rodar_gerador(self, gerador, nome):
        if not self._confirmar_empresa_selecionada(
            nome, extra="(o período é selecionado sozinho: sempre o mês fechado anterior ao atual)\n\n",
        ):
            return

        def rodar():
            interacao.focar_dominio()
            resultado = gerador()
            if resultado:
                print(f"Fim da rotina ({nome}).")
            return resultado

        self._rodar_em_thread(rodar, nome_rotina=nome)

    def acao_sped_fiscal(self):
        self._rodar_gerador(dominio.gerar_sped_fiscal, "SPED Fiscal")

    def acao_efd_contribuicoes(self):
        self._rodar_gerador(dominio.gerar_efd_contribuicoes, "EFD Contribuições")

    def acao_registro_saidas(self):
        """Gera o livro escolhido usando o período informado na interface.

        O mecanismo dos dois livros foi observado no Domínio real
        (seções 0.59/0.60). A versão atual, com a nova conferência de
        PDF, requer revalidação; sucesso histórico não aprova a atual.
        """
        tipo = self.combo_tipo_livro.get() or "Registro de Saídas"
        funcao = dominio.gerar_registro_entradas if "Entradas" in tipo else dominio.gerar_registro_saidas

        data_inicial = self.entrada_data_inicial.get().strip()
        data_final = self.entrada_data_final.get().strip()
        if not data_inicial or not data_final:
            messagebox.showerror("Competência vazia", "Preencha as duas datas da competência.")
            return
        if not self._confirmar_empresa_selecionada(
            f"{tipo} ({data_inicial} a {data_final})",
            extra="Confirme também que essa competência já tem a apuração de ICMS fechada no Domínio.\n\n",
        ):
            return

        def rodar():
            interacao.focar_dominio()
            return funcao(PASTA_SAIDA_PADRAO, data_inicial=data_inicial, data_final=data_final)

        self._rodar_em_thread(rodar, nome_rotina=f"{tipo} ({data_inicial} a {data_final})")

    def acao_configurar_ia(self):
        situacao = "configurada" if ia.disponivel() else "não configurada"
        chave = simpledialog.askstring(
            "Configurar IA",
            "A IA (Claude Haiku) só é consultada quando aparece uma caixa de\n"
            "erro/aviso do Domínio nunca vista antes — e só recebe o texto\n"
            "dela, já sem nome/código/CNPJ da empresa. Sem chave, o motor\n"
            "pula essas empresas em vez de arriscar (comportamento de sempre).\n\n"
            f"IA hoje: {situacao}.\n\n"
            "Pegue uma chave em https://console.anthropic.com/settings/keys\n"
            "Cole a chave aqui (ou deixe em branco pra não mexer):",
        )
        if not chave:
            return
        ia.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        ia.ARQUIVO_CHAVE.write_text(chave.strip(), encoding="utf-8")
        messagebox.showinfo("Salvo", f"Chave salva em {ia.ARQUIVO_CHAVE} (local, nunca sobe pro GitHub).")

    def acao_gravar(self):
        nome_funcao = simpledialog.askstring(
            "Gravar clique — automação nova",
            "Nome da função nova (ex.: gerar_dctf):",
        )
        if not nome_funcao:
            return
        if not messagebox.askyesno(
            "Pronto pra gravar?",
            "A partir de agora, todo clique seu no Domínio vai ser gravado\n"
            "(posição + print + palpite de texto por OCR).\n\n"
            "Clique normal nos passos do caminho novo que você quer ensinar.\n"
            "Aperte F12 quando terminar — aí sim gera o rascunho.\n\n"
            "Gera rascunho pra revisar, não automação pronta — confira cada\n"
            "palpite contra o print antes de usar de verdade.\n\n"
            "Continuar?",
        ):
            return

        def rodar():
            gravador = Gravador()
            gravador.gravar()
            gravador.gerar_rascunho(nome_funcao.strip())

        self._rodar_em_thread(rodar)


def _normalizar_resultado(resultado, deu_erro):
    """`alvo(*args)` pode devolver `True`/`False` (maioria das rotinas)
    ou `(True/False, caminho_ou_None)` (`gerar_registro_saidas()`) ou
    `None` (rotinas que só imprimem, sem devolver nada, ex.: lote,
    gravador). Normaliza pra `(sucesso, caminho_ou_None)` — único
    formato que `historico.registrar()` entende."""
    if deu_erro:
        return False, None
    if isinstance(resultado, tuple) and len(resultado) == 2:
        return resultado
    if isinstance(resultado, bool):
        return resultado, None
    # None ou qualquer outra coisa — sem informação de sucesso própria
    # (ex.: executar_lote(), que trata falha por empresa internamente
    # e só imprime o resumo) — considera concluído sem erro de topo.
    return True, None


def main():
    root = tb.Window(themename="flatly")
    JanelaPrincipal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
