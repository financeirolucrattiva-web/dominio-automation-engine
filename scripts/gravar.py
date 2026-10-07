"""Grava clique, digitação e hover manuais no Domínio pra gerar o
RASCUNHO de uma automação nova ("caminho" — seção 0.35 do documento) —
em vez de escrever cada `achar_ou_parar()`/`clicar()`/`digitar()` na
mão (do jeito que `gerar_sped()` foi feito), grava você fazendo a
tarefa uma vez e monta um rascunho de função parecido com o resto de
`app/dominio.py`.

**Gera RASCUNHO, não automação pronta.** O texto que este script
adivinha perto de cada clique (por OCR) pode vir errado, incompleto ou
vazio — mesmo risco visto a sessão inteira contra o Domínio real:
texto curto (ex.: "OK") costuma ser ilegível, tela densa confunde o
OCR (seções 0.10/0.29). **Revise cada linha do rascunho contra o print
salvo daquele passo antes de usar de verdade** — o rascunho é ponto de
partida, não substitui o mesmo trabalho de ajuste fino que toda
automação deste projeto já passou.

**Grava digitação de verdade agora (seção 0.70)** — tudo que você
digitar entre um clique e outro vira um passo `interacao.digitar(...)`
no rascunho, com o texto LITERAL que foi digitado. **Isso inclui
qualquer coisa digitada em QUALQUER janela**, não só no Domínio — o
gravador não sabe distinguir foco de janela. Se precisar digitar uma
senha ou dado sensível fora do Domínio enquanto grava, pare a gravação
(F12) antes, digite, e comece uma gravação nova depois. O texto
digitado fica só localmente (`capturas/gravacao_*/passos.json`,
gitignored) — nunca sai da máquina, mas revise antes de colar num
rascunho que você for compartilhar: texto digitado literal (ex.: um
código de empresa) geralmente deveria virar um PARÂMETRO da função, não
ficar fixo no código — o rascunho marca isso com um comentário, mas
quem revisa decide.

**Hover marcado manualmente, não adivinhado** — aperte **F9** com o
mouse em cima do item que abre um submenu (ex.: "Livros", antes de
"Livros Fiscais" aparecer), antes de clicar no item de dentro do
submenu. Inferir hover automaticamente (por pausa do mouse) não é
confiável o bastante pra confiar sem revisão; marcação explícita evita
hover fantasma ou hover que faltou.

**Espera por estado genérica, não mais `time.sleep()` fixo** — depois
de cada clique, o rascunho gerado espera a tela mudar de verdade
(`tela.assinatura_tela()`/`tela.tela_mudou()`, mesmo fingerprint usado
no resto do projeto, seção 0.58) em vez de um tempo fixo. Isso é
genérico (o gravador não sabe o que esperar especificamente depois de
cada clique) — ao revisar o rascunho, trocar por
`estados.esperar_por_estado()` mirando um texto conhecido continua
sendo o ideal, mas a espera genérica já é muito melhor que sleep fixo
puro.

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela):

    python scripts\\gravar.py

A gravação começa assim que o script roda. Clique normal, digite
normal, em cada passo do caminho novo que você quer ensinar (ex.:
Relatórios > Informativos > Federais > algum item > OK > Fechar).
Aperte **F9** antes de passar o mouse sobre um item só pra abrir
submenu (sem clicar nele). Aperte **F12** quando terminar — aí sim
gera o rascunho.

Precisa de `pynput` (`pip install -r requirements.txt`) — é a única
peça deste projeto que ESCUTA entrada real (mouse/teclado). Todo o
resto só ENVIA entrada sintética (`pyautogui`); nunca os dois ao mesmo
tempo aqui (evita o script reagir ao próprio clique sintético de outra
parte do motor).
"""

import datetime
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pynput import keyboard, mouse

from app import tela

PASTA_CAPTURAS = Path(__file__).resolve().parent.parent / "capturas"

# Mapeia tecla especial do pynput pro nome usado por app/interacao.py
# (pressionar_tecla()/pressionar_enter()) — só as que fazem sentido
# como fim de campo de digitação, não toda tecla especial existente.
_TECLAS_ESPECIAIS_RELEVANTES = {
    keyboard.Key.enter: "enter",
    keyboard.Key.tab: "tab",
    keyboard.Key.esc: "esc",
}


def nome_de_funcao_valido(bruto):
    """Transforma texto livre (o que a pessoa digitar) num nome de
    função Python válido — achado real, seção 0.38: um nome digitado
    com espaço (ex.: "Teste 3 pela interface") gerava
    `def Teste 3 pela interface(...)`, erro de sintaxe, nem colava.
    Troca tudo que não é letra/número/underscore por "_", e garante que
    não fica vazio nem começa com número."""
    nome = re.sub(r"\W+", "_", bruto.strip(), flags=re.UNICODE).strip("_").lower()
    if not nome or nome[0].isdigit():
        nome = f"gerar_{nome}" if nome else "gerar_novo_caminho"
    return nome


class Gravador:
    def __init__(self):
        self.passos = []
        self.rodando = True
        self._buffer_digitado = []
        agora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pasta = PASTA_CAPTURAS / f"gravacao_{agora}"
        self.pasta.mkdir(parents=True, exist_ok=True)

    def _flush_digitacao_pendente(self):
        """Fecha o texto acumulado desde o último passo (clique, tecla
        especial, ou hover) num passo `digitar` — chamado sempre antes
        de registrar qualquer outro tipo de passo, pra manter a ordem
        cronológica certa entre digitar e agir."""
        if not self._buffer_digitado:
            return
        texto = "".join(self._buffer_digitado)
        self._buffer_digitado = []
        indice = len(self.passos) + 1
        print(f"Passo {indice}: digitou {texto!r}")
        self.passos.append({"tipo": "digitar", "indice": indice, "texto": texto})

    def ao_clicar(self, x, y, botao, pressionado):
        # Só grava no instante do "pressionar" (não do "soltar") — mais
        # perto do estado da tela ANTES do clique surtir efeito (o que
        # importa pra adivinhar o texto de quem foi clicado, não o que
        # apareceu depois).
        if not pressionado or not self.rodando:
            return

        self._flush_digitacao_pendente()

        indice = len(self.passos) + 1
        print(f"Passo {indice}: clique em ({x}, {y})...")

        imagem = tela.capturar_tela()
        nome_tela_cheia = f"passo_{indice:02d}_tela_cheia.png"
        tela.salvar(imagem, self.pasta / nome_tela_cheia)

        recorte, _, _ = tela.recortar_ao_redor(imagem, x, y, raio_x=150, raio_y=60)
        nome_recorte = f"passo_{indice:02d}_recorte.png"
        tela.salvar(recorte, self.pasta / nome_recorte)

        # texto_mais_proximo(), não ler_texto() — achado real do
        # primeiro teste (seção 0.36): ler_texto() devolve a primeira
        # linha de toda a área, que numa área com várias
        # colunas/rótulos quase nunca é a coisa clicada de verdade.
        adivinhado = tela.texto_mais_proximo(imagem, x, y, raio_x=150, raio_y=60)
        print(f"  Texto adivinhado perto do clique: {adivinhado!r}" if adivinhado else "  Não consegui ler nenhum texto perto do clique.")

        self.passos.append({
            "tipo": "clicar",
            "indice": indice,
            "x": x,
            "y": y,
            "texto_adivinhado": adivinhado,
            "print_tela_cheia": nome_tela_cheia,
            "print_recorte": nome_recorte,
        })

    def _marcar_hover(self):
        """F9 — marca a posição ATUAL do mouse como um passo de hover
        (`interacao.passar_mouse()`), sem clicar. Pedido explícito do
        usuário (06/10/2026, seção 0.70): hover inferido por pausa do
        mouse não é confiável o bastante; marcação manual é."""
        self._flush_digitacao_pendente()
        x, y = mouse.Controller().position
        indice = len(self.passos) + 1
        print(f"Passo {indice}: hover marcado em ({x}, {y}) (F9)")
        self.passos.append({"tipo": "hover", "indice": indice, "x": x, "y": y})

    def ao_apertar_tecla(self, tecla):
        if tecla == keyboard.Key.f12:
            print("\nF12 — parando a gravação.")
            self._flush_digitacao_pendente()
            self.rodando = False
            return False  # encerra o listener de teclado

        if tecla == keyboard.Key.f9:
            self._marcar_hover()
            return

        if tecla in _TECLAS_ESPECIAIS_RELEVANTES:
            self._flush_digitacao_pendente()
            indice = len(self.passos) + 1
            nome = _TECLAS_ESPECIAIS_RELEVANTES[tecla]
            print(f"Passo {indice}: tecla {nome}")
            self.passos.append({"tipo": "tecla", "indice": indice, "tecla": nome})
            return

        # Tecla de caractere normal (letra/número/pontuação) — pynput
        # devolve KeyCode com `.char` preenchido; teclas especiais sem
        # mapeamento relevante acima (Shift, Ctrl sozinhos, setas etc.)
        # têm `.char` None e são ignoradas de propósito, não fazem
        # parte de "texto digitado".
        char = getattr(tecla, "char", None)
        if char is not None:
            self._buffer_digitado.append(char)

    def gravar(self):
        print(f"Gravando em: {self.pasta}")
        print("Clique e digite normal no Domínio.")
        print("F9 = marcar hover (mouse já posicionado, sem clicar) antes de abrir submenu.")
        print("F12 = terminar a gravação.")
        print("Atenção: tudo que você digitar é gravado, em qualquer janela —")
        print("pare (F12) antes de digitar senha/dado sensível fora do Domínio.\n")
        with mouse.Listener(on_click=self.ao_clicar), \
                keyboard.Listener(on_press=self.ao_apertar_tecla) as ouvinte_teclado:
            ouvinte_teclado.join()

    def gerar_rascunho(self, nome_funcao):
        if not self.passos:
            print("Nenhum passo gravado — nada pra gerar.")
            return

        nome_funcao = nome_de_funcao_valido(nome_funcao)

        caminho_json = self.pasta / "passos.json"
        caminho_json.write_text(json.dumps(self.passos, ensure_ascii=False, indent=2), encoding="utf-8")

        linhas = [
            f'def {nome_funcao}(prefixo=""):',
            f'    """RASCUNHO gerado por scripts/gravar.py em '
            f'{datetime.datetime.now().strftime("%d/%m/%Y %H:%M")} — '
            f'REVISE cada passo contra os prints em',
            f'    {self.pasta.as_posix()}/ antes de usar de verdade',
            f'    (texto adivinhado por OCR pode estar errado, seção 0.10/0.29).',
            f'    Texto digitado literal (passos "digitar" abaixo) veio da',
            f'    gravação — se for um dado que muda por execução (código de',
            f'    empresa, período, valor), troque pelo parâmetro certo em vez',
            f'    de deixar fixo.',
            f'    Texto curto ou tela densa (ex.: "OK", "Fechar", "Sim", "Não")',
            f'    pode falhar na busca direta pela tela inteira (achado real,',
            f'    seção 0.46) — pra esses casos, troque por achar_texto_ou_no_',
            f'    centro() ou pelo padrão de _fechar_tela_geracao() em',
            f'    app/dominio.py (recorta a área antes, zoom maior dentro do',
            f'    recorte), em vez de achar_ou_parar() direto na tela inteira.',
            f'    A espera depois de cada clique abaixo é genérica (só confere',
            f'    que A TELA MUDOU, via fingerprint — seção 0.58), não que o',
            f'    estado certo apareceu; trocar por estados.esperar_por_estado()',
            f'    mirando um texto conhecido é o ideal ao revisar.',
            f'    """',
        ]

        def gerar_espera_generica():
            linhas.append(f"    assinatura_antes = tela.assinatura_tela(tela.capturar_tela())")
            linhas.append(f"    for _ in range(10):")
            linhas.append(f"        time.sleep(0.5)")
            linhas.append(f"        if tela.tela_mudou(assinatura_antes, tela.assinatura_tela(tela.capturar_tela())):")
            linhas.append(f"            break")
            linhas.append(f"")

        for passo in self.passos:
            i = passo["indice"]
            tipo = passo.get("tipo", "clicar")  # gravações antigas (antes da seção 0.70) não tinham "tipo"

            if tipo == "digitar":
                linhas.append(f"    # Passo {i}: digitou {passo['texto']!r} — confira se deveria ser parâmetro")
                linhas.append(f"    interacao.digitar({passo['texto']!r})")
                linhas.append(f"")
                continue

            if tipo == "hover":
                linhas.append(f"    # Passo {i}: hover marcado (F9) em ({passo['x']}, {passo['y']})")
                linhas.append(f"    interacao.passar_mouse({passo['x']}, {passo['y']})")
                linhas.append(f"    time.sleep(0.5)")
                linhas.append(f"")
                continue

            if tipo == "tecla":
                linhas.append(f"    # Passo {i}: tecla {passo['tecla']}")
                if passo["tecla"] == "enter":
                    linhas.append(f"    interacao.pressionar_enter()")
                else:
                    linhas.append(f"    interacao.pressionar_tecla({passo['tecla']!r})")
                linhas.append(f"")
                continue

            # tipo == "clicar" (ou gravação antiga sem "tipo")
            alvo = passo.get("texto_adivinhado") or "TEXTO_NAO_ADIVINHADO_confira_o_print"
            recorte = passo.get("print_recorte", "")
            linhas.append(f"    # Passo {i}: clique em ({passo['x']}, {passo['y']}) — confira")
            linhas.append(f"    # {recorte}")
            linhas.append(f"    imagem = tela.capturar_tela()")
            linhas.append(
                f'    pos = achar_ou_parar(imagem, "{alvo}", f"{{prefixo}}erro_passo_{i:02d}.png")'
            )
            linhas.append(f"    if pos is None:")
            linhas.append(f"        return False")
            linhas.append(f"    interacao.clicar(*pos)")
            gerar_espera_generica()

        linhas.append(f"    return True")

        codigo = "\n".join(linhas) + "\n"
        caminho_rascunho = self.pasta / "rascunho.py"
        caminho_rascunho.write_text(codigo, encoding="utf-8")

        print(f"\n{len(self.passos)} passo(s) gravado(s).")
        print(f"Dados brutos: {caminho_json}")
        print(f"Rascunho de função: {caminho_rascunho}")
        print("\nAbra o rascunho, confira cada texto adivinhado contra o print")
        print("correspondente, ajuste o que precisar, e só depois cole dentro de")
        print("app/dominio.py (já tem achar_ou_parar/tela/interacao importados lá).")


def main():
    nome_funcao = input("Nome da função nova (ex.: gerar_dctf): ").strip() or "gerar_novo_caminho"
    gravador = Gravador()
    gravador.gravar()
    gravador.gerar_rascunho(nome_funcao)


if __name__ == "__main__":
    main()
