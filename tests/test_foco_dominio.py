"""Win32 simulado: foco confirmado sem clicar nem alcançar UI real."""

import ctypes
from ctypes import wintypes
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao, verificar_antes_de_agir


def carregar_interacao():
    spec = importlib.util.spec_from_file_location("app._interacao_teste", Path(__file__).resolve().parents[1] / "app" / "interacao.py")
    modulo = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", {"pyautogui": types.ModuleType("pyautogui")}):
        spec.loader.exec_module(modulo)
    return modulo


class TestFocoDominio(unittest.TestCase):
    def setUp(self):
        self.modulo = carregar_interacao()
        self.janelas = {
            42: {"titulo": "Domínio Escrita Fiscal - Versão: 10", "classe": "DisplayClientWindowClass", "pid": 100},
            99: {"titulo": "exportacao_ficticia.pdf - Adobe Acrobat", "classe": "AcrobatWindow", "pid": 200},
        }
        self.foreground = 99
        self.api = Mock()
        self.api.IsWindow.side_effect = lambda hwnd: hwnd in self.janelas
        self.api.IsWindowVisible.return_value = True
        self.api.IsIconic.return_value = False
        self.api.GetForegroundWindow.side_effect = lambda: self.foreground
        self.api.GetWindowTextW.side_effect = lambda hwnd, buffer, tamanho: setattr(buffer, "value", self.janelas[hwnd]["titulo"])
        self.api.GetClassNameW.side_effect = lambda hwnd, buffer, tamanho: setattr(buffer, "value", self.janelas[hwnd]["classe"])
        self.api.GetWindowThreadProcessId.side_effect = lambda hwnd, pid: setattr(pid._obj, "value", self.janelas[hwnd]["pid"])

        def enumerar(callback, parametro):
            for hwnd in list(self.janelas):
                callback(hwnd, parametro)
            return True

        def ativar(hwnd):
            self.foreground = hwnd
            return True

        self.api.EnumWindows.side_effect = enumerar
        self.api.SetForegroundWindow.side_effect = ativar
        self.press = Mock()
        self.patchers = [
            patch.object(ctypes, "windll", types.SimpleNamespace(
                kernel32=types.SimpleNamespace(GetCurrentThreadId=lambda: 111)), create=True),
            patch.object(self.modulo, "_api_janelas", return_value=(self.api, lambda callback: callback)),
            patch.object(self.modulo, "pressionar_tecla", self.press),
            patch.object(self.modulo.time, "sleep"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def token(self, hwnd=42):
        return dict(self.janelas[hwnd], hwnd=hwnd)

    def test_titulo_unico_retoma_dominio_sem_teclas_no_acrobat(self):
        self.assertTrue(self.modulo.pressionar_esc_no_dominio())
        self.api.SetForegroundWindow.assert_called_once_with(42)
        self.assertEqual(self.press.call_count, 2)
        self.press.assert_called_with("esc")

    def test_hwnd_vinculado_ao_checkpoint_aceita_titulo_vazio(self):
        self.janelas[42]["titulo"] = ""
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=lambda: True))
        self.assertEqual(self.press.call_count, 2)

    def test_classe_sozinha_sem_checkpoint_nao_autoriza_foco(self):
        self.janelas[42]["titulo"] = ""
        self.assertFalse(self.modulo.pressionar_esc_no_dominio())
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_janelas_elegiveis_ambiguas_nao_agir(self):
        self.janelas[43] = dict(self.janelas[42], pid=101)
        for token in (None, self.token()):
            self.assertFalse(self.modulo.pressionar_esc_no_dominio(token))
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_setforeground_falha_nao_envia_esc(self):
        self.api.SetForegroundWindow.side_effect = None
        self.api.SetForegroundWindow.return_value = False
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_not_called()

    def _com_acrobat(self, *hwnds):
        self.janelas.pop(99, None)  # o leitor de PDF fictício do fixture (que agora também seria listado por título)
        for hwnd in hwnds:
            self.janelas[hwnd] = {"titulo": f"Empresa {hwnd} - SPRAYAGRO.pdf - Adobe Acrobat", "classe": "AcrobatSDIWindow", "pid": 300}
        self.janelas[88] = {"titulo": "Relatorio.pdf - Adobe Acrobat", "classe": "AcrobatSDIWindow", "pid": 300}
        self.janelas[89] = {"titulo": "Documento.pdf - Bloco de Notas", "classe": "Notepad", "pid": 400}
        self.fechadas = []

        def fechar(hwnd, mensagem, a, b):
            self.fechadas.append((hwnd, mensagem))
            self.janelas.pop(hwnd, None)
            return True
        self.api.PostMessageW.side_effect = fechar

    def test_leitor_remoto_do_go_global_e_reconhecido_pelo_titulo_nao_pelo_processo(self):
        self.janelas.pop(99, None)
        # Caso real: o Acrobat roda no servidor remoto e aparece como janela do cliente GO-Global.
        self.janelas[461] = {"titulo": "Empresa 70 - SPRAYAGRO.pdf - Adobe Acrobat Reader (32-bit)",
                             "classe": "DisplayClientWindowClass", "pid": 100}
        self.assertEqual(self.modulo.listar_leitores_pdf(), {461: self.janelas[461]["titulo"]})  # o Domínio (42) não entra

    def test_plano_b_clica_no_x_se_a_janela_do_leitor_nao_fechar_com_wm_close(self):
        self.janelas.pop(99, None)
        self.janelas[461] = {"titulo": "Empresa 70 - SPRAYAGRO.pdf - Adobe Acrobat Reader (32-bit)",
                             "classe": "DisplayClientWindowClass", "pid": 100}
        self.foreground = 461
        self.api.PostMessageW.return_value = True  # o pedido é aceito mas a janela continua
        def retangulo(hwnd, ref):
            r = ref._obj; r.left, r.top, r.right, r.bottom = 0, 0, 1440, 850
            return True
        self.api.GetWindowRect.side_effect = retangulo
        self.modulo.pyautogui.size = Mock(return_value=(1440, 900))
        self.modulo.pyautogui.moveTo = Mock()
        self.modulo.pyautogui.hotkey = Mock()  # Alt+F4 também recusado neste cenário
        clicado = []
        def clicar(x, y):
            clicado.append((x, y)); self.janelas.pop(461, None)
        self.modulo.pyautogui.click = Mock(side_effect=clicar)
        with patch.object(self.modulo.time, "monotonic", side_effect=iter(range(0, 1000))):
            quantidade = self.modulo.fechar_leitores_pdf_novos({}, espera=5, intervalo=0, calma=1, espera_clique=2)
        self.assertEqual(quantidade, 1)
        self.assertEqual(clicado, [(1416, 16)])  # X do canto superior direito (como no print do operador)

    def test_alt_tab_so_quando_o_foco_nao_esta_no_dominio_e_para_ao_voltar(self):
        self.foreground = 99  # outro programa na frente
        def alt_tab(*teclas):
            self.teclas = teclas; self.foreground = 42
        self.modulo.pyautogui.hotkey = Mock(side_effect=alt_tab)
        with patch.object(self.modulo, "_trazer_para_frente", return_value=False):
            self.assertTrue(self.modulo.voltar_ao_dominio_com_alt_tab(self.token(), espera=0))
        self.modulo.pyautogui.hotkey.assert_called_once_with("alt", "tab")
        self.modulo.pyautogui.hotkey.reset_mock()
        self.assertTrue(self.modulo.voltar_ao_dominio_com_alt_tab(self.token(), espera=0))  # já no Domínio
        self.modulo.pyautogui.hotkey.assert_not_called()
        self.assertFalse(self.modulo.voltar_ao_dominio_com_alt_tab(None))

    def test_alt_tab_desiste_depois_de_algumas_tentativas_sem_repetir_indefinidamente(self):
        self.foreground = 99
        self.modulo.pyautogui.hotkey = Mock()  # o foco não volta
        with patch.object(self.modulo, "_trazer_para_frente", return_value=False):
            self.assertFalse(self.modulo.voltar_ao_dominio_com_alt_tab(self.token(), tentativas=3, espera=0))
        self.assertEqual(self.modulo.pyautogui.hotkey.call_count, 3)

    def _leitor_remoto(self):
        self.janelas.pop(99, None)
        self.janelas[77] = {"titulo": "Documento ficticio.pdf - Adobe Acrobat Reader (32-bit)",
                            "classe": "DisplayClientWindowClass", "pid": 100}
        self.foreground = 77

    def test_acrobat_mesmo_pid_nao_confirma_retorno_restaura_hwnd_principal(self):
        self._leitor_remoto()
        self.assertTrue(self.modulo.janela_dominio_ou_remota_em_foco(self.token()))
        self.modulo.pyautogui.hotkey = Mock()
        self.assertTrue(self.modulo.voltar_ao_dominio_com_alt_tab(self.token()))
        self.assertEqual(self.foreground, 42)
        self.api.SetForegroundWindow.assert_called_once_with(42)
        self.modulo.pyautogui.hotkey.assert_not_called()

    def test_acrobat_mesmo_pid_persistente_nao_vira_sucesso(self):
        self._leitor_remoto()
        self.modulo.pyautogui.hotkey = Mock()
        with patch.object(self.modulo, "_trazer_para_frente", return_value=False):
            self.assertFalse(self.modulo.voltar_ao_dominio_com_alt_tab(self.token(), espera=0))
        self.assertEqual(self.modulo.pyautogui.hotkey.call_count, 3)

    def test_recuperacao_recusa_hwnd_reutilizado_por_outro_programa(self):
        token = self.token()
        self.janelas[42]["titulo"] = "Documento.pdf - Adobe Acrobat"
        self.modulo.pyautogui.hotkey = Mock()
        self.assertFalse(self.modulo.voltar_ao_dominio_com_alt_tab(token))
        self.api.SetForegroundWindow.assert_not_called()
        self.modulo.pyautogui.hotkey.assert_not_called()

    def test_esc_nao_e_enviado_ao_acrobat_remoto(self):
        self._leitor_remoto()
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), vezes=1))
        self.assertEqual(self.foreground, 42)
        self.press.assert_called_once_with("esc")

    def test_parar_impede_wm_close_e_recuperacao_de_foco(self):
        self._leitor_remoto()
        controle = ControleExecucao(); controle.interromper()
        with controlar_execucao(controle):
            for acao in (lambda: self.modulo.fechar_leitores_pdf_uma_vez({}, set()),
                         lambda: self.modulo.fechar_leitores_pdf_novos({}),
                         lambda: self.modulo.voltar_ao_dominio_com_alt_tab(self.token())):
                with self.assertRaises(ExecucaoInterrompida):
                    acao()
        self.api.PostMessageW.assert_not_called()
        self.api.SetForegroundWindow.assert_not_called()

    def test_interromper_apos_primeiro_pdf_nao_fecha_segundo(self):
        self._com_acrobat(201, 202)
        controle = ControleExecucao()
        self.api.PostMessageW.side_effect = lambda *args: controle.interromper()
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.modulo.fechar_leitores_pdf_uma_vez({88: "anterior"}, set())
        self.assertEqual(self.api.PostMessageW.call_count, 1)

    def test_alt_f4_so_no_pdf_novo_sem_depender_da_trava_fiscal(self):
        self._com_acrobat(201)
        self.api.PostMessageW.side_effect = None  # WM_CLOSE não fechou
        def fechar(*teclas):
            self.assertEqual(teclas, ("alt", "f4"))
            self.assertEqual(self.foreground, 201)
            self.janelas.pop(201)
        self.modulo.pyautogui.hotkey = Mock(side_effect=fechar)
        guarda_fiscal = Mock(side_effect=RuntimeError("fora do Domínio"))
        with verificar_antes_de_agir(guarda_fiscal), patch.object(self.modulo.time, "monotonic", side_effect=iter(range(1000))):
            self.assertEqual(self.modulo.fechar_leitores_pdf_novos({88: "anterior"}, intervalo=0), 1)
        self.assertIn(88, self.janelas)
        self.modulo.pyautogui.hotkey.assert_called_once_with("alt", "f4")
        guarda_fiscal.assert_not_called()

    def test_alt_f4_nunca_atinge_dominio_ou_pdf_anterior(self):
        self.modulo.pyautogui.hotkey = Mock()
        self.assertFalse(self.modulo._fechar_leitor_pdf_com_atalho(self.api, 42))
        with patch.object(self.modulo.time, "monotonic", side_effect=iter(range(1000))):
            self.assertEqual(self.modulo.fechar_leitores_pdf_novos({99: "anterior"}, espera=1, intervalo=0), 0)
        self.modulo.pyautogui.hotkey.assert_not_called()

    def test_interrupcao_no_atalho_e_propagada_sem_tentar_x(self):
        self._leitor_remoto()
        controle = ControleExecucao()
        self.modulo.pyautogui.hotkey = Mock(side_effect=lambda *args: controle.interromper())
        with controlar_execucao(controle), patch.object(self.modulo.time, "monotonic", side_effect=iter(range(1000))), patch.object(self.modulo, "_clicar_x_da_janela") as clique:
            with self.assertRaises(ExecucaoInterrompida):
                self.modulo.fechar_leitores_pdf_novos({}, intervalo=0)
        clique.assert_not_called()

    def test_pausa_antes_do_alt_f4_exige_reconfirmar_foco_e_identidade(self):
        self._leitor_remoto()
        self.modulo.pyautogui.hotkey = Mock()
        for mudanca in (lambda: setattr(self, "foreground", 42),
                        lambda: self.janelas[77].update(titulo="Outra janela")):
            self._leitor_remoto()
            # Simula uma pausa depois de focar o Adobe; ao voltar o alvo mudou.
            with patch.object(self.modulo, "_focar_leitor_pdf", return_value=True), patch.object(self.modulo, "ponto_seguro_sem_foco", side_effect=mudanca):
                self.assertFalse(self.modulo._fechar_leitor_pdf_com_atalho(self.api, 77))
        self.modulo.pyautogui.hotkey.assert_not_called()

    def test_falha_no_inventario_anterior_nao_autoriza_fechar_pdf(self):
        self._leitor_remoto()
        self.assertEqual(self.modulo.fechar_leitores_pdf_novos(None), 0)
        self.api.PostMessageW.assert_not_called()

    def test_falha_de_enumeracao_nao_equivale_a_inventario_vazio(self):
        self.api.EnumWindows.side_effect = None
        self.api.EnumWindows.return_value = False
        with self.assertRaises(OSError):
            self.modulo.listar_leitores_pdf()

    def test_leitor_persistente_nao_conta_como_fechado(self):
        self._leitor_remoto()
        with patch.object(self.modulo.time, "monotonic", side_effect=iter(range(1000))), patch.object(self.modulo, "_fechar_leitor_pdf_com_atalho", return_value=False), patch.object(self.modulo, "_clicar_x_da_janela", return_value=False):
            self.assertEqual(self.modulo.fechar_leitores_pdf_novos({}, espera=3, intervalo=0), 0)

    def test_x_fora_da_tela_ou_sem_retangulo_nao_clica(self):
        self._leitor_remoto()
        self.modulo.pyautogui.size = Mock(return_value=(1440, 900))
        self.modulo.pyautogui.moveTo = Mock()
        self.modulo.pyautogui.click = Mock()
        for limites in ((1000, 0, 1800, 850), (0, -15, 1440, 850), (0, 200, 1440, 1000)):
            def retangulo(hwnd, ref):
                r = ref._obj; r.left, r.top, r.right, r.bottom = limites
                return True
            self.api.GetWindowRect.side_effect = retangulo
            self.assertFalse(self.modulo._clicar_x_da_janela(self.api, 77))
        self.api.GetWindowRect.side_effect = None
        self.api.GetWindowRect.return_value = False
        self.assertFalse(self.modulo._clicar_x_da_janela(self.api, 77))
        self.modulo.pyautogui.moveTo.assert_not_called()
        self.modulo.pyautogui.click.assert_not_called()

    def test_foco_muda_antes_do_clique_no_x_nao_clica(self):
        self._leitor_remoto()
        def retangulo(hwnd, ref):
            r = ref._obj; r.left, r.top, r.right, r.bottom = 0, 0, 1440, 850
            return True
        self.api.GetWindowRect.side_effect = retangulo
        self.modulo.pyautogui.size = Mock(return_value=(1440, 900))
        self.modulo.pyautogui.moveTo = Mock(side_effect=lambda *args, **kw: setattr(self, "foreground", 42))
        self.modulo.pyautogui.click = Mock()
        self.assertFalse(self.modulo._clicar_x_da_janela(self.api, 77))
        self.modulo.pyautogui.click.assert_not_called()

    def test_janela_muda_de_posicao_apos_mover_mouse_nao_clica(self):
        self._leitor_remoto()
        limites = iter(((0, 0, 1440, 850), (300, 0, 1740, 850)))
        def retangulo(hwnd, ref):
            r = ref._obj; r.left, r.top, r.right, r.bottom = next(limites)
            return True
        self.api.GetWindowRect.side_effect = retangulo
        self.modulo.pyautogui.size = Mock(return_value=(1440, 900))
        self.modulo.pyautogui.moveTo = Mock()
        self.modulo.pyautogui.click = Mock()
        self.assertFalse(self.modulo._clicar_x_da_janela(self.api, 77))
        self.modulo.pyautogui.click.assert_not_called()

    def test_lista_so_leitor_de_pdf_com_pdf_no_titulo(self):
        self._com_acrobat(201)
        self.assertEqual(set(self.modulo.listar_leitores_pdf()), {88, 201})  # nem Domínio nem outro programa

    def test_fecha_so_o_leitor_novo_e_nunca_o_que_ja_estava_aberto(self):
        self._com_acrobat()
        base = self.modulo.listar_leitores_pdf()  # o 88 já estava aberto pelo operador
        self.assertEqual(set(base), {88})
        self._com_acrobat(201)  # o Domínio abre o PDF exportado
        fechadas = set()
        abertas = self.modulo.fechar_leitores_pdf_uma_vez(base, fechadas)
        self.assertEqual(fechadas, {201})
        self.assertEqual(self.fechadas, [(201, 0x0010)])  # WM_CLOSE (o X), nada além disso
        self.assertEqual(abertas, [201])  # a varredura listou antes de fechar; a próxima confirma que sumiu
        self.assertIn(88, self.janelas)  # o do operador continua
        self.press.assert_not_called()  # nenhuma tecla enviada

    def test_espera_o_leitor_aparecer_fecha_e_confirma_que_sumiu(self):
        self._com_acrobat()
        base = self.modulo.listar_leitores_pdf()
        self._com_acrobat(201, 202)
        with patch.object(self.modulo.time, "monotonic", side_effect=iter(range(0, 1000))):
            quantidade = self.modulo.fechar_leitores_pdf_novos(base, espera=5, intervalo=0, calma=2)
        self.assertEqual(quantidade, 2)
        self.assertEqual({h for h, _ in self.fechadas}, {201, 202})

    def test_sem_leitor_novo_devolve_zero_depois_do_prazo(self):
        self._com_acrobat()
        base = self.modulo.listar_leitores_pdf()
        with patch.object(self.modulo.time, "monotonic", side_effect=iter(range(0, 1000))):
            self.assertEqual(self.modulo.fechar_leitores_pdf_novos(base, espera=3, intervalo=0), 0)
        self.assertEqual(self.fechadas, [])

    def test_pergunta_de_guias_clica_no_botao_e_nunca_na_caixa_sempre_fechar(self):
        def dados(linhas):
            d = {'text': [], 'left': [], 'top': [], 'width': [], 'height': []}
            for y, palavras in linhas:
                x = 100
                for p in palavras.split():
                    d['text'].append(p); d['left'].append(x); d['top'].append(y)
                    d['width'].append(60); d['height'].append(20)
                    x += 70
            return d
        d = dados([(10, 'Deseja fechar todas as guias ou a guia atual?'),
                   (60, 'Sempre fechar todas as guias'),
                   (100, 'Fechar todas as guias Fechar a guia atual Cancelar')])
        x, y = self.modulo._posicao_fechar_todas_as_guias(d, 1)
        self.assertEqual(y, 110)  # linha do botão, não a da caixa Sempre (y=70)
        self.assertEqual(x, 100 + (3 * 70 + 60) // 2)
        sem_pergunta = dados([(60, 'Sempre fechar todas as guias')])
        self.assertIsNone(self.modulo._posicao_fechar_todas_as_guias(sem_pergunta, 1))

    def test_clicar_duplo_move_e_da_duplo_clique_respeitando_a_trava_de_foco(self):
        mover, duplo = Mock(), Mock()
        self.modulo.pyautogui.moveTo = mover
        self.modulo.pyautogui.doubleClick = duplo
        with patch.object(self.modulo, "ponto_seguro") as trava:
            self.modulo.clicar_duplo(533, 466)
        trava.assert_called_once()
        mover.assert_called_once()
        self.assertEqual(mover.call_args.args[:2], (533, 466))
        duplo.assert_called_once_with(interval=0.1)

    def _com_dialogo_remoto(self):
        # "Salvar em PDF": outra janela do MESMO cliente (pid e classe iguais), outro HWND.
        self.janelas[77] = {"titulo": "Salvar em PDF", "classe": "DisplayClientWindowClass", "pid": 100}
        self.foreground = 77

    def test_dialogo_remoto_do_mesmo_cliente_conta_como_foco_mas_outro_programa_nao(self):
        self._com_dialogo_remoto()
        self.assertFalse(self.modulo.janela_dominio_em_foco(self.token()))  # estrita: só a principal
        self.assertTrue(self.modulo.janela_dominio_ou_remota_em_foco(self.token()))
        self.foreground = 99  # leitor de PDF: outro processo
        self.assertFalse(self.modulo.janela_dominio_ou_remota_em_foco(self.token()))
        self.assertFalse(self.modulo.janela_dominio_ou_remota_em_foco(None))

    def test_esc_vai_para_o_dialogo_remoto_sem_trocar_o_foco(self):
        self._com_dialogo_remoto()
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), vezes=2))
        self.assertEqual(self.press.call_count, 2)
        self.api.SetForegroundWindow.assert_not_called()

    def test_esc_no_dialogo_remoto_para_se_o_foco_sair_do_cliente(self):
        self._com_dialogo_remoto()
        self.press.side_effect = lambda _: setattr(self, "foreground", 99)
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token(), vezes=2))
        self.press.assert_called_once_with("esc")

    def test_windows_recusa_primeira_tentativa_e_anexa_entrada_na_segunda(self):
        original = self.api.GetWindowThreadProcessId.side_effect
        self.api.GetWindowThreadProcessId.side_effect = (
            lambda hwnd, pid: 555 if pid is None else original(hwnd, pid))
        anexado = []
        self.api.AttachThreadInput.side_effect = lambda a, b, ligar: anexado.append(ligar) or True

        def ativar(hwnd):
            if True in anexado:  # só obedece com a entrada anexada à thread em primeiro plano
                self.foreground = hwnd
            return True
        self.api.SetForegroundWindow.side_effect = ativar
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.assertEqual(anexado, [True, False])  # anexa e sempre desanexa
        self.assertEqual(self.api.SetForegroundWindow.call_count, 2)
        self.assertEqual(self.press.call_count, 2)  # só então envia Esc

    def test_sem_segunda_tentativa_possivel_descreve_janela_e_nao_envia_esc(self):
        self.api.SetForegroundWindow.side_effect = None
        self.api.SetForegroundWindow.return_value = False
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_not_called()
        texto = self.modulo.descrever_primeiro_plano(100)
        self.assertIn("AcrobatWindow", texto)
        self.assertIn("False", texto)  # processo diferente do Domínio
        self.assertNotIn("exportacao_ficticia", texto)  # nunca o título

    def test_foco_perdido_entre_esc_interrompe_segunda_tecla(self):
        self.press.side_effect = lambda _: setattr(self, "foreground", 99)
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_called_once_with("esc")

    def test_hwnd_pid_classe_titulo_incompativeis_sem_fallback(self):
        token = self.token()
        for chave, valor in (("hwnd", 88), ("pid", 999), ("classe", "OutraClasse"), ("titulo", "")):
            invalido = dict(token, **{chave: valor})
            self.assertFalse(self.modulo.pressionar_esc_no_dominio(invalido))
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_captura_token_apenas_foreground_compativel_no_checkpoint(self):
        self.assertIsNone(self.modulo.identificar_janela_dominio_atual())
        self.foreground = 42
        self.janelas[42]["titulo"] = ""
        self.assertEqual(self.modulo.identificar_janela_dominio_atual(), self.token())

    def test_titulo_outro_app_na_classe_go_global_nao_vincula_checkpoint(self):
        self.foreground = 42
        self.janelas[42]["titulo"] = "Adobe Acrobat"
        self.assertIsNone(self.modulo.identificar_janela_dominio_atual())

    def test_go_global_sem_confirmacao_ocr_nao_envia_teclas(self):
        self.janelas[42]["titulo"] = ""
        ocr = Mock(return_value=False)
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.assertEqual(ocr.call_count, 3)
        self.press.assert_not_called()

    def test_go_global_ocr_confirma_apos_repintar_e_por_tecla(self):
        self.janelas[42]["titulo"] = ""
        ocr = Mock(side_effect=[False, False, True, True])
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.assertEqual(ocr.call_count, 4)
        self.assertEqual(self.press.call_count, 2)

    def test_titulo_muda_antes_segunda_tecla_interrompe(self):
        self.press.side_effect = lambda _: self.janelas[42].update(titulo="Adobe Acrobat")
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_called_once_with("esc")

    def test_ocr_muda_foco_nao_envia_esc(self):
        self.janelas[42]["titulo"] = ""

        def ocr():
            self.foreground = 99
            return True

        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.press.assert_not_called()

    def test_verificacao_foreground_apenas_leitura(self):
        self.assertFalse(self.modulo.janela_dominio_em_foco(self.token()))
        self.foreground = 42
        self.assertTrue(self.modulo.janela_dominio_em_foco(self.token()))
        self.api.SetForegroundWindow.assert_not_called()
        self.api.EnumWindows.assert_not_called()
        self.api.ShowWindow.assert_not_called()
        self.press.assert_not_called()


class TestTiposWin32(unittest.TestCase):
    def test_hwnd_retornos_e_argumentos_tipos_pointer(self):
        modulo = carregar_interacao()
        api = Mock()
        with patch("ctypes.windll", types.SimpleNamespace(user32=api), create=True):
            modulo._api_janelas()
        self.assertIs(api.GetForegroundWindow.restype, wintypes.HWND)
        self.assertEqual(api.SetForegroundWindow.argtypes, [wintypes.HWND])
        self.assertEqual(ctypes.sizeof(api.GetForegroundWindow.restype), ctypes.sizeof(ctypes.c_void_p))


if __name__ == "__main__":
    unittest.main()
