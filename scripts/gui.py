"""Interface gráfica do motor — mesmas ações do menu de texto
(`scripts/app.py`), só que em janela (Tkinter), sem digitar comando.

Pensado como o novo "jeito fácil" (pedido do usuário, seção 0.33 do
documento): botão em vez de número de menu, confirmação por caixa de
diálogo em vez de digitar "sim"/"não", e o que normalmente aparece no
terminal (todo o debug de OCR, passo a passo) aparece numa caixa de
texto dentro da própria janela, em tempo real.

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela):

    python scripts\\gui.py

Não muda nada do motor em si (`app/dominio.py`) além de dois parâmetros
novos, opcionais, em `executar_lote()` (`regime`, `confirmar`) — sem
informar os dois, o comportamento por terminal (`scripts/app.py`,
`scripts/executar_lote.py`) continua idêntico a antes.
"""

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, empresas, ia, interacao
from gravar import Gravador


class EscritorFila:
    """Arquivo falso: em vez de escrever num arquivo/terminal, poem
    cada linha numa fila — é o que deixa o print() de dentro de
    app/dominio.py (rodando numa thread separada) aparecer na caixa de
    texto da janela, sem mexer em cada print um por um."""

    def __init__(self, fila):
        self.fila = fila

    def write(self, texto):
        if texto:
            self.fila.put(texto)

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
        ttk.Label(master, text="Qual regime você quer processar hoje?").pack(padx=10, pady=(10, 4))
        self.combo = ttk.Combobox(master, values=self.regimes, state="readonly")
        self.combo.pack(padx=10, pady=(0, 10))
        if self.regimes:
            self.combo.current(0)
        return self.combo

    def apply(self):
        self.resultado = self.combo.get()


_AZUL_ESCURO = "#0d2b4e"
_AZUL = "#1f5fa8"
_CINZA_CLARO = "#f2f4f7"
_VERDE = "#2e9e4f"
_LARANJA = "#e08a1e"
_VERMELHO = "#c0392b"
_CINZA = "#9aa0a6"


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
        self.root.geometry("880x640")
        self.root.minsize(720, 520)
        self.root.configure(background=_CINZA_CLARO)

        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass  # tema pode não existir em toda instalação — segue com o padrão
        estilo.configure("TFrame", background=_CINZA_CLARO)
        estilo.configure("TLabelframe", background=_CINZA_CLARO, font=("Segoe UI", 10, "bold"))
        estilo.configure("TLabelframe.Label", background=_CINZA_CLARO, foreground=_AZUL_ESCURO)
        estilo.configure("TButton", font=("Segoe UI", 10), padding=6)
        estilo.configure("Acento.TButton", font=("Segoe UI", 10, "bold"))
        estilo.configure("Status.TLabel", background=_CINZA_CLARO, font=("Segoe UI", 10))

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
        self.root.after(100, self._drenar_fila)

    def _montar_layout(self):
        cabecalho = tk.Frame(self.root, background=_AZUL_ESCURO)
        cabecalho.pack(fill="x")
        tk.Label(
            cabecalho, text="Automação Fiscal Domínio", background=_AZUL_ESCURO,
            foreground="white", font=("Segoe UI", 16, "bold"), padx=16, pady=12,
        ).pack(side="left")

        corpo = ttk.Frame(self.root, padding=14)
        corpo.pack(fill="both", expand=True)

        secao_lote = ttk.LabelFrame(corpo, text="Rodar em lote (várias empresas)", padding=10)
        secao_lote.pack(fill="x", pady=(0, 10))
        if self.modo != "operador":
            self._botao(secao_lote, "Empresas de EXEMPLO (sem risco)", self.acao_lote_exemplo)
        rotulo_lote_real = "Rodar SPED" if self.modo == "operador" else "Empresas REAIS"
        self._botao(secao_lote, rotulo_lote_real, self.acao_lote_real, acento=True)

        secao_empresa = ttk.LabelFrame(corpo, text="Empresa já selecionada no Domínio", padding=10)
        secao_empresa.pack(fill="x", pady=(0, 10))
        self._botao(secao_empresa, "Trocar só a empresa", self.acao_trocar_empresa)
        self._botao(secao_empresa, "Gerar SPED Fiscal", self.acao_sped_fiscal)
        self._botao(secao_empresa, "Gerar EFD Contribuições", self.acao_efd_contribuicoes)
        # Automações extras, promovidas do gravador (seção 0.48) — um
        # botão a mais por item de dominio.AUTOMACOES_EXTRAS, sem
        # editar esta função de novo a cada automação nova.
        for nome, funcao in dominio.AUTOMACOES_EXTRAS:
            self._botao(secao_empresa, nome, lambda f=funcao, n=nome: self._rodar_gerador(f, n))

        if self.modo != "operador":
            secao_gravar = ttk.LabelFrame(corpo, text="Criar automação nova", padding=10)
            secao_gravar.pack(fill="x", pady=(0, 10))
            self._botao(secao_gravar, "Gravar clique (rascunho de automação nova)", self.acao_gravar)

        secao_config = ttk.LabelFrame(corpo, text="Configuração", padding=10)
        secao_config.pack(fill="x", pady=(0, 10))
        self._botao(secao_config, "Configurar chave da IA de erro", self.acao_configurar_ia)

        barra_status = ttk.Frame(corpo)
        barra_status.pack(fill="x", pady=(4, 6))
        self._bolinha = tk.Canvas(barra_status, width=14, height=14, background=_CINZA_CLARO, highlightthickness=0)
        self._bolinha.pack(side="left", padx=(2, 6))
        self._id_bolinha = self._bolinha.create_oval(2, 2, 12, 12, fill=_CINZA, outline="")
        self.status = ttk.Label(barra_status, text="Pronto.", style="Status.TLabel")
        self.status.pack(side="left")
        self.botao_pausa = ttk.Button(barra_status, text="Pausar", command=self._alternar_pausa, state="disabled")
        self.botao_pausa.pack(side="right")

        self.log = scrolledtext.ScrolledText(
            corpo, width=100, height=20, state="disabled",
            font=("Consolas", 9), background="white", relief="solid", borderwidth=1,
        )
        self.log.pack(fill="both", expand=True)

    def _botao(self, pai, texto, comando, acento=False):
        botao = ttk.Button(pai, text=texto, command=comando, style="Acento.TButton" if acento else "TButton")
        botao.pack(fill="x", pady=3)
        self.botoes.append(botao)
        return botao

    def _marcar_status(self, texto, cor):
        self.status.configure(text=texto)
        self._bolinha.itemconfigure(self._id_bolinha, fill=cor)

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

    def _rodar_em_thread(self, alvo, *args, pausavel=False):
        """Roda `alvo(*args)` numa thread separada, com o print() dela
        redirecionado pra a caixa de texto (`EscritorFila`), sem travar
        a janela enquanto a automação demora (até ~3 minutos por
        documento, seção 0.27).

        `pausavel=True` (só as ações em lote) habilita o botão
        "Pausar" — pra ação de empresa só, rápida, não faz sentido
        pausar no meio, então o botão fica desabilitado (seção 0.34)."""
        if self.em_execucao:
            messagebox.showwarning("Aguarde", "Já tem uma ação rodando — espera terminar.")
            return

        def trabalho():
            saida_original = sys.stdout
            sys.stdout = EscritorFila(self.fila)
            deu_erro = False
            try:
                alvo(*args)
            except Exception as e:  # nunca deixa a janela travada por um erro não previsto
                deu_erro = True
                self.fila.put(f"\nErro inesperado: {e}\n")
            finally:
                sys.stdout = saida_original
                self.root.after(0, self._fim_execucao, deu_erro)

        self.evento_pausa.set()
        self.em_execucao = True
        for botao in self.botoes:
            botao.configure(state="disabled")
        if pausavel:
            self.botao_pausa.configure(state="normal", text="Pausar")
        self._marcar_status("Rodando...", _LARANJA)
        self.fila.put(f"\n{'=' * 60}\n")
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
            self._marcar_status("Pausando (termina a empresa atual antes de parar)...", _LARANJA)
        else:
            self.evento_pausa.set()
            self.botao_pausa.configure(text="Pausar")
            self._marcar_status("Rodando...", _LARANJA)

    def _fim_execucao(self, deu_erro=False):
        self.em_execucao = False
        self.root.deiconify()
        for botao in self.botoes:
            botao.configure(state="normal")
        self.botao_pausa.configure(state="disabled", text="Pausar")
        self.evento_pausa.set()
        if deu_erro:
            self._marcar_status("Erro — veja o log acima.", _VERMELHO)
        else:
            self._marcar_status("Pronto.", _VERDE)

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
            resposta.put(messagebox.askyesno(
                "Confirmar lote",
                f"Rodar pra essas {len(selecionadas)} empresa(s)?\n\n{lista}",
            ))

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
            pausavel=True,
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

        self._rodar_em_thread(rodar)

    def _confirmar_empresa_selecionada(self, nome):
        return messagebox.askyesno(
            "Confirmar antes de continuar",
            f"A empresa certa já está selecionada no Domínio?\n\n"
            f"(o período é selecionado sozinho: sempre o mês fechado anterior ao atual)\n\n"
            f"Vai gerar: {nome}",
        )

    def _rodar_gerador(self, gerador, nome):
        if not self._confirmar_empresa_selecionada(nome):
            return

        def rodar():
            interacao.focar_dominio()
            if gerador():
                print(f"Fim da rotina ({nome}).")

        self._rodar_em_thread(rodar)

    def acao_sped_fiscal(self):
        self._rodar_gerador(dominio.gerar_sped_fiscal, "SPED Fiscal")

    def acao_efd_contribuicoes(self):
        self._rodar_gerador(dominio.gerar_efd_contribuicoes, "EFD Contribuições")

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


def main():
    root = tk.Tk()
    JanelaPrincipal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
