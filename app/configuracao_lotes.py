"""Cadastros locais e plano explícito: empresa → regime → rotinas ordenadas."""

import hashlib
import json
import re
import uuid

from app import capacidades


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
            """)

    def listar(self, banco=None):
        if banco is None:
            with self.repositorio.conectar() as conexao:
                return self.listar(conexao)
        return {
            "regimes": [{"id": r["id"], "nome": r["nome"], "rotinas": json.loads(r["rotinas"])}
                        for r in banco.execute("SELECT * FROM regimes ORDER BY rowid")],
            "empresas": [dict(e) for e in banco.execute("SELECT * FROM empresas_painel ORDER BY rowid")],
        }

    def salvar_regime(self, identificador, nome, rotinas):
        nome = nome_cadastro(nome)
        if identificador is not None and (not isinstance(identificador, str) or not re.fullmatch(r"[0-9a-f]{32}", identificador)):
            raise ValueError("Regime inválido.")
        if not isinstance(rotinas, list) or len(rotinas) > 4 or any(not isinstance(r, str) for r in rotinas) or len(set(rotinas)) != len(rotinas):
            raise ValueError("Escolha as rotinas uma vez, na ordem de execução.")
        for rotina in rotinas:
            capacidades.obter_capacidade(rotina)
        with self.repositorio.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
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
                validar_pedido({"request_id": str(uuid.uuid4()), "capacidade": rotina, "empresa_codigo": codigo,
                                "inicio": selecao["inicio"], "fim": selecao["fim"], "apuracao_confirmada": True})
            plano["empresas"].append({**empresa, "regime": regime["nome"], "rotinas": list(regime["rotinas"])})
            plano["quantidade_rotinas"] += len(regime["rotinas"])
        # O cliente aprova exatamente o cadastro, período e ordem vistos.
        plano["hash"] = hashlib.sha256(json.dumps(plano, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return plano
