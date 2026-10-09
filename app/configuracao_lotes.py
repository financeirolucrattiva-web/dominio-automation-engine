"""Cadastros locais e plano explícito: empresa → regime → rotinas ordenadas."""

import hashlib
import json
import re
import uuid

from app import capacidades, configuracao_rotinas


def codigo_empresa(valor):
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9]{1,12}", valor):
        raise ValueError("Informe o código numérico da empresa no Domínio.")
    return str(int(valor))


def nome_cadastro(valor):
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 100 or any(ord(c) < 32 for c in valor):
        raise ValueError("Informe um nome de até 100 caracteres.")
    return valor.strip()


class ConfiguracaoLotes:
    def __init__(self, repositorio):
        self.repositorio = repositorio
        with repositorio.conectar() as banco:
            banco.executescript("""
                CREATE TABLE IF NOT EXISTS regimes (
                    id TEXT PRIMARY KEY, nome TEXT NOT NULL, rotinas TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS empresas_painel (
                    codigo TEXT PRIMARY KEY, nome TEXT NOT NULL, regime_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rotinas_cadastradas (
                    id TEXT PRIMARY KEY, nome TEXT NOT NULL, passos TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS marcos_cadastro (
                    id TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS rotinas_cadastradas_arquivo (
                    id TEXT PRIMARY KEY, nome TEXT NOT NULL, passos TEXT NOT NULL,
                    status TEXT NOT NULL
                );
            """)

    def listar(self, banco=None):
        if banco is None:
            with self.repositorio.conectar() as conexao:
                return self.listar(conexao)
        return {
            "regimes": [{"id": r["id"], "nome": r["nome"], "rotinas": json.loads(r["rotinas"])}
                        for r in banco.execute("SELECT * FROM regimes ORDER BY rowid")],
            "empresas": [dict(e) for e in banco.execute("SELECT * FROM empresas_painel ORDER BY rowid")],
            "rotinas": [{"id": c.id, "nome": c.nome, "status": "integrada", "quantidade_passos": None}
                        for c in capacidades.listar_capacidades()] +
                       [{"id": r["id"], "nome": r["nome"], "status": r["status"],
                         "quantidade_passos": len(json.loads(r["passos"]))}
                        for r in banco.execute("SELECT * FROM rotinas_cadastradas ORDER BY rowid")],
        }

    def preparar_piloto(self):
        """Cadastros pedidos pelo escritório, uma vez; sem empresas ou execução."""
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            if not banco.execute("SELECT 1 FROM marcos_cadastro WHERE id='piloto_lp_lr_v1'").fetchone():
                resumo = self._cadastrar_pendente(banco, "Resumo por Acumulador")
                rotinas = [resumo, "efd_contribuicoes", "registro_entradas", "registro_saidas"]
                for nome in ("Lucro Presumido", "Lucro Real"):
                    # Preserva configurações já feitas pelo operador.
                    if not any(r["nome"].casefold() == nome.casefold() for r in self.listar(banco)["regimes"]):
                        banco.execute("INSERT INTO regimes VALUES (?,?,?)", (uuid.uuid4().hex, nome, json.dumps(rotinas)))
                banco.execute("INSERT INTO marcos_cadastro VALUES ('piloto_lp_lr_v1')")
            if not banco.execute("SELECT 1 FROM marcos_cadastro WHERE id='piloto_lp_lr_icms_v2'").fetchone():
                icms = self._cadastrar_pendente(banco, "Livro Fiscal de ICMS")
                for regime in self.listar(banco)["regimes"]:
                    if regime["nome"].casefold() in ("lucro presumido", "lucro real") and icms not in regime["rotinas"]:
                        banco.execute("UPDATE regimes SET rotinas=? WHERE id=?",
                                      (json.dumps(regime["rotinas"] + [icms]), regime["id"]))
                banco.execute("INSERT INTO marcos_cadastro VALUES ('piloto_lp_lr_icms_v2')")
            if not banco.execute("SELECT 1 FROM marcos_cadastro WHERE id='piloto_lp_lr_efd_integrada_v3'").fetchone():
                duplicadas = [r for r in banco.execute("SELECT * FROM rotinas_cadastradas")
                              if r["nome"].casefold() in ("demonstrativo efd contribuições", "efd contribuições")]
                ids_antigos = {r["id"] for r in duplicadas}
                for regime in self.listar(banco)["regimes"]:
                    # Mantém a ordem; se as duas versões estavam vinculadas,
                    # a capacidade integrada aparece somente uma vez.
                    rotinas = list(dict.fromkeys("efd_contribuicoes" if r in ids_antigos else r
                                                 for r in regime["rotinas"]))
                    if regime["nome"].casefold() in ("lucro presumido", "lucro real") and "efd_contribuicoes" not in rotinas:
                        rotinas.append("efd_contribuicoes")
                    banco.execute("UPDATE regimes SET rotinas=? WHERE id=?", (json.dumps(rotinas), regime["id"]))
                for rotina in duplicadas:
                    # Guarda configurações anteriores antes de retirar a cópia
                    # do catálogo ativo. Histórico de tarefas não é alterado.
                    banco.execute("INSERT OR IGNORE INTO rotinas_cadastradas_arquivo VALUES (?,?,?,?)",
                                  (rotina["id"], rotina["nome"], rotina["passos"], rotina["status"]))
                    banco.execute("DELETE FROM rotinas_cadastradas WHERE id=?", (rotina["id"],))
                banco.execute("INSERT INTO marcos_cadastro VALUES ('piloto_lp_lr_efd_integrada_v3')")

    def _cadastrar_pendente(self, banco, nome):
        existente = next((r for r in self.listar(banco)["rotinas"] if r["nome"].casefold() == nome.casefold()), None)
        if existente:
            return existente["id"]
        identificador = uuid.uuid4().hex
        banco.execute("INSERT INTO rotinas_cadastradas VALUES (?,?,?,?)",
                      (identificador, nome, "[]", "pendente_configuracao"))
        return identificador

    def cadastrar_rotina(self, nome):
        nome = nome_cadastro(nome)
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            if any(r["nome"].casefold() == nome.casefold() for r in self.listar(banco)["rotinas"]):
                raise ValueError("Já existe uma rotina com esse nome.")
            identificador = uuid.uuid4().hex
            banco.execute("INSERT INTO rotinas_cadastradas VALUES (?,?,?,?)",
                          (identificador, nome, "[]", "pendente_configuracao"))
        return self.obter_rotina(identificador)

    def obter_rotina(self, identificador):
        with self.repositorio.conectar() as banco:
            rotina = banco.execute("SELECT * FROM rotinas_cadastradas WHERE id=?", (identificador,)).fetchone()
        if rotina is None:
            raise ValueError("Rotina cadastrada não encontrada.")
        return {"id": rotina["id"], "nome": rotina["nome"], "passos": json.loads(rotina["passos"]), "status": rotina["status"]}

    def configurar_rotina(self, identificador, dados):
        # Usa o mesmo validador de passos do gravador; salvar não aprova.
        configuracao_rotinas.validar_rotina(dados)
        nome = nome_cadastro(dados["nome"])
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            if not banco.execute("SELECT 1 FROM rotinas_cadastradas WHERE id=?", (identificador,)).fetchone():
                raise ValueError("Rotina cadastrada não encontrada.")
            if any(r["id"] != identificador and r["nome"].casefold() == nome.casefold() for r in self.listar(banco)["rotinas"]):
                raise ValueError("Já existe uma rotina com esse nome.")
            banco.execute("UPDATE rotinas_cadastradas SET nome=?,passos=?,status='rascunho' WHERE id=?",
                          (nome, json.dumps(dados["passos"], ensure_ascii=False), identificador))
        return self.obter_rotina(identificador)

    def enviar_validacao(self, identificador):
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            rotina = banco.execute("SELECT * FROM rotinas_cadastradas WHERE id=?", (identificador,)).fetchone()
            if rotina is None:
                raise ValueError("Rotina não encontrada.")
            configuracao_rotinas.validar_rotina({"nome": rotina["nome"], "passos": json.loads(rotina["passos"])})
            banco.execute("UPDATE rotinas_cadastradas SET status='aguardando_validacao' WHERE id=?", (identificador,))
        return self.obter_rotina(identificador)

    def salvar_regime(self, identificador, nome, rotinas):
        nome = nome_cadastro(nome)
        if identificador is not None and (not isinstance(identificador, str) or not re.fullmatch(r"[0-9a-f]{32}", identificador)):
            raise ValueError("Regime inválido.")
        if not isinstance(rotinas, list) or len(rotinas) > 80 or any(not isinstance(r, str) for r in rotinas) or len(set(rotinas)) != len(rotinas):
            raise ValueError("Escolha as rotinas uma vez, na ordem de execução.")
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            disponiveis = {r["id"] for r in self.listar(banco)["rotinas"]}
            if any(r not in disponiveis for r in rotinas):
                raise ValueError("Escolha rotinas cadastradas.")
            existentes = self.listar(banco)["regimes"]
            if identificador is not None and not any(r["id"] == identificador for r in existentes):
                raise ValueError("Regime não encontrado.")
            if any(r["id"] != identificador and r["nome"].casefold() == nome.casefold() for r in existentes):
                raise ValueError("Já existe um regime com esse nome; selecione-o para editar.")
            identificador = identificador or uuid.uuid4().hex
            banco.execute("INSERT INTO regimes VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, rotinas=excluded.rotinas",
                          (identificador, nome, json.dumps(rotinas)))
        return {"id": identificador, "nome": nome, "rotinas": list(rotinas)}

    def salvar_empresa(self, codigo, nome, regime_id):
        codigo, nome = codigo_empresa(codigo), nome_cadastro(nome)
        if not isinstance(regime_id, str):
            raise ValueError("Escolha o regime da empresa.")
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            if not banco.execute("SELECT 1 FROM regimes WHERE id=?", (regime_id,)).fetchone():
                raise ValueError("Escolha um regime cadastrado.")
            banco.execute("INSERT INTO empresas_painel VALUES (?,?,?) ON CONFLICT(codigo) DO UPDATE SET nome=excluded.nome, regime_id=excluded.regime_id",
                          (codigo, nome, regime_id))
        return {"codigo": codigo, "nome": nome, "regime_id": regime_id}

    def planejar(self, selecao, banco=None):
        from app.servidor import validar_pedido
        if not isinstance(selecao, dict) or set(selecao) != {"empresas", "inicio", "fim"}:
            raise ValueError("Selecione empresas e período para o lote.")
        codigos = selecao["empresas"]
        if not isinstance(codigos, list) or not 1 <= len(codigos) <= 100:
            raise ValueError("Escolha entre 1 e 100 empresas por lote.")
        codigos = [codigo_empresa(c) for c in codigos]
        if len(set(codigos)) != len(codigos):
            raise ValueError("Cada empresa deve aparecer uma vez no lote.")
        cadastro = self.listar(banco)
        empresas = {e["codigo"]: e for e in cadastro["empresas"]}
        regimes = {r["id"]: r for r in cadastro["regimes"]}
        plano = {"inicio": selecao["inicio"], "fim": selecao["fim"], "empresas": [], "quantidade_rotinas": 0}
        for codigo in codigos:
            empresa = empresas.get(codigo)
            regime = regimes.get(empresa["regime_id"]) if empresa else None
            if regime is None:
                raise ValueError("Uma empresa não está cadastrada com um regime válido.")
            if not regime["rotinas"]:
                raise ValueError("Configure as rotinas de todos os regimes selecionados antes de iniciar.")
            for rotina in regime["rotinas"]:
                if rotina not in {c.id for c in capacidades.listar_capacidades()}:
                    raise ValueError("O regime contém rotinas em configuração/validação, ainda não liberadas no executor.")
                validar_pedido({"request_id": str(uuid.uuid4()), "capacidade": rotina, "empresa_codigo": codigo,
                                "inicio": selecao["inicio"], "fim": selecao["fim"], "apuracao_confirmada": True})
            plano["empresas"].append({**empresa, "regime": regime["nome"], "rotinas": list(regime["rotinas"])})
            plano["quantidade_rotinas"] += len(regime["rotinas"])
        # O cliente aprova exatamente o cadastro, período e ordem vistos.
        plano["hash"] = hashlib.sha256(json.dumps(plano, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return plano
