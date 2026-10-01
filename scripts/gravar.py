"""Grava clique manual no Domínio pra gerar o RASCUNHO de uma
automação nova ("caminho" — seção 0.35 do documento) — em vez de
escrever cada `achar_ou_parar()`/`clicar()` na mão (do jeito que
`gerar_sped()` foi feito), grava você fazendo a tarefa uma vez e monta
um rascunho de função parecido com o resto de `app/dominio.py`.

**Gera RASCUNHO, não automação pronta.** O texto que este script
adivinha perto de cada clique (por OCR) pode vir errado, incompleto ou
vazio — mesmo risco visto a sessão inteira contra o Domínio real:
texto curto (ex.: "OK") costuma ser ilegível, tela densa confunde o
OCR (seções 0.10/0.29). **Revise cada linha do rascunho contra o print
salvo daquele passo antes de usar de verdade** — o rascunho é ponto de
partida, não substitui o mesmo trabalho de ajuste fino que toda
automação deste projeto já passou.

**Só grava clique, não digitação.** Passo que precisa digitar algo
(ex.: código da empresa) não sai pronto — o rascunho marca esse ponto
com um comentário lembrando de preencher à mão (mesmo padrão de
`trocar_empresa()`/`selecionar_competencia_anterior()`, que digitam
valor vindo de dado, não de gravação).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela):

    python scripts\\gravar.py

A gravação começa assim que o script roda. Clique normal, em cada
passo do caminho novo que você quer ensinar (ex.: Relatórios >
Informativos > Federais > algum item > OK > Fechar). Aperte **F12**
quando terminar — aí sim gera o rascunho.

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
        agora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pasta = PASTA_CAPTURAS / f"gravacao_{agora}"
        self.pasta.mkdir(parents=True, exist_ok=True)

    def ao_clicar(self, x, y, botao, pressionado):
        # Só grava no instante do "pressionar" (não do "soltar") — mais
        # perto do estado da tela ANTES do clique surtir efeito (o que
        # importa pra adivinhar o texto de quem foi clicado, não o que
        # apareceu depois).
        if not pressionado or not self.rodando:
            return

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
            "indice": indice,
            "x": x,
            "y": y,
            "texto_adivinhado": adivinhado,
            "print_tela_cheia": nome_tela_cheia,
            "print_recorte": nome_recorte,
        })

    def ao_apertar_tecla(self, tecla):
        if tecla == keyboard.Key.f12:
            print("\nF12 — parando a gravação.")
            self.rodando = False
            return False  # encerra o listener de teclado

    def gravar(self):
        print(f"Gravando em: {self.pasta}")
        print("Clique normal no Domínio. Aperte F12 quando terminar.\n")
        with mouse.Listener(on_click=self.ao_clicar), \
                keyboard.Listener(on_press=self.ao_apertar_tecla) as ouvinte_teclado:
            ouvinte_teclado.join()

    def gerar_rascunho(self, nome_funcao):
        if not self.passos:
            print("Nenhum clique gravado — nada pra gerar.")
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
            f'    Não grava digitação — se algum passo precisar digitar algo',
            f'    (ex.: código de empresa), preencha à mão onde marcado abaixo.',
            f'    Texto curto ou tela densa (ex.: "OK", "Fechar", "Sim", "Não")',
            f'    pode falhar na busca direta pela tela inteira (achado real,',
            f'    seção 0.46) — pra esses casos, troque por achar_texto_ou_no_',
            f'    centro() ou pelo padrão de _fechar_tela_geracao() em',
            f'    app/dominio.py (recorta a área antes, zoom maior dentro do',
            f'    recorte), em vez de achar_ou_parar() direto na tela inteira.',
            f'    """',
        ]
        for passo in self.passos:
            i = passo["indice"]
            alvo = passo["texto_adivinhado"] or "TEXTO_NAO_ADIVINHADO_confira_o_print"
            linhas.append(f"    # Passo {i}: clique em ({passo['x']}, {passo['y']}) — confira")
            linhas.append(f"    # {passo['print_recorte']}")
            linhas.append(f"    imagem = tela.capturar_tela()")
            linhas.append(
                f'    pos = achar_ou_parar(imagem, "{alvo}", f"{{prefixo}}erro_passo_{i:02d}.png")'
            )
            linhas.append(f"    if pos is None:")
            linhas.append(f"        return False")
            linhas.append(f"    interacao.clicar(*pos)")
            linhas.append(f"    time.sleep(2)")
            linhas.append(f"")
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
