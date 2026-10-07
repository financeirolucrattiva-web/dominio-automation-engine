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

O painel introduzido em 07/10/2026 consome eventos estruturados do motor
e separa confirmação, falha e retorno. Finalização e confirmação de lote
passam pela fila da thread Tk; ferramentas locais não disputam a sessão
com uma execução. Catálogo e andamento não habilitam agentes operadores.

Não muda nada do motor em si (`app/dominio.py`) além do que já estava
documentado (`regime`, `confirmar` em `executar_lote()`) — sem
informar os dois, o comportamento por terminal (`scripts/app.py`,
`scripts/executar_lote.py`) continua idêntico a antes.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X, Y
try:
    from ttkbootstrap.widgets.scrolled import ScrolledFrame
except ImportError:
    from ttkbootstrap.scrolled import ScrolledFrame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import capacidades, dominio, empresas, estados, historico, ia, interacao, painel, rotina_gravada, verificacao
from gravar import Gravador

PASTA_SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "saida"
ROOT = Path(__file__).resolve().parent.parent
FONTE_INTERFACE = "Segoe UI" if sys.platform == "win32" else "Helvetica"


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


class RevisarGravacao(simpledialog.Dialog):
    """Depois de gravar (F12), deixa nomear a rotina e marcar quais
    textos digitados são PARÂMETROS (mudam toda vez — ex.: código da
    empresa) em vez de ficarem fixos pra sempre — sem editar nenhum
    arquivo Python. Pedido do usuário (07/10/2026, seção 0.82): criar
    rotina nova tem que ficar fácil pra quem não programa.

    `self.resultado` fica `None` se cancelado, ou
    `(nome_exibicao, passos_com_parametro_marcado, lista_de_parametros)`
    — pronto pra `rotina_gravada.salvar_rotina_gravada()`."""

    def __init__(self, pai, passos, nome_sugerido):
        self.passos_originais = passos
        self.nome_sugerido = nome_sugerido
        self.entradas_parametro = {}
        self.resultado = None
        super().__init__(pai, title="Revisar rotina gravada")

    def body(self, master):
        tb.Label(master, text="Nome da rotina (como vai aparecer na lista):").pack(anchor="w", padx=10, pady=(10, 2))
        self.entrada_nome = tb.Entry(master, width=50)
        self.entrada_nome.insert(0, self.nome_sugerido)
        self.entrada_nome.pack(padx=10, pady=(0, 10), fill=X)

        passos_digitar = [p for p in self.passos_originais if p.get("tipo") == "digitar"]
        if passos_digitar:
            tb.Label(
                master,
                text='Pra cada texto digitado, deixe em branco se é sempre igual, ou dê um\n'
                     'nome curto se muda toda vez que rodar (vira um campo pra preencher):',
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 6))

            quadro = tb.Frame(master)
            quadro.pack(padx=10, pady=(0, 10), fill=BOTH, expand=True)
            altura = min(220, 36 * len(passos_digitar) + 10)
            canvas = tk.Canvas(quadro, height=altura, highlightthickness=0)
            rolagem = tb.Scrollbar(quadro, orient="vertical", command=canvas.yview)
            interno = tb.Frame(canvas)
            interno.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=interno, anchor="nw")
            canvas.configure(yscrollcommand=rolagem.set)
            canvas.pack(side=LEFT, fill=BOTH, expand=True)
            rolagem.pack(side=RIGHT, fill=Y)

            for passo in passos_digitar:
                linha = tb.Frame(interno)
                linha.pack(fill=X, pady=3)
                tb.Label(linha, text=f'Passo {passo["indice"]}: {passo["texto"]!r}', width=35, anchor="w").pack(side=LEFT, padx=(0, 6))
                entrada = tb.Entry(linha, width=20)
                entrada.pack(side=LEFT)
                self.entradas_parametro[passo["indice"]] = entrada
        else:
            tb.Label(master, text="(essa gravação não tem nenhum texto digitado pra revisar)").pack(padx=10, pady=(0, 10))

        return self.entrada_nome

    def apply(self):
        nome_exibicao = self.entrada_nome.get().strip() or self.nome_sugerido
        passos_marcados = []
        parametros = []
        for passo in self.passos_originais:
            passo = dict(passo)
            if passo.get("tipo") == "digitar":
                entrada = self.entradas_parametro.get(passo["indice"])
                nome_parametro = entrada.get().strip() if entrada is not None else ""
                if nome_parametro:
                    passo["parametro"] = nome_parametro
                    parametros.append(nome_parametro)
            passos_marcados.append(passo)
        self.resultado = (nome_exibicao, passos_marcados, parametros)


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
        self.root.geometry("1120x780")
        self.root.minsize(900, 640)
        self.root.option_add("*Font", (FONTE_INTERFACE, 10))
        self.root.style.configure("Treeview", rowheight=29)

        self.fila = queue.Queue()
        self.fila_estados = queue.Queue()
        self.painel = painel.EstadoPainel()
        self.ferramenta_local = None
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
        self._atualizar_painel()
        self.root.after(100, self._drenar_fila)

    def _montar_layout(self):
        cabecalho = tb.Frame(self.root, bootstyle="primary")
        cabecalho.pack(fill=X)
        tb.Label(
            cabecalho, text="DOMÍNIO  |  Automação Fiscal", bootstyle="inverse-primary",
            font=(FONTE_INTERFACE, 20, "bold"), padding=(20, 18),
        ).pack(side=LEFT)
        tb.Label(cabecalho, text="Execução local · Tesseract", bootstyle="inverse-primary",
                 padding=(14, 18)).pack(side=RIGHT)

        corpo = tb.Frame(self.root, padding=14)
        corpo.pack(fill=BOTH, expand=True)

        self.abas = tb.Notebook(corpo)
        self.abas.pack(fill=BOTH, expand=True, pady=(0, 10))

        aba_painel = tb.Frame(self.abas, padding=16)
        aba_rotinas = tb.Frame(self.abas)
        rotinas_scroll = ScrolledFrame(aba_rotinas, padding=10, autohide=True)
        rotinas_scroll.pack(fill=BOTH, expand=True)
        aba_capacidades = tb.Frame(self.abas, padding=16)
        aba_historico = tb.Frame(self.abas, padding=10)
        aba_projeto = tb.Frame(self.abas, padding=16)
        aba_log = tb.Frame(self.abas, padding=10)
        self.abas.add(aba_painel, text="Painel")
        self.abas.add(aba_rotinas, text="Rotinas")
        self.abas.add(aba_capacidades, text="Funções disponíveis")
        self.abas.add(aba_historico, text="Histórico")
        self.abas.add(aba_projeto, text="Projeto")
        self.abas.add(aba_log, text="Log")
        self._aba_log = aba_log
        self._aba_painel = aba_painel

        self._montar_aba_painel(aba_painel)
        self._montar_aba_rotinas(rotinas_scroll)
        self._montar_aba_capacidades(aba_capacidades)
        self._montar_aba_historico(aba_historico)
        self._montar_aba_projeto(aba_projeto)
        self._montar_aba_log(aba_log)

    def _montar_aba_painel(self, pai):
        barra = tb.Frame(pai)
        barra.pack(fill=X, pady=(0, 14))
        tb.Label(barra, text="Acompanhar execução", font=(FONTE_INTERFACE, 17, "bold")).pack(side=LEFT)
        tb.Button(barra, text="Ver log", bootstyle="secondary-outline",
                  command=lambda: self.abas.select(self._aba_log)).pack(side=RIGHT)
        tb.Button(barra, text="Escolher rotina", bootstyle="primary",
                  command=lambda: self.abas.select(1)).pack(side=RIGHT, padx=8)

        cartoes = tb.Frame(pai)
        cartoes.pack(fill=X, pady=(0, 14))
        self.valores_painel = {}
        for coluna, (chave, titulo) in enumerate((("rotina", "ROTINA"), ("etapa", "ETAPA ATUAL"), ("resultado", "RESULTADO"))):
            cartoes.columnconfigure(coluna, weight=1, uniform="cartao")
            card = tb.Labelframe(cartoes, text=titulo, padding=14, bootstyle="primary")
            card.grid(row=0, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 8, 0))
            valor = tb.Label(card, text="—", font=(FONTE_INTERFACE, 12, "bold"), wraplength=290)
            valor.pack(fill=X)
            self.valores_painel[chave] = valor

        self.progresso_etapas = tb.Progressbar(pai, bootstyle="success", maximum=100)
        self.progresso_etapas.pack(fill=X)
        self.rotulo_progresso = tb.Label(pai, text="As etapas aparecerão quando uma rotina iniciar.", bootstyle="secondary")
        self.rotulo_progresso.pack(anchor="w", pady=(5, 12))
        self.rotulo_retorno = tb.Label(pai, text="Retorno à tela principal: ainda não observado.", bootstyle="secondary")
        self.rotulo_retorno.pack(anchor="w", pady=(0, 10))

        area_tabela = tb.Frame(pai)
        self.tabela_estados = tb.Treeview(area_tabela, columns=("etapa", "status", "tempo"), show="headings", height=9)
        for coluna, titulo, largura in (("etapa", "Etapa", 440), ("status", "Situação", 300), ("tempo", "Tempo observado", 150)):
            self.tabela_estados.heading(coluna, text=titulo)
            self.tabela_estados.column(coluna, width=largura, anchor="w")
        rolagem = tb.Scrollbar(area_tabela, orient="vertical", command=self.tabela_estados.yview)
        self.tabela_estados.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side=RIGHT, fill=Y)
        self.tabela_estados.pack(side=LEFT, fill=BOTH, expand=True)
        for tag, cor in (("confirmado", "#168056"), ("falha", "#bd3737"),
                         ("inconclusivo", "#986800"), ("acao_executada", "#986800"),
                         ("resultado_nao_verificado", "#986800")):
            self.tabela_estados.tag_configure(tag, foreground=cor)
        tb.Label(pai, text="Ação enviada e retorno confirmado são acompanhados separadamente. "
                 "A janela minimiza durante a execução para manter o Domínio em foco.",
                 wraplength=820, bootstyle="secondary").pack(side="bottom", fill=X, pady=(12, 0))
        area_tabela.pack(fill=BOTH, expand=True)

    def _atualizar_painel(self):
        for chave, label in self.valores_painel.items():
            label.configure(text=getattr(self.painel, chave))
        total = len(self.painel.etapas)
        self.progresso_etapas.configure(value=100 * self.painel.confirmadas / total if total else 0)
        self.rotulo_progresso.configure(text=(f"{self.painel.confirmadas} de {total} etapas confirmadas · Tentativa {self.painel.tentativa}"
                                             if total else "As etapas aparecerão quando uma rotina iniciar."))
        self.rotulo_retorno.configure(text=f"Retorno à tela principal: {self.painel.retorno}.")
        for item in self.tabela_estados.get_children():
            self.tabela_estados.delete(item)
        for etapa, nome, status, tempo, tag in self.painel.linhas_tabela():
            self.tabela_estados.insert("", "end", iid=etapa, values=(nome, status, tempo), tags=(tag,))

    def _processar_eventos(self):
        mudou = False
        conclusao = None
        try:
            while True:
                item = self.fila_estados.get_nowait()
                if isinstance(item, tuple) and len(item) == 3 and item[0] == "finalizar_atividade":
                    conclusao = item[1:]
                elif isinstance(item, tuple) and len(item) == 3 and item[0] == "confirmar_lote":
                    self._mostrar_confirmacao_lote(item[1], item[2])
                else:
                    mudou = self.painel.receber(item) or mudou
        except queue.Empty:
            pass
        if mudou:
            self._atualizar_painel()
        if conclusao is not None:
            self._fim_execucao(*conclusao)

    def _montar_aba_capacidades(self, pai):
        tb.Label(pai, text="Funções conhecidas do motor", font=(FONTE_INTERFACE, 17, "bold")).pack(anchor="w")
        tb.Label(pai, text="Selecione uma função para consultar suas condições e verificações.",
                 bootstyle="secondary").pack(anchor="w", pady=(6, 14))
        self.tabela_capacidades = tb.Treeview(pai, columns=("nome", "periodo", "situacao"), show="headings", height=5)
        for coluna, titulo, largura in (("nome", "Função", 240), ("periodo", "Período", 320), ("situacao", "Situação", 390)):
            self.tabela_capacidades.heading(coluna, text=titulo)
            self.tabela_capacidades.column(coluna, width=largura, anchor="w")
        for item in capacidades.listar_capacidades():
            self.tabela_capacidades.insert("", "end", iid=item.id, values=(
                item.nome, "Informado na interface" if item.id.startswith("registro_") else "Mês anterior",
                "Revalidação da versão atual pendente",
            ))
        self.tabela_capacidades.pack(fill=X, pady=(0, 12))
        self.detalhes_capacidade = scrolledtext.ScrolledText(pai, state="disabled", wrap="word",
                                                           font=(FONTE_INTERFACE, 10), height=12, relief="flat")
        self.detalhes_capacidade.pack(fill=BOTH, expand=True)
        self.tabela_capacidades.bind("<<TreeviewSelect>>", self._mostrar_capacidade)
        self.tabela_capacidades.selection_set("sped_fiscal")
        self._mostrar_capacidade()

    def _mostrar_capacidade(self, evento=None):
        selecao = self.tabela_capacidades.selection()
        if not selecao:
            return
        item = capacidades.obter_capacidade(selecao[0])
        partes = [item.nome, item.objetivo, "", "Antes de executar:"]
        partes.extend(f"• {texto}" for texto in item.precondicoes)
        partes.extend(("", "Período:", item.politica_periodo, "", "Verificações atuais:"))
        partes.extend(f"• {texto}" for texto in item.checagens_atuais)
        partes.extend(("", "Falta validar:"))
        partes.extend(f"• {texto}" for texto in item.pendencias)
        self.detalhes_capacidade.configure(state="normal")
        self.detalhes_capacidade.delete("1.0", "end")
        self.detalhes_capacidade.insert("end", "\n".join(partes))
        self.detalhes_capacidade.configure(state="disabled")

    def _montar_aba_projeto(self, pai):
        tb.Label(pai, text="Caminho até o RPA com agentes", font=(FONTE_INTERFACE, 17, "bold")).pack(anchor="w")
        tb.Label(pai, text="Etapa atual: consolidar execução e recuperação. "
                 "Os testes no Windows confirmam a conclusão de cada incremento.",
                 wraplength=980, bootstyle="secondary").pack(fill=X, pady=(6, 14))
        tabela = tb.Treeview(pai, columns=("n", "fase", "status", "proximo"), show="headings", height=6)
        for coluna, titulo, largura in (("n", "", 35), ("fase", "Incremento", 230),
                                       ("status", "Andamento", 280), ("proximo", "Próxima evidência", 450)):
            tabela.heading(coluna, text=titulo)
            tabela.column(coluna, width=largura, anchor="w")
        for item in painel.PROJETO:
            tabela.insert("", "end", values=item)
        tabela.pack(fill=X, pady=(0, 18))
        preparacao = tb.Labelframe(pai, text="Preparar e conferir o ambiente", padding=12)
        preparacao.pack(fill=X)
        self._botao(preparacao, "Calibrar tela principal do Domínio", lambda: self._abrir_ferramenta("calibrar"), "primary-outline")
        self._botao(preparacao, "Comparar OCR na tela atual", lambda: self._abrir_ferramenta("ocr"), "secondary-outline")
        self._botao(preparacao, "Abrir instruções dos próximos testes", lambda: _abrir_no_explorador(ROOT / "docs" / "RETOMADA.md"), "secondary-outline")
        tb.Label(pai, text="Paddle CPU foi avaliado em uma captura Windows e levou cerca de 25 vezes mais tempo "
                 "que Tesseract. O OCR principal continua Tesseract; agentes operadores gerais estão planejados.",
                 wraplength=980, bootstyle="secondary").pack(fill=X, pady=(14, 0))

    def _abrir_ferramenta(self, identificador):
        if self.em_execucao or (self.ferramenta_local is not None and self.ferramenta_local.poll() is None):
            messagebox.showwarning("Aguarde", "Aguarde a execução ou ferramenta atual terminar.")
            return
        if identificador == "calibrar":
            comando = [sys.executable, str(ROOT / "scripts" / "abrir_ferramenta.py"), "calibrar"]
        elif identificador == "ocr":
            python_ocr = ROOT / ".venv-ocr-paddle" / "Scripts" / "python.exe"
            if not python_ocr.is_file():
                messagebox.showinfo("OCR opcional", "Prepare o OCR com Instalar Python OCR.bat antes de comparar.")
                return
            comando = [str(python_ocr), str(ROOT / "scripts" / "abrir_ferramenta.py"), "ocr"]
        else:
            return
        try:
            self.ferramenta_local = subprocess.Popen(comando, cwd=str(ROOT),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except OSError:
            messagebox.showerror("Ferramenta não iniciada", "Não consegui abrir a ferramenta local. Use seu atalho na pasta do projeto.")
            return
        for botao in self.botoes:
            botao.configure(state="disabled")
        self._marcar_status("Ferramenta aberta em outro Prompt; aguarde o resultado.", "info")
        self.root.iconify()
        self.root.after(500, self._conferir_ferramenta)

    def _conferir_ferramenta(self):
        codigo = self.ferramenta_local.poll()
        if codigo is None:
            self.root.after(500, self._conferir_ferramenta)
            return
        self.ferramenta_local = None
        for botao in self.botoes:
            botao.configure(state="normal")
        self.root.deiconify()
        self._marcar_status("Ferramenta concluída." if codigo == 0 else "Ferramenta não concluída; consulte o Prompt.",
                            "info" if codigo == 0 else "warning")

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
        self.status = tb.Label(barra_status, text="Pronto.", bootstyle="success", font=(FONTE_INTERFACE, 10, "bold"))
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

        # Rotinas gravadas e salvas direto (seção 0.82) — sem precisar
        # de programador colando código em app/dominio.py. Separado de
        # AUTOMACOES_EXTRAS de propósito: essas nunca foram revisadas
        # linha a linha por um programador, só pelo texto que o OCR
        # adivinhou na hora da gravação.
        self._secao_rotinas_gravadas = tb.Labelframe(
            pai, text="Rotinas gravadas (sem código)", padding=10, bootstyle="success",
        )
        self._secao_rotinas_gravadas.pack(fill=X, pady=(0, 10))
        self._recarregar_rotinas_gravadas()

        if self.modo != "operador":
            secao_gravar = tb.Labelframe(pai, text="Criar automação nova", padding=10, bootstyle="secondary")
            secao_gravar.pack(fill=X, pady=(0, 10))
            self._botao(secao_gravar, "Gravar clique (nova rotina)", self.acao_gravar, estilo="secondary")

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
        self._processar_eventos()
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
        ferramenta = getattr(self, "ferramenta_local", None)
        if self.em_execucao or (ferramenta is not None and ferramenta.poll() is None):
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
                with estados.observar_eventos(self.fila_estados.put):
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
                    try:
                        historico.registrar(nome_rotina, sucesso, arquivo_gerado=arquivo)
                    except OSError:
                        self.fila.put("Não foi possível gravar o histórico local; confira o resultado no painel e no log.\n")
                confirmado = (False if deu_erro else _normalizar_resultado(resultado, False)[0]
                              if isinstance(resultado, bool) or (isinstance(resultado, tuple) and len(resultado) == 2)
                              else None)
                self.fila_estados.put(("finalizar_atividade", deu_erro, confirmado))

        self.evento_pausa.set()
        self.em_execucao = True
        self.painel.limpar()
        self.painel.rotina = nome_rotina or "Atividade local"
        self.painel.etapa = "Aguardando primeira evidência"
        self.painel.resultado = "Em execução"
        self._atualizar_painel()
        for botao in self.botoes:
            botao.configure(state="disabled")
        if pausavel:
            self.botao_pausa.configure(state="normal", text="Pausar")
        self._marcar_status("Rodando...", "warning")
        self.fila.put(f"\n{'=' * 60}\n")
        # Troca pra aba "Painel" sozinha — assim, se/quando a pessoa
        # restaurar a janela (minimizada a seguir), já está na aba
        # certa, sem precisar clicar em nada a mais (pedido do usuário,
        # 06/10/2026).
        self.abas.select(self._aba_painel)
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

    def _fim_execucao(self, deu_erro=False, sucesso=None):
        self._processar_eventos()
        self.em_execucao = False
        self.root.deiconify()
        for botao in self.botoes:
            botao.configure(state="normal")
        self.botao_pausa.configure(state="disabled", text="Pausar")
        self.evento_pausa.set()
        if deu_erro or sucesso is False:
            self._marcar_status("Falha — consulte a aba Log.", "danger")
            if self.painel.execution_id is None:
                self.painel.resultado = "Falhou; consulte o log"
        elif sucesso is True:
            self._marcar_status("Concluído pela rotina; confira resultado e retorno no painel.", "info")
            if self.painel.execution_id is None:
                self.painel.resultado = "Concluído pela rotina"
        else:
            self._marcar_status("Atividade encerrada; consulte os resultados no log.", "info")
            if self.painel.execution_id is None:
                self.painel.resultado = "Atividade encerrada; consulte o log"
        self._atualizar_painel()
        self._carregar_historico()

    # --- Ações (espelham scripts/app.py, seção 0.18) ---

    def _confirmar_lote(self, selecionadas):
        """Chamado de dentro de `dominio.executar_lote()`, que roda na
        thread de trabalho (seção 0.33). A fila encaminha a pergunta à
        thread Tk; a thread de trabalho espera somente a resposta."""
        resposta = queue.Queue()
        self.fila_estados.put(("confirmar_lote", selecionadas, resposta))
        return resposta.get()

    def _mostrar_confirmacao_lote(self, selecionadas, resposta):
        lista = "\n".join(f"  {e['codigo']} - {e['apelido']}" for e in selecionadas)
        aceitou = messagebox.askyesno("Confirmar lote", f"Rodar pra essas {len(selecionadas)} empresa(s)?\n\n{lista}")
        if aceitou:
            self.root.iconify()
        resposta.put(aceitou)

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
            nome, extra="O período será o mês anterior. Confirme que a apuração dessa competência já está fechada.\n\n",
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
        nome_sugerido = simpledialog.askstring(
            "Gravar clique — rotina nova",
            "Nome da rotina nova (ex.: Emitir DCTF):",
        )
        if not nome_sugerido:
            return
        if not messagebox.askyesno(
            "Pronto pra gravar?",
            "A partir de agora, clique e digite normal nos passos do caminho novo\n"
            "que você quer ensinar (posição, texto digitado e palpite de OCR ficam\n"
            "gravados).\n\n"
            "F9 = marcar hover (passar o mouse sem clicar, pra abrir submenu).\n"
            "F12 = terminar — aí abre uma telinha pra você nomear e revisar\n"
            "antes de salvar como rotina de verdade.\n\n"
            "Atenção: tudo que você digitar é gravado, em qualquer janela — se\n"
            "precisar digitar senha fora do Domínio, pare (F12) antes.\n\n"
            "Continuar?",
        ):
            return

        def rodar():
            gravador = Gravador()
            gravador.gravar()
            gravador.gerar_rascunho(nome_sugerido.strip())
            self.root.after(0, self._revisar_gravacao, gravador.passos, nome_sugerido.strip())

        self._rodar_em_thread(rodar)

    def _revisar_gravacao(self, passos, nome_sugerido):
        """Mostrado depois que F12 encerra a gravação (agendado via
        `root.after`, roda na thread do Tk) — deixa nomear a rotina e
        marcar parâmetros antes de salvar. Nada é salvo se a pessoa
        cancelar o diálogo."""
        if not passos:
            messagebox.showinfo("Nada gravado", "Nenhum passo foi gravado — nada pra revisar.")
            return
        dialogo = RevisarGravacao(self.root, passos, nome_sugerido)
        if dialogo.resultado is None:
            return
        nome_exibicao, passos_marcados, parametros = dialogo.resultado
        caminho = rotina_gravada.salvar_rotina_gravada(nome_exibicao, passos_marcados, parametros)
        self._recarregar_rotinas_gravadas()
        messagebox.showinfo(
            "Rotina salva",
            f'"{nome_exibicao}" salva em {caminho.name} — já aparece em "Rotinas gravadas", '
            "pronta pra rodar. Supervisione a primeira execução.",
        )

    def _recarregar_rotinas_gravadas(self):
        # Descarta referência a botões já destruídos antes de reconstruir
        # a seção — evita acumular widget morto em self.botoes a cada
        # rotina nova gravada/salva/excluída.
        self.botoes = [b for b in self.botoes if b.winfo_exists()]
        for widget in self._secao_rotinas_gravadas.winfo_children():
            widget.destroy()
        rotinas = rotina_gravada.listar_rotinas_gravadas()
        if not rotinas:
            tb.Label(
                self._secao_rotinas_gravadas,
                text='Nenhuma ainda — grave uma em "Criar automação nova" abaixo.',
            ).pack(anchor="w")
            return
        for info in rotinas:
            aprovada = info["status"] == rotina_gravada.STATUS_APROVADA
            linha = tb.Frame(self._secao_rotinas_gravadas)
            linha.pack(fill=X, pady=2)

            rotulo_status = "aprovada" if aprovada else "rascunho — testar antes"
            botao = tb.Button(
                linha, text=f'{info["nome_exibicao"]}  ({rotulo_status})',
                bootstyle="success" if aprovada else "warning",
                command=lambda i=info: self.acao_rotina_gravada(i),
            )
            botao.pack(side=LEFT, fill=X, expand=True)
            self.botoes.append(botao)

            if aprovada:
                botao_lote = tb.Button(
                    linha, text="Em lote", bootstyle="success-outline", width=9,
                    command=lambda i=info: self.acao_rotina_gravada_lote(i),
                )
                botao_lote.pack(side=LEFT, padx=(4, 0))
                self.botoes.append(botao_lote)

            botao_excluir = tb.Button(
                linha, text="Excluir", bootstyle="danger-outline", width=8,
                command=lambda i=info: self.acao_excluir_rotina_gravada(i),
            )
            botao_excluir.pack(side=LEFT, padx=(4, 0))
            self.botoes.append(botao_excluir)

    def acao_excluir_rotina_gravada(self, info):
        if not messagebox.askyesno(
            "Excluir rotina",
            f'Excluir "{info["nome_exibicao"]}" de vez? Não dá pra desfazer\n'
            "(mas os prints da gravação original continuam em capturas/, se precisar).",
        ):
            return
        rotina_gravada.excluir_rotina_gravada(info["caminho"])
        self._recarregar_rotinas_gravadas()

    def acao_rotina_gravada(self, info):
        """Roda numa empresa só, sempre supervisionado — rascunho ou
        aprovada. Ao final de uma rotina ainda RASCUNHO, pergunta se
        funcionou certinho; só confirmando explicitamente é que ela
        vira APROVADA (e passa a poder rodar em lote)."""
        if not self._confirmar_empresa_selecionada(
            info["nome_exibicao"],
            extra="Rotina gravada pelo usuário — sem revisão de programador linha a linha, "
                  "só o texto que o OCR adivinhou na hora da gravação. Supervisione.\n\n",
        ):
            return

        parametros = {}
        for nome_parametro in info["parametros"]:
            valor = simpledialog.askstring("Valor do parâmetro", f"{nome_parametro}:")
            if valor is None:
                return  # cancelou
            parametros[nome_parametro] = valor

        era_rascunho = info["status"] != rotina_gravada.STATUS_APROVADA

        def rodar():
            passos = rotina_gravada.carregar_passos(info["caminho"])
            resultado = rotina_gravada.executar_passos(passos, parametros=parametros)
            if era_rascunho:
                self.root.after(0, self._perguntar_aprovacao, info, resultado)
            return resultado

        self._rodar_em_thread(rodar, nome_rotina=info["nome_exibicao"])

    def _perguntar_aprovacao(self, info, resultado):
        if not resultado:
            messagebox.showwarning(
                "Não funcionou",
                "A rotina não terminou certo dessa vez — continua como rascunho.\n"
                "Confira o log/print de erro, grave de novo corrigindo o passo que falhou,\n"
                "ou exclua e recomece.",
            )
            return
        if messagebox.askyesno(
            "Funcionou certinho?",
            f'"{info["nome_exibicao"]}" terminou sem erro. Conferiu que o resultado\n'
            "no Domínio está correto de verdade (não só que não travou)?\n\n"
            "Se sim, ela vira APROVADA e passa a poder rodar em lote, em várias\n"
            "empresas de uma vez.",
        ):
            rotina_gravada.marcar_status(info["caminho"], rotina_gravada.STATUS_APROVADA)
            self._recarregar_rotinas_gravadas()
            messagebox.showinfo("Aprovada", f'"{info["nome_exibicao"]}" aprovada — já aparece com a opção "Em lote".')

    def acao_rotina_gravada_lote(self, info):
        """Só pra rotina já APROVADA — entra no MESMO loop de lote do
        SPED Fiscal/EFD Contribuições (`dominio.executar_lote()`, seção
        0.82): troca de empresa automática entre uma e outra, falha
        isolada por empresa, pausa, verificação de tela principal.
        Parâmetro (se houver) é pedido uma vez só e usado em todas as
        empresas do lote — não por empresa individualmente ainda."""
        parametros = {}
        for nome_parametro in info["parametros"]:
            valor = simpledialog.askstring(
                "Valor do parâmetro (vale pra todas as empresas do lote)", f"{nome_parametro}:",
            )
            if valor is None:
                return
            parametros[nome_parametro] = valor

        gerador = rotina_gravada.criar_gerador(
            rotina_gravada.carregar_passos(info["caminho"]), parametros=parametros,
        )
        documentos_personalizados = [(info["nome_exibicao"], gerador)]

        regimes = empresas.regimes_disponiveis(empresas.carregar_empresas(empresas.ARQUIVO_EXEMPLO))
        dialogo = EscolherRegime(self.root, regimes)
        regime = dialogo.resultado
        if not regime:
            return

        usar_real = messagebox.askyesno(
            "Empresas reais ou exemplo?",
            "Rodar contra empresas REAIS (data/empresas.csv)?\n\n"
            "Não = roda contra a planilha de exemplo (sem risco), pra testar o lote em si.",
        )

        def confirmar(selecionadas):
            lista = "\n".join(f'  {e["codigo"]} - {e["apelido"]}' for e in selecionadas)
            return messagebox.askyesno(
                "Confirmar lote",
                f'Rodar "{info["nome_exibicao"]}" (aprovada) em {len(selecionadas)} empresa(s)?\n\n{lista}',
            )

        def rodar():
            dominio.executar_lote(
                usar_real=usar_real, regime=regime, confirmar=confirmar,
                pausa=self.evento_pausa, documentos_personalizados=documentos_personalizados,
            )

        self._rodar_em_thread(rodar, pausavel=True)


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
